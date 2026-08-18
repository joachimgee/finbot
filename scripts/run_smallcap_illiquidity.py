"""Illiquidité (Amihud) et volume sur SMALL-CAPS — le test au bon endroit.

L'illiquidité d'Amihud (2002) avait été testée sur **50 large-caps** et rejetée — un
contresens : la prime d'illiquidité est par construction un phénomène **small-cap**.
Ici on la teste là où la littérature l'attend, avec les **vrais volumes** Alpaca.

**Hypothèses PRÉ-ENREGISTRÉES** (3, pas de sweep) :

1. ``amihud`` — illiquidité ``moy(|r| / $volume)`` sur 60 j → **prime d'illiquidité**
   (Amihud 2002) : long les plus illiquides, short les plus liquides.
2. ``volume_shock`` — $volume 5 j / $volume 60 j → **effet d'attention** (Gervais-Kaniel-
   Mingelgrin 2001, *The High-Volume Return Premium*) : long les chocs de volume.
3. ``turnover_low`` — inverse du $volume moyen → proxy de **négligence** (neglected firm
   effect, Arbel-Strebel 1982).

Coûts **60 bps** (small-cap) et alpha **excédentaire** vs équipondéré du même univers.

Usage::

    python scripts/run_smallcap_illiquidity.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

COST_BPS = 60.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ohlcv-cache", default="/tmp/smallcap_ohlcv.pkl")
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--window", type=int, default=60)
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import daily_returns
    from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights

    ohlcv = pd.read_pickle(args.ohlcv_cache)
    close = pd.DataFrame({s: d["close"] for s, d in ohlcv.items()}).sort_index()
    vol = pd.DataFrame({s: d["volume"] for s, d in ohlcv.items()}).sort_index()
    close = close.ffill().dropna(axis=1, thresh=int(0.6 * len(close))).dropna(how="all")
    vol = vol.reindex(columns=close.columns, index=close.index)
    print(f"Small-caps avec volumes : {close.shape[1]} titres × {close.shape[0]} jours "
          f"({close.index.min():%Y-%m} → {close.index.max():%Y-%m})")

    rets = daily_returns(close)
    dollar_vol = (close * vol).replace(0, np.nan)

    # --- Facteurs pré-enregistrés ---
    amihud = (rets.abs() / dollar_vol).rolling(args.window).mean() * 1e9  # échelle lisible
    volume_shock = dollar_vol.rolling(5).mean() / dollar_vol.rolling(args.window).mean()
    turnover_low = -dollar_vol.rolling(args.window).mean()  # signe : long = peu négocié

    factors = {
        "amihud (illiquidité)": amihud,
        "volume_shock (attention)": volume_shock,
        "turnover_low (négligé)": turnover_low,
    }
    cost_rate = COST_BPS / 1e4

    def book_excess(scores, long_short):
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
                out[dt] = float((cur.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum()) - to * cost_rate
        book = pd.Series(out).dropna()
        bench = rets.mean(axis=1).reindex(book.index).fillna(0.0)
        return book, (book - bench).dropna()

    def _sh(s):
        s = pd.Series(s).dropna()
        return float(s.mean() / s.std(ddof=1) * np.sqrt(252)) if len(s) > 2 and s.std(ddof=1) > 0 else 0.0

    def _t(s):
        s = pd.Series(s).dropna()
        return float(s.mean() / s.std(ddof=1) * np.sqrt(len(s))) if len(s) > 2 and s.std(ddof=1) > 0 else 0.0

    def _ic_t(scores):
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

    bench = rets.mean(axis=1)
    print(f"\n{'=' * 88}")
    print(f"ILLIQUIDITÉ / VOLUME sur SMALL-CAPS — coûts {COST_BPS:.0f} bps, reb={args.reb}")
    print(f"[benchmark équipondéré : Sharpe {_sh(bench):+.2f}]")
    print(f"{'=' * 88}")
    print(f"  {'facteur':26} {'IC t':>7} {'L/S Sh':>8} {'LO excès Sh':>12} {'excès t':>8} "
          f"{'excès an.':>10}")
    any_pass = False
    for fname, panel in factors.items():
        if panel.dropna(how="all").empty:
            print(f"  {fname:26}  (panel vide)")
            continue
        ls, _ = book_excess(panel, True)
        _, exc = book_excess(panel, False)
        ic_t, e_t = _ic_t(panel), _t(exc)
        ok = abs(ic_t) > 2 and e_t > 2
        any_pass = any_pass or ok
        print(f"  {fname:26} {ic_t:>+7.2f} {_sh(ls):>+8.2f} {_sh(exc):>+12.2f} {e_t:>+8.2f} "
              f"{float(exc.mean() * 252):>+9.1%}{' ⭐' if ok else ''}")

    print("\n" + "-" * 88)
    if any_pass:
        print("→ Un facteur d'illiquidité/volume montre un alpha significatif en small-cap :")
        print("  candidat à passer au portail complet (DSR/PBO).")
    else:
        print("→ AUCUN facteur d'illiquidité/volume ne produit d'alpha excédentaire")
        print("  significatif en small-cap après coûts — la prime d'illiquidité d'Amihud")
        print("  n'est pas capturable ici (elle est justement mangée par... l'illiquidité).")
    print("\n⚠️ Fenêtre ~2020-2026 (profondeur du feed Alpaca IEX), univers survivant.")
    print("Note : la prime d'illiquidité est théoriquement une compensation POUR le coût de")
    print("transaction — la capturer net de ces mêmes coûts est intrinsèquement difficile.")


if __name__ == "__main__":
    main()
