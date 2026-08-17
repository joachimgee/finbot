"""Contrôle de drawdown du book méta — vol-target (Barroso) & régime-HMM.

Le Monte-Carlo a révélé un drawdown sévère (médiane −51 %, pire −83 %). On teste les
overlays de dé-risque **déjà présents** sur la série de rendements réelle du book méta
(RICH, reb=21), et on re-mesure le drawdown par bootstrap :

* vol-target (Barroso-Santa-Clara) : levier ``vol_cible / vol réalisée du book``, causal.
  - cap 1.0 : **dé-risque seulement** (jamais de levier) — le contrôle de drawdown pur.
  - cap 2.0 : Barroso complet (peut lever en régime calme).
* régime-HMM : exposition ∈ [0.5, 1] réduite en régime turbulent (marché équipondéré).

Verdict : quel overlay coupe le drawdown (médiane + queue bootstrap) au moindre coût
de Sharpe. Le meilleur serait à brancher dans MetaLabelConstruction avant tout live.

Usage::

    python scripts/run_meta_drawdown_control_alpaca.py --cache /tmp/yahoo_long.csv --reb 21
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
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--target-vol", type=float, default=0.10)
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("--cache", default="/tmp/yahoo_long.csv")
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import (
        META_FEATURES_RICH,
        confirm_meta_labeling,
        regime_features,
    )
    from financial_analyzer.backtest.regime import regime_risk_series
    from financial_analyzer.backtest.robustness import block_bootstrap_metrics
    from financial_analyzer.backtest.signal_evaluation import CostModel
    from financial_analyzer.backtest.vol_management import apply_vol_target
    from financial_analyzer.data.alpaca_history import load_or_fetch

    px = load_or_fetch(UNIVERSE, args.start, args.end, cache_path=args.cache)
    px = px[[c for c in UNIVERSE if c in px.columns]].ffill().dropna(axis=1, how="any").dropna(how="all")
    factors = compute_classic_factors(px)
    scores = factors["momentum_12_1"]
    returns = daily_returns(px)
    rich = dict(factors)
    rich.update(regime_features(px, scores))
    cost = CostModel.alpaca_equities()
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres | reb={args.reb}")

    print("Reconstruction de la série méta…", flush=True)
    c = confirm_meta_labeling(scores, returns, rich, rebalance_every=args.reb, horizon=args.reb,
                              cost_rate=cost.cost_rate, feature_names=META_FEATURES_RICH,
                              n_random=1, n_perm=1)
    r = c.meta_returns.dropna()

    # Overlays (tous causaux).
    vt1, _ = apply_vol_target(r, target_vol=args.target_vol, max_leverage=1.0)
    vt2, _ = apply_vol_target(r, target_vol=args.target_vol, max_leverage=2.0)
    regime_exp = regime_risk_series(px).reindex(r.index).ffill().fillna(1.0).shift(1).fillna(1.0)
    reg = r * regime_exp

    variants = {
        "raw (aucun)": r,
        f"vol-target {args.target_vol:.0%} cap1 (dé-risque)": vt1.dropna(),
        f"vol-target {args.target_vol:.0%} cap2 (Barroso)": vt2.dropna(),
        "régime-HMM (rof=0.5)": reg.dropna(),
    }

    print("\n" + "=" * 84)
    print("CONTRÔLE DE DRAWDOWN DU BOOK MÉTA — réalisé + bootstrap")
    print("=" * 84)
    print(f"\n  {'variante':34} {'Sharpe':>7} {'DD réal.':>9} {'DD méd.':>8} {'DD pire1%':>9} {'levier':>7}")
    rows = {}
    for name, series in variants.items():
        m = block_bootstrap_metrics(series, n_boot=args.n_boot)
        eq = (1.0 + series).cumprod()
        dd_real = float(((eq / eq.cummax()) - 1.0).min() * 100.0)
        sh = float(series.mean() / series.std(ddof=1) * np.sqrt(252)) if series.std(ddof=1) > 0 else 0.0
        # levier moyen effectif (variante vs raw) : rapport des écarts-types.
        lev = float(series.std(ddof=1) / r.std(ddof=1)) if r.std(ddof=1) > 0 else 1.0
        rows[name] = (sh, dd_real, m["maxdd_median"], m["maxdd_worst"], lev)
        print(f"  {name:34} {sh:>+7.2f} {dd_real:>+8.1f}% {m['maxdd_median']:>+7.1f}% "
              f"{m['maxdd_worst']:>+8.1f}% {lev:>7.2f}")

    raw = rows["raw (aucun)"]
    print("\n" + "-" * 84)
    # Meilleur = plus petit drawdown médian bootstrap, sous contrainte Sharpe ≥ 90% du raw.
    elig = {n: v for n, v in rows.items() if n != "raw (aucun)" and v[0] >= 0.9 * raw[0]}
    if elig:
        best = max(elig, key=lambda n: elig[n][2])  # DD médian le moins profond (moins négatif)
        bs, _, bmed, bworst, _ = rows[best]
        cut = raw[2] - bmed
        print(f"→ Meilleur contrôle (Sharpe préservé ≥ 90 %) : « {best} »")
        print(f"  DD médian {raw[2]:+.0f}% → {bmed:+.0f}% (−{cut:.0f} pts), pire1% {raw[3]:+.0f}% → "
              f"{bworst:+.0f}%, Sharpe {raw[0]:+.2f} → {bs:+.2f}.")
        print(f"  → À brancher dans MetaLabelConstruction si le gain de drawdown le justifie.")
    else:
        print("→ Aucun overlay ne réduit le drawdown sans coûter >10 % de Sharpe. "
              "Le drawdown du L/S momentum est structurel ici ; à gérer par le sizing global.")
    print("\nRappel : overlays causaux (dé-risque sur info passée). Le bootstrap ne corrige")
    print("pas le biais de survie. Le vol-target cap2 peut lever → décision de risque à part.")


if __name__ == "__main__":
    main()
