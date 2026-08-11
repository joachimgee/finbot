"""Diagnostic de l'anomalie du combinateur : IC négatif, Sharpe net positif (P1).

Sur univers large, le combinateur ridge (`FactorCombiner`) sort un IC
*significativement négatif* mais un Sharpe net *positif* — apparemment
contradictoire. Ce script établit le mécanisme, chiffres à l'appui, et tranche :
bug, ou artefact ?

Méthode : on reconstruit le panel de scores combinés OOS (mêmes fenêtres
walk-forward que `walk_forward_combine`), puis on ventile chaque jour les titres
en déciles de score et on mesure le **rendement forward moyen par décile**. Un
edge réel est *monotone* (le score croît → le rendement croît). Ici, la
« performance » long/short vient d'un unique décile aberrant à queue épaisse :
le Sharpe net positif n'est donc pas un edge, et l'IC négatif n'est pas un bug.

Conclusion opérationnelle : un Sharpe net *seul* ne valide pas un signal — d'où
le portail à double critère (IC t > 2 ET Sharpe net > 0).

Usage::

    python scripts/diagnose_combiner_anomaly.py --broad 500
"""
from __future__ import annotations

import argparse
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.factor_combiner import (
    FactorCombiner,
    _slice_panels,
    walk_forward_combine,
)
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.data.alpaca_history import fetch_daily_history


def _broad_universe(cap: int) -> list[str]:
    from financial_analyzer.universe.market_selector import UniverseSelector

    raw = UniverseSelector().select_equities(sector=None, country="United States")
    return sorted({t for t in raw if re.fullmatch(r"[A-Z]{1,5}", t)})[:cap]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--broad", type=int, default=500)
    ap.add_argument("--deciles", type=int, default=10)
    args = ap.parse_args()

    universe = _broad_universe(args.broad)
    print(f"Univers large: {len(universe)} candidats — fetch Alpaca…")
    prices = fetch_daily_history(universe, args.start, args.end, progress=False)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel: {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)
    cost = CostModel(commission_bps=5, slippage_bps=3)

    out = walk_forward_combine(factors, returns, n_splits=args.splits, cost_model=cost)
    comb = out["combined"]
    print("=== Combinateur ridge (agrégat OOS) ===")
    print(f"  IC = {comb.ic_mean:+.4f} (t = {comb.ic_t_stat:+.2f})   "
          f"Sharpe net = {comb.net_sharpe:+.2f}   turnover = {comb.avg_turnover:.2f}")
    verdict_ic = "NÉGATIF significatif" if comb.ic_t_stat < -2 else (
        "positif" if comb.ic_t_stat > 2 else "non significatif")
    print(f"  -> IC {verdict_ic}, Sharpe net {'positif' if comb.net_sharpe > 0 else 'négatif'}"
          f" : {'ANOMALIE reproduite' if comb.ic_t_stat < -2 and comb.net_sharpe > 0 else 'pas d’anomalie ici'}\n")

    # Reconstruire le panel combiné OOS (mêmes fenêtres).
    sources = sorted(factors)
    common = returns.index
    for s in sources:
        common = common.intersection(factors[s].index)
    common = common.sort_values()
    returns = returns.loc[common]
    factors = {s: factors[s].loc[common] for s in sources}
    fwd_full = returns.shift(-1)
    n, ns = len(common), args.splits
    fold = n // (ns + 1)
    parts = []
    for i in range(1, ns + 1):
        tr = common[: fold * i]
        te = common[fold * i : (fold * (i + 1) if i < ns else n)]
        if len(te) < 5:
            continue
        c = FactorCombiner(method="ridge", l2=1.0).fit(_slice_panels(factors, tr), fwd_full.loc[tr])
        parts.append(c.predict(_slice_panels(factors, te)))
    comb_panel = pd.concat(parts)
    fret = returns.shift(-1).reindex(comb_panel.index)

    # Rendement forward moyen par décile de score combiné.
    d = args.deciles
    bucket_rets: dict[int, list[float]] = {k: [] for k in range(d)}
    for dt in comb_panel.index:
        s = comb_panel.loc[dt].dropna()
        if len(s) < 2 * d:
            continue
        q = pd.qcut(s.rank(method="first"), d, labels=False)
        r = fret.loc[dt]
        for k in range(d):
            vals = r.reindex(q.index[q == k]).dropna()
            if len(vals):
                bucket_rets[k].append(float(vals.mean()))
    means = [float(np.mean(bucket_rets[k])) * 1e4 for k in range(d)]

    print("=== Rendement forward moyen par décile de score combiné (bps/jour) ===")
    print(f"   (D0 = score le plus bas … D{d - 1} = le plus haut)")
    for k in range(d):
        bar = "█" * max(0, int(means[k] / 3))
        flag = "  <-- décile aberrant" if means[k] == max(means) and means[k] > 3 * sorted(means)[-2] else ""
        print(f"  D{k}: {means[k]:+7.2f}  {bar}{flag}")

    top = round(d * 0.2) or 1
    long_mean = float(np.mean(means[-top:]))
    short_mean = float(np.mean(means[:top]))
    from scipy.stats import spearmanr
    rho, _ = spearmanr(range(d), means)
    print(f"\n  Long top-20% ≈ {long_mean:+.2f} bps | Short bottom-20% ≈ {short_mean:+.2f} bps"
          f" | spread ≈ {long_mean - short_mean:+.2f} bps/j")
    print(f"  Spearman(décile, rendement) = {rho:+.3f}  "
          f"({'monotone' if abs(rho) > 0.6 else 'NON monotone -> pas d’edge de tri'})")
    print("\nVerdict : si un unique décile aberrant porte le spread et que le Spearman")
    print("est ≈ 0, le Sharpe net positif est un artefact de queue épaisse, pas un edge.")
    print("Le portail de validation exige IC t > 2 ET Sharpe net > 0 : le combinateur échoue.")


if __name__ == "__main__":
    main()
