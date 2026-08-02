"""FinBot Backtester autonome (Option B).

Moteur de backtest multi-actifs autonome qui orchestre la Pipeline FinBot pour
produire des allocations, applique des contraintes de risque et gère
stop-loss / take-profit basés sur le prix d'entrée.

Compat: fournit un alias FinBotStrategy pour compatibilité ascendante.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.caching.cache_manager import CacheManager
from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.strategy.signal_fusion import SignalFusion
from financial_analyzer.strategy.ensemble_allocator import EnsembleAllocator

logger = get_logger(__name__)


@dataclass
class RiskConfig:
    """Configuration de gestion du risque.

    Attributes:
        max_position: poids max par actif (après normalisation)
        stop_loss_pct: seuil de perte relatif au prix d'entrée pour liquidation
        take_profit_pct: seuil de gain relatif au prix d'entrée pour prise de profit (50%)
        rebalance_period: nombre de barres entre rééquilibrages
    """
    max_position: float = 0.2
    stop_loss_pct: float = 0.15
    take_profit_pct: float = 0.50
    rebalance_period: int = 20


class FinBotBacktester:
    """Moteur de backtest autonome.

    Contrat minimal:
    - init(): prépare l'état
    - next(i): avance d'une barre, gère risques et rééquilibrages
    - equity(): série d'équity
    - positions(): poids courants
    """

    def __init__(
        self,
        data: Dict[str, pd.DataFrame],
        initial_cash: float = 100_000.0,
        universe: Optional[List[str]] = None,
        lookback_days: int = 60,
        forecast_horizon: int = 5,
        risk: Optional[RiskConfig] = None,
        cache: Optional[CacheManager] = None,
    ) -> None:
        self.data = data
        self.tickers = universe or list(data.keys())
        self.initial_cash = initial_cash
        self.lookback_days = lookback_days
        self.forecast_horizon = forecast_horizon
        self.risk = risk or RiskConfig()
        self.cache = cache or CacheManager(url=None)
        self.signal_fusion = SignalFusion()
        self.allocator = EnsembleAllocator()
        # Portefeuille
        self.weights: Dict[str, float] = {t: 0.0 for t in self.tickers}
        self.cash: float = 1.0
        self.equity_curve: List[float] = []
        self.last_rebalance_idx: int = -1
        self.entry_prices: Dict[str, float] = {}

        # Stubs injectés pour la Pipeline afin d'utiliser les données déjà chargées
        class _SimpleSelector:
            def get_metadata(self, universe: List[str]) -> pd.DataFrame:  # noqa: N805
                return pd.DataFrame({"symbol": universe})

        self.pipeline = Pipeline(
            universe_selector=_SimpleSelector(),
            lookback_days=self.lookback_days,
            forecast_horizon=self.forecast_horizon,
            market_data_fetcher=None,  # remplacé dynamiquement à chaque rebalance
            signal_fusion=self.signal_fusion,
            allocator=self.allocator,
        )

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def init(self) -> None:
        logger.info("FinBotBacktester.init()")
        self.cache.reset_metrics()
        self.equity_curve.clear()
        self.weights = {t: 0.0 for t in self.tickers}
        self.entry_prices.clear()
        self.cash = 1.0
        self.last_rebalance_idx = -1

    def next(self, idx: int) -> None:
        prices = {t: self._price_at(t, idx) for t in self.tickers}
        port_ret = self._portfolio_return(prices, idx)
        self._update_equity(port_ret)

        # Gestion du risque basée sur prix d'entrée
        self._check_stop_losses(idx)

        if self._should_rebalance(idx):
            self._rebalance(idx)
            self.last_rebalance_idx = idx

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _price_at(self, ticker: str, idx: int) -> Optional[float]:
        df = self.data.get(ticker)
        if df is None or idx >= len(df):
            return None
        return float(df["Close"].iloc[idx])

    def _portfolio_return(self, prices: Dict[str, Optional[float]], idx: int) -> float:
        if idx == 0:
            return 0.0
        prev_prices = {t: self._price_at(t, idx - 1) for t in self.tickers}
        ret = 0.0
        for t in self.tickers:
            w = self.weights.get(t, 0.0)
            p0 = prev_prices.get(t)
            p1 = prices.get(t)
            if w > 0 and p0 and p1 and p0 > 0:
                ret += w * ((p1 - p0) / p0)
        return float(ret)

    def _update_equity(self, port_ret: float) -> None:
        if not self.equity_curve:
            self.equity_curve.append(self.initial_cash)
        else:
            self.equity_curve.append(self.equity_curve[-1] * (1.0 + port_ret))

    def _should_rebalance(self, idx: int) -> bool:
        return self.last_rebalance_idx < 0 or (idx - self.last_rebalance_idx) >= self.risk.rebalance_period

    # ------------------------------------------------------------------
    # Risk Management (entrée-based)
    # ------------------------------------------------------------------
    def _check_stop_losses(self, idx: int) -> None:
        for t in list(self.weights.keys()):
            w = self.weights.get(t, 0.0)
            if w <= 0:
                continue
            p = self._price_at(t, idx)
            entry = self.entry_prices.get(t)
            if p is None or entry is None or entry <= 0:
                continue
            pnl = (p - entry) / entry
            # Stop-loss: close
            if pnl <= -self.risk.stop_loss_pct:
                freed = self.weights[t]
                self.weights[t] = 0.0
                self.entry_prices.pop(t, None)
                self.cash = min(1.0, self.cash + freed)
                logger.info(f"Stop-loss {t}: freed={freed:.2%}")
            # Take-profit: scale down by 50% and reset entry
            elif pnl >= self.risk.take_profit_pct:
                freed = self.weights[t] * 0.5
                self.weights[t] *= 0.5
                self.entry_prices[t] = p
                self.cash = min(1.0, self.cash + freed)
                logger.info(f"Take-profit {t}: freed={freed:.2%}")

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------
    def _rebalance(self, idx: int) -> None:
        # Construire fenêtres de lookback
        frames: Dict[str, pd.DataFrame] = {}
        for t in self.tickers:
            df = self.data[t]
            if idx < 1:
                continue
            sub = df.iloc[max(0, idx - self.lookback_days + 1) : idx + 1]
            frames[t] = sub
        if not frames:
            return

        # Injecter un fetcher basé sur frames pour la Pipeline
        class _DataDictFetcher:
            def __init__(self, frames: Dict[str, pd.DataFrame]) -> None:
                self.frames = frames

            def get_historical_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:  # noqa: N802
                df = self.frames.get(ticker)
                return df if df is not None else pd.DataFrame(columns=["Close"])  # simple stub

        self.pipeline.market_data_fetcher = _DataDictFetcher(frames)

        # Exécuter la pipeline avec la bonne signature
        run_dt = str(next(iter(frames.values())).index[-1].date())
        try:
            _ = self.pipeline.run(run_date=run_dt, universe=list(frames.keys()), optimization_method='inverse_variance')
            # Récupérer l'allocation finale (optimisée si dispo)
            alloc = self.pipeline.cache.optimized_allocations or self.pipeline.cache.allocations or {}
        except Exception as e:
            logger.warning(f"Pipeline failed in rebalance: {e}")
            alloc = {}

        # Fallback égalitaire si vide
        if not alloc:
            alloc = {t: 1.0 / max(1, len(frames)) for t in frames}

        # Retirer cash si présent
        alloc = {t: w for t, w in alloc.items() if t != 'cash'}
        # Fallback égalitaire si plus aucun actif
        if not alloc:
            alloc = {t: 1.0 / max(1, len(frames)) for t in frames}
        # Appliquer contraintes
        alloc = self._apply_risk_constraints(alloc)

        # Mise à jour des poids et cash
        risky_sum = sum(alloc.values())
        self.weights = {t: float(w) for t, w in alloc.items()}
        self.cash = float(max(0.0, 1.0 - risky_sum))

        # Mettre à jour les prix d'entrée pour nouvelles positions
        for t, w in self.weights.items():
            p = self._price_at(t, idx)
            if w > 0 and p is not None and t not in self.entry_prices:
                self.entry_prices[t] = p
            if w == 0:
                self.entry_prices.pop(t, None)

        logger.info(
            "Rebalance applied: risky_sum=%.2f, cash=%.2f, top=%s",
            risky_sum,
            self.cash,
            sorted(self.weights.items(), key=lambda x: x[1], reverse=True)[:3],
        )

    def _apply_risk_constraints(self, alloc: Dict[str, float]) -> Dict[str, float]:
        capped = {t: min(max(0.0, w), self.risk.max_position) for t, w in alloc.items()}
        total = sum(capped.values())
        # Ne renormaliser que si la somme dépasse 1.0; sinon laisser du cash
        if total > 1.0:
            capped = {t: w / total for t, w in capped.items()}
        return capped

    # ------------------------------------------------------------------
    # Résultats
    # ------------------------------------------------------------------
    def equity(self) -> pd.Series:
        idx = range(len(self.equity_curve))
        return pd.Series(self.equity_curve, index=idx, name="equity")

    def positions(self) -> Dict[str, float]:
        return dict(self.weights)


# Compatibilité ascendante
class FinBotStrategy(FinBotBacktester):  # pragma: no cover - alias
    pass
