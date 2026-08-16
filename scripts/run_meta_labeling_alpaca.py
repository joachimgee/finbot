"""Meta-labeling sur momentum_12_1 réel (Alpaca) — le méta-modèle aide-t-il ?

Signal primaire = momentum 12-1 (direction). Modèle secondaire (logistique) =
filtre/sizing des paris via P(gain), walk-forward avec purge+embargo, features
motivées ex-ante, coûts Alpaca calibrés. Compare raw vs méta-filtre vs méta-sizing.

Discipline : le méta-labeling ajoute des essais (features/seuil) → à compter au DSR
avant toute inscription. Ce script *mesure* ; l'inscription resterait soumise au
portail complet (IC t > 2 ET Sharpe net > 0, DSR).

Usage::

    python scripts/run_meta_labeling_alpaca.py
    python scripts/run_meta_labeling_alpaca.py --threshold 0.55 --embargo 10
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
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10, help="Cadence (jours) — défaut validé 10.")
    ap.add_argument("--threshold", type=float, default=0.5, help="Seuil P(gain) du filtre.")
    ap.add_argument("--embargo", type=int, default=10)
    ap.add_argument("--min-train", type=int, default=400)
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import META_FEATURES, walk_forward_meta
    from financial_analyzer.backtest.signal_evaluation import CostModel
    from financial_analyzer.data.alpaca_history import load_or_fetch

    px = load_or_fetch(UNIVERSE, args.start, args.end, cache_path=args.cache)
    px = px[[c for c in UNIVERSE if c in px.columns]].ffill().dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres\n")

    factors = compute_classic_factors(px)
    scores = factors["momentum_12_1"]
    returns = daily_returns(px)
    cost_rate = CostModel.alpaca_equities().cost_rate

    res = walk_forward_meta(
        scores, returns, factors, rebalance_every=args.rebalance, horizon=args.rebalance,
        embargo=args.embargo, min_train=args.min_train, p_threshold=args.threshold,
        cost_rate=cost_rate, feature_names=META_FEATURES)

    print("=" * 78)
    print("META-LABELING — momentum_12_1 (primaire) + logistique secondaire (filtre/sizing)")
    print("=" * 78)
    print(f"\nFeatures méta : {list(META_FEATURES)}")
    print(f"Échantillons : {res.n_samples} | taux de gain de base : {res.base_win_rate:.1%} | "
          f"AUC OOS du méta-modèle : {res.oos_auc:.3f}")
    print(f"\n  {'stratégie':16} {'Sharpe net':>11} {'turnover':>9} {'noms moy.':>10}")
    print(f"  {'raw (primaire)':16} {res.raw_net_sharpe:>+11.2f} {res.raw_turnover:>9.2f} {res.raw_avg_names:>10.0f}")
    print(f"  {'méta-filtre':16} {res.meta_filter_net_sharpe:>+11.2f} {res.meta_filter_turnover:>9.2f} {res.meta_filter_avg_names:>10.0f}")
    print(f"  {'méta-sizing':16} {res.meta_size_net_sharpe:>+11.2f} {res.meta_size_turnover:>9.2f} {'—':>10}")

    print("\n" + "-" * 78)
    best = max([("raw", res.raw_net_sharpe), ("méta-filtre", res.meta_filter_net_sharpe),
                ("méta-sizing", res.meta_size_net_sharpe)], key=lambda kv: kv[1])
    uplift = best[1] - res.raw_net_sharpe
    if best[0] == "raw" or uplift < 0.05:
        print(f"→ Le méta-labeling n'améliore PAS matériellement (meilleur : {best[0]} "
              f"{best[1]:+.2f} vs raw {res.raw_net_sharpe:+.2f}).")
    else:
        print(f"→ {best[0]} devance raw de {uplift:+.2f} de Sharpe net — candidat, "
              f"À CONFIRMER via le portail (IC t, DSR avec essais comptés).")
    if abs(res.oos_auc - 0.5) < 0.03:
        print("  AUC OOS ≈ 0.5 : le méta-modèle ne discrimine quasi pas les gagnants "
              "(cohérent avec le plafond de données) — pas d'edge secondaire fiable.")
    print("\nRappel : le méta-modèle ne change PAS la direction (paris du primaire), il ne")
    print("peut que filtrer/redimensionner. Verdict soumis au portail ; ce run mesure.")


if __name__ == "__main__":
    main()
