"""Validation du momentum RÉSIDUEL via le portail, à breadth élevée (Tier 2 ter).

Le test de breadth a montré que le levier n'est pas le nombre de titres mais la
**décorrélation**. Le momentum résiduel (Blitz-Huij-Martens : momentum sur la part
idiosyncratique, marché retiré) est le candidat naturel. On le passe au **même
portail** (IC t > 2 ET Sharpe net > 0, + DSR) sur l'univers large, et — question
décisive — on mesure sa **corrélation** aux rendements OOS du momentum classique :
s'il est décorrélé ET rentable, c'est de la vraie breadth (à combiner par
risk-weighting).

⚠️ Univers Alpaca = titres encore cotés (biais de survie assumé).

Usage::

    python scripts/run_residual_momentum_alpaca.py
    python scripts/run_residual_momentum_alpaca.py --n 500 --rebalance 10
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
from financial_analyzer.backtest.residual_momentum import residual_momentum_score
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.backtest.validation_gate import evaluate_signal_gate
from financial_analyzer.data.alpaca_universe_liquid import (
    load_prices_for_universe,
    top_liquid_us_equities,
)


def _oos_net(scores, returns, cost, reb, splits):
    out = walk_forward_evaluate(scores, returns, n_splits=splits, cost_model=cost,
                               rebalance_every=reb)
    oos = out["oos"]
    if oos is None or oos.net_equity_curve.empty:
        return None
    return oos.net_equity_curve.pct_change().dropna()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--rank-cache", default="/tmp/alpaca_liquid_rank.json")
    ap.add_argument("--price-cache", default="/tmp/alpaca_breadth_prices.csv")
    args = ap.parse_args()

    universe = top_liquid_us_equities(n=args.n, cache_path=args.rank_cache)
    prices = load_prices_for_universe(universe, args.start, args.end,
                                      cache_path=args.price_cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel: {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()
    factors = compute_classic_factors(prices)
    resid = residual_momentum_score(prices)

    print("=" * 74)
    print("MOMENTUM RÉSIDUEL vs MOMENTUM CLASSIQUE — portail, breadth élevée")
    print("=" * 74)
    # Compte d'essais cohérent avec le sweep (facteurs × cadences) + celui-ci.
    n_trials, sr_std = 33, 0.045
    vr = evaluate_signal_gate(
        "residual_momentum", resid, returns, cost_model=cost,
        rebalance_every=args.rebalance, n_splits=args.splits,
        n_trials=n_trials, trial_sharpe_std=sr_std,
    )
    vm = evaluate_signal_gate(
        "momentum_12_1", factors["momentum_12_1"], returns, cost_model=cost,
        rebalance_every=args.rebalance, n_splits=args.splits,
        n_trials=n_trials, trial_sharpe_std=sr_std,
    )
    print("\n  " + vr.summary())
    print("  " + vm.summary())

    rr = _oos_net(resid, returns, cost, args.rebalance, args.splits)
    mr = _oos_net(factors["momentum_12_1"], returns, cost, args.rebalance, args.splits)
    corr = None
    if rr is not None and mr is not None:
        idx = rr.index.intersection(mr.index)
        corr = float(np.corrcoef(rr.loc[idx], mr.loc[idx])[0, 1])
        print(f"\n  Corrélation OOS résiduel↔classique : {corr:+.2f}")
        print("  (momentum brut TSMOM était +0.74 ; plus bas = plus de breadth)")

    print("\n--- Décision d'inscription ---")
    if vr.passed:
        print("  ✅ Le momentum résiduel passe le portail. Candidat à inscrire, et —")
        print("     s'il est peu corrélé au classique — à combiner par risk-weighting.")
    else:
        print("  ❌ Ne passe pas le portail -> NON inscrit. Raisons ci-dessus.")
        if vr.net_sharpe > 0 and corr is not None and abs(corr) < 0.5:
            print("  NB : décorrélé et net-positif mais sous les seuils — piste à creuser")
            print("       (fenêtres, β sectoriel) avant toute inscription.")


if __name__ == "__main__":
    main()
