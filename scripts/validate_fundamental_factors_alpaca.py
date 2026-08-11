"""Valide les facteurs value/quality **point-in-time** (Polygon + Alpaca), OOS.

Prix réels (Alpaca) + fondamentaux réels **avec dates de dépôt** (Polygon), joints
as-of (aucun look-ahead). Chaque facteur passe le portail de validation à double
critère (IC t > 2 ET Sharpe net > 0), coûts Alpaca calibrés. Les facteurs value
étant lents (mis à jour trimestriellement), on teste aussi une cadence mensuelle.

Usage::

    python scripts/validate_fundamental_factors_alpaca.py
    python scripts/validate_fundamental_factors_alpaca.py --broad 120 --fund-start 2017-01-01
"""
from __future__ import annotations

import argparse
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.backtest.classic_factors import daily_returns
from financial_analyzer.backtest.fundamental_factors import (
    FUNDAMENTAL_FACTORS,
    compute_fundamental_factors,
)
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.backtest.validation_gate import evaluate_signal_gate
from financial_analyzer.data.alpaca_history import fetch_daily_history, load_or_fetch
from financial_analyzer.data.fundamentals_pit_loader import FundamentalsPITLoader

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
    return sorted({t for t in raw if re.fullmatch(r"[A-Z]{1,5}", t)})[:cap]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2020-01-01", help="Début du panel de prix.")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--fund-start", default="2018-06-01",
                    help="Début des fondamentaux (antériorité pour le TTM + as-of).")
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--broad", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0,
                    help="Cape l'univers (utile pour le quota Polygon 5 req/min).")
    ap.add_argument("--rebalance", type=int, nargs="+", default=[1, 21],
                    help="Cadences testées (les facteurs value sont lents).")
    args = ap.parse_args()

    universe = _broad_universe(args.broad) if args.broad > 0 else DEFAULT_UNIVERSE
    if args.limit > 0:
        universe = universe[:args.limit]

    print(f"Prix Alpaca ({len(universe)} titres) {args.start}..{args.end}…")
    if args.broad > 0:
        prices = fetch_daily_history(universe, args.start, args.end, progress=True)
    else:
        prices = load_or_fetch(universe, args.start, args.end, cache_path="/tmp/alpaca_fund_prices.csv")
    prices = prices.dropna(axis=1, thresh=int(0.6 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel prix: {prices.shape[0]} jours × {prices.shape[1]} titres")

    print(f"Fondamentaux Polygon (avec dates de dépôt) depuis {args.fund_start}…")
    loader = FundamentalsPITLoader(source="polygon", allow_synthetic_fallback=False)
    fundamentals = loader.load(list(prices.columns), start=args.fund_start, end=args.end)
    print(f"{len(fundamentals)} dépôts, {fundamentals['ticker'].nunique()} titres avec fondamentaux.\n")

    factors = compute_fundamental_factors(prices, fundamentals)
    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()

    print("=" * 82)
    print(f"VALIDATION FACTEURS VALUE/QUALITY (point-in-time) — {prices.shape[1]} titres, "
          f"{args.splits} fenêtres OOS, coûts Alpaca calibrés")
    print("=" * 82)
    print(f"\n  {'facteur':20s} {'reb':>4} {'IC':>8} {'t(IC)':>7} {'netSharpe':>10} {'turnover':>9}  verdict")
    survivors: list[tuple[str, int, float, float]] = []
    for name in FUNDAMENTAL_FACTORS:
        panel = factors.get(name)
        if panel is None or panel.notna().sum().sum() < 0.2 * panel.size:
            print(f"  {name:20s} — couverture fondamentale insuffisante")
            continue
        for reb in args.rebalance:
            try:
                v = evaluate_signal_gate(name, panel, returns, cost_model=cost,
                                         rebalance_every=reb, n_splits=args.splits)
            except Exception as e:  # noqa: BLE001
                print(f"  {name:20s} {reb:>4}  échec: {e}")
                continue
            flag = "✅ VALIDÉ" if v.passed else "—"
            print(f"  {name:20s} {reb:>4} {v.ic_mean:+.4f} {v.ic_t_stat:+7.2f} "
                  f"{v.net_sharpe:+10.2f} {v.avg_turnover:9.2f}  {flag}")
            if v.passed:
                survivors.append((name, reb, v.ic_t_stat, v.net_sharpe))

    print("\n--- Survivants (IC t > 2 ET Sharpe net > 0 OOS) ---")
    if survivors:
        for name, reb, t, ns in sorted(survivors, key=lambda x: x[3], reverse=True):
            print(f"  {name:20s} reb={reb:>2}  t(IC)={t:+.2f}  netSharpe={ns:+.2f}  "
                  f"-> candidat au registre VALIDATED_SIGNALS")
    else:
        print("  Aucun : aucun facteur value/quality ne passe le double critère sur cette")
        print("  période/univers. (Honnête : posséder des fondamentaux ≠ edge tradeable.)")


if __name__ == "__main__":
    main()
