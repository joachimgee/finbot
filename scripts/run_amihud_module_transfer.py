"""Transfert vers Amihud des modules construits (et souvent abandonnés) pour momentum.

Huit modules ont été écrits pendant la campagne momentum : ``vol_management``,
``regime`` (HMM), ``cost_aware`` (bande de non-transaction), ``meta_labeling``,
``multi_strategy``, ``robustness`` (DSR/PBO), ``tearsheet``, ``execution_algos``.
**Aucun** n'est branché sur le book Amihud aujourd'hui — sauf un, la bande de
non-transaction 0.02, qui tourne **en live sans avoir jamais été testée pour Amihud**
(elle avait été calibrée sur le book méta-momentum). C'est une dette de validation.

Ce script fait le transfert et le **teste sur 18 ans** :

1. **Bande de non-transaction** (``cost_aware``) — 0 / 0.01 / 0.02 / 0.03 / 0.05.
   Comble le trou de validation du paramètre qui tourne en production.
2. **Ciblage de volatilité** (``vol_management``) — Barroso & Santa-Clara (2015),
   *Momentum has its moments* : le levier inverse-vol sauve momentum de ses krachs.
   Amihud a-t-il aussi des « moments » à gérer ?
3. **Overlay de régime HMM** (``regime``) — réduction d'exposition en régime turbulent.
4. **Filtre de tendance 200 j** (``vol_management.trend_scalar``) — version pauvre du
   précédent, testée pour vérifier que la complexité du HMM se paie.
5. **Stop-loss** — Kaminski & Lo (2014) prédisent que les stops **détruisent** de la
   valeur sur des rendements à retour à la moyenne. Test de la prédiction, pas
   candidat au déploiement.
6. **PBO / CSCV** (``robustness``) sur la matrice complète des configurations
   ci-dessus : si l'on choisissait la meilleure, aurait-on sur-appris ?

Lecture seule, aucun ordre. Sortie : tableau + verdict par module.

Usage::

    python scripts/run_amihud_module_transfer.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

COST_BPS = 60.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ohlcv-cache", default="/tmp/smallcap_ohlcv_18y.pkl")
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--out", default="/tmp/amihud_module_transfer.csv")
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import daily_returns
    from financial_analyzer.backtest.cost_aware import apply_no_trade_band
    from financial_analyzer.backtest.illiquidity import amihud_illiquidity, prepare_panels
    from financial_analyzer.backtest.regime import regime_risk_series
    from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights
    from financial_analyzer.backtest.vol_management import apply_vol_target

    ohlcv = pd.read_pickle(args.ohlcv_cache)
    close, vol = prepare_panels(
        pd.DataFrame({s: d["close"] for s, d in ohlcv.items()}),
        pd.DataFrame({s: d["volume"] for s, d in ohlcv.items()}),
    )
    rets = daily_returns(close)
    # Définition importée, jamais recalculée (cf. backtest/illiquidity.py).
    amihud = amihud_illiquidity(close, vol, window=args.window)
    fwd = rets.shift(-1)
    cost_rate = COST_BPS / 1e4
    reb_set = {amihud.index[i] for i in range(0, len(amihud.index), args.reb)}

    print("=" * 92)
    print(f"TRANSFERT DES MODULES → AMIHUD | {close.shape[1]} titres × {close.shape[0]} j "
          f"({close.index.min():%Y-%m} → {close.index.max():%Y-%m}), coûts {COST_BPS:.0f} bps")
    print("=" * 92)

    def book(band: float = 0.0) -> tuple[pd.Series, float]:
        """Rendements nets du book Amihud L/S, avec bande de non-transaction."""
        cur = prev = pd.Series(dtype=float)
        out, turn = {}, []
        for dt in amihud.index:
            to = 0.0
            row = amihud.loc[dt].dropna()
            if dt in reb_set and len(row) >= 10:
                tgt = cross_sectional_weights(row, quantile=args.quantile, long_short=True)
                tgt = tgt[tgt.abs() > 1e-12]
                w = apply_no_trade_band(tgt, prev if len(prev) else None, band)
                w = w[w.abs() > 1e-12]
                idx = w.index.union(prev.index)
                to = float((w.reindex(idx).fillna(0.0)
                            - prev.reindex(idx).fillna(0.0)).abs().sum())
                turn.append(to)
                cur = prev = w
            if dt in fwd.index and len(cur):
                f = fwd.loc[dt]
                out[dt] = float((cur.reindex(f.index).fillna(0.0)
                                 * f.fillna(0.0)).sum()) - to * cost_rate
        return pd.Series(out).dropna(), float(np.mean(turn)) if turn else 0.0

    def sh(s):
        s = pd.Series(s).dropna()
        return float(s.mean() / s.std(ddof=1) * np.sqrt(252)) if len(s) > 2 and s.std(ddof=1) > 0 else 0.0

    def ann(s):
        return float(pd.Series(s).dropna().mean() * 252)

    def mdd(s):
        c = (1 + pd.Series(s).dropna()).cumprod()
        return float((c / c.cummax() - 1).min() * 100)

    rows, matrix = [], {}

    def record(name, module, r, turnover=np.nan, note=""):
        rows.append({"config": name, "module": module, "sharpe": sh(r),
                     "ann_return": ann(r), "max_dd_pct": mdd(r),
                     "turnover_per_reb": turnover, "note": note})
        matrix[name] = r
        print(f"  {name:34} {sh(r):>+7.2f} {ann(r):>+9.1%} {mdd(r):>+8.1f}% "
              f"{turnover if turnover == turnover else float('nan'):>8.2f}  {note}")

    hdr = f"  {'configuration':34} {'Sharpe':>7} {'rdt an.':>9} {'maxDD':>9} {'turn.':>8}"

    # ---------------------------------------------------------------- 1. bande
    print(f"\n1. BANDE DE NON-TRANSACTION (cost_aware) — le paramètre qui tourne en live\n{hdr}")
    base, base_turn = book(0.0)
    record("band=0.00 (référence)", "—", base, base_turn)
    band_best, band_best_sh = 0.0, sh(base)
    for b in (0.01, 0.02, 0.03, 0.05):
        r, t = book(b)
        record(f"band={b:.2f}" + ("  ← LIVE" if abs(b - 0.02) < 1e-9 else ""), "cost_aware", r, t)
        if sh(r) > band_best_sh:
            band_best, band_best_sh = b, sh(r)
    # Bande RELATIVE à la taille d'une ligne — la seule formulation transposable d'un
    # book à l'autre (0.02 absolu = 20 % d'une ligne à 10 positions, 130 % à 68 lignes).
    w0 = cross_sectional_weights(amihud.iloc[-1].dropna(), quantile=args.quantile,
                                 long_short=True)
    mean_w = float(w0[w0.abs() > 1e-12].abs().mean())
    print(f"  (poids absolu moyen d'une ligne : {mean_w:.4f} — la bande absolue doit "
          f"lui être très inférieure)")
    for k in (0.10, 0.25, 0.50):
        r, t = book(k * mean_w)
        record(f"band={k:.0%} de |w| ({k * mean_w:.4f})", "cost_aware", r, t)
        if sh(r) > band_best_sh:
            band_best, band_best_sh = k * mean_w, sh(r)

    # ------------------------------------------------------- 2. ciblage de vol
    print(f"\n2. CIBLAGE DE VOLATILITÉ (vol_management) — Barroso & Santa-Clara 2015\n{hdr}")
    for tv in (0.08, 0.10, 0.15):
        scaled, lev = apply_vol_target(base, target_vol=tv, lookback=126, max_leverage=2.0)
        record(f"vol-target {tv:.0%}", "vol_management", scaled,
               note=f"levier moyen {lev.mean():.2f}×")

    # --------------------------------------------------------- 3. régime / 4. tendance
    print(f"\n3-4. OVERLAYS DE RÉGIME (regime HMM, filtre de tendance)\n{hdr}")
    try:
        risk = regime_risk_series(close, warmup=252, refit_every=63, risk_off_factor=0.5)
        risk = risk.reindex(base.index).ffill().fillna(1.0)
        record("HMM risk-off (×0.5)", "regime", base * risk,
               note=f"exposition moyenne {risk.mean():.2f}")
    except Exception as e:  # noqa: BLE001
        print(f"  (HMM indisponible : {e})")
    idx_eq = close.div(close.iloc[0]).mean(axis=1)
    above = (idx_eq >= idx_eq.rolling(200).mean()).reindex(base.index).fillna(True)
    trend = pd.Series(np.where(above, 1.0, 0.5), index=base.index)
    record("tendance 200 j (×0.5)", "vol_management", base * trend,
           note=f"exposition moyenne {trend.mean():.2f}")

    # ----------------------------------------------------------- 5. stop-loss
    print(f"\n5. STOP-LOSS — test de la prédiction de Kaminski & Lo (2014)\n{hdr}")
    for stop in (0.05, 0.10, 0.15):
        eq, peak, hold, r = 1.0, 1.0, True, {}
        cooldown = 0
        for dt, x in base.items():
            if cooldown > 0:
                cooldown -= 1
                hold = cooldown == 0
                r[dt] = 0.0
                continue
            r[dt] = x if hold else 0.0
            eq *= 1 + r[dt]
            peak = max(peak, eq)
            if hold and eq / peak - 1 <= -stop:
                hold, cooldown, peak, eq = False, args.reb, eq, eq  # pause 1 cycle
        record(f"stop-loss {stop:.0%} (pause {args.reb} j)", "—", pd.Series(r),
               note="Kaminski-Lo : attendu destructeur")

    # ----------------------------------------------------------------- 6. PBO
    print("\n6. PBO / CSCV (robustness) sur la matrice des configurations")
    perf = pd.DataFrame(matrix).dropna(how="any")
    try:
        from financial_analyzer.backtest.robustness import (
            deflated_sharpe_ratio,
            probability_of_backtest_overfitting,
        )

        pbo, diag = probability_of_backtest_overfitting(perf, n_splits=10)
        sr_std = float(pd.Series({k: sh(v) for k, v in matrix.items()}).std(ddof=1))
        dsr, _ = deflated_sharpe_ratio(perf[max(matrix, key=lambda k: sh(matrix[k]))],
                                       n_trials=perf.shape[1], sr_std=sr_std / np.sqrt(252))
        print(f"  PBO = {pbo:.1%} sur {int(diag.get('n_configs', perf.shape[1]))} "
              f"configurations ({int(diag.get('n_combinations', 0))} combinaisons)")
        print(f"  DSR de la meilleure config = {dsr:.3f} (N={perf.shape[1]} essais)")
    except Exception as e:  # noqa: BLE001
        print(f"  (PBO/DSR indisponible : {e})")
        pbo = float("nan")

    # -------------------------------------------------------------- verdicts
    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    ref = sh(base)
    print("\n" + "=" * 92)
    print("VERDICTS PAR MODULE (référence : Sharpe {:+.2f})".format(ref))
    print("=" * 92)
    for mod in ("cost_aware", "vol_management", "regime"):
        sub = df[df["module"] == mod]
        if sub.empty:
            continue
        best = sub.loc[sub["sharpe"].idxmax()]
        gain = best["sharpe"] - ref
        verdict = "RETENIR" if gain > 0.10 else ("neutre" if gain > -0.10 else "REJETER")
        print(f"  {mod:16} meilleur = {best['config']:28} {best['sharpe']:+.2f} "
              f"({gain:+.2f}) → {verdict}")
    live = df[df["config"].str.contains("LIVE")]
    if not live.empty:
        d = float(live.iloc[0]["sharpe"]) - ref
        print(f"\n  ⚠️ Paramètre en production (band=0.02) : {float(live.iloc[0]['sharpe']):+.2f} "
              f"({d:+.2f} vs sans bande) — "
              f"{'justifié' if d > 0 else 'NON justifié pour Amihud'}")
        if band_best != 0.02:
            print(f"     Meilleure bande testée : {band_best:.2f} ({band_best_sh:+.2f})")
    print(f"\n  → {args.out}")
    print("\n⚠️ Toutes ces variantes sont des essais sur le MÊME historique : la PBO ci-dessus")
    print("   est le juge du processus de sélection, pas le Sharpe de la meilleure ligne.")


if __name__ == "__main__":
    main()
