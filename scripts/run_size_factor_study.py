"""ÉTUDE SYSTÉMATIQUE FACTEURS × TAILLE — small/mid/large, 18 ans, coûts différenciés.

Trou comblé : jusqu'ici, un SEUL facteur (momentum) avait été testé sur les small-caps.
Or la littérature dit que ce sont des facteurs **différents** qui y opèrent (reversal court
terme plus fort en illiquide — Jegadeesh 1990/Lehmann 1990 ; value/quality plus fort en
small — Fama-French, Piotroski ; low-vol/BAB — Frazzini-Pedersen). Cette étude teste
**les 8 facteurs classiques × 3 terciles de taille**, sur 18 ans.

Deux améliorations méthodologiques majeures :

1. **Coûts DIFFÉRENCIÉS par taille** (au lieu de 2.5 bps partout, calibré large-cap) :
   grand 5 bps / moyen 25 bps / petit 60 bps d'aller simple — ordres de grandeur usuels
   (Lesmond-Schill-Zhou 2004 ; Novy-Marx & Velikov 2016). Un facteur ne « passe » que
   s'il survit aux frictions **de son propre segment**.
2. **Alpha EXCÉDENTAIRE en long-only** (book − équipondéré du *même* tercile) en plus du
   L/S : en long-only, un Sharpe brut positif n'est que du beta.

Usage::

    python scripts/run_size_factor_study.py --reb 21
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

#: Coût aller simple (bps) par tercile de liquidité — ordres de grandeur réalistes.
COSTS_BPS = {"T1 grand": 5.0, "T2 moyen": 25.0, "T3 petit": 60.0}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--px-cache", default="/tmp/yahoo_broad_prices_18y.csv")
    ap.add_argument("--uni-cache", default="/tmp/alpaca_broad_universe.json")
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--quantile", type=float, default=0.2)
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights

    px_all = pd.read_csv(args.px_cache, index_col=0, parse_dates=True)
    px_all = px_all.ffill().dropna(axis=1, thresh=int(0.5 * len(px_all))).dropna(how="all")
    universe = json.loads(Path(args.uni_cache).read_text())
    ordered = [s for s in universe if s in px_all.columns]  # trié dollar-volume ↓
    t = len(ordered) // 3
    terciles = {
        "T1 grand": ordered[:t],
        "T2 moyen": ordered[t:2 * t],
        "T3 petit": ordered[2 * t:],
    }
    print(f"Panel : {px_all.shape[0]} jours ({px_all.index.min():%Y-%m} → "
          f"{px_all.index.max():%Y-%m}) × {len(ordered)} titres")
    print(f"Coûts aller simple : " + " | ".join(f"{k} {v:.0f} bps" for k, v in COSTS_BPS.items()))

    def book_and_excess(scores, rets, cost_rate, long_short):
        """(rendements nets du book, excès vs équipondéré du même univers)."""
        fwd = rets.shift(-1)
        reb_set = {scores.index[i] for i in range(0, len(scores.index), args.reb)}
        cur = prev = pd.Series(dtype=float)
        out = {}
        for dt in scores.index:
            to = 0.0
            if dt in reb_set:
                w = cross_sectional_weights(scores.loc[dt], quantile=args.quantile,
                                            long_short=long_short)
                w = w[w.abs() > 1e-12]
                idx = w.index.union(prev.index)
                to = float((w.reindex(idx).fillna(0.0) - prev.reindex(idx).fillna(0.0)).abs().sum())
                cur = prev = w
            if dt in fwd.index and len(cur):
                f = fwd.loc[dt]
                g = float((cur.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum())
                out[dt] = g - to * cost_rate
        book = pd.Series(out).dropna()
        bench = rets.mean(axis=1).reindex(book.index).fillna(0.0)
        return book, (book - bench).dropna()

    def _sh(s):
        s = pd.Series(s).dropna()
        return float(s.mean() / s.std(ddof=1) * np.sqrt(252)) if len(s) > 2 and s.std(ddof=1) > 0 else 0.0

    def _t(s):
        s = pd.Series(s).dropna()
        return float(s.mean() / s.std(ddof=1) * np.sqrt(len(s))) if len(s) > 2 and s.std(ddof=1) > 0 else 0.0

    def _ic_t(scores, rets):
        fwd = rets.shift(-1)
        ics = []
        for dt in scores.index[::args.reb]:
            if dt not in fwd.index:
                continue
            a, b = scores.loc[dt], fwd.loc[dt]
            m = a.notna() & b.notna()
            if m.sum() >= 10:
                ics.append(float(a[m].corr(b[m], method="spearman")))
        ics = pd.Series(ics).dropna()
        return _t(ics) if len(ics) > 2 else 0.0

    results = []
    for tname, syms in terciles.items():
        px = px_all[[s for s in syms if s in px_all.columns]]
        rets = daily_returns(px)
        factors = compute_classic_factors(px)
        cost_rate = COSTS_BPS[tname] / 1e4
        bench = rets.mean(axis=1)
        print(f"\n{'=' * 92}")
        print(f"{tname}  ({px.shape[1]} titres, coût {COSTS_BPS[tname]:.0f} bps, reb={args.reb})"
              f"   [benchmark équipondéré : Sharpe {_sh(bench):+.2f}]")
        print(f"{'=' * 92}")
        print(f"  {'facteur':16} {'IC t':>7} {'L/S Sh net':>11} {'LO excès Sh':>12} "
              f"{'excès t':>8} {'excès an.':>10}")
        for fname in sorted(factors):
            sc = factors[fname]
            if sc.dropna(how="all").empty:
                continue
            ls_book, _ = book_and_excess(sc, rets, cost_rate, long_short=True)
            _, lo_exc = book_and_excess(sc, rets, cost_rate, long_short=False)
            row = {
                "tercile": tname, "facteur": fname, "ic_t": _ic_t(sc, rets),
                "ls_sharpe": _sh(ls_book), "exc_sharpe": _sh(lo_exc),
                "exc_t": _t(lo_exc), "exc_ann": float(lo_exc.mean() * 252),
            }
            results.append(row)
            star = " ⭐" if (abs(row["ic_t"]) > 2 and row["exc_t"] > 2) else ""
            print(f"  {fname:16} {row['ic_t']:>+7.2f} {row['ls_sharpe']:>+11.2f} "
                  f"{row['exc_sharpe']:>+12.2f} {row['exc_t']:>+8.2f} {row['exc_ann']:>+9.1%}{star}")

    df = pd.DataFrame(results)
    out_csv = "/tmp/size_factor_study.csv"
    df.to_csv(out_csv, index=False)

    print("\n" + "=" * 92)
    print("SURVIVANTS — |IC t| > 2 ET alpha excédentaire significatif (t > 2), coûts du segment")
    print("=" * 92)
    surv = df[(df["ic_t"].abs() > 2) & (df["exc_t"] > 2)].sort_values("exc_sharpe", ascending=False)
    if surv.empty:
        print("\n  AUCUN facteur ne produit d'alpha excédentaire significatif dans son propre")
        print("  segment après coûts réalistes — y compris en small/mid-cap.")
    else:
        for _, r in surv.iterrows():
            print(f"  {r['tercile']:10} {r['facteur']:16} IC t={r['ic_t']:+.2f}  "
                  f"excès Sharpe={r['exc_sharpe']:+.2f} (t={r['exc_t']:+.2f}, "
                  f"{r['exc_ann']:+.1%}/an)")
        print(f"\n  → Candidats à passer au portail complet (DSR/PBO). Détail : {out_csv}")

    print("\nLecture : « L/S Sh net » = market-neutral (isole l'alpha mais paie le short, cher")
    print("en small-cap). « LO excès » = long-only MOINS l'équipondéré du MÊME tercile — c'est")
    print("l'alpha honnête d'un book long-only. Coûts différenciés par segment (5/25/60 bps).")
    print("⚠️ Univers survivant (Yahoo, 18 ans d'historique requis) → biais de survie à la hausse.")


if __name__ == "__main__":
    main()
