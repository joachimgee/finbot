"""Value/Quality sur SMALL-CAPS — le test que la littérature réclame le plus.

Les facteurs value/quality avaient été testés sur **50 large-caps** (rejetés). Or c'est
précisément en **small-cap** que la littérature les attend : Fama-French (value plus fort
en small), **Piotroski (2000)** — son F-score a été conçu *pour* les small value stocks,
Novy-Marx (2013) pour la profitabilité brute. Ce script les teste sur un **sous-échantillon
de small-caps** (quota Polygon 5 req/min → ~150 titres réalistes).

Discipline :
* fondamentaux **point-in-time** (``filing_date``) — aucun look-ahead ;
* ``allow_synthetic_fallback=False`` — **données réelles obligatoires**, on refuse de
  conclure sur du synthétique ;
* **coût small-cap 60 bps** (pas 2.5 bps large-cap) ;
* alpha **excédentaire** vs équipondéré du même univers (le seul honnête en long-only).

Usage::

    python scripts/run_smallcap_value_quality.py --n 150
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

COST_BPS = 60.0  # aller simple, small-cap


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=150, help="Nb de small-caps (quota Polygon).")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--px-cache", default="/tmp/yahoo_broad_prices_18y.csv")
    ap.add_argument("--uni-cache", default="/tmp/alpaca_broad_universe.json")
    ap.add_argument("--fund-cache", default="/tmp/smallcap_fundamentals.pkl")
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import daily_returns
    from financial_analyzer.backtest.fundamental_factors import compute_fundamental_factors
    from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights
    from financial_analyzer.data.fundamentals_pit_loader import (
        FundamentalsPITLoader,
        RealDataUnavailableError,
    )

    px_all = pd.read_csv(args.px_cache, index_col=0, parse_dates=True)
    px_all = px_all.ffill().dropna(axis=1, thresh=int(0.5 * len(px_all))).dropna(how="all")
    universe = json.loads(Path(args.uni_cache).read_text())
    ordered = [s for s in universe if s in px_all.columns]
    t = len(ordered) // 3
    small = ordered[2 * t:][: args.n]  # les plus liquides du tercile petit (fetchables)
    px = px_all[small].loc[args.start:]
    print(f"Small-caps testées : {len(small)} | panel {px.shape[0]} jours "
          f"({px.index.min():%Y-%m} → {px.index.max():%Y-%m})")

    # --- Fondamentaux PIT réels (cache : le quota Polygon est de 5 req/min) ---
    fc = Path(args.fund_cache)
    if fc.exists():
        fund = pd.read_pickle(fc)
        print(f"Fondamentaux chargés du cache : {fund.shape[0]} lignes, "
              f"{fund['ticker'].nunique()} tickers")
    else:
        print(f"Fetch fondamentaux PIT Polygon pour {len(small)} titres "
              f"(~{len(small) / 5:.0f} min au quota 5/min)…", flush=True)
        loader = FundamentalsPITLoader(source="polygon", allow_synthetic_fallback=False)
        try:
            fund = loader.load(small, args.start)
        except RealDataUnavailableError as e:
            print(f"\n❌ Fondamentaux réels indisponibles ({e}) — on NE conclut PAS "
                  f"sur des données synthétiques.")
            return
        fund.to_pickle(fc)
        print(f"OK : {fund.shape[0]} lignes, {fund['ticker'].nunique()} tickers")

    if fund.empty or fund["ticker"].nunique() < 20:
        print("❌ Couverture fondamentale trop faible pour conclure.")
        return

    rets = daily_returns(px)
    factors = compute_fundamental_factors(px, fund)
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

    bench_all = rets.mean(axis=1)
    print(f"\n{'=' * 88}")
    print(f"VALUE / QUALITY sur SMALL-CAPS — coûts {COST_BPS:.0f} bps, reb={args.reb}")
    print(f"[benchmark équipondéré small-cap : Sharpe {_sh(bench_all):+.2f}]")
    print(f"{'=' * 88}")
    print(f"  {'facteur':22} {'couv.':>6} {'IC t':>7} {'L/S Sh':>8} {'LO excès Sh':>12} "
          f"{'excès t':>8} {'excès an.':>10}")
    any_pass = False
    for fname, panel in factors.items():
        if panel is None or panel.dropna(how="all").empty:
            print(f"  {fname:22} {'—':>6}  (panel vide)")
            continue
        cov = float(panel.notna().mean().mean())
        ls, _ = book_excess(panel, True)
        _, exc = book_excess(panel, False)
        ic_t, e_t = _ic_t(panel), _t(exc)
        ok = abs(ic_t) > 2 and e_t > 2
        any_pass = any_pass or ok
        print(f"  {fname:22} {cov:>5.0%} {ic_t:>+7.2f} {_sh(ls):>+8.2f} {_sh(exc):>+12.2f} "
              f"{e_t:>+8.2f} {float(exc.mean() * 252):>+9.1%}{' ⭐' if ok else ''}")

    print("\n" + "-" * 88)
    if any_pass:
        print("→ Un facteur value/quality montre un alpha significatif en small-cap : "
              "candidat à passer au portail complet (DSR/PBO).")
    else:
        print("→ AUCUN facteur value/quality ne produit d'alpha excédentaire significatif")
        print("  en small-cap après coûts — malgré l'hypothèse de Piotroski/Fama-French.")
    print("\n⚠️ Réserves : sous-échantillon (quota Polygon), univers survivant, fondamentaux")
    print("Polygon (couverture small-cap parfois partielle — voir la colonne « couv. »).")


if __name__ == "__main__":
    main()
