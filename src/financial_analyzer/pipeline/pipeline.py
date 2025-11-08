"""Unified Orchestration Pipeline V2.

Phase 5.5 Module 7: Final unified pipeline that composes previously built
modules (data fetching, feature engineering, sentiment, ML predictions,
signal fusion, portfolio allocation, risk optimization, order generation).

This pipeline is designed for production usage with:
- Dependency injection (no hardcoded class instantiation inside methods)
- Graceful degradation: failures in sub-steps are logged; pipeline continues
- Comprehensive logging for every phase
- Internal caching of intermediate state to allow inspection and reuse
- Clean, typed interfaces for each stage

Contract Summary
----------------
Inputs:
    run_date (str | pd.Timestamp): Date for pipeline execution
    universe (List[str]): List of tickers to process
    optimization_method (str): Risk optimization method (e.g. 'none', 'equal_weight', 'inverse_variance')

Outputs:
    Dict[str, Any] structured with keys:
        status: 'success' | 'partial' | 'error'
        run_date: str
        universe: List[str]
        steps: Dict[str, Any]   # detailed outputs per stage
        errors: List[str]
        metrics: Dict[str, Any]

Edge Cases:
    - Empty universe: returns early with warning
    - Partial failures (e.g. sentiment unavailable) recorded and pipeline proceeds
    - Optimization errors revert to pre-optimization weights

Example
-------
>>> from financial_analyzer.pipeline.pipeline import Pipeline
>>> pipeline = Pipeline(
...     universe_selector=selector,
...     lookback_days=120,
...     forecast_horizon=5,
...     optimization_method='inverse_variance'
... )
>>> result = pipeline.run('2025-11-08', ['AAPL', 'MSFT', 'GOOGL'], optimization_method='inverse_variance')
>>> result['status']
'success'

"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from financial_analyzer.utils.helpers import get_logger, calculate_returns, calculate_volatility
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.strategy.signal_fusion import SignalFusion
from financial_analyzer.strategy.ensemble_allocator import EnsembleAllocator

logger = get_logger(__name__)


@dataclass
class PipelineCache:
    """Internal cache structure for pipeline intermediate results."""
    raw_data: Dict[str, pd.DataFrame] | None = None
    returns: pd.DataFrame | None = None
    metadata: pd.DataFrame | None = None
    technical_features: Dict[str, Dict[str, float]] | None = None
    sentiment: Dict[str, float] | None = None
    ml_predictions: Dict[str, float] | None = None
    fused_signals: Dict[str, Dict[str, float]] | None = None
    allocations: Dict[str, float] | None = None
    optimized_allocations: Dict[str, float] | None = None
    orders: List[Dict[str, Any]] | None = None


class Pipeline:
    """Unified multi-stage trading pipeline.

    Orchestrates data retrieval, feature engineering, sentiment analysis,
    ML prediction generation, signal fusion, portfolio allocation, optional
    risk optimization, and order creation.

    Parameters
    ----------
    universe_selector : UniverseSelector
        Instance used to fetch metadata and validate universe.
    lookback_days : int
        Number of past days of data to fetch for features and predictions.
    forecast_horizon : int
        Forward horizon (days) for generating predictive signals.
    optimization_method : str, default 'none'
        Default optimization method applied in run().
    market_data_fetcher : MarketDataFetcher | None
        External dependency for OHLCV data.
    signal_fusion : SignalFusion | None
        Component to fuse technical/sentiment/ML signals.
    allocator : EnsembleAllocator | None
        Portfolio allocation engine.

    Raises
    ------
    ValueError
        If lookback_days <= 0 or forecast_horizon <= 0.

    """
    def __init__(
        self,
        universe_selector: UniverseSelector,
        lookback_days: int = 120,
        forecast_horizon: int = 5,
        optimization_method: str = 'none',
        market_data_fetcher: Optional[MarketDataFetcher] = None,
        signal_fusion: Optional[SignalFusion] = None,
        allocator: Optional[EnsembleAllocator] = None,
    ) -> None:
        if lookback_days <= 0:
            raise ValueError("lookback_days must be > 0")
        if forecast_horizon <= 0:
            raise ValueError("forecast_horizon must be > 0")

        self.universe_selector = universe_selector
        self.lookback_days = lookback_days
        self.forecast_horizon = forecast_horizon
        self.default_optimization_method = optimization_method

        # Dependencies with defaults
        self.market_data_fetcher = market_data_fetcher or MarketDataFetcher()
        self.signal_fusion = signal_fusion or SignalFusion()
        self.allocator = allocator or EnsembleAllocator()

        self.cache = PipelineCache()

        logger.info(
            f"Pipeline initialized: lookback_days={lookback_days}, forecast_horizon={forecast_horizon}, "
            f"default_opt_method={optimization_method}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        run_date: str | datetime,
        universe: List[str],
        optimization_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the full pipeline for a given universe.

        Parameters
        ----------
        run_date : str | datetime
            Date to anchor data fetch (end date).
        universe : list of str
            List of tickers.
        optimization_method : str, optional
            Override default optimization method.

        Returns
        -------
        dict
            Structured result with steps, metrics, errors.
        """
        errors: List[str] = []
        steps: Dict[str, Any] = {}

        if not universe:
            logger.warning("Empty universe provided; aborting pipeline")
            return {
                'status': 'error',
                'run_date': str(run_date),
                'universe': universe,
                'steps': {},
                'errors': ['Empty universe'],
                'metrics': {},
            }

        opt_method = optimization_method or self.default_optimization_method
        logger.info(
            f"Pipeline run start date={run_date}, universe_size={len(universe)}, optimization_method={opt_method}"
        )

        # 1. Fetch data -------------------------------------------------
        try:
            returns_df, metadata = self._fetch_data(universe, self.lookback_days, run_date)
            steps['data'] = {
                'returns_shape': returns_df.shape,
                'metadata_count': len(metadata) if metadata is not None else 0,
            }
        except Exception as e:
            logger.error(f"Data fetch failed: {e}")
            errors.append(f"fetch_data: {e}")
            returns_df = pd.DataFrame()
            metadata = pd.DataFrame()
            steps['data'] = {}

        # 2. Features ---------------------------------------------------
        try:
            technical = self._engineer_features(returns_df)
            steps['features'] = {
                'technical_count': len(technical),
                'sample': list(technical.values())[0] if technical else {},
            }
        except Exception as e:
            logger.error(f"Feature engineering failed: {e}")
            errors.append(f"engineer_features: {e}")
            technical = {}
            steps['features'] = {}

        # 3. Sentiment --------------------------------------------------
        try:
            sentiment = self._analyze_sentiment(universe)
            steps['sentiment'] = {'count': len(sentiment)}
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            errors.append(f"analyze_sentiment: {e}")
            sentiment = {t: 0.0 for t in universe}  # Neutral fallback
            steps['sentiment'] = {}

        # 4. ML Predictions ---------------------------------------------
        try:
            ml_pred = self._generate_predictions(returns_df)
            steps['ml_predictions'] = {'count': len(ml_pred)}
        except Exception as e:
            logger.error(f"ML prediction generation failed: {e}")
            errors.append(f"generate_predictions: {e}")
            ml_pred = {t: 0.5 for t in universe}  # Neutral probability
            steps['ml_predictions'] = {}

        # 5. Signal Fusion ----------------------------------------------
        try:
            fused = self._fuse_signals(technical, sentiment, ml_pred)
            steps['fused_signals'] = {
                'count': len(fused),
                'sample': fused[next(iter(fused))] if fused else {},
            }
        except Exception as e:
            logger.error(f"Signal fusion failed: {e}")
            errors.append(f"fuse_signals: {e}")
            fused = {t: {'final_score': 0.5, 'confidence': 0.0} for t in universe}
            steps['fused_signals'] = {}

        # 6. Allocation -------------------------------------------------
        try:
            allocations = self._allocate_portfolio(fused)
            steps['allocation'] = {
                'count': len(allocations),
                'cash_weight': allocations.get('cash', 0.0),
            }
        except Exception as e:
            logger.error(f"Allocation failed: {e}")
            errors.append(f"allocate_portfolio: {e}")
            allocations = {'cash': 1.0}
            steps['allocation'] = {}

        # 7. Risk Optimization -----------------------------------------
        try:
            optimized = self._optimize_risk(allocations, returns_df, opt_method)
            steps['optimization'] = {'method': opt_method, 'count': len(optimized)}
        except Exception as e:
            logger.error(f"Risk optimization failed: {e}")
            errors.append(f"optimize_risk: {e}")
            optimized = allocations  # Fallback
            steps['optimization'] = {}

        # 8. Order Generation ------------------------------------------
        try:
            orders = self._generate_orders(current_positions={}, target_weights=optimized, capital=100_000)
            steps['orders'] = {'count': len(orders)}
        except Exception as e:
            logger.error(f"Order generation failed: {e}")
            errors.append(f"generate_orders: {e}")
            orders = []
            steps['orders'] = {}

        # Cache everything
        self.cache.raw_data = None  # Omitted large data for memory
        self.cache.returns = returns_df
        self.cache.metadata = metadata
        self.cache.technical_features = technical
        self.cache.sentiment = sentiment
        self.cache.ml_predictions = ml_pred
        self.cache.fused_signals = fused
        self.cache.allocations = allocations
        self.cache.optimized_allocations = optimized
        self.cache.orders = orders

        status = 'success' if not errors else ('partial' if steps else 'error')

        metrics = self._compute_metrics(returns_df, allocations, optimized)

        logger.info(
            f"Pipeline completed: status={status}, errors={len(errors)}, allocations={len(allocations)}"
        )

        return {
            'status': status,
            'run_date': str(run_date),
            'universe': universe,
            'steps': steps,
            'errors': errors,
            'metrics': metrics,
        }

    # ------------------------------------------------------------------
    # Internal Methods
    # ------------------------------------------------------------------
    def _fetch_data(
        self,
        universe: List[str],
        lookback_days: int,
        run_date: str | datetime,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch historical data and metadata.

        Returns
        -------
        returns_df : pd.DataFrame
            Multi-asset returns (columns=tickers)
        metadata : pd.DataFrame
            Metadata dataframe from UniverseSelector
        """
        end_dt = pd.Timestamp(run_date)
        start_dt = end_dt - timedelta(days=lookback_days)

        all_prices: Dict[str, pd.DataFrame] = {}
        for ticker in universe:
            try:
                data = self.market_data_fetcher.get_historical_data(
                    ticker, start_date=start_dt.strftime('%Y-%m-%d'), end_date=end_dt.strftime('%Y-%m-%d')
                )
                all_prices[ticker] = data
            except Exception as e:
                logger.error(f"Price fetch failed {ticker}: {e}")
                all_prices[ticker] = pd.DataFrame()

        # Build returns frame
        returns_frames = []
        for t, df in all_prices.items():
            if not df.empty and 'Close' in df.columns:
                r = calculate_returns(df['Close']).rename(t)
                returns_frames.append(r)
        if returns_frames:
            returns_df = pd.concat(returns_frames, axis=1).dropna(how='all').fillna(0.0)
        else:
            returns_df = pd.DataFrame(columns=universe)
            logger.warning("No valid price data; returns_df empty")

        # Metadata
        try:
            metadata = self.universe_selector.get_metadata(universe)
        except Exception as e:
            logger.error(f"Metadata fetch failed: {e}")
            metadata = pd.DataFrame(columns=['symbol'])

        return returns_df, metadata

    def _engineer_features(self, returns: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Compute simple technical features per ticker.

        For each ticker, derive:
            - mean_return (last N days)
            - volatility (rolling)
            - momentum (return over last 5 days)
            - sharpe_proxy (mean / volatility)

        Returns
        -------
        dict
            {ticker: {feature_name: value}}
        """
        features: Dict[str, Dict[str, float]] = {}
        if returns.empty:
            logger.warning("Empty returns passed to _engineer_features")
            return features

        window = min(20, len(returns))
        for ticker in returns.columns:
            series = returns[ticker].dropna()
            if series.empty:
                continue
            mean_ret = float(series.tail(window).mean())
            vol = float(series.tail(window).std()) if window > 1 else 0.0
            momentum = float(series.tail(5).sum())
            sharpe_proxy = mean_ret / vol if vol > 0 else 0.0
            features[ticker] = {
                'mean_return': mean_ret,
                'volatility': vol,
                'momentum': momentum,
                'sharpe_proxy': sharpe_proxy,
            }
        return features

    def _analyze_sentiment(self, universe: List[str]) -> Dict[str, float]:
        """Mock sentiment analysis producing values in [-1, 1]."""
        np.random.seed(42)
        return {t: float(np.random.uniform(-1, 1)) for t in universe}

    def _generate_predictions(self, returns: pd.DataFrame) -> Dict[str, float]:
        """Mock ML predictions producing probability-like scores in [0, 1]."""
        np.random.seed(123)
        return {
            t: float(np.random.uniform(0.0, 1.0))
            for t in returns.columns
        }

    def _fuse_signals(
        self,
        technical: Dict[str, Dict[str, float]],
        sentiment: Dict[str, float],
        ml_pred: Dict[str, float],
    ) -> Dict[str, Dict[str, float]]:
        """Fuse signals per ticker using SignalFusion component.

        Falls back to neutral signal if any source missing.
        """
        fused: Dict[str, Dict[str, float]] = {}
        for ticker in set(sentiment.keys()) | set(technical.keys()) | set(ml_pred.keys()):
            try:
                tech_score = technical.get(ticker, {})
                sent_score = sentiment.get(ticker)
                ml_score = ml_pred.get(ticker)
                result = self.signal_fusion.fuse(
                    ticker=ticker,
                    sentiment=sent_score,
                    technical_signals={
                        'rsi': abs(tech_score.get('momentum', 0.0) * 10) % 100,  # heuristic mapping
                        'macd': tech_score.get('mean_return', 0.0),
                        'sma_cross': 1 if tech_score.get('momentum', 0.0) > 0 else -1,
                        'bb_position': 0.5 + tech_score.get('sharpe_proxy', 0.0),
                    } if tech_score else None,
                    dl_prediction=ml_score,
                )
                fused[ticker] = {
                    'final_score': float(result['final_score']),
                    'confidence': float(result['confidence']),
                }
            except Exception as e:
                logger.error(f"Fusion failed {ticker}: {e}")
                fused[ticker] = {'final_score': 0.5, 'confidence': 0.0}
        return fused

    def _allocate_portfolio(self, signals: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Allocate portfolio weights using EnsembleAllocator."""
        return self.allocator.allocate(signals, total_capital=100_000, risk_model='signal_based')

    def _optimize_risk(
        self,
        weights: Dict[str, float],
        returns: pd.DataFrame,
        method: str = 'none',
    ) -> Dict[str, float]:
        """Apply simple risk optimization heuristics.

        Methods
        -------
        none : return weights unchanged
        equal_weight : reassign equal weights to non-cash positions
        inverse_variance : weight by inverse variance of returns
        """
        if method == 'none' or not weights:
            return weights

        cash_weight = weights.get('cash', 0.0)
        asset_weights = {k: v for k, v in weights.items() if k != 'cash'}

        if not asset_weights:
            return weights

        try:
            if method == 'equal_weight':
                n = len(asset_weights)
                eq = (1.0 - cash_weight) / n if n > 0 else 0.0
                new_w = {k: eq for k in asset_weights}
            elif method == 'inverse_variance':
                inv_vars: Dict[str, float] = {}
                for t in asset_weights:
                    series = returns.get(t)
                    if series is not None and len(series) > 10:
                        var = float(series.var())
                        inv_vars[t] = 1.0 / var if var > 0 else 0.0
                    else:
                        inv_vars[t] = 0.0
                total = sum(inv_vars.values())
                if total > 0:
                    new_w = {k: (v / total) * (1.0 - cash_weight) for k, v in inv_vars.items()}
                else:
                    new_w = asset_weights  # fallback
            else:
                logger.warning(f"Unknown optimization method {method}; returning original weights")
                return weights

            # Recombine with cash
            new_w['cash'] = cash_weight
            return new_w
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            return weights

    def _generate_orders(
        self,
        current_positions: Dict[str, float],
        target_weights: Dict[str, float],
        capital: float,
    ) -> List[Dict[str, Any]]:
        """Generate mock orders comparing current vs target weights.

        Returns list of orders with fields:
            ticker, action (BUY/SELL/HOLD), target_weight, delta_weight, notional
        """
        orders: List[Dict[str, Any]] = []
        for ticker, tgt_w in target_weights.items():
            if ticker == 'cash':
                continue
            cur_w = current_positions.get(ticker, 0.0)
            delta = tgt_w - cur_w
            action = 'HOLD'
            if delta > 0.001:
                action = 'BUY'
            elif delta < -0.001:
                action = 'SELL'
            notional = delta * capital
            orders.append({
                'ticker': ticker,
                'action': action,
                'target_weight': tgt_w,
                'delta_weight': delta,
                'notional': notional,
            })
        return orders

    def _compute_metrics(
        self,
        returns: pd.DataFrame,
        alloc: Dict[str, float],
        opt_alloc: Dict[str, float],
    ) -> Dict[str, Any]:
        """Compute simple diagnostic metrics."""
        metrics: Dict[str, Any] = {}
        try:
            metrics['universe_size'] = len(returns.columns)
            metrics['allocation_positions'] = len([k for k in alloc if k != 'cash'])
            metrics['optimized_positions'] = len([k for k in opt_alloc if k != 'cash'])
            metrics['cash_weight_initial'] = float(alloc.get('cash', 0.0))
            metrics['cash_weight_final'] = float(opt_alloc.get('cash', 0.0))
            # Basic volatility proxy
            if not returns.empty:
                daily_port_ret = returns.mean(axis=1)  # naive average
                metrics['avg_daily_return'] = float(daily_port_ret.mean())
                metrics['daily_volatility'] = float(daily_port_ret.std())
        except Exception as e:
            logger.error(f"Metric computation failed: {e}")
        return metrics

__all__ = ["Pipeline", "PipelineCache"]
