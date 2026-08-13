"""Validation empirique de la bande de non-transaction (#4) sur momentum réel.

La bande de non-transaction est faite pour des **poids continus** (façon
Black-Litterman du pipeline live), pas pour un book quantile équipondéré. On la
teste donc sur un momentum à **poids continus** : chaque jour, poids ∝ z-score
cross-section de ``momentum_12_1`` (dollar-neutre, gross = 1), rééquilibré **tous
les jours** (là où le turnover — donc la bande — compte le plus). On balaie
plusieurs largeurs de bande, coûts Alpaca calibrés, et on rapporte turnover moyen,
Sharpe brut/net et rendement net.

Lecture honnête : si une bande > 0 relève le **Sharpe net** (moins de coûts pour
un signal quasi inchangé), le cost-aware paie ; sinon le rééquilibrage espacé
(déjà en place) suffit.

Usage::

    python scripts/run_cost_aware_band_alpaca.py
    python scripts/run_cost_aware_band_alpaca.py --bands 0 0.005 0.01 0.02 0.05
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.cost_aware import apply_no_trade_band
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.data.alpaca_history import load_or_fetch

DEFAULT_UNIVERSE = sorted(
    {
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
        "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
        "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
        "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
        "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
        "MS", "AXP", "BLK", "C", "SCHW", "T", "VZ", "CMCSA", "PM", "MO",
        "IBM", "NOW", "INTU", "AMAT", "MU", "LRCX", "GILD", "AMGN", "BMY", "DE",
        "MMM", "LMT", "RTX", "SPGI", "ISRG", "MDT", "CVS", "TGT", "COP", "PYPL",
    }
)


def _continuous_weights(score_row: pd.Series) -> pd.Series:
    """Poids continus dollar-neutres ∝ z-score cross-section (gross = 1)."""
    s = score_row.dropna()
    if len(s) < 5 or s.std(ddof=0) == 0:
        return pd.Series(0.0, index=score_row.index)
    z = (s - s.mean()) / s.std(ddof=0)
    gross = z.abs().sum()
    w = z / gross if gross > 0 else z * 0.0
    return w.reindex(score_row.index).fillna(0.0)


def _sharpe(r: pd.Series) -> float:
    r = r.dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(252)) if len(r) > 1 and sd > 0 else 0.0


def _simulate(scores: pd.DataFrame, returns: pd.DataFrame, cost_rate: float, band: float):
    fwd = returns.shift(-1)
    prev = None
    gross_rets, net_rets, tos = [], [], []
    for dt in scores.index:
        f = fwd.loc[dt]
        if f.isna().all():
            continue
        target = _continuous_weights(scores.loc[dt])
        if prev is None:
            to = float(target.abs().sum())
        else:
            if band > 0:
                target = apply_no_trade_band(target, prev, band)
            to = float((target - prev.reindex(target.index).fillna(0.0)).abs().sum())
        prev = target
        g = float((target.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum())
        gross_rets.append(g)
        net_rets.append(g - to * cost_rate)
        tos.append(to)
    net = pd.Series(net_rets)
    gross = pd.Series(gross_rets)
    eq = (1.0 + net).cumprod()
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) else 0.0
    return {
        "turnover": float(np.mean(tos)) if tos else 0.0,
        "gross_sharpe": _sharpe(gross), "net_sharpe": _sharpe(net),
        "net_ann": float(net.mean() * 252 * 100.0), "maxdd": dd,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--bands", type=float, nargs="+",
                    default=[0.0, 0.005, 0.01, 0.02, 0.05])
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    scores = compute_classic_factors(prices)["momentum_12_1"]
    returns = daily_returns(prices)
    cost_rate = CostModel.alpaca_equities().cost_rate

    print("=" * 74)
    print("BANDE DE NON-TRANSACTION — momentum 12-1 à poids continus, reb quotidien")
    print("=" * 74)
    print(f"\n  {'bande':>7} {'turnover':>9} {'Sharpe brut':>12} {'Sharpe net':>11} "
          f"{'rdt net an.':>12} {'maxDD':>8}")
    for band in args.bands:
        m = _simulate(scores, returns, cost_rate, band)
        print(f"  {band:>7.3f} {m['turnover']:>9.3f} {m['gross_sharpe']:>+12.2f} "
              f"{m['net_sharpe']:>+11.2f} {m['net_ann']:>+11.1f}% {m['maxdd']:>+7.1f}%")

    print("\nLecture : à bande=0 on paie le turnover plein. Si une bande > 0 remonte le")
    print("Sharpe NET (turnover ↓ pour un brut ~stable), le cost-aware paie. La bande")
    print("est câblée en option dans le pipeline live (LiveTradingPipeline.no_trade_band).")


if __name__ == "__main__":
    main()
