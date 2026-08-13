"""Momentum piloté par le régime HMM sur données réelles (détection de régime).

Applique l'exposition régime-conditionnelle (HMM gaussien 2 états, filtre causal)
aux rendements nets de ``momentum_12_1`` et compare Sharpe net / max drawdown :
brut vs régime-HMM vs (référence) filtre de tendance MA200 déjà en place. Question
honnête : réduire l'exposition dans les régimes turbulents paie-t-il ?

⚠️ Causal : l'exposition à t (régime ≤ t) est appliquée au rendement t+1 (shift 1).

Usage::

    python scripts/run_regime_momentum_alpaca.py
    python scripts/run_regime_momentum_alpaca.py --risk-off 0.3 0.5 --rebalance 10
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
from financial_analyzer.backtest.regime import regime_risk_series
from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
from financial_analyzer.backtest.vol_management import sharpe, trend_scalar
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


def _maxdd(r: pd.Series) -> float:
    eq = (1.0 + r.fillna(0.0)).cumprod()
    return float(((eq / eq.cummax()) - 1.0).min() * 100.0)


def _apply(strat: pd.Series, exposure: pd.Series) -> pd.Series:
    e = exposure.reindex(strat.index).shift(1).fillna(1.0)  # causal
    return strat * e


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--risk-off", type=float, nargs="+", default=[0.3, 0.5])
    ap.add_argument("--warmup", type=int, default=252)
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)
    res = evaluate_signal(factors["momentum_12_1"], returns,
                          cost_model=CostModel.alpaca_equities(),
                          rebalance_every=args.rebalance)
    strat = res.net_equity_curve.pct_change().dropna()

    print("=" * 74)
    print(f"MOMENTUM 12-1 RÉGIME-HMM — reb={args.rebalance}, coûts calibrés")
    print("=" * 74)
    print(f"\n  {'variante':26s} {'Sharpe net':>11} {'drawdown max':>13} {'expo. moy.':>11}")
    print(f"  {'brut (non géré)':26s} {sharpe(strat):>+11.2f} {_maxdd(strat):>+12.2f}% "
          f"{1.0:>11.2f}")

    for rof in args.risk_off:
        print("  … estimation HMM (peut prendre ~1 min)…", end="\r")
        expo = regime_risk_series(prices, warmup=args.warmup, risk_off_factor=rof)
        scaled = _apply(strat, expo)
        print(f"  {'régime-HMM rof=' + f'{rof:.1f}':26s} {sharpe(scaled):>+11.2f} "
              f"{_maxdd(scaled):>+12.2f}% {expo.reindex(strat.index).mean():>11.2f}")

    # Référence : filtre de tendance MA200 déjà en place (trend_scalar), série causale.
    close = prices
    trend = pd.Series(
        {close.index[i]: trend_scalar(close.iloc[: i + 1], ma_window=200, risk_off_factor=0.5)
         for i in range(len(close))})
    scaled_t = _apply(strat, trend)
    print(f"  {'réf. tendance MA200':26s} {sharpe(scaled_t):>+11.2f} "
          f"{_maxdd(scaled_t):>+12.2f}% {trend.reindex(strat.index).mean():>11.2f}")

    print("\nLecture : si le régime-HMM réduit le drawdown (Sharpe ~stable ou mieux) et")
    print("bat le filtre MA200, la détection data-driven paie ; sinon le filtre simple")
    print("suffit. Overlay causal, à brancher comme risk-off alternatif si concluant.")


if __name__ == "__main__":
    main()
