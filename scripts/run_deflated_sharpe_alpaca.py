"""Deflated Sharpe Ratio du seul signal validé, sur données Alpaca réelles (Tier 3).

Le portail a retenu ``momentum_12_1`` (reb=10) après avoir *balayé* une grille de
configurations (facteurs classiques × cadences de rééquilibrage). Chaque essai est
une chance de trouver un Sharpe positif par hasard : le **Deflated Sharpe Ratio**
(Bailey & López de Prado) corrige le Sharpe du meilleur essai de ce biais de
sélection, de la longueur d'échantillon et de la non-normalité.

Ce script reconstruit exactement la grille du sweep comme *ensemble d'essais*,
mesure la dispersion des Sharpes (par période) à travers les essais, puis calcule
le DSR de la meilleure config. Verdict honnête : le seul edge prouvé survit-il à
la correction des tests multiples ?

Usage::

    python scripts/run_deflated_sharpe_alpaca.py
    python scripts/run_deflated_sharpe_alpaca.py --splits 5
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
from financial_analyzer.backtest.robustness import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    sharpe_per_period,
)
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.data.alpaca_history import load_or_fetch

REBALANCE_PERIODS = (1, 5, 10, 21)
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
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--pbo-splits", type=int, default=10, help="Blocs CSCV (pair).")
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    if prices.empty:
        print("Aucune donnée (clés Alpaca présentes ?).")
        return
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel prix réel: {prices.shape[0]} jours × {prices.shape[1]} tickers\n")

    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()

    # Chaque (facteur × cadence) est un ESSAI. On collecte le Sharpe par période
    # (OOS, net) de chacun, la série de rendements (pour la matrice PBO), et on
    # garde les rendements de la meilleure config.
    trial_sharpes: list[float] = []
    trial_series: dict[str, pd.Series] = {}
    best = {"name": None, "reb": None, "sr_pp": -np.inf, "net_returns": None}
    for name, panel in factors.items():
        for reb in REBALANCE_PERIODS:
            try:
                out = walk_forward_evaluate(
                    panel, returns, n_splits=args.splits, cost_model=cost,
                    rebalance_every=reb,
                )
            except Exception:  # noqa: BLE001 - essai infaisable -> ignoré
                continue
            oos = out["oos"]
            if oos is None or oos.net_equity_curve.empty:
                continue
            net_r = oos.net_equity_curve.pct_change().dropna()
            sr_pp = sharpe_per_period(net_r)
            trial_sharpes.append(sr_pp)
            trial_series[f"{name}@{reb}"] = net_r
            if sr_pp > best["sr_pp"]:
                best = {"name": name, "reb": reb, "sr_pp": sr_pp, "net_returns": net_r}

    n_trials = len(trial_sharpes)
    sr_std = float(np.std(trial_sharpes, ddof=1)) if n_trials > 1 else 0.0
    print("=" * 74)
    print("DEFLATED SHARPE RATIO — seul signal validé vs biais de sélection")
    print("=" * 74)
    print(f"\n  Essais (facteur × cadence)   : {n_trials}")
    print(f"  Dispersion Sharpe/période σ  : {sr_std:.4f}")
    print(f"  Meilleur essai               : {best['name']} @ reb={best['reb']}")

    if best["net_returns"] is None:
        print("\n  Aucun essai exploitable.")
        return

    dsr, diag = deflated_sharpe_ratio(best["net_returns"], n_trials, sr_std)
    ann = diag["sr_per_period"] * np.sqrt(252)
    bench_ann = diag["sr_benchmark"] * np.sqrt(252)
    print(f"\n  Sharpe/période observé       : {diag['sr_per_period']:+.4f} "
          f"(annualisé {ann:+.2f})")
    print(f"  Repère dégonflé E[max|H0]    : {diag['sr_benchmark']:+.4f} "
          f"(annualisé {bench_ann:+.2f})")
    print(f"  Asymétrie / kurtosis         : {diag['skew']:+.2f} / {diag['kurtosis']:.2f}")
    print(f"  Observations                 : {int(diag['n_obs'])}")
    print(f"\n  >>> DSR = {dsr:.3f}  "
          f"({'✅ ≥ 0.95 : crédible' if dsr >= 0.95 else '❌ < 0.95 : NON crédible'} "
          "après correction des tests multiples)")
    print("\nLecture : le DSR est la probabilité que le vrai Sharpe dépasse le meilleur")
    print("Sharpe *attendu par pur hasard* sur autant d'essais. En dessous de 0.95, le")
    print("portail (seuil dsr_min) refuserait le signal malgré un Sharpe brut positif.")

    # --- PBO (CSCV) : le PROCESSUS de sélection sur-apprend-il ? ---
    matrix = pd.DataFrame(trial_series).dropna(how="any")
    if matrix.shape[1] >= 2 and matrix.shape[0] >= 10:
        pbo, pdiag = probability_of_backtest_overfitting(matrix, n_splits=args.pbo_splits)
        print("\n" + "=" * 74)
        print("PROBABILITY OF BACKTEST OVERFITTING (CSCV) — le tri lui-même")
        print("=" * 74)
        print(f"\n  Configs dans la matrice      : {int(pdiag['n_configs'])}")
        print(f"  Combinaisons CSCV            : {int(pdiag['n_combinations'])} "
              f"(S={args.pbo_splits})")
        print(f"  Logit médian                 : {pdiag['median_logit']:+.2f}")
        print(f"\n  >>> PBO = {pbo:.3f}  "
              f"({'✅ ≤ 0.50 : sélection robuste' if pbo <= 0.5 else '❌ > 0.50 : le tri sur-apprend'})")
        print("\nLecture : PBO = fréquence où la config *meilleure in-sample* finit sous la")
        print("médiane out-of-sample. > 0.5 => choisir le meilleur du sweep est illusoire.")


if __name__ == "__main__":
    main()
