"""Cadence de rééquilibrage du book MÉTA-LABELÉ — quotidien vs espacé, sur 18 ans.

Le book planifié tourne actuellement chaque jour ouvré, mais le momentum (et le méta,
validé à horizon=10) est un signal *lent* : rééquilibrer trop souvent paie du turnover.
On teste le book méta-labelé lui-même à plusieurs cadences (reb ∈ {1,5,10,21} jours),
horizon = cadence (on labellise « le pari gagne-t-il sur la période de détention »),
coûts Alpaca calibrés, features de régime (modèle RICH). On rapporte Sharpe **net**,
turnover et nombre de noms — pour savoir à quelle cadence le book est le meilleur.

Fenêtre d'entraînement plafonnée (``--max-train``) identiquement pour toutes les
cadences → borne le coût du cas quotidien et compare à fenêtre égale.

Usage::

    python scripts/run_meta_cadence_sweep_alpaca.py --cache /tmp/yahoo_long.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

UNIVERSE = sorted({
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
    "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
    "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
    "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2008-01-01")
    ap.add_argument("--end", default="2026-08-01")
    ap.add_argument("--cadences", type=int, nargs="+", default=[1, 5, 10, 21])
    ap.add_argument("--max-train", type=int, default=6000)
    ap.add_argument("--cache", default="/tmp/yahoo_long.csv")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import (
        META_FEATURES_RICH,
        regime_features,
        walk_forward_meta,
    )
    from financial_analyzer.backtest.signal_evaluation import CostModel
    from financial_analyzer.data.alpaca_history import load_or_fetch

    px = load_or_fetch(UNIVERSE, args.start, args.end, cache_path=args.cache)
    px = px[[c for c in UNIVERSE if c in px.columns]].ffill().dropna(axis=1, how="any").dropna(how="all")
    factors = compute_classic_factors(px)
    scores = factors["momentum_12_1"]
    returns = daily_returns(px)
    rich = dict(factors)
    rich.update(regime_features(px, scores))
    cost = CostModel.alpaca_equities()
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres | fenêtre train ≤ {args.max_train}\n")

    print("=" * 78)
    print("CADENCE DU BOOK MÉTA-LABELÉ (RICH) — Sharpe NET par cadence, coûts inclus")
    print("=" * 78)
    print(f"\n  {'reb (jours)':>12} {'Sharpe net':>11} {'turnover':>9} {'noms moy.':>10} {'AUC':>6}")
    rows = []
    for reb in args.cadences:
        r = walk_forward_meta(
            scores, returns, rich, rebalance_every=reb, horizon=reb,
            cost_rate=cost.cost_rate, feature_names=META_FEATURES_RICH,
            max_train=args.max_train)
        rows.append((reb, r))
        print(f"  {reb:>12} {r.meta_filter_net_sharpe:>+11.2f} {r.meta_filter_turnover:>9.3f} "
              f"{r.meta_filter_avg_names:>10.0f} {r.oos_auc:>6.3f}", flush=True)

    best_reb, best = max(rows, key=lambda kv: kv[1].meta_filter_net_sharpe)
    daily = dict(rows).get(1)
    print("\n" + "-" * 78)
    print(f"→ Meilleure cadence (Sharpe net) : reb={best_reb} "
          f"(Sharpe {best.meta_filter_net_sharpe:+.2f}, turnover {best.meta_filter_turnover:.3f})")
    if daily is not None and best_reb != 1:
        uplift = best.meta_filter_net_sharpe - daily.meta_filter_net_sharpe
        to_cut = 1.0 - (best.meta_filter_turnover / daily.meta_filter_turnover) if daily.meta_filter_turnover else 0.0
        print(f"  vs quotidien (reb=1) : Sharpe {daily.meta_filter_net_sharpe:+.2f} → "
              f"{best.meta_filter_net_sharpe:+.2f} ({uplift:+.2f}), turnover −{to_cut*100:.0f}%")
        if uplift > 0.03:
            print(f"  ✅ Espacer à reb={best_reb} AMÉLIORE le book — cadence à adopter.")
        elif uplift > -0.03:
            print(f"  ≈ Neutre en Sharpe mais turnover bien plus bas → espacer reste préférable (coûts, robustesse).")
        else:
            print(f"  ⚠️ Le quotidien fait mieux ici — garder reb=1.")
    print("\nNote : horizon = cadence (le label suit la période de détention). Cadence à")
    print("adopter pour le forward-test paper (RebalanceGate) selon ce résultat.")


if __name__ == "__main__":
    main()
