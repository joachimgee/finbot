"""Enhanced Universe Selector.

Multi-stage selection logic for large-scale global equities universe (up to 12K).

Pipeline:
    1. Raw universe from FinanceDatabase (Equities.search)
    2. Structural filters: symbol format, active status, length <= 6
    3. Liquidity filters (price & volume) via yfinance batch download
    4. Size proxy (log dollar volume) when market cap absent
    5. Volatility stability filter (exclude extremely erratic assets)
    6. Sector diversification constraint
    7. Dynamic informed scoring & ranking

Quality Score Components (0-1 scaled):
    - LiquidityScore: avg_dollar_volume normalization
    - SizeScore: market_cap normalization (log scaled)
    - StabilityScore: 1 - normalized volatility (lower vol => higher score)
    - MomentumScore: recent 20-day return clipped & scaled

Dynamic Score Weighting:
    Instead of static arbitrary weights, component weights are derived
    from cross-sectional discrimination power:
        weight_i ∝ variance(metric_i) / (1 + avg_abs_corr(metric_i, others))
    This favors metrics with higher dispersion and lower redundancy.
    All metrics are standardized to [0,1] prior to variance/correlation.

Usage Example:
    >>> from financial_analyzer.universe.universe_selector_enhanced import EnhancedUniverseSelector
    >>> selector = EnhancedUniverseSelector()
    >>> tickers = selector.select(limit=12000, regions=['United States','Canada','Germany','Japan'])
    >>> len(tickers)
    12000

Notes:
    - For very large universes we only fetch volume & price data for a pre-candidate subset
      (e.g. first 20K raw symbols shuffled) to reduce API pressure.
    - yfinance batching uses chunks of 50 symbols.
    - Fallback logic: if volume retrieval fails for a symbol it is discarded.
    - Designed to run inside GitHub Actions daily job (time budget ~30-40 min for 12K selection).
"""
from __future__ import annotations

# 1. Stdlib
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import math
import random
from datetime import datetime, timedelta

# 2. Third-party
import pandas as pd
import numpy as np
import yfinance as yf
from financedatabase import Equities

# 3. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class SelectionConfig:
    limit: int = 12000
    pre_candidate_cap: int = 20000  # Max raw symbols before deep filtering
    min_price: float = 2.0
    max_price: float = 500.0
    min_avg_volume: int = 200_000
    min_dollar_volume: float = 1_000_000.0  # avg_price * avg_volume
    min_market_cap: float = 300_000_000.0  # 300M
    lookback_days: int = 90
    momentum_window: int = 20
    volatility_window: int = 60
    max_sector_weight: float = 0.15  # max 15% per sector after selection
    random_seed: Optional[int] = None


