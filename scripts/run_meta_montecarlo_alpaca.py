"""Monte-Carlo (block bootstrap) du book méta-labelé — distribution du résultat.

Le DSR corrige le biais de sélection (point ~0.6) ; il ne dit pas la *dispersion*
de ce qu'on aurait observé si l'histoire s'était rejouée un peu différemment. On
ré-échantillonne la série de rendements réelle du book méta (RICH, cadence adoptée
reb=21) par blocs circulaires — non-paramétrique, préserve queues et autocorrélation
— et on rapporte médiane + intervalle 5-95 % du Sharpe, du rendement annualisé et du
max drawdown, plus P(Sharpe>0) et P(période positive).

Usage::

    python scripts/run_meta_montecarlo_alpaca.py --cache /tmp/yahoo_long.csv --reb 21
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
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--block", type=int, default=21)
    ap.add_argument("--cache", default="/tmp/yahoo_long.csv")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.meta_labeling import (
        META_FEATURES_RICH,
        confirm_meta_labeling,
        regime_features,
    )
    from financial_analyzer.backtest.robustness import block_bootstrap_metrics
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
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres | reb={args.reb}")

    # Série de rendements réelle du book méta (RICH) à la cadence adoptée.
    print("Reconstruction de la série de rendements du book méta…", flush=True)
    c = confirm_meta_labeling(scores, returns, rich, rebalance_every=args.reb, horizon=args.reb,
                              cost_rate=cost.cost_rate, feature_names=META_FEATURES_RICH,
                              n_random=1, n_perm=1)
    r = c.meta_returns
    print(f"Série : {len(r)} jours de rendement net | Sharpe réalisé {c.meta_sharpe:+.2f}\n")

    m = block_bootstrap_metrics(r, n_boot=args.n_boot, block=args.block)

    print("=" * 78)
    print(f"MONTE-CARLO (block bootstrap, {int(m['n_boot'])} chemins, blocs de {int(m['block'])} j)")
    print("=" * 78)
    print(f"\n  {'métrique':22} {'médiane':>9} {'5 %':>9} {'95 %':>9}")
    print(f"  {'Sharpe annualisé':22} {m['sharpe_median']:>+9.2f} {m['sharpe_p05']:>+9.2f} {m['sharpe_p95']:>+9.2f}")
    print(f"  {'Rendement an. net':22} {m['ann_ret_median']:>+8.1%} {m['ann_ret_p05']:>+8.1%} {m['ann_ret_p95']:>+8.1%}")
    print(f"  {'Max drawdown':22} {m['maxdd_median']:>+8.1f}% {m['maxdd_p05']:>+8.1f}% {'(pire 1% '+format(m['maxdd_worst'],'+.1f')+'%)':>9}")
    print("\n  Probabilités :")
    print(f"    P(Sharpe > 0)            = {m['prob_sharpe_pos']:.1%}")
    print(f"    P(période nette positive) = {m['prob_period_pos']:.1%}")

    print("\n" + "-" * 78)
    robust = m["sharpe_p05"] > 0 and m["prob_sharpe_pos"] >= 0.9
    if robust:
        print(f"→ Le book méta est ROBUSTE au ré-échantillonnage : Sharpe positif dans "
              f"{m['prob_sharpe_pos']:.0%} des chemins, borne basse 5 % = {m['sharpe_p05']:+.2f} > 0.")
    else:
        print(f"→ Résultat DISPERSÉ : la borne basse 5 % du Sharpe = {m['sharpe_p05']:+.2f} "
              f"(P(Sharpe>0)={m['prob_sharpe_pos']:.0%}). L'edge tient en médiane mais l'incertitude "
              f"est réelle — cohérent avec le DSR ~0.6. Le drawdown peut atteindre "
              f"{m['maxdd_worst']:+.0f}% (pire 1%).")
    print("\nRappel : bootstrap = incertitude d'échantillonnage sur CE panel (survivants).")
    print("Il ne corrige PAS le biais de survie — seule une base sans biais le fera.")


if __name__ == "__main__":
    main()
