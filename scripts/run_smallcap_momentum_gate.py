"""(a) PORTAIL COMPLET du small-cap momentum LONG-ONLY sur 18 ans.

Le test 18 ans a montré que le momentum small-cap long-only bat le beta de son univers
(+1.14 vs +0.92) avec un IC très significatif (t=4.77). On le passe maintenant par
**exactement le portail** des autres signaux — walk-forward OOS, DSR (essais comptés),
PBO (CSCV) — plus un critère supplémentaire **indispensable en long-only** :

⚠️ **Le test d'ALPHA EXCÉDENTAIRE.** Pour un long-only, « Sharpe net > 0 » est trivial en
marché haussier (c'est du beta). Le vrai test est la série **excédentaire** :
``rendement du book − rendement du benchmark équipondéré du MÊME univers``. Si son Sharpe
et son DSR tiennent, l'edge est de l'alpha ; sinon c'est du beta déguisé.

Usage::

    python scripts/run_smallcap_momentum_gate.py --px-cache /tmp/yahoo_broad_prices_18y.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--px-cache", default="/tmp/yahoo_broad_prices_18y.csv")
    ap.add_argument("--uni-cache", default="/tmp/alpaca_broad_universe.json")
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--pbo-splits", type=int, default=10)
    ap.add_argument("--tercile", choices=["small", "all"], default="small")
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.robustness import (
        deflated_sharpe_ratio,
        probability_of_backtest_overfitting,
        sharpe_per_period,
    )
    from financial_analyzer.backtest.signal_evaluation import (
        CostModel,
        cross_sectional_weights,
        evaluate_signal,
    )
    from financial_analyzer.backtest.validation_gate import GateThresholds, decide

    px = pd.read_csv(args.px_cache, index_col=0, parse_dates=True)
    px = px.ffill().dropna(axis=1, thresh=int(0.5 * len(px))).dropna(how="all")
    universe = json.loads(Path(args.uni_cache).read_text())
    ordered = [s for s in universe if s in px.columns]
    if args.tercile == "small":
        t = len(ordered) // 3
        px = px[ordered[2 * t:]]
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres ({args.tercile})\n")

    factors = compute_classic_factors(px)
    rets = daily_returns(px)
    cost = CostModel.alpaca_equities()

    def book_returns(scores: pd.DataFrame, reb: int, long_short: bool = False) -> pd.Series:
        """Rendements nets du book (tenu entre rééq.), coûts inclus."""
        fwd = rets.shift(-1)
        reb_i = list(range(0, len(scores.index), reb))
        cur = pd.Series(dtype=float)
        prev = pd.Series(dtype=float)
        out = {}
        reb_set = {scores.index[i] for i in reb_i}
        for dt in scores.index:
            to = 0.0
            if dt in reb_set:
                w = cross_sectional_weights(scores.loc[dt], quantile=0.2, long_short=long_short)
                w = w[w.abs() > 1e-12]
                idx = w.index.union(prev.index)
                to = float((w.reindex(idx).fillna(0.0) - prev.reindex(idx).fillna(0.0)).abs().sum())
                cur, prev = w, w
            if dt in fwd.index and len(cur):
                f = fwd.loc[dt]
                g = float((cur.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum())
                out[dt] = g - to * cost.cost_rate
        return pd.Series(out).dropna()

    mom = factors["momentum_12_1"]

    # --- 1. Portail standard (walk-forward OOS via evaluate_signal, long-only) ---
    res = evaluate_signal(mom, rets, cost_model=cost, rebalance_every=args.reb, long_short=False)
    print("=" * 80)
    print("PORTAIL — small-cap momentum LONG-ONLY (18 ans)")
    print("=" * 80)
    print(f"\n[1] Critères standards")
    print(f"    IC t-stat  = {res.ic_t_stat:+.2f}   (seuil > 2)")
    print(f"    Sharpe net = {res.net_sharpe:+.2f}   (seuil > 0)  ← trivial en long-only, cf. [2]")
    print(f"    Rdt net an = {res.net_ann_return:+.1%} | turnover {res.avg_turnover:.3f}")

    # --- 2. Le test qui compte : ALPHA EXCÉDENTAIRE vs benchmark équipondéré ---
    book = book_returns(mom, args.reb, long_short=False)
    bench = rets.mean(axis=1).reindex(book.index).fillna(0.0)
    excess = (book - bench).dropna()
    sh_book = float(book.mean() / book.std(ddof=1) * np.sqrt(252))
    sh_bench = float(bench.mean() / bench.std(ddof=1) * np.sqrt(252))
    sh_exc = float(excess.mean() / excess.std(ddof=1) * np.sqrt(252))
    t_exc = float(excess.mean() / excess.std(ddof=1) * np.sqrt(len(excess)))
    print(f"\n[2] ALPHA EXCÉDENTAIRE (book − benchmark équipondéré) ← le vrai test long-only")
    print(f"    book {sh_book:+.2f} | benchmark {sh_bench:+.2f} | "
          f"EXCÈS Sharpe {sh_exc:+.2f} (t={t_exc:+.2f})")
    print(f"    rdt excédentaire annualisé = {excess.mean() * 252:+.2%}")

    # --- 3. Matrice d'essais (facteurs × cadences) pour DSR + PBO ---
    print(f"\n[3] Matrice d'essais (facteurs × cadences) pour DSR/PBO…", flush=True)
    trial_series: dict[str, pd.Series] = {}
    trial_sharpes: list[float] = []
    for fname, fdf in factors.items():
        for reb in (5, 10, 21, 63):
            try:
                s = book_returns(fdf, reb, long_short=False)
                e = (s - rets.mean(axis=1).reindex(s.index).fillna(0.0)).dropna()
                if len(e) > 100:
                    trial_series[f"{fname}@{reb}"] = e  # matrice sur l'EXCÈS (alpha)
                    trial_sharpes.append(sharpe_per_period(e))
            except Exception:  # noqa: BLE001
                continue
    n_trials = len(trial_sharpes)
    sr_std = float(np.std(trial_sharpes, ddof=1)) if n_trials > 1 else 0.0
    print(f"    {n_trials} essais | dispersion σ des Sharpes/période = {sr_std:.4f}")

    dsr, diag = deflated_sharpe_ratio(excess, n_trials, sr_std)
    print(f"\n[4] DSR sur l'EXCÈS (essais comptés = {n_trials})")
    print(f"    Sharpe/période {diag['sr_per_period']:+.4f} vs repère E[max|H0] "
          f"{diag['sr_benchmark']:+.4f}")
    print(f"    skew {diag['skew']:+.2f} / kurtosis {diag['kurtosis']:.1f} | "
          f"obs {int(diag['n_obs'])}")
    print(f"    >>> DSR = {dsr:.3f}")

    pbo = None
    matrix = pd.DataFrame(trial_series).dropna(how="any")
    if matrix.shape[1] >= 2 and matrix.shape[0] >= 10:
        pbo, pdiag = probability_of_backtest_overfitting(matrix, n_splits=args.pbo_splits)
        print(f"\n[5] PBO (CSCV, {int(pdiag['n_configs'])} configs) = {pbo:.3f}")

    # --- 6. Verdict du portail, appliqué à l'EXCÈS (pas au book brut) ---
    ok, reasons = decide(res.ic_t_stat, sh_exc, GateThresholds(), dsr=dsr, pbo=pbo)
    print("\n" + "-" * 80)
    print(f"VERDICT (critères appliqués à l'alpha EXCÉDENTAIRE) : "
          f"{'✅ PASSE' if ok else '❌ NE PASSE PAS'}")
    for r in reasons:
        print(f"   - {r}")
    print("\nRappel : le Sharpe net brut d'un long-only inclut le beta ; seul l'EXCÈS sur le")
    print("benchmark du même univers mesure l'alpha. Le DSR/PBO ci-dessus portent donc sur")
    print("l'excès. Réserves inchangées : survivants de 18 ans (Shumway) + coûts small-cap")
    print("sous-estimés (2.5 bps) — l'étape (c) chiffre ces coûts réels.")


if __name__ == "__main__":
    main()
