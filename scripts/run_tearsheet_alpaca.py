"""Tearsheet enrichi du signal validé sur données réelles (Sortino/Calmar/PSR).

Le portail ne montrait que IC / Sharpe net / turnover. Ce script sort le
**tearsheet complet** (Sortino, Calmar, max drawdown, PSR) pour ``momentum_12_1``
via ``backtest/tearsheet.py`` — métriques qui existaient déjà dans ``metrics.py``
mais n'étaient jamais affichées. Applicable à n'importe quel ``SignalEvalResult``.

Usage::

    python scripts/run_tearsheet_alpaca.py
    python scripts/run_tearsheet_alpaca.py --factor momentum_6_1 --rebalance 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.backtest.tearsheet import format_tearsheet
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--factor", default="momentum_12_1")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")

    factors = compute_classic_factors(prices)
    if args.factor not in factors:
        print(f"Facteur inconnu : {args.factor}. Dispo : {sorted(factors)}")
        return
    returns = daily_returns(prices)
    out = walk_forward_evaluate(
        factors[args.factor], returns, n_splits=args.splits,
        cost_model=CostModel.alpaca_equities(), rebalance_every=args.rebalance,
    )
    oos = out["oos"]
    if oos is None:
        print("Aucune fenêtre OOS exploitable.")
        return
    print(f"Panel : {prices.shape[0]} jours × {prices.shape[1]} titres, "
          f"reb={args.rebalance}\n")
    print(format_tearsheet(oos, name=args.factor))


if __name__ == "__main__":
    main()
