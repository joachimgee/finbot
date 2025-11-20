"""Backtest Runner V2 pour FinBot.

Fonctions clés:
- load_data(): charge des OHLC 'Close' via yfinance (ou DataFrame fournis)
- run(): backtest simple avec FinBotStrategy
- optimize(): recherche de paramètres (grid) sur quelques hyperparamètres
- walk_forward_analysis(): validation robuste avec fenêtres glissantes
- generate_report(): synthèse de perfs

Cette implémentation évite les appels réseau dans les tests; yfinance peut être
remplacé par des DataFrames fournis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from financial_analyzer.backtesting.finbot_strategy import FinBotBacktester, RiskConfig
from financial_analyzer.caching.cache_manager import CacheManager
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


try:
    import yfinance as yf  # type: ignore
except Exception:  # pragma: no cover
    yf = None  # type: ignore


@dataclass
class BacktestResult:
    equity: pd.Series
    params: Dict[str, Any]
    metrics: Dict[str, float]


def load_data(tickers: List[str], start: str, end: str, interval: str = "1d") -> Dict[str, pd.DataFrame]:
    """Charge des prix 'Close' depuis yfinance (si dispo), sinon retourne vide.

    Returns: dict[ticker] -> DataFrame('Close')
    """
    frames: Dict[str, pd.DataFrame] = {}
    if yf is None:
        logger.warning("yfinance indisponible - load_data renvoie {}")
        return frames
    for t in tickers:
        df = yf.download(t, start=start, end=end, interval=interval, progress=False)
        if isinstance(df, pd.DataFrame) and not df.empty:
            if 'Close' not in df.columns and 'Adj Close' in df.columns:
                df = df.rename(columns={'Adj Close': 'Close'})
            frames[t] = df[['Close']].dropna()
    return frames


def _compute_metrics(equity: pd.Series) -> Dict[str, float]:
    if equity.empty:
        return {"return": 0.0, "vol": 0.0, "sharpe": 0.0, "max_dd": 0.0}
    rets = equity.pct_change().fillna(0.0)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    vol = float(rets.std() * np.sqrt(252))
    sharpe = float((rets.mean() * 252) / (vol + 1e-12))
    cummax = equity.cummax()
    dd = (equity - cummax) / cummax
    max_dd = float(dd.min())
    return {"return": total_return, "vol": vol, "sharpe": sharpe, "max_dd": max_dd}


def run(
    data: Dict[str, pd.DataFrame],
    initial_cash: float = 100_000.0,
    lookback_days: int = 60,
    forecast_horizon: int = 5,
    risk: Optional[RiskConfig] = None,
) -> BacktestResult:
    """Exécute un backtest simple.

    Args:
        data: dict[ticker]->DataFrame('Close') alignés temporellement.
    """
    if not data:
        raise ValueError("No data provided")
    # Alignement index
    length = min(len(df) for df in data.values())
    data = {t: df.iloc[-length:] for t, df in data.items()}

    strat = FinBotBacktester(
        data=data,
        initial_cash=initial_cash,
        universe=list(data.keys()),
        lookback_days=lookback_days,
        forecast_horizon=forecast_horizon,
        risk=risk or RiskConfig(),
        cache=CacheManager(url=None),
    )
    strat.init()
    for i in range(length):
        strat.next(i)
    equity = strat.equity()
    metrics = _compute_metrics(equity)
    return BacktestResult(equity=equity, params={
        "lookback_days": lookback_days,
        "forecast_horizon": forecast_horizon,
    }, metrics=metrics)


def optimize(
    data: Dict[str, pd.DataFrame],
    lookback_grid: Iterable[int] = (30, 60, 90),
    horizon_grid: Iterable[int] = (3, 5, 10),
    max_position_grid: Iterable[float] = (0.15, 0.2, 0.3),
) -> List[BacktestResult]:
    """Grid-search très simple sur 2-3 hyperparamètres."""
    results: List[BacktestResult] = []
    for lb in lookback_grid:
        for hz in horizon_grid:
            for mp in max_position_grid:
                risk = RiskConfig(max_position=mp)
                res = run(data, lookback_days=lb, forecast_horizon=hz, risk=risk)
                res.params.update({"max_position": mp})
                results.append(res)
    # Tri par Sharpe décroissant
    results.sort(key=lambda r: r.metrics.get("sharpe", 0.0), reverse=True)
    return results


def walk_forward_analysis(
    data: Dict[str, pd.DataFrame],
    windows: int = 3,
    train_ratio: float = 0.7,
    lb: int = 60,
    hz: int = 5,
    mp: float = 0.2,
) -> Dict[str, Any]:
    """WFA basique: split en fenêtres, optimise sur train, teste sur test."""
    length = min(len(df) for df in data.values())
    fold_size = length // windows
    folds: List[Dict[str, Any]] = []

    for i in range(windows):
        start = i * fold_size
        end = (i + 1) * fold_size if i < windows - 1 else length
        train_end = start + int((end - start) * train_ratio)
        train = {t: df.iloc[start:train_end] for t, df in data.items()}
        test = {t: df.iloc[train_end:end] for t, df in data.items()}

        # Optimise sur un petit grid autour des params fournis
        results = optimize(
            train,
            lookback_grid=(max(20, lb - 20), lb, lb + 20),
            horizon_grid=(max(2, hz - 2), hz, hz + 2),
            max_position_grid=(max(0.1, mp - 0.05), mp, min(0.5, mp + 0.05)),
        )
        best = results[0]
        # Run sur test avec ces params
        risk = RiskConfig(max_position=float(best.params.get("max_position", mp)))
        test_res = run(
            test,
            lookback_days=int(best.params.get("lookback_days", lb)),
            forecast_horizon=int(best.params.get("forecast_horizon", hz)),
            risk=risk,
        )
        folds.append({
            "train_best": best.metrics,
            "test": test_res.metrics,
        })

    # Agrégation simple
    agg = {
        "test_return_mean": float(np.mean([f["test"]["return"] for f in folds])),
        "test_sharpe_mean": float(np.mean([f["test"]["sharpe"] for f in folds])),
        "folds": folds,
    }
    return agg


def generate_report(result: BacktestResult) -> str:
    lines = [
        "# FinBot Backtest Report",
        "",
        "## Parameters",
        *(f"- {k}: {v}" for k, v in result.params.items()),
        "",
        "## Metrics",
        *(f"- {k}: {v:.4f}" for k, v in result.metrics.items()),
    ]
    return "\n".join(lines)
