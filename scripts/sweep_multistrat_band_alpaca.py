"""Sweep de la **bande de non-transaction** sur le *book multi-stratégie* réel.

Contrairement à ``run_cost_aware_band_alpaca`` (momentum seul, poids continus), ce
script balaie la bande sur le **book combiné effectivement planifié** — le même
``combined_book`` (momentum + PCA-résiduel + paires, long/short) que
``run_multi_strategy_paper.py``. But : choisir la largeur de bande qui maximise le
**Sharpe net de coûts**, plutôt que de garder le défaut arbitraire de 2 %.

Méthode :

1. On rejoue le book **jour par jour** (walk-forward) : à chaque date, le book
   cible est calculé sur l'historique jusqu'à ce jour inclus. Ce book cible **ne
   dépend pas de la bande** — on le calcule donc **une seule fois** (coûteux : PCA
   + recherche de paires cointégrées par jour) et on le met en cache.
2. Pour chaque bande, on rejoue la **détention** : on applique ``apply_no_trade_band``
   (exactement comme le pipeline live) vs les poids tenus la veille, on mesure le
   turnover, et on calcule le rendement net = brut − turnover × coût Alpaca.

Approximation (identique au sweep momentum) : les poids « tenus » sont ceux fixés
la veille (pas de dérive intra-période modélisée) — l'effet de la bande sur le
turnover est mesuré de façon comparable d'un book à l'autre.

⚠️ Rappel discipline : PCA-résiduel & paires ne sont **pas validés** — ce book
tourne en **paper** uniquement. Ce sweep éclaire un **paramètre de coûts**, il ne
valide pas les familles.

Usage::

    python scripts/sweep_multistrat_band_alpaca.py
    python scripts/sweep_multistrat_band_alpaca.py --bands 0 0.01 0.02 0.03 0.05 0.08
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

from financial_analyzer.backtest.cost_aware import apply_no_trade_band
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.data.alpaca_history import load_or_fetch
from financial_analyzer.trading.multi_strategy_book import combined_book

# Univers du book planifié (miroir de run_multi_strategy_paper.py:UNIVERSE).
UNIVERSE = sorted({
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
    "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
    "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
    "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
})


def _sharpe(r: pd.Series) -> float:
    r = pd.Series(r).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(252)) if len(r) > 1 and sd > 0 else 0.0


def compute_target_books(px: pd.DataFrame, warmup: int, cache: Path) -> pd.DataFrame:
    """Série de books cibles (dates × symboles), calculée une fois puis mise en cache.

    Le book cible d'un jour est indépendant de la bande — le cache permet de
    rebalayer les bandes sans relancer le calcul coûteux (PCA + cointégration).
    """
    if cache.exists():
        tb = pd.read_csv(cache, index_col=0, parse_dates=True)
        if len(tb) == len(px.index) - warmup:
            print(f"Books cibles chargés du cache : {tb.shape[0]} dates × {tb.shape[1]} symboles")
            return tb
        print("Cache des books obsolète (dimensions changées) — recalcul.")
    rows: dict[pd.Timestamp, dict[str, float]] = {}
    dates = px.index
    n = len(dates) - warmup
    for k, i in enumerate(range(warmup, len(dates))):
        rows[dates[i]] = combined_book(px.iloc[: i + 1])
        if (k + 1) % 50 == 0 or k + 1 == n:
            print(f"  book cible {k + 1}/{n} ({str(dates[i])[:10]})", end="\r", flush=True)
    print()
    tb = pd.DataFrame(rows).T.sort_index().fillna(0.0)
    tb.to_csv(cache)
    print(f"Books cibles calculés et mis en cache -> {cache}")
    return tb


def simulate(targets: pd.DataFrame, fwd: pd.DataFrame, cost_rate: float, band: float) -> dict:
    """Rejoue la détention sous une bande donnée ; renvoie turnover, Sharpe, rdt, DD.

    ``apply_no_trade_band`` est appelée exactement comme dans le pipeline live
    (cible et détenu réindexés sur l'**union** des symboles, pour ne pas perdre une
    ligne tenue absente de la cible du jour).
    """
    prev: pd.Series | None = None
    gross_r, net_r, tos = [], [], []
    for dt in targets.index:
        tgt = targets.loc[dt]
        tgt = tgt[tgt.abs() > 1e-12]  # symboles réellement ciblés ce jour
        if prev is None:
            held = tgt
            to = float(tgt.abs().sum())
        else:
            idx = tgt.index.union(prev.index)
            tt = tgt.reindex(idx).fillna(0.0)
            pp = prev.reindex(idx).fillna(0.0)
            held = apply_no_trade_band(tt, pp, band) if band > 0 else tt
            held = held[held.abs() > 1e-12]
            to = float((held.reindex(idx).fillna(0.0) - pp).abs().sum())
        prev = held
        if dt not in fwd.index:
            continue
        f = fwd.loc[dt]
        g = float((held.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum())
        gross_r.append(g)
        net_r.append(g - to * cost_rate)
        tos.append(to)
    net = pd.Series(net_r)
    eq = (1.0 + net).cumprod()
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) else 0.0
    return {
        "turnover": float(np.mean(tos)) if tos else 0.0,
        "gross_sharpe": _sharpe(pd.Series(gross_r)),
        "net_sharpe": _sharpe(net),
        "net_ann": float(net.mean() * 252 * 100.0) if len(net) else 0.0,
        "maxdd": dd,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--bands", type=float, nargs="+",
                    default=[0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12])
    ap.add_argument("--warmup", type=int, default=252,
                    help="Barres d'historique avant le premier book (momentum 12-1 / paires).")
    ap.add_argument("--price-cache", default="/tmp/alpaca_rebalance_sweep.csv")
    ap.add_argument("--book-cache", default="/tmp/multistrat_target_books.csv")
    args = ap.parse_args()

    px = load_or_fetch(UNIVERSE, args.start, args.end, cache_path=args.price_cache)
    px = px[[c for c in UNIVERSE if c in px.columns]]
    px = px.dropna(axis=1, thresh=int(0.8 * len(px))).ffill()
    px = px.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {px.shape[0]} jours × {px.shape[1]} titres  "
          f"({str(px.index.min())[:10]} → {str(px.index.max())[:10]})\n")

    targets = compute_target_books(px, args.warmup, Path(args.book_cache))
    fwd = px.pct_change().shift(-1)
    cost_rate = CostModel.alpaca_equities().cost_rate
    print(f"Coût Alpaca : {cost_rate * 1e4:.1f} bps/unité de turnover  "
          f"| dates de rééq. : {len(targets)}\n")

    print("=" * 78)
    print("BANDE DE NON-TRANSACTION — book multi-stratégie combiné, rééq. quotidien")
    print("=" * 78)
    header = (f"\n  {'bande':>7} {'turnover':>9} {'Sharpe brut':>12} {'Sharpe net':>11} "
              f"{'rdt net an.':>12} {'maxDD':>8}")
    print(header)
    rows = []
    for band in args.bands:
        m = simulate(targets, fwd, cost_rate, band)
        rows.append((band, m))
        print(f"  {band:>7.3f} {m['turnover']:>9.3f} {m['gross_sharpe']:>+12.2f} "
              f"{m['net_sharpe']:>+11.2f} {m['net_ann']:>+11.1f}% {m['maxdd']:>+7.1f}%")

    by_band = dict(rows)
    base = by_band.get(0.0, rows[0][1])
    base_net, base_gross = base["net_sharpe"], base["gross_sharpe"]

    # Garde-fou anti-surapprentissage : ne considérer que les bandes qui PRÉSERVENT
    # le signal (Sharpe brut ≥ 90 % du brut à bande=0). Une bande large « gagne » en
    # Sharpe net en GELANT le book (turnover ~0, brut effondré) — ce gain est un
    # artefact dépendant du chemin, pas un vrai bénéfice cost-aware. On sélectionne
    # donc le meilleur Sharpe net PARMI les bandes à signal préservé.
    gross_floor = 0.90 * base_gross
    eligible = [(b, m) for b, m in rows if m["gross_sharpe"] >= gross_floor]
    best_band, best = max(eligible, key=lambda kv: (kv[1]["net_sharpe"], kv[1]["net_ann"]))
    raw_band, raw = max(rows, key=lambda kv: kv[1]["net_sharpe"])

    print("\n" + "-" * 78)
    print(f"Argmax brut du Sharpe net : bande {raw_band:.3f} (net {raw['net_sharpe']:+.2f}, "
          f"brut {raw['gross_sharpe']:+.2f}, turnover {raw['turnover']:.3f})")
    if raw_band != best_band and raw["gross_sharpe"] < gross_floor:
        print(f"  ⚠️  REJETÉE : brut {raw['gross_sharpe']:+.2f} < {gross_floor:+.2f} "
              f"(90 % du brut à bande=0) — le book est gelé, gain net = artefact.")
    print(f"\nRecommandation (signal préservé, brut ≥ {gross_floor:+.2f}) : "
          f"bande {best_band:.3f}")
    print(f"  Sharpe net {best['net_sharpe']:+.2f} vs {base_net:+.2f} à bande=0  |  "
          f"brut {best['gross_sharpe']:+.2f}  |  turnover {best['turnover']:.3f}  |  "
          f"rdt net {best['net_ann']:+.1f}%")
    if best_band == 0.0:
        print("→ Aucune bande à signal préservé n'améliore le net : garder 0 (viser le cible).")
    else:
        uplift = best["net_sharpe"] - base_net
        verdict = "matériel" if uplift >= 0.10 else "marginal"
        print(f"→ Gain {verdict} ({uplift:+.2f} de Sharpe net). Défaut suggéré pour "
              f"run_multi_strategy_paper.py : --no-trade-band {best_band:g}")
    print("\nLecture : à bande=0 on paie le turnover plein. Une bande > 0 qui remonte le")
    print("Sharpe NET *sans effondrer le brut* paie le cost-aware ; une bande qui gèle le")
    print("book (brut ↓↓, turnover ~0) « gagne » par surapprentissage — écartée. Familles")
    print("PCA/paires NON validées : ce sweep calibre un coût, il ne valide pas le book.")


if __name__ == "__main__":
    main()
