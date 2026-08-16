"""Méta-labeling : features enrichies (régime) + DSR campagne — la double vérif.

Deux questions, dans l'ordre (discipline anti-p-hacking) :

1. **Meilleures features** — le méta-modèle n'avait que 5 features de la famille
   momentum (AUC 0.563). On ajoute UNE batterie **pré-enregistrée** de features de
   *régime* (Daniel-Moskowitz 2016, Barroso 2015 : ce qui prédit les krachs de
   momentum est l'état du marché, pas une caractéristique du titre) : rendement
   marché 126 j, vol marché 21 j, dispersion cross-section. On compare BASE vs RICH
   par les MÊMES contrôles d'artefact (filtre aléatoire, permutation AUC, tiers).

2. **DSR campagne** — le méta a passé les contrôles *intra-méta* ; il manque la
   correction du **best-of-N** global. On déflate le Sharpe du méta (modèle RICH,
   pré-enregistré) par le **nombre d'essais** de toute la campagne (facteurs prix,
   TSMOM, résiduels, paires, sentiment, microstructure, méta base+rich ≈ 20), avec
   la dispersion σ des Sharpes/période mesurée sur le sweep 18 ans. Si le Sharpe reste
   au-dessus du repère dégonflé E[max|H0], l'edge survit ; sinon c'est du best-of-N.

Usage::

    python scripts/run_meta_features_dsr_alpaca.py --cache /tmp/yahoo_long.csv \
        --start 2008-01-01 --end 2026-08-01
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
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--n-random", type=int, default=50)
    ap.add_argument("--n-perm", type=int, default=300)
    ap.add_argument("--n-trials", type=int, default=20, help="Essais campagne pour le DSR.")
    ap.add_argument("--sr-std", type=float, default=0.0247,
                    help="Dispersion σ des Sharpes/période (mesurée sur le sweep 18 ans).")
    ap.add_argument("--cache", default="/tmp/yahoo_long.csv")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import (
        META_FEATURES,
        META_FEATURES_RICH,
        confirm_meta_labeling,
        regime_features,
    )
    from financial_analyzer.backtest.robustness import deflated_sharpe_ratio
    from financial_analyzer.backtest.signal_evaluation import CostModel
    from financial_analyzer.data.alpaca_history import load_or_fetch

    px = load_or_fetch(UNIVERSE, args.start, args.end, cache_path=args.cache)
    px = px[[c for c in UNIVERSE if c in px.columns]].ffill().dropna(axis=1, how="any").dropna(how="all")
    factors = compute_classic_factors(px)
    scores = factors["momentum_12_1"]
    returns = daily_returns(px)
    cost = CostModel.alpaca_equities()
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres\n")

    # Jeu enrichi = facteurs classiques + features de régime diffusées.
    rich = dict(factors)
    rich.update(regime_features(px, scores))

    def _run(label, feats, features_dict):
        print(f"[{label}] confirmation ({len(feats)} features)…", flush=True)
        c = confirm_meta_labeling(
            scores, returns, features_dict, rebalance_every=args.rebalance,
            horizon=args.rebalance, cost_rate=cost.cost_rate, feature_names=feats,
            n_random=args.n_random, n_perm=args.n_perm)
        print(f"    AUC={c.auc:.3f} (p={c.auc_perm_pvalue:.3f}) | méta Sh={c.meta_sharpe:+.2f} "
              f"| bat {c.meta_percentile_vs_random:.0f}% aléatoires | tiers "
              f"{[round(x,2) for x in c.subperiod_meta_sharpes]}")
        return c

    print("=" * 82)
    print("MÉTA-LABELING — features enrichies (régime) vs base")
    print("=" * 82 + "\n")
    base = _run("BASE ", META_FEATURES, factors)
    richc = _run("RICH ", META_FEATURES_RICH, rich)

    print("\n" + "-" * 82)
    better = richc.meta_sharpe > base.meta_sharpe and richc.auc > base.auc
    print(f"→ Features de régime : {'AMÉLIORENT' if better else \"n'améliorent pas clairement\"} "
          f"(AUC {base.auc:.3f}→{richc.auc:.3f}, Sharpe {base.meta_sharpe:+.2f}→{richc.meta_sharpe:+.2f}).")

    # --- DSR campagne sur le modèle RICH (pré-enregistré) ---
    print("\n" + "=" * 82)
    print("DSR CAMPAGNE — le Sharpe du méta survit-il à la correction best-of-N ?")
    print("=" * 82)
    r = richc.meta_returns
    if len(r) < 30:
        print("  Série de rendements méta trop courte pour un DSR fiable.")
        return
    for nt in sorted({args.n_trials, 30}):
        dsr, diag = deflated_sharpe_ratio(r, n_trials=nt, sr_std=args.sr_std)
        print(f"\n  Essais campagne N={nt}  (σ Sharpes/période = {args.sr_std}) :")
        print(f"    Sharpe/période observé (méta RICH) = {diag['sr_per_period']:+.4f} "
              f"(annualisé {diag['sr_per_period']*(252**0.5):+.2f})")
        print(f"    Repère dégonflé E[max|H0] sur {nt} essais = {diag['sr_benchmark']:+.4f}")
        print(f"    Asymétrie/kurtosis = {diag['skew']:+.2f} / {diag['kurtosis']:.1f} | "
              f"obs = {int(diag['n_obs'])}")
        verdict = "✅ survit" if dsr >= 0.95 else ("⚠️ limite" if dsr >= 0.5 else "❌ ne survit pas")
        print(f"    >>> DSR = {dsr:.3f}  ({verdict})")

    print("\nLecture : DSR ≥ 0.95 = le Sharpe du méta dépasse ce qu'on attendrait du "
          "meilleur de N\nessais de bruit → edge crédible même après best-of-N. En dessous, "
          "prudence :\nla magnitude n'est pas distinguable de la chance de sélection (comme "
          "momentum lui-même,\nqui tient sur son prior). Réserve inchangée : biais de survie non levé.")


if __name__ == "__main__":
    main()
