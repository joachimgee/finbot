"""Momentum sur univers LARGE (small/mid-caps) + gradient de taille — l'angle mort.

Tous les tests précédents portaient sur ~50-80 large-caps. L'ancien FinBot tradait un
panier **small/micro-cap** (payoffs asymétriques, quelques 5×). La littérature (Hong-Lim-
Stein 2000, Fama-French) dit que le momentum est **plus fort en small-cap**. On teste :

1. momentum_12_1 sur un univers large (top N par dollar-volume, plancher bas → small/mid) ;
2. **gradient de taille** : terciles de dollar-volume (grand/moyen/petit) → l'IC/Sharpe
   du momentum croît-il quand on descend en taille ?

⚠️ CAVEATS SCIENTIFIQUES (à lire avant toute conclusion) :
- **Biais de survie MAXIMAL** : Alpaca = titres *encore cotés*. Les small-caps radiées à
  zéro (cf. EPWKF/YGMZF de l'ancien book) sont ABSENTES → résultat gonflé À LA HAUSSE.
- **Coûts** : le modèle 2.5 bps est pour large-caps ; les small/penny ont des spreads de
  1-10 % → la rentabilité nette réelle est BIEN plus basse que l'affichage.
- Donc : test INDICATIF (l'edge apparaît-il plus fort ?), PAS une validation.

Usage::

    python scripts/run_broad_universe_momentum.py --n 2000 --min-dollar 1e6
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=2000, help="Nb de titres (top dollar-volume).")
    ap.add_argument("--min-dollar", type=float, default=1e6, help="Plancher dollar-volume médian.")
    ap.add_argument("--start", default="2022-06-01")
    ap.add_argument("--end", default="2026-08-01")
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--uni-cache", default="/tmp/alpaca_broad_universe.json")
    ap.add_argument("--px-cache", default="/tmp/alpaca_broad_prices.csv")
    args = ap.parse_args()

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
    from financial_analyzer.data.alpaca_history import fetch_daily_history, load_or_fetch
    from financial_analyzer.data.alpaca_universe_liquid import top_liquid_us_equities

    # 1. Univers large (cache).
    import json
    up = Path(args.uni_cache)
    if up.exists():
        universe = json.loads(up.read_text())
        print(f"Univers chargé du cache : {len(universe)} titres")
    else:
        print(f"Classement de l'univers Alpaca (dollar-volume, plancher {args.min_dollar:.0e})…")
        universe = top_liquid_us_equities(n=args.n, min_dollar=args.min_dollar,
                                          cache_path="/tmp/alpaca_dollar_volume_rank.csv")
        up.write_text(json.dumps(universe))
        print(f"Univers : {len(universe)} titres retenus")

    # 2. Prix (cache).
    pxp = Path(args.px_cache)
    if pxp.exists():
        px = pd.read_csv(pxp, index_col=0, parse_dates=True)
        print(f"Prix chargés du cache : {px.shape}")
    else:
        print(f"Fetch prix {args.start}→{args.end} pour {len(universe)} titres (long)…")
        px = fetch_daily_history(universe, args.start, args.end, progress=True)
        px.to_csv(pxp)
    px = px.ffill().dropna(axis=1, thresh=int(0.5 * len(px))).dropna(how="all")
    print(f"Panel exploitable : {px.shape[0]} jours × {px.shape[1]} titres\n")

    cost = CostModel.alpaca_equities()

    def _eval(prices: pd.DataFrame, label: str, long_short: bool = True) -> None:
        if prices.shape[1] < 20 or prices.shape[0] < 300:
            print(f"  {label:26} — trop peu de données")
            return
        factors = compute_classic_factors(prices)
        scores = factors.get("momentum_12_1")
        if scores is None:
            print(f"  {label:26} — momentum indisponible")
            return
        r = evaluate_signal(scores, daily_returns(prices), cost_model=cost,
                            rebalance_every=args.reb, long_short=long_short)
        print(f"  {label:26} {r.ic_t_stat:>+7.2f} {r.net_sharpe:>+8.2f} {r.gross_sharpe:>+8.2f} "
              f"{prices.shape[1]:>7}")

    def _benchmark(prices: pd.DataFrame) -> float:
        b = daily_returns(prices).mean(axis=1)
        return float(b.mean() / b.std() * np.sqrt(252)) if b.std() > 0 else 0.0

    print("=" * 78)
    print(f"MOMENTUM_12_1 — univers LARGE vs gradient de taille (reb={args.reb}, coûts calibrés)")
    print("=" * 78)
    print(f"\n  {'univers':26} {'IC t':>7} {'Sh net':>8} {'Sh brut':>8} {'#titres':>7}")
    print(f"  {'(rappel large-cap ~50)':26} {'+2.56':>7} {'+0.76':>8} {'—':>8} {'50':>7}")
    _eval(px, "LARGE (tout)")

    # Gradient de taille : terciles de liquidité (proxy taille) via l'ordre du classement.
    ordered = [s for s in universe if s in px.columns]  # déjà trié dollar-volume ↓
    t = len(ordered) // 3
    _eval(px[ordered[:t]], "T1 grand (top liquidité)")
    _eval(px[ordered[t:2 * t]], "T2 moyen")
    _eval(px[ordered[2 * t:]], "T3 petit (small-cap)")

    # LONG-ONLY (l'approche de l'ancien système) + benchmark equipondéré (le beta).
    print(f"\n  {'--- LONG-ONLY (top 20%, pas de short) ---':26}")
    _eval(px, "LARGE long-only", long_short=False)
    _eval(px[ordered[2 * t:]], "T3 petit long-only", long_short=False)
    print(f"\n  Benchmark « acheter TOUT équipondéré » (aucun signal) : Sharpe "
          f"{_benchmark(px):+.2f} ← le BETA de l'univers")

    print("\n" + "-" * 78)
    print("Lecture CLÉ : en LONG-ONLY, le momentum a un beau Sharpe — mais si le benchmark")
    print("equipondéré (acheter tout, sans signal) fait AUSSI BIEN ou MIEUX, alors ce Sharpe")
    print("est du BETA (régime haussier), pas de l'alpha du momentum. En L/S (market-neutral,")
    print("qui isole l'alpha), le momentum small-cap PERD (côté short = squeezes/coûts). Et")
    print("tout est gonflé par le biais de survie (radiées absentes — Shumway 1997). L'edge")
    print("répétable reste le momentum L/S large-cap modeste ; le reste est beta + survivorship.")


if __name__ == "__main__":
    main()
