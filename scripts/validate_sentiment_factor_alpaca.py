"""Valide un facteur de **sentiment de presse** point-in-time via le portail.

Sentiment Polygon (natif, avec ``published_utc`` → PIT) + prix Alpaca. Le facteur
« sentiment net moyen sur fenêtre glissante » passe le portail à double critère
(IC t > 2 ET Sharpe net > 0, coûts calibrés). Fidèle à la discipline du projet :
le sentiment n'entre dans la décision **que** s'il prouve un edge OOS.

⚠️ Le sentiment natif Polygon n'existe que sur les articles récents (~2024+) et le
quota (5 req/min) borne l'échelle : viser une fenêtre récente + petit univers.

Usage::

    python scripts/validate_sentiment_factor_alpaca.py --limit 15 --start 2024-06-01
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from financial_analyzer.backtest.classic_factors import daily_returns
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.backtest.validation_gate import evaluate_signal_gate
from financial_analyzer.data.alpaca_history import load_or_fetch
from financial_analyzer.data.polygon_news_sentiment import (
    NewsSentimentLoader,
    build_sentiment_panel,
)

UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "V",
            "KO", "XOM", "CVX", "JNJ", "PG", "WMT", "HD", "BAC", "DIS", "NFLX", "AMD"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2024-06-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--window", type=int, default=30, help="Fenêtre sentiment (jours).")
    ap.add_argument("--splits", type=int, default=3)
    ap.add_argument("--rebalance", type=int, nargs="+", default=[5, 21])
    ap.add_argument("--cache", default="/tmp/polygon_news_sentiment.parquet")
    args = ap.parse_args()

    universe = UNIVERSE[:args.limit]
    print(f"Prix Alpaca ({len(universe)} titres) {args.start}..{args.end}…")
    prices = load_or_fetch(universe, args.start, args.end, cache_path="/tmp/alpaca_sent_prices.csv")
    prices = prices.dropna(axis=1, thresh=int(0.6 * len(prices))).ffill().dropna(axis=1, how="any")
    print(f"Panel prix: {prices.shape[0]} jours × {prices.shape[1]} titres")

    cache = Path(args.cache)
    if cache.exists():
        long = pd.read_parquet(cache)
        print(f"Sentiment (cache {cache}): {len(long)} articles notés.")
    else:
        print("Sentiment Polygon News (published_utc + insights)… (quota 5 req/min)")
        long = NewsSentimentLoader(source="polygon", allow_synthetic_fallback=False).load(
            list(prices.columns), start=args.start, end=args.end)
        long.to_parquet(cache)
    print(f"{len(long)} articles notés, {long['ticker'].nunique()} titres avec sentiment.\n")

    panel = build_sentiment_panel(long, pd.DatetimeIndex(prices.index), window_days=args.window)
    panel = panel.reindex(columns=prices.columns)
    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()

    print("=" * 80)
    print(f"VALIDATION FACTEUR SENTIMENT (point-in-time) — {prices.shape[1]} titres, "
          f"{args.splits} fenêtres OOS, fenêtre {args.window}j, coûts calibrés")
    print("=" * 80)
    print(f"\n  couverture sentiment : {panel.notna().mean().mean():.1%} des cases\n")
    print(f"  {'reb':>4} {'IC':>8} {'t(IC)':>7} {'netSharpe':>10} {'turnover':>9}  verdict")
    passed_any = False
    for reb in args.rebalance:
        try:
            v = evaluate_signal_gate("news_sentiment", panel, returns, cost_model=cost,
                                     rebalance_every=reb, n_splits=args.splits)
        except Exception as e:  # noqa: BLE001
            print(f"  {reb:>4}  échec: {e}")
            continue
        flag = "✅ VALIDÉ" if v.passed else "—"
        print(f"  {reb:>4} {v.ic_mean:+.4f} {v.ic_t_stat:+7.2f} {v.net_sharpe:+10.2f} "
              f"{v.avg_turnover:9.2f}  {flag}")
        passed_any = passed_any or v.passed

    print("\n--- Verdict ---")
    if passed_any:
        print("  Le sentiment passe le portail → candidat au registre VALIDATED_SIGNALS.")
    else:
        print("  Le sentiment NE passe PAS le portail sur cette fenêtre. Honnête :")
        print("  disposer du sentiment ≠ edge tradeable. Ne pas l'inscrire à la décision.")


if __name__ == "__main__":
    main()
