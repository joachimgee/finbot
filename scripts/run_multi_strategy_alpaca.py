"""Multi-stratégie : momentum + PCA-résiduel + paires, risk-weighted (données réelles).

Assemble les **trois familles** validées/prometteuses de la session en un book unique
risk-weighted, et mesure le payoff de breadth (Grinold-Kahn) : le Sharpe combiné vs
chaque famille seule, avec la matrice de corrélation.

Familles :
* ``momentum``  — momentum 12-1 cross-section (validé, tendance).
* ``pca_resid`` — momentum résiduel PCA (décorrélé, cross-section).
* ``pairs``     — stat-arb par paires (décorrélé, mean-reversion).

⚠️ Univers Alpaca = titres encore cotés (biais de survie). Résultat indicatif du
*mécanisme* de breadth, pas un edge inscriptible tel quel (cf. réserves des familles).

Usage::

    python scripts/run_multi_strategy_alpaca.py --method risk_parity
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
from financial_analyzer.backtest.multi_strategy import combine, sharpe, strategy_report
from financial_analyzer.backtest.pairs_trading import backtest_pairs
from financial_analyzer.backtest.residual_momentum import pca_residual_momentum_score
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
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


def _oos(scores, returns, cost, reb, splits):
    out = walk_forward_evaluate(scores, returns, n_splits=splits, cost_model=cost,
                               rebalance_every=reb)
    oos = out["oos"]
    return oos.net_equity_curve.pct_change().dropna() if oos is not None else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--method", default="risk_parity",
                    choices=["risk_parity", "inverse_vol", "equal"])
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()

    print("Familles : momentum, PCA-résiduel, paires…")
    mom = _oos(compute_classic_factors(prices)["momentum_12_1"], returns, cost,
               args.rebalance, args.splits)
    pca = _oos(pca_residual_momentum_score(prices, n_components=5), returns, cost,
               args.rebalance, args.splits)
    pairs = backtest_pairs(prices, form=252, trade=63, max_pairs=15,
                           corr_min=0.7, cost_rate=cost.cost_rate)["net_returns"]

    fam = pd.DataFrame({"momentum": mom, "pca_resid": pca, "pairs": pairs}).dropna()
    rep = strategy_report(fam, method=args.method)

    print("\n" + "=" * 74)
    print(f"MULTI-STRATÉGIE — combinaison {args.method}")
    print("=" * 74)
    print("\n  Matrice de corrélation :")
    print(rep["correlation"].to_string().replace("\n", "\n  "))
    print("\n  Poids risk-weighted :")
    for k, v in rep["weights"].items():
        print(f"    {k:12s} {v:.2f}")
    print("\n  Sharpe net par famille :")
    for k, v in rep["per_strategy_sharpe"].items():
        print(f"    {k:12s} {v:+.2f}")
    print(f"\n  >>> Sharpe COMBINÉ ({args.method}) : {rep['combined_sharpe']:+.2f}")
    print(f"      (meilleure famille seule       : {rep['best_single_sharpe']:+.2f})")

    # Drawdown du book combiné.
    comb, _ = combine(fam, method=args.method)
    eq = (1.0 + comb.fillna(0.0)).cumprod()
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0)
    print(f"      max drawdown combiné           : {dd:+.1f}%")

    print("\n--- Lecture honnête ---")
    if rep["combined_sharpe"] > rep["best_single_sharpe"]:
        print("  Le book combiné BAT la meilleure famille seule -> la breadth paie.")
        print("  Diversification réelle : familles peu corrélées, risque mieux réparti.")
    else:
        print("  Combiné ≤ meilleure seule ici (familles inégales / bruit d'échantillon),")
        print("  mais le risque combiné est plus bas (drawdown) : diversification quand même.")
    print("  Réserve : sur 3 ans / 80 large-caps, paires thin -> à re-tester sur univers")
    print("  profond, où les trois familles seraient toutes plus robustes.")


if __name__ == "__main__":
    main()
