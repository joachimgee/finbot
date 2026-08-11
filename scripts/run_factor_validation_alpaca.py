"""Valide les facteurs classiques sur de vraies données **Alpaca** (out-of-sample).

Pendant que ``run_factor_validation.py`` vise Polygon, celui-ci utilise le feed
Alpaca (clés ``ALPACA_API_KEY`` / ``ALPACA_SECRET_KEY``, fallback ``APCA_*``) :
il récupère un panel de clôtures ajustées, calcule les 8 facteurs price-based,
et affiche leur IC / Sharpe net hors échantillon, coûts inclus — le test « edge
réel ou bruit ».

Usage::

    python scripts/run_factor_validation_alpaca.py            # univers curé (~120)
    python scripts/run_factor_validation_alpaca.py --broad 1200  # univers large FinanceDatabase
    python scripts/run_factor_validation_alpaca.py --start 2023-08-01 --end 2026-07-31

Un IC significatif exige |t| > ~2. En-dessous, le signal n'est pas distinguable
du bruit sur l'échantillon. Attention : un IC significatif n'implique pas la
profitabilité nette de coûts — calibrer la période de rebalancement en aval.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.factor_combiner import walk_forward_combine
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.data.alpaca_history import fetch_daily_history, load_or_fetch

# Univers curé par défaut : large-caps US liquides, multi-secteurs.
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
    """Univers large depuis FinanceDatabase, filtré aux symboles US propres."""
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
                    help="Si >0, univers large FinanceDatabase capé à cette taille (Alpaca filtre les liquides).")
    ap.add_argument("--cache", default="/tmp/alpaca_factor_universe.csv")
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
    # Garder les titres avec >=80% d'historique (liquides/tradables réels).
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel prix réel: {prices.shape[0]} jours × {prices.shape[1]} tickers\n")

    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()
    out = walk_forward_combine(factors, returns, n_splits=args.splits, cost_model=cost)

    print("=" * 74)
    print(f"VALIDATION WALK-FORWARD OOS — {prices.shape[1]} titres, {out['n_splits']} fenêtres, coûts inclus")
    print("=" * 74)
    print(f"\n  {'facteur':16s} {'IC':>8} {'t(IC)':>7} {'net Sharpe':>11} {'turnover':>9}")
    ranked = sorted(out["per_source"].items(), key=lambda kv: abs(kv[1].ic_t_stat), reverse=True)
    for name, r in ranked:
        flag = " *" if abs(r.ic_t_stat) > 2 else ""
        print(f"  {name:16s} {r.ic_mean:+.4f} {r.ic_t_stat:+7.2f} {r.net_sharpe:+11.2f} {r.avg_turnover:9.2f}{flag}")
    print(f"\n  {'equal_weight':16s} {out['equal_weight'].summary()}")
    print(f"  {'combined':16s} {out['combined'].summary()}")
    print("\n(*) IC significatif : |t| > 2. Rappel : IC significatif n'implique pas")
    print("    profitabilité nette — calibrer la période de rebalancement en aval.")


if __name__ == "__main__":
    main()
