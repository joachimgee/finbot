"""Passe de CONFIRMATION du méta-labeling — l'edge est-il réel ou un artefact ?

Le méta-filtre a montré un Sharpe net bien supérieur au raw sur 18 ans (AUC 0.563).
Avant toute inscription, on isole la **compétence** du méta-modèle des **artefacts**
(concentration/turnover, chance de sous-période) par trois contrôles :

1. **Filtre aléatoire** (le test clé) : filtrer les paris du primaire vers le *même
   nombre de noms* que le méta, mais au **hasard**, N fois. Si le méta ne bat pas
   nettement cette distribution nulle, son edge = concentration, pas compétence.
2. **Permutation de l'AUC** : labels OOS mélangés → p-value du pouvoir discriminant.
3. **Stabilité par sous-période** (tiers).

Usage::

    python scripts/confirm_meta_labeling_alpaca.py --cache /tmp/yahoo_long.csv \
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
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--n-random", type=int, default=100)
    ap.add_argument("--n-perm", type=int, default=1000)
    ap.add_argument("--cache", default="/tmp/yahoo_long.csv")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import META_FEATURES, confirm_meta_labeling
    from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
    from financial_analyzer.data.alpaca_history import load_or_fetch

    px = load_or_fetch(UNIVERSE, args.start, args.end, cache_path=args.cache)
    px = px[[c for c in UNIVERSE if c in px.columns]].ffill().dropna(axis=1, how="any").dropna(how="all")
    factors = compute_classic_factors(px)
    scores = factors["momentum_12_1"]
    returns = daily_returns(px)
    cost = CostModel.alpaca_equities()
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres\n")

    # --- Réconciliation du baseline : raw méta-construction vs portail evaluate_signal ---
    portal = evaluate_signal(scores, returns, cost_model=cost, rebalance_every=args.rebalance)

    print("Confirmation en cours (entraînement logistique par rééq. + 100 filtres aléatoires)…")
    c = confirm_meta_labeling(
        scores, returns, factors, rebalance_every=args.rebalance, horizon=args.rebalance,
        p_threshold=args.threshold, cost_rate=cost.cost_rate, feature_names=META_FEATURES,
        n_random=args.n_random, n_perm=args.n_perm)

    print("\n" + "=" * 80)
    print("CONFIRMATION MÉTA-LABELING — compétence réelle ou artefact ?")
    print("=" * 80)

    print("\n[0] Réconciliation du baseline")
    print(f"    raw (construction méta)   Sharpe net = {c.raw_sharpe:+.2f}")
    print(f"    raw (portail evaluate_signal) Sharpe net = {portal.net_sharpe:+.2f}  "
          f"(IC t {portal.ic_t_stat:+.2f})")
    print(f"    → écart = construction (holding/quantile) ; on compare méta vs raw À MÉTHODE ÉGALE.")

    print("\n[1] CONTRÔLE FILTRE ALÉATOIRE (même nombre de noms, tirés au hasard)")
    print(f"    méta          Sharpe net = {c.meta_sharpe:+.2f}  (garde ~{c.avg_kept:.0f} noms)")
    print(f"    aléatoire     moyenne    = {c.rand_sharpe_mean:+.2f}  |  p95 = {c.rand_sharpe_p95:+.2f}  "
          f"({c.n_random} tirages)")
    print(f"    → le méta bat {c.meta_percentile_vs_random:.0f}% des filtres aléatoires.")

    print("\n[2] PERMUTATION DE L'AUC (pouvoir discriminant réel)")
    print(f"    AUC OOS = {c.auc:.3f} sur {c.n_oos_preds} prédictions  |  "
          f"p-value permutation = {c.auc_perm_pvalue:.3f}")

    print("\n[3] STABILITÉ PAR SOUS-PÉRIODE (tiers)")
    print(f"    méta : {[round(x, 2) for x in c.subperiod_meta_sharpes]}")
    print(f"    raw  : {[round(x, 2) for x in c.subperiod_raw_sharpes]}")

    # --- Verdict ---
    print("\n" + "-" * 80)
    beats_random = c.meta_percentile_vs_random >= 95.0
    auc_real = c.auc_perm_pvalue <= 0.05
    stable = sum(1 for x in c.subperiod_meta_sharpes if x > 0) >= 2
    checks = sum([beats_random, auc_real, stable])
    print(f"Contrôles réussis : {checks}/3  "
          f"(bat l'aléatoire ≥95%: {beats_random} ; AUC significative: {auc_real} ; "
          f"stable ≥2/3 tiers: {stable})")
    if checks == 3:
        print("→ L'edge du méta-filtre RÉSISTE aux trois contrôles : compétence plausible, "
              "candidat sérieux. Prochaine étape : DSR formel avec essais comptés + test paper.")
    elif beats_random is False:
        print("→ Le méta NE bat PAS l'aléatoire : son Sharpe vient de la CONCENTRATION "
              "(garder peu de noms), pas d'une compétence du modèle. PISTE INFIRMÉE.")
    else:
        print("→ Résultat MITIGÉ : une partie des contrôles échoue. Pas d'inscription ; "
              "l'edge n'est pas robuste tel quel.")


if __name__ == "__main__":
    main()
