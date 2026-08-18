"""Sensibilité de la FENÊTRE d'Amihud, passée au **portail de validation**.

La fenêtre de 60 jours du book Amihud n'a jamais été justifiée : elle a été posée, pas
choisie. Amihud (2002) calcule la mesure sur un **an** ; les pipelines publics
(p.ex. *Stock_master*) la calculent à **1 et 3 mois**. 60 j est entre les deux, sans
argument. Ce script teste la sensibilité — mais par le portail, pas par un sweep.

**La différence est essentielle.** Un sweep répond « quelle fenêtre est la meilleure ? »,
question qui fabrique du sur-apprentissage : sur 5 essais, la meilleure gagne toujours un
peu, par construction. Le portail répond à la seule question honnête : **chaque fenêtre
tient-elle debout toute seule**, une fois les essais comptés ? D'où trois règles :

1. **Fenêtres PRÉ-ENREGISTRÉES** : 21, 42, 60, 90, 126 j (mois, 2 mois, valeur en place,
   trimestre, semestre). Aucune fenêtre ajoutée après avoir vu les résultats.
2. **Essais comptés cumulativement** : la campagne en comptait 32 ; ce script en ajoute 4
   (60 j était déjà compté) → **N = 36** dans le DSR de *chaque* fenêtre. Tester la
   sensibilité d'un paramètre n'est pas gratuit : cela dégonfle tout le reste.
3. **PBO / CSCV sur la matrice des fenêtres** : si l'on *choisissait* la meilleure,
   quelle probabilité de finir sous la médiane hors échantillon ?

Critère de succès **déclaré à l'avance** : le résultat souhaitable n'est pas « 60 j gagne »
— c'est que **toutes** (ou presque) les fenêtres passent. Un signal qui ne survit qu'à une
fenêtre est un artefact de réglage ; un signal robuste tolère la variation du paramètre.

Lecture seule, aucun ordre. Sortie : verdict du portail par fenêtre + décision.

Usage::

    python scripts/run_amihud_window_gate.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

#: Fenêtres pré-enregistrées (jours ouvrés). NE PAS étendre après lecture des résultats.
WINDOWS = (21, 42, 60, 90, 126)
#: Fenêtre en production.
LIVE_WINDOW = 60
#: Essais de la campagne AVANT ce script (cf. IMPROVEMENT_RESEARCH.md).
PRIOR_TRIALS = 32
#: Coûts small-cap retenus pour toute la campagne Amihud.
COST_BPS = 60.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ohlcv-cache", default="/tmp/smallcap_ohlcv_18y.pkl")
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--out", default="/tmp/amihud_window_gate.csv")
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import daily_returns
    from financial_analyzer.backtest.robustness import probability_of_backtest_overfitting
    from financial_analyzer.backtest.signal_evaluation import (
        CostModel,
        cross_sectional_weights,
    )
    from financial_analyzer.backtest.validation_gate import evaluate_signal_gate

    ohlcv = pd.read_pickle(args.ohlcv_cache)
    close = pd.DataFrame({s: d["close"] for s, d in ohlcv.items()}).sort_index()
    vol = pd.DataFrame({s: d["volume"] for s, d in ohlcv.items()}).sort_index()
    close = close.ffill().dropna(axis=1, thresh=int(0.6 * len(close))).dropna(how="all")
    vol = vol.reindex(columns=close.columns, index=close.index)
    rets = daily_returns(close)
    dollar_vol = (close * vol).replace(0, np.nan)
    illiq = rets.abs() / dollar_vol  # brut, avant lissage : la fenêtre est LE paramètre

    n_trials = PRIOR_TRIALS + len([w for w in WINDOWS if w != LIVE_WINDOW])
    cost = CostModel(commission_bps=COST_BPS, slippage_bps=0.0)

    print("=" * 94)
    print(f"SENSIBILITÉ DE LA FENÊTRE AMIHUD — PORTAIL | {close.shape[1]} titres × "
          f"{close.shape[0]} j ({close.index.min():%Y-%m} → {close.index.max():%Y-%m})")
    print(f"Fenêtres pré-enregistrées {WINDOWS} | coûts {COST_BPS:.0f} bps | "
          f"reb {args.reb} j | essais comptés N={n_trials}")
    print("=" * 94)

    # --- 1er passage : séries de rendements par fenêtre (pour PBO + dispersion) ---
    panels, series = {}, {}
    for w in WINDOWS:
        panel = illiq.rolling(w).mean() * 1e9
        panels[w] = panel
        cur = prev = pd.Series(dtype=float)
        fwd, out = rets.shift(-1), {}
        reb_set = {panel.index[i] for i in range(0, len(panel.index), args.reb)}
        for dt in panel.index:
            to = 0.0
            row = panel.loc[dt].dropna()
            if dt in reb_set and len(row) >= 10:
                ww = cross_sectional_weights(row, quantile=args.quantile, long_short=True)
                ww = ww[ww.abs() > 1e-12]
                idx = ww.index.union(prev.index)
                to = float((ww.reindex(idx).fillna(0.0)
                            - prev.reindex(idx).fillna(0.0)).abs().sum())
                cur = prev = ww
            if dt in fwd.index and len(cur):
                f = fwd.loc[dt]
                out[dt] = float((cur.reindex(f.index).fillna(0.0)
                                 * f.fillna(0.0)).sum()) - to * cost.cost_rate
        series[w] = pd.Series(out).dropna()

    perf = pd.DataFrame({f"w{w}": s for w, s in series.items()}).dropna(how="any")
    pbo, diag = probability_of_backtest_overfitting(perf, n_splits=10)
    # Dispersion des Sharpes PAR PÉRIODE à travers les essais — l'entrée honnête du DSR.
    trial_std = float(pd.Series(
        {w: (s.mean() / s.std(ddof=1)) for w, s in series.items() if s.std(ddof=1) > 0}
    ).std(ddof=1))
    print(f"\nPBO du choix de fenêtre = {pbo:.1%} "
          f"({int(diag.get('n_combinations', 0))} combinaisons) | "
          f"dispersion des Sharpes/période = {trial_std:.5f}\n")

    # --- 2e passage : le PORTAIL, walk-forward OOS, sur chaque fenêtre ---
    print(f"  {'fenêtre':>9} {'IC t':>7} {'Sharpe net':>11} {'DSR':>7} {'PBO':>7} "
          f"{'turn.':>7} {'pér.':>6}  verdict")
    rows = []
    for w in WINDOWS:
        v = evaluate_signal_gate(
            f"amihud_w{w}", panels[w], rets, cost_model=cost,
            rebalance_every=args.reb, n_splits=args.n_splits, quantile=args.quantile,
            long_short=True, n_trials=n_trials, trial_sharpe_std=trial_std, pbo=pbo,
        )
        tag = "  ← LIVE" if w == LIVE_WINDOW else ""
        print(f"  {w:>7} j {v.ic_t_stat:>+7.2f} {v.net_sharpe:>+11.2f} "
              f"{(v.dsr if v.dsr is not None else float('nan')):>7.3f} {pbo:>7.2f} "
              f"{v.avg_turnover:>7.2f} {v.n_periods:>6} "
              f" {'✅ VALIDÉ' if v.passed else '❌ REJETÉ'}{tag}")
        for r in v.reasons:
            print(f"              ↳ {r}")
        rows.append({"window": w, "ic_t_stat": v.ic_t_stat, "net_sharpe": v.net_sharpe,
                     "dsr": v.dsr, "pbo": pbo, "turnover": v.avg_turnover,
                     "n_periods": v.n_periods, "passed": v.passed,
                     "full_sample_sharpe": float(
                         series[w].mean() / series[w].std(ddof=1) * np.sqrt(252))})

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)

    # --- Décision, selon le critère déclaré AVANT le test ---
    n_pass = int(df["passed"].sum())
    live = df[df["window"] == LIVE_WINDOW].iloc[0]
    print("\n" + "=" * 94)
    print(f"{n_pass}/{len(WINDOWS)} fenêtres passent le portail complet "
          f"(IC t>2, Sharpe net>0, DSR≥0.95, PBO≤0.50)")
    print("=" * 94)
    if n_pass == len(WINDOWS):
        print("  → ROBUSTE au paramètre : le signal ne dépend pas du réglage de la fenêtre.")
        print("    Le choix de 60 j n'a donc pas besoin d'être défendu — n'importe laquelle")
        print("    des fenêtres pré-enregistrées aurait fait l'affaire. On NE CHANGE PAS")
        print("    la production : changer pour la meilleure du tableau serait exactement")
        print("    le sur-apprentissage que la PBO mesure.")
    elif live["passed"] and n_pass >= 3:
        print(f"  → La fenêtre live ({LIVE_WINDOW} j) tient, et la majorité des fenêtres")
        print("    tiennent : robustesse partielle. On garde 60 j (déjà en place, déjà")
        print("    forward-testée) plutôt que de rouvrir un choix sans gain démontré.")
    elif not live["passed"]:
        print(f"  🔴 La fenêtre EN PRODUCTION ({LIVE_WINDOW} j) ÉCHOUE au portail.")
        print("    À traiter comme le bug de la bande : la production ne doit pas tourner")
        print("    sur une configuration que le portail rejette.")
    else:
        print(f"  ⚠️ Seules {n_pass} fenêtres passent : le signal dépend du réglage.")
        print("    Faisceau d'indice d'un artefact de paramètre — à peser contre le reste")
        print("    du dossier (6 régimes, robustesse coûts, correction microstructure).")
    print(f"\n  → {args.out}")
    print("\n⚠️ Le DSR ci-dessus intègre les 36 essais cumulés de la campagne, pas seulement")
    print("   les 5 fenêtres : c'est ce qui rend le verdict comparable aux précédents.")
    return 0 if (n_pass == len(WINDOWS) or bool(live["passed"])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
