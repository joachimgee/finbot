"""Momentum résiduel PCA vs marché-seul vs brut — via le portail (données réelles).

Ferme la boucle du momentum résiduel : le résiduel *vs marché seul* restait +0.85
corrélé au momentum brut (orthogonalisation mono-facteur insuffisante). On teste la
version **multi-facteurs par PCA** (retire les k premières composantes = marché +
secteur/style implicites, sans labels) et on mesure la **corrélation au momentum
brut** — le vrai test de breadth — plus le portail (IC t, Sharpe net, DSR).

⚠️ Univers Alpaca = titres encore cotés (biais de survie assumé).

Usage::

    python scripts/run_pca_residual_momentum_alpaca.py
    python scripts/run_pca_residual_momentum_alpaca.py --components 1 3 5 --rebalance 10
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
from financial_analyzer.backtest.residual_momentum import (
    pca_residual_momentum_score,
    residual_momentum_score,
)
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
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


def _oos_net(scores, returns, cost, reb, splits):
    out = walk_forward_evaluate(scores, returns, n_splits=splits, cost_model=cost,
                               rebalance_every=reb)
    oos = out["oos"]
    if oos is None or oos.net_equity_curve.empty:
        return None
    return oos.net_equity_curve.pct_change().dropna()


def _corr(a, b) -> float:
    idx = a.index.intersection(b.index)
    return float(np.corrcoef(a.loc[idx], b.loc[idx])[0, 1]) if len(idx) > 10 else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--components", type=int, nargs="+", default=[1, 3, 5])
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()
    mom = compute_classic_factors(prices)["momentum_12_1"]
    mom_oos = _oos_net(mom, returns, cost, args.rebalance, args.splits)

    variants = {"marché-seul": residual_momentum_score(prices)}
    for k in args.components:
        variants[f"PCA k={k}"] = pca_residual_momentum_score(prices, n_components=k)

    print("=" * 82)
    print("MOMENTUM RÉSIDUEL — corrélation au momentum BRUT (bas = décorrélé = breadth)")
    print("=" * 82)
    print(f"\n  {'variante':14s} {'IC t':>7} {'Sharpe net':>11} {'DSR':>6} {'corr↔brut':>11}")
    # Référence : le momentum brut lui-même.
    vb = evaluate_signal_gate("momentum_12_1", mom, returns, cost_model=cost,
                              rebalance_every=args.rebalance, n_splits=args.splits,
                              n_trials=33, trial_sharpe_std=0.045)
    print(f"  {'brut (réf)':14s} {vb.ic_t_stat:>7.2f} {vb.net_sharpe:>+11.2f} "
          f"{vb.dsr:>6.2f} {'—':>11}")
    for name, panel in variants.items():
        v = evaluate_signal_gate(name, panel, returns, cost_model=cost,
                                 rebalance_every=args.rebalance, n_splits=args.splits,
                                 n_trials=33, trial_sharpe_std=0.045)
        oos = _oos_net(panel, returns, cost, args.rebalance, args.splits)
        corr = _corr(oos, mom_oos) if (oos is not None and mom_oos is not None) else float("nan")
        flag = "✅" if v.passed else "❌"
        print(f"  {name:14s} {v.ic_t_stat:>7.2f} {v.net_sharpe:>+11.2f} "
              f"{v.dsr:>6.2f} {corr:>+11.2f} {flag}")

    print("\nLecture : si la corrélation au brut CHUTE (vs +0.85 du marché-seul) tout en")
    print("gardant un edge, la PCA fournit un pari décorrélé -> vraie breadth, à combiner")
    print("par risk-weighting. Sinon, l'edge du momentum est irréductiblement commun.")


if __name__ == "__main__":
    main()
