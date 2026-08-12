"""Momentum piloté par la volatilité sur données réelles (Tier 1.1).

Prend la stratégie long/short du facteur validé ``momentum_12_1`` (mêmes coûts
calibrés, reb=10) et applique l'overlay de ciblage de volatilité (Barroso &
Santa-Clara). Compare Sharpe **net** et drawdown max, brut vs *risk-managed*.

Usage::

    python scripts/run_vol_managed_momentum_alpaca.py
    python scripts/run_vol_managed_momentum_alpaca.py --target-vols 0.08 0.10 0.15
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
from financial_analyzer.backtest.vol_management import apply_vol_target, sharpe
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


def _max_drawdown(returns: pd.Series) -> float:
    eq = (1.0 + returns.fillna(0.0)).cumprod()
    return float(((eq / eq.cummax()) - 1.0).min() * 100.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--lookback", type=int, default=126, help="Fenêtre de vol (jours).")
    ap.add_argument("--target-vols", type=float, nargs="+", default=[0.08, 0.10, 0.15])
    args = ap.parse_args()

    print(f"Prix Alpaca ({len(DEFAULT_UNIVERSE)} titres) {args.start}..{args.end}…")
    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end,
                           cache_path="/tmp/alpaca_rebalance_sweep.csv")
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel: {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()

    res = evaluate_signal(factors["momentum_12_1"], returns, cost_model=cost,
                          rebalance_every=args.rebalance)
    # Rendements nets quotidiens de la stratégie L/S (depuis la courbe d'equity).
    strat = res.net_equity_curve.pct_change().dropna()

    print("=" * 74)
    print(f"MOMENTUM 12-1 RISK-MANAGED — reb={args.rebalance}, coûts calibrés, "
          f"vol {args.lookback}j")
    print("=" * 74)
    print(f"\n  {'variante':22s} {'Sharpe net':>11} {'drawdown max':>13}")
    print(f"  {'brut (non géré)':22s} {sharpe(strat):+11.2f} {_max_drawdown(strat):+12.2f}%")
    for tv in args.target_vols:
        scaled, lev = apply_vol_target(strat, target_vol=tv, lookback=args.lookback)
        print(f"  {'vol-ciblé ' + f'{tv:.0%}':22s} {sharpe(scaled):+11.2f} "
              f"{_max_drawdown(scaled):+12.2f}%   (levier moyen {lev.mean():.2f})")

    print("\nLecture : si le Sharpe monte et le drawdown se réduit, l'overlay de vol")
    print("améliore le seul edge prouvé. À câbler ensuite au sizing du pipeline (1.2).")


if __name__ == "__main__":
    main()
