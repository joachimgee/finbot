"""Valide les facteurs classiques sur de vraies données Polygon (out-of-sample).

Récupère un univers liquide sur ~2 ans, calcule momentum/reversal/low_vol, et
lance le combinateur B validé par le harness A. Affiche les IC/Sharpe réels,
nets de coûts, hors échantillon — le vrai test « significatif ou pas ».
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.data.polygon_history import load_or_fetch
from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.factor_combiner import walk_forward_combine
from financial_analyzer.backtest.signal_evaluation import CostModel

UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM",
    "BAC", "XOM", "CVX", "JNJ", "PFE", "UNH", "PG", "KO",
    "WMT", "HD", "DIS", "V", "MA", "INTC", "AMD", "NFLX",
]
START, END = "2024-08-01", "2026-07-31"
CACHE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/polygon_universe.csv"


def main() -> None:
    print(f"Chargement {len(UNIVERSE)} tickers {START}..{END} (cache={CACHE})")
    prices = load_or_fetch(UNIVERSE, START, END, cache_path=CACHE)
    if prices.empty:
        print("Aucune donnée récupérée.")
        return
    prices = prices.dropna(axis=1, how="all").ffill().dropna(how="all")
    print(f"Panel prix: {prices.shape[0]} jours × {prices.shape[1]} tickers\n")

    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)

    cost = CostModel(commission_bps=5, slippage_bps=3)  # ~0.08% par unité de turnover
    out = walk_forward_combine(factors, returns, n_splits=5, cost_model=cost)

    print("=" * 68)
    print(f"VALIDATION WALK-FORWARD OUT-OF-SAMPLE  ({out['n_splits']} fenêtres, coûts inclus)")
    print("=" * 68)
    print("\nSources seules (OOS):")
    for name, res in out["per_source"].items():
        print(f"  {name:16s} {res.summary()}")
    print("\nBaseline égal-poids (OOS):")
    print(f"  {'equal_weight':16s} {out['equal_weight'].summary()}")
    print("\nCombinateur appris (OOS):")
    print(f"  {'combined':16s} {out['combined'].summary()}")
    print("\nPoids moyens appris (normalisés, somme |w|=1):")
    w = out["avg_weights"]
    wn = w / w.abs().sum() if w.abs().sum() > 0 else w
    for name, val in wn.items():
        print(f"  {name:16s} {val:+.3f}")
    print(
        "\nRappel : un IC significatif exige |t| > ~2. En-dessous, le signal "
        "n'est pas distinguable du bruit sur cet échantillon."
    )


if __name__ == "__main__":
    main()