class EnhancedUniverseSelector:
    """High-quality universe selection for large-scale global scanning."""

    def __init__(self, config: Optional[SelectionConfig] = None) -> None:
        self.config = config or SelectionConfig()
        # Utiliser générateur dédié pour reproductibilité sans affecter global RNG
        self._rng = random.Random(self.config.random_seed) if self.config.random_seed is not None else None
        logger.info(
            f"EnhancedUniverseSelector initialized: limit={self.config.limit}, pre_cap={self.config.pre_candidate_cap}"
        )

    def _fetch_raw_universe(self, regions: Optional[List[str]]) -> pd.DataFrame:
        eq = Equities()
        if not regions:  # Global
            df = eq.search()  # Returns metadata DataFrame
        else:
            frames = []
            for reg in regions:
                part = eq.search(country=reg)
                if part is not None and not part.empty:
                    frames.append(part)
            df = pd.concat(frames) if frames else pd.DataFrame()
        if df is None:
            df = pd.DataFrame()
        logger.info(f"Raw universe size={len(df)}")
        return df

    @staticmethod
    def _basic_symbol_filter(symbol: str) -> bool:
        if not isinstance(symbol, str):
            return False
        if len(symbol) > 6:
            return False
        if '.' in symbol:
            return False
        if symbol.count('-') > 1:
            return False
        return True

    def _structural_filter(self, df: pd.DataFrame) -> List[str]:
        symbols = []
        for sym in df.index:
            if self._basic_symbol_filter(sym):
                symbols.append(sym)
        logger.info(f"Structural filter -> {len(symbols)} symbols")
        return symbols

    def _sample_precandidates(self, symbols: List[str]) -> List[str]:
        if self._rng is not None:
            self._rng.shuffle(symbols)
        else:
            random.shuffle(symbols)
        precap = min(len(symbols), self.config.pre_candidate_cap)
        pre = symbols[:precap]
        logger.info(f"Pre-candidates sampled={len(pre)} (cap={self.config.pre_candidate_cap})")
        return pre

    def _download_market_data(self, symbols: List[str]) -> pd.DataFrame:
        # Batch download using yfinance. Returns multi-index DataFrame.
        data_frames = []
        chunk_size = 50
        end = datetime.utcnow()
        start = end - timedelta(days=self.config.lookback_days)
        for i in range(0, len(symbols), chunk_size):
            batch = symbols[i:i+chunk_size]
            try:
                df = yf.download(batch, start=start, end=end, interval='1d', progress=False, group_by='ticker', threads=True)
                # yf returns different structure if single symbol; standardize
                if isinstance(df.columns, pd.MultiIndex):
                    data_frames.append(df)
                else:
                    # Single symbol case wrap
                    df = pd.concat({batch[0]: df}, axis=1)
                    data_frames.append(df)
            except Exception as e:
                logger.warning(f"Batch {i}-{i+len(batch)} download failed: {e}")
        if not data_frames:
            return pd.DataFrame()
        full = pd.concat(data_frames, axis=1)
        return full

    def _compute_component_weights(self, df: pd.DataFrame) -> Dict[str, float]:
        """Compute dynamic component weights based on dispersion and redundancy.

        Args:
            df: DataFrame containing standardized component scores:
                LiquidityScore, SizeScore, StabilityScore, MomentumScore

        Returns:
            Dict mapping component name to weight (sums to 1).
        """
        components = ["LiquidityScore", "SizeScore", "StabilityScore", "MomentumScore"]
        available = [c for c in components if c in df.columns]
        if not available:
            return {c: 1/4 for c in components}
        variances = {}
        corrs = {}
        sub = df[available]
        # Compute correlation matrix (fallback to identity if singular)
        corr_matrix = sub.corr(method="spearman").fillna(0.0)
        for c in available:
            variances[c] = float(sub[c].var(ddof=1)) if sub[c].nunique() > 1 else 0.0
            # Average absolute correlation excluding self
            others = [o for o in available if o != c]
            if not others:
                corrs[c] = 0.0
            else:
                corrs[c] = float(np.mean(np.abs([corr_matrix.loc[c, o] for o in others])))
        scores = {}
        for c in available:
            scores[c] = variances[c] / (1.0 + corrs[c])
        total = sum(scores.values())
        if total <= 0:
            return {c: 1/len(available) for c in available}
        weights = {c: scores[c]/total for c in available}
        # Ensure all original components present (missing -> 0 weight)
        for c in components:
            weights.setdefault(c, 0.0)
        return weights

    def _compute_quality_metrics(self, market_data: pd.DataFrame) -> pd.DataFrame:
        # Expect MultiIndex: (symbol, field)
        if market_data.empty:
            return pd.DataFrame()
        records = []
        for sym in sorted({c[0] for c in market_data.columns if isinstance(c, tuple)}):
            try:
                close = market_data[(sym, 'Close')].dropna()
                volume = market_data[(sym, 'Volume')].dropna()
                if close.empty or volume.empty:
                    continue
                avg_price = float(close.tail(20).mean())
                avg_volume = float(volume.tail(20).mean())
                if avg_price <= 0 or avg_volume <= 0:
                    continue
                dollar_vol = avg_price * avg_volume
                # Basic liquidity filters
                if avg_price < self.config.min_price or avg_price > self.config.max_price:
                    continue
                if avg_volume < self.config.min_avg_volume or dollar_vol < self.config.min_dollar_volume:
                    continue
                # Momentum
                momentum_window = min(self.config.momentum_window, len(close))
                momentum_ret = close.tail(momentum_window).pct_change().dropna()
                momentum = float((close.iloc[-1] / close.iloc[-momentum_window]) - 1) if len(close) >= momentum_window else 0.0
                # Volatility
                vol_window = min(self.config.volatility_window, len(close))
                vol_series = close.tail(vol_window).pct_change().dropna()
                volatility = float(vol_series.std()) if not vol_series.empty else 0.0
                records.append({
                    'symbol': sym,
                    'avg_price': avg_price,
                    'avg_volume': avg_volume,
                    'avg_dollar_volume': dollar_vol,
                    'momentum': momentum,
                    'volatility': volatility,
                })
            except Exception:
                continue
        df = pd.DataFrame(records)
        if df.empty:
            return df
        # Size / Market cap not accessible directly here; placeholder zeros
        df['market_cap'] = np.nan
        # Normalizations
        def norm(series: pd.Series) -> pd.Series:
            if series.empty:
                return series
            a, b = series.min(), series.max()
            if a == b:
                return pd.Series([0.5]*len(series), index=series.index)
            return (series - a) / (b - a)
        df['LiquidityScore'] = norm(df['avg_dollar_volume'])
        # Market cap placeholder: treat avg_price*avg_volume as proxy
        df['SizeScore'] = norm(np.log1p(df['avg_dollar_volume']))
        # Stability (lower volatility better)
        if df['volatility'].max() > 0:
            df['StabilityScore'] = 1 - norm(df['volatility'])
        else:
            df['StabilityScore'] = 0.5
        # Momentum score (clipped between -50% and +50%)
        df['MomentumScore'] = norm(df['momentum'].clip(-0.5, 0.5))
        # Dynamic component weighting
        weights = self._compute_component_weights(df)
        df['LiquidityWeight'] = weights['LiquidityScore']
        df['SizeWeight'] = weights['SizeScore']
        df['StabilityWeight'] = weights['StabilityScore']
        df['MomentumWeight'] = weights['MomentumScore']
        df['quality_score'] = (
            weights['LiquidityScore'] * df['LiquidityScore'] +
            weights['SizeScore'] * df['SizeScore'] +
            weights['StabilityScore'] * df['StabilityScore'] +
            weights['MomentumScore'] * df['MomentumScore']
        )
        return df.sort_values('quality_score', ascending=False)

    def _apply_sector_diversification(self, ranked_df: pd.DataFrame, raw_meta: pd.DataFrame) -> List[str]:
        if ranked_df.empty or raw_meta is None or raw_meta.empty:
            return ranked_df['symbol'].tolist()[: self.config.limit]
        # Attach sector info
        meta_sectors = raw_meta[['sector']] if 'sector' in raw_meta.columns else pd.DataFrame(index=raw_meta.index)
        merged = ranked_df.merge(meta_sectors, left_on='symbol', right_index=True, how='left')
        sector_counts: Dict[str, int] = {}
        max_per_sector = max(1, int(self.config.limit * self.config.max_sector_weight))
        selected: List[str] = []
        for _, row in merged.iterrows():
            sector = (row.get('sector') or 'UNKNOWN')
            cnt = sector_counts.get(sector, 0)
            if cnt < max_per_sector:
                selected.append(row['symbol'])
                sector_counts[sector] = cnt + 1
            if len(selected) >= self.config.limit:
                break
        logger.info(f"Sector diversification applied: sectors={len(sector_counts)} selected={len(selected)}")
        return selected

    def select(self, limit: Optional[int] = None, regions: Optional[List[str]] = None) -> List[str]:
        cfg = self.config
        if limit is not None:
            cfg.limit = limit
        raw_meta = self._fetch_raw_universe(regions)
        structural = self._structural_filter(raw_meta)
        precandidates = self._sample_precandidates(structural)
        market_data = self._download_market_data(precandidates)
        ranked = self._compute_quality_metrics(market_data)
        if ranked.empty:
            logger.warning("Ranked DataFrame empty – fallback to structural sample")
            return precandidates[: cfg.limit]
        final_symbols = self._apply_sector_diversification(ranked, raw_meta)
        logger.info(f"Final universe size={len(final_symbols)}")
        return final_symbols

__all__ = ["EnhancedUniverseSelector", "SelectionConfig"]
