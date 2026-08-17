"""Sizing du book méta par la probabilité (Kelly / confidence, AFML ch.10).

López de Prado appaire meta-labeling (ch.3) et bet-sizing (ch.10) : le méta produit
P(gain) par pari ; le book actuel **équipondère** les noms retenus, jetant cette
information. On teste si sizer par P(gain) améliore le book, sur 18 ans (modèle RICH,
horizon = cadence, coûts calibrés) :

* equal      — équipondéré (book actuel), brut = 1 ;
* confidence — ∝ bet_size_from_probability(P) (AFML 10.1), brut = 1 ;
* kelly       — Kelly fractionnaire (f=0.25, ratio gain/perte estimé), brut capé à 1.

Usage::

    python scripts/run_meta_kelly_sizing_alpaca.py --cache /tmp/yahoo_long.csv --reb 21
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
    ap.add_argument("--reb", type=int, default=21, help="Cadence = horizon (défaut 21, mensuel).")
    ap.add_argument("--kelly-fraction", type=float, default=0.25)
    ap.add_argument("--max-train", type=int, default=6000)
    ap.add_argument("--cache", default="/tmp/yahoo_long.csv")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import (
        META_FEATURES_RICH,
        compare_meta_sizing,
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

    res = compare_meta_sizing(
        scores, returns, rich, rebalance_every=args.reb, horizon=args.reb,
        cost_rate=cost.cost_rate, feature_names=META_FEATURES_RICH,
        kelly_fraction=args.kelly_fraction, max_train=args.max_train)

    b = res.pop("_kelly_b", {}).get("win_loss_ratio", float("nan"))
    print("=" * 78)
    print("SIZING DU BOOK MÉTA PAR P(gain) — Kelly / confidence vs équipondéré")
    print("=" * 78)
    print(f"  (ratio gain/perte estimé pour Kelly : b = {b:.2f})\n")
    print(f"  {'schéma':14} {'Sharpe net':>11} {'turnover':>9} {'maxDD':>8} {'brut moy.':>10}")
    order = ["equal", "confidence", "kelly"]
    for name in order:
        m = res[name]
        print(f"  {name:14} {m['net_sharpe']:>+11.2f} {m['turnover']:>9.3f} "
              f"{m['maxdd']:>+7.1f}% {m['avg_gross']:>10.2f}")

    base = res["equal"]["net_sharpe"]
    base_dd = res["equal"]["maxdd"]
    # Un sizing ne « gagne » que s'il relève le Sharpe SANS aggraver le drawdown
    # (sinon c'est juste de la concentration de risque). Seuil matériel : +0.10.
    winners = [n for n in ("confidence", "kelly")
               if res[n]["net_sharpe"] - base >= 0.10 and res[n]["maxdd"] >= base_dd]
    print("\n" + "-" * 78)
    if not winners:
        print("→ Sizer par P(gain) N'AMÉLIORE PAS l'équipondéré de façon robuste : les gains "
              "de Sharpe sont dans le bruit (< 0.10) et/ou payés d'un drawdown pire. Le méta "
              "garde P≈0.5 (AUC 0.56) → conviction trop peu dispersée pour différencier les "
              "tailles. GARDER L'ÉQUIPONDÉRATION.")
    else:
        best = max(winners, key=lambda n: res[n]["net_sharpe"])
        print(f"→ {best} améliore matériellement (Sharpe {res[best]['net_sharpe']:+.2f} vs "
              f"{base:+.2f}, drawdown non aggravé). Candidat : brancher dans MetaLabelConstruction.")
    print("\nNote : le méta ne garde que P ≥ 0.5, tous proches du seuil (AUC ~0.56) → la")
    print("dispersion de conviction est faible ; sur-pondérer peut concentrer le risque")
    print("sans gain net. Verdict empirique ci-dessus, coûts inclus.")


if __name__ == "__main__":
    main()
