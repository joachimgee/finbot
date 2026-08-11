"""Sweep de période de rééquilibrage (P1) sur les facteurs classiques, données Alpaca.

Un IC significatif ne suffit pas : ce qui compte pour trader, c'est le **Sharpe
net de coûts**, et celui-ci dépend fortement de la **fréquence de rééquilibrage**.
Rééquilibrer tous les jours paie le turnover plein ; espacer les rebalances réduit
les coûts au prix d'un signal plus rassis. Ce script balaie
``rebalance_every ∈ {1, 5, 10, 21}`` pour chaque facteur classique, out-of-sample
et coûts inclus, et retient pour chacun la **configuration tradeable** (Sharpe net
maximal, et strictement positif).

Usage::

    python scripts/run_rebalance_sweep_alpaca.py
    python scripts/run_rebalance_sweep_alpaca.py --broad 800 --splits 5
    python scripts/run_rebalance_sweep_alpaca.py --start 2023-08-01 --end 2026-07-31
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.data.alpaca_history import fetch_daily_history, load_or_fetch

REBALANCE_PERIODS = (1, 5, 10, 21)

# Même univers curé que run_factor_validation_alpaca : large-caps US liquides.
DEFAULT_UNIVERSE = sorted(
    {
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
        "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
        "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
        "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
        "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
        "MS", "AXP", "BLK", "C", "SCHW", "T", "VZ", "CMCSA", "PM", "MO",
        "IBM", "NOW", "INTU", "AMAT", "MU", "LRCX", "GILD", "AMGN", "BMY", "DE",
        "MMM", "LMT", "RTX", "SPGI", "ISRG", "MDT", "CVS", "TGT", "COP", "PYPL",
    }
)


def _broad_universe(cap: int) -> list[str]:
    from financial_analyzer.universe.market_selector import UniverseSelector

    raw = UniverseSelector().select_equities(sector=None, country="United States")
    clean = sorted({t for t in raw if re.fullmatch(r"[A-Z]{1,5}", t)})
    return clean[:cap]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--broad", type=int, default=0,
                    help="Si >0, univers large FinanceDatabase capé à cette taille.")
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    if args.broad > 0:
        universe = _broad_universe(args.broad)
        print(f"Univers large: {len(universe)} candidats US propres.")
        prices = fetch_daily_history(universe, args.start, args.end, progress=True)
    else:
        universe = DEFAULT_UNIVERSE
        print(f"Univers curé: {len(universe)} tickers (cache={args.cache}).")
        prices = load_or_fetch(universe, args.start, args.end, cache_path=args.cache)

    if prices.empty:
        print("Aucune donnée récupérée (clés Alpaca présentes ?).")
        return
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel prix réel: {prices.shape[0]} jours × {prices.shape[1]} tickers\n")

    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()
    ns: dict[str, dict[int, float]] = {}
    tov: dict[str, dict[int, float]] = {}
    for name, panel in factors.items():
        ns[name], tov[name] = {}, {}
        for reb in REBALANCE_PERIODS:
            try:
                out = walk_forward_evaluate(
                    panel, returns, n_splits=args.splits, cost_model=cost,
                    rebalance_every=reb,
                )
                oos = out["oos"]
                ns[name][reb] = float(oos.net_sharpe) if oos is not None else float("nan")
                tov[name][reb] = float(oos.avg_turnover) if oos is not None else float("nan")
            except Exception as e:  # noqa: BLE001 - un facteur qui échoue est simplement laissé NaN
                ns[name][reb] = float("nan")
                tov[name][reb] = float("nan")
                print(f"  (⚠️ {name} @ reb={reb} : {e})")

    # --- Matrice Sharpe net par (facteur × période) ---
    header = "  ".join(f"reb={r:>2}" for r in REBALANCE_PERIODS)
    print("=" * 78)
    print(f"SWEEP RÉÉQUILIBRAGE — Sharpe NET de coûts (OOS, {args.splits} fenêtres)")
    print("=" * 78)
    print(f"\n  {'facteur':16s} {header}   meilleur")
    tradeable: list[tuple[str, int, float]] = []
    for name in sorted(ns, key=lambda k: max((v for v in ns[k].values() if not math.isnan(v)), default=float('-inf')), reverse=True):
        cells = "  ".join(
            (f"{ns[name][r]:+5.2f}" if not math.isnan(ns[name][r]) else "  n/a")
            for r in REBALANCE_PERIODS
        )
        valid = {r: v for r, v in ns[name].items() if not math.isnan(v)}
        if valid:
            best_reb = max(valid, key=valid.get)
            best_val = valid[best_reb]
            best = f"reb={best_reb} ({best_val:+.2f})"
            if best_val > 0:
                tradeable.append((name, best_reb, best_val))
        else:
            best = "—"
        print(f"  {name:16s} {cells}   {best}")

    # --- Configurations tradeables retenues ---
    print("\n--- Configurations TRADEABLES (Sharpe net > 0 à la meilleure période) ---")
    if not tradeable:
        print("  Aucune : aucun facteur classique n'est net-positif après coûts sur cette période.")
    else:
        for name, reb, val in sorted(tradeable, key=lambda x: x[2], reverse=True):
            print(f"  {name:16s} rebalance_every={reb:>2}  netSharpe={val:+.2f}  "
                  f"turnover={tov[name][reb]:.2f}")
    print("\nRappel : le turnover chute avec la période ; la meilleure config équilibre")
    print("edge du signal et coûts. À câbler comme rebalance_every du chemin canonique.")


if __name__ == "__main__":
    main()
