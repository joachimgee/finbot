"""Validation *honnête* du time-series momentum via le portail (Tier 2).

Fait passer le signal d'ensemble de trend-following (1/3/12 mois, vol-normalisé)
par EXACTEMENT le même portail que les autres facteurs : walk-forward OOS, coûts
Alpaca calibrés, double critère (IC t > 2 ET Sharpe net > 0), plus le Deflated
Sharpe Ratio (Tier 3). Puis mesure sa **corrélation** aux rendements OOS de
``momentum_12_1`` — car sa seule raison d'être est la *breadth* (un pari
décorrélé). Un signal qui ne passe pas le portail n'est PAS inscrit.

Usage::

    python scripts/run_tsmom_validation_alpaca.py
    python scripts/run_tsmom_validation_alpaca.py --rebalance 10 --splits 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.backtest.timeseries_momentum import tsmom_ensemble_score
from financial_analyzer.backtest.validation_gate import evaluate_signal_gate
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


def _oos_net_returns(scores, returns, cost, reb, splits):
    out = walk_forward_evaluate(scores, returns, n_splits=splits, cost_model=cost,
                               rebalance_every=reb)
    oos = out["oos"]
    if oos is None or oos.net_equity_curve.empty:
        return None
    return oos.net_equity_curve.pct_change().dropna()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    if prices.empty:
        print("Aucune donnée (clés Alpaca présentes ?).")
        return
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel prix réel: {prices.shape[0]} jours × {prices.shape[1]} tickers\n")

    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()
    tsmom = tsmom_ensemble_score(prices)

    print("=" * 74)
    print("TIME-SERIES MOMENTUM (ensemble 1/3/12 m, vol-normalisé) — portail")
    print("=" * 74)
    verdict = evaluate_signal_gate(
        "tsmom_ensemble", tsmom, returns, cost_model=cost,
        rebalance_every=args.rebalance, n_splits=args.splits,
        # 32 essais du sweep + celui-ci : on compte honnêtement les tentatives.
        n_trials=33, trial_sharpe_std=0.0442,
    )
    print("\n  " + verdict.summary())

    # --- Breadth : corrélation aux rendements OOS de momentum_12_1 ---
    factors = compute_classic_factors(prices)
    mom = _oos_net_returns(factors["momentum_12_1"], returns, cost, args.rebalance, args.splits)
    ts = _oos_net_returns(tsmom, returns, cost, args.rebalance, args.splits)
    if mom is not None and ts is not None:
        aligned = np.corrcoef(*_align(mom, ts))
        corr = float(aligned[0, 1])
        print(f"\n  Corrélation OOS avec momentum_12_1 : {corr:+.2f}")
        print(f"  {'-> pari relativement indépendant (breadth utile)' if abs(corr) < 0.6 else '-> fortement corrélé (peu de breadth ajoutée)'}")

    print("\n--- Décision d'inscription ---")
    if verdict.passed:
        print("  ✅ Passe le portail. À inscrire dans VALIDATED_SIGNALS (avec preuve),")
        print("     et à combiner par risk-weighting avec momentum_12_1.")
    else:
        print("  ❌ Ne passe PAS le portail -> NON inscrit (discipline : rien n'entre")
        print("     dans la décision sans preuve OOS chiffrée). Raisons ci-dessus.")


def _align(a, b):
    idx = a.index.intersection(b.index)
    return a.loc[idx].to_numpy(), b.loc[idx].to_numpy()


if __name__ == "__main__":
    main()
