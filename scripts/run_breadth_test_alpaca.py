"""Test de *breadth* : re-passer le portail sur un univers LARGE (Tier 2 bis).

Le portail a montré que le plafond de FinBot est la breadth (Grinold-Kahn :
IR ≈ IC·√Breadth). On teste l'hypothèse *empiriquement* : passer de ~80 large-caps
à ~500 titres liquides et re-mesurer les mêmes signaux, au même portail.

Question centrale : **plus de paris indépendants améliore-t-il le seul edge prouvé
(momentum_12_1) et fait-il émerger d'autres facteurs ?** On rapporte :
- IC t / Sharpe net / **DSR** de chaque facteur classique à breadth élevée,
- le DSR de momentum_12_1 (à comparer au 0.13 du baseline 80 titres),
- la corrélation OOS TSMOM↔momentum (breadth ajoutée ?).

⚠️ Biais de survie assumé (Alpaca = titres encore cotés). Mesure l'effet breadth,
pas un rendement absolu non biaisé.

Usage::

    python scripts/run_breadth_test_alpaca.py
    python scripts/run_breadth_test_alpaca.py --n 500 --rebalance 10 --splits 5
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
from financial_analyzer.backtest.robustness import sharpe_per_period
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.backtest.timeseries_momentum import tsmom_ensemble_score
from financial_analyzer.backtest.validation_gate import evaluate_signal_gate
from financial_analyzer.data.alpaca_universe_liquid import (
    load_prices_for_universe,
    top_liquid_us_equities,
)

REBALANCE_PERIODS = (1, 5, 10, 21)


def _oos(scores, returns, cost, reb, splits):
    out = walk_forward_evaluate(scores, returns, n_splits=splits, cost_model=cost,
                               rebalance_every=reb)
    return out["oos"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=500, help="Taille cible de l'univers.")
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--rank-cache", default="/tmp/alpaca_liquid_rank.json")
    ap.add_argument("--price-cache", default="/tmp/alpaca_breadth_prices.csv")
    args = ap.parse_args()

    print(f"Construction univers liquide (top {args.n}, fonds exclus)…")
    universe = top_liquid_us_equities(n=args.n, cache_path=args.rank_cache)
    print(f"  {len(universe)} tickers. Chargement des prix {args.start}..{args.end}…")
    prices = load_prices_for_universe(universe, args.start, args.end,
                                      cache_path=args.price_cache)
    if prices.empty:
        print("Aucune donnée.")
        return
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"  Panel exploitable : {prices.shape[0]} jours × {prices.shape[1]} titres "
          f"(vs 80 au baseline)\n")

    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()
    factors = compute_classic_factors(prices)

    # --- Dispersion des essais (facteur × cadence) pour le DSR, sur CET univers ---
    trial_sharpes: list[float] = []
    for panel in factors.values():
        for reb in REBALANCE_PERIODS:
            try:
                oos = _oos(panel, returns, cost, reb, args.splits)
            except Exception:  # noqa: BLE001
                continue
            if oos is not None and not oos.net_equity_curve.empty:
                trial_sharpes.append(sharpe_per_period(oos.net_equity_curve.pct_change().dropna()))
    n_trials = max(2, len(trial_sharpes))
    sr_std = float(np.std(trial_sharpes, ddof=1)) if len(trial_sharpes) > 1 else 0.05

    print("=" * 78)
    print(f"PORTAIL À BREADTH ÉLEVÉE — {prices.shape[1]} titres, reb={args.rebalance}, "
          f"{n_trials} essais")
    print("=" * 78)
    print(f"\n  {'facteur':16s} {'IC t':>7} {'Sharpe net':>11} {'DSR':>6}  verdict")
    for name in sorted(factors):
        v = evaluate_signal_gate(
            name, factors[name], returns, cost_model=cost,
            rebalance_every=args.rebalance, n_splits=args.splits,
            n_trials=n_trials, trial_sharpe_std=sr_std,
        )
        flag = "✅" if v.passed else "❌"
        dsr = f"{v.dsr:.2f}" if v.dsr is not None else " n/a"
        print(f"  {name:16s} {v.ic_t_stat:>7.2f} {v.net_sharpe:>+11.2f} {dsr:>6}  {flag}")

    # --- Focus momentum_12_1 : DSR vs baseline 80 titres (0.13) ---
    mom = evaluate_signal_gate(
        "momentum_12_1", factors["momentum_12_1"], returns, cost_model=cost,
        rebalance_every=args.rebalance, n_splits=args.splits,
        n_trials=n_trials, trial_sharpe_std=sr_std,
    )
    print(f"\n  momentum_12_1 : IC t={mom.ic_t_stat:+.2f}, Sharpe net={mom.net_sharpe:+.2f}, "
          f"DSR={mom.dsr:.2f}")
    print("    (baseline 80 titres : IC t=+2.56, Sharpe net=+0.76, DSR=0.13)")

    # --- TSMOM : breadth ajoutée ? ---
    tsmom = tsmom_ensemble_score(prices)
    ts_oos = _oos(tsmom, returns, cost, args.rebalance, args.splits)
    mom_oos = _oos(factors["momentum_12_1"], returns, cost, args.rebalance, args.splits)
    if ts_oos is not None and mom_oos is not None:
        a = ts_oos.net_equity_curve.pct_change().dropna()
        b = mom_oos.net_equity_curve.pct_change().dropna()
        idx = a.index.intersection(b.index)
        corr = float(np.corrcoef(a.loc[idx], b.loc[idx])[0, 1])
        print(f"\n  TSMOM↔momentum corrélation OOS : {corr:+.2f} "
              f"(baseline 80 titres : +0.72)")

    print("\n--- Lecture ---")
    print("  Si le DSR de momentum monte nettement à breadth élevée, la loi de")
    print("  Grinold-Kahn est confirmée : le plafond était bien la breadth. Sinon, le")
    print("  plafond est ailleurs (edge du signal lui-même). Biais de survie assumé.")


if __name__ == "__main__":
    main()
