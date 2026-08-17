"""Triple-barrier labeling (AFML ch.3) vs label horizon — améliore-t-il le méta ?

Le méta-modèle a une AUC de ~0.56 : ses labels (« signe du rendement à h jours ») sont
bruités. López de Prado (AFML ch.3) propose le **triple-barrier** : labelliser chaque
pari par la 1ère barrière touchée — profit-take / stop-loss dimensionnés par la vol du
titre, ou temps. Labels moins bruités → le méta pourrait mieux discriminer (AUC ↑) et le
book filtré s'améliorer. On compare les DEUX labelings par les MÊMES contrôles d'artefact
(filtre aléatoire, permutation AUC, tiers), sur 18 ans (RICH, reb=21).

Usage::

    python scripts/run_meta_triple_barrier_alpaca.py --cache /tmp/yahoo_long.csv --reb 21
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
    ap.add_argument("--pt", type=float, default=1.0, help="Multiplicateur profit-take (×σ√h).")
    ap.add_argument("--sl", type=float, default=1.0, help="Multiplicateur stop-loss (×σ√h).")
    ap.add_argument("--n-random", type=int, default=50)
    ap.add_argument("--n-perm", type=int, default=300)
    ap.add_argument("--cache", default="/tmp/yahoo_long.csv")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import (
        META_FEATURES_RICH,
        confirm_meta_labeling,
        regime_features,
    )
    from financial_analyzer.backtest.signal_evaluation import CostModel
    from financial_analyzer.data.alpaca_history import load_or_fetch

    px = load_or_fetch(UNIVERSE, args.start, args.end, cache_path=args.cache)
    px = px[[c for c in UNIVERSE if c in px.columns]].ffill().dropna(axis=1, how="any").dropna(how="all")
    factors = compute_classic_factors(px)
    scores = factors["momentum_12_1"]
    returns = daily_returns(px)
    rich = dict(factors)
    rich.update(regime_features(px, scores))
    cost = CostModel.alpaca_equities()
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres | reb={args.reb}\n")

    def _run(label, method, **kw):
        print(f"[{label}] confirmation…", flush=True)
        c = confirm_meta_labeling(
            scores, returns, rich, rebalance_every=args.reb, horizon=args.reb,
            cost_rate=cost.cost_rate, feature_names=META_FEATURES_RICH,
            n_random=args.n_random, n_perm=args.n_perm, label_method=method, **kw)
        print(f"    AUC={c.auc:.3f} (p={c.auc_perm_pvalue:.3f}) | méta Sh={c.meta_sharpe:+.2f} "
              f"| bat {c.meta_percentile_vs_random:.0f}% aléatoires | raw {c.raw_sharpe:+.2f}")
        return c

    print("=" * 80)
    print("LABELING DU MÉTA — triple-barrier (AFML) vs horizon")
    print("=" * 80 + "\n")
    hz = _run("HORIZON       ", "horizon")
    tb = _run(f"TRIPLE-BARRIER pt={args.pt} sl={args.sl}", "triple_barrier",
              pt_mult=args.pt, sl_mult=args.sl)

    print("\n" + "-" * 80)
    d_auc = tb.auc - hz.auc
    d_sh = tb.meta_sharpe - hz.meta_sharpe
    print(f"  AUC     : {hz.auc:.3f} → {tb.auc:.3f}  ({d_auc:+.3f})")
    print(f"  Sharpe  : {hz.meta_sharpe:+.2f} → {tb.meta_sharpe:+.2f}  ({d_sh:+.2f})")
    if d_auc >= 0.01 and d_sh >= 0.05:
        print("→ Le triple-barrier AMÉLIORE le méta (labels moins bruités). "
              "À adopter dans MetaLabelConstruction (label_method='triple_barrier').")
    elif d_auc <= -0.01 or d_sh <= -0.05:
        print("→ Le triple-barrier DÉGRADE le méta ici — garder le label horizon.")
    else:
        print("→ Équivalent (écart dans le bruit) : le label horizon suffit sur cet univers. "
              "Le triple-barrier aide surtout avec des barrières/exits réels (intraday).")
    print("\nNote : le triple-barrier améliore les LABELS d'entraînement ; le book tient")
    print("toujours jusqu'au rééq. (pas d'exit intra-holding — hors périmètre temps-réel).")


if __name__ == "__main__":
    main()
