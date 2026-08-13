"""Stat-arb par paires sur données réelles — edge + décorrélation au momentum.

Backtest walk-forward de la stratégie paires (cointégration → z-score du spread,
mean-reversion) sur les large-caps Alpaca, coûts calibrés. Question centrale
(Grinold-Kahn) : c'est une **famille mean-reversion**, censée être **décorrélée du
momentum** → un vrai pari indépendant. On mesure Sharpe net, drawdown, nb de paires,
et surtout la **corrélation aux rendements du momentum**.

⚠️ Univers Alpaca = titres encore cotés (biais de survie). Sur ~80 large-caps, les
paires cointégrées stables sont peu nombreuses — plafond de données probable.

Usage::

    python scripts/run_pairs_trading_alpaca.py
    python scripts/run_pairs_trading_alpaca.py --form 252 --trade 63 --max-pairs 15
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.pairs_trading import backtest_pairs
from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
from financial_analyzer.data.alpaca_history import load_or_fetch

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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--form", type=int, default=252)
    ap.add_argument("--trade", type=int, default=63)
    ap.add_argument("--max-pairs", type=int, default=15)
    ap.add_argument("--corr-min", type=float, default=0.7)
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    cost = CostModel.alpaca_equities()
    print("Backtest paires (walk-forward, sélection par cointégration)…")
    res = backtest_pairs(prices, form=args.form, trade=args.trade,
                         max_pairs=args.max_pairs, corr_min=args.corr_min,
                         cost_rate=cost.cost_rate)

    # Momentum pour la corrélation (famille tendance).
    factors = compute_classic_factors(prices)
    returns = daily_returns(prices)
    mom = evaluate_signal(factors["momentum_12_1"], returns, cost_model=cost,
                          rebalance_every=10).net_equity_curve.pct_change().dropna()
    pr = res["net_returns"]
    idx = pr.index.intersection(mom.index)
    corr = float(np.corrcoef(pr.loc[idx], mom.loc[idx])[0, 1]) if len(idx) > 20 else float("nan")

    print("\n" + "=" * 74)
    print("STAT-ARB PAIRES — edge & décorrélation")
    print("=" * 74)
    print(f"\n  Fenêtres walk-forward       : {res['n_windows']}")
    print(f"  Paires actives (moyenne)    : {res['avg_pairs']:.1f}")
    print(f"  Sharpe net                  : {res['sharpe']:+.2f}")
    print(f"  Rendement annualisé net     : {res['ann_return_pct']:+.1f}%")
    print(f"  Max drawdown                : {res['max_drawdown_pct']:+.1f}%")
    print(f"  Corrélation ↔ momentum      : {corr:+.2f}")

    # --- Payoff Grinold-Kahn : combo risk-weighted momentum + paires ---
    def _sh(x):
        x = x.dropna()
        sd = x.std(ddof=1)
        return float(x.mean() / sd * np.sqrt(252)) if len(x) > 1 and sd > 0 else 0.0

    m, p = mom.loc[idx], pr.loc[idx]
    wm = 1.0 / (m.std(ddof=1) or 1.0)
    wp = 1.0 / (p.std(ddof=1) or 1.0)
    combo = (wm * m + wp * p) / (wm + wp)  # inverse-vol (risk-weighting)
    print("\n  --- Combinaison risk-weighted (payoff de breadth) ---")
    print(f"  Sharpe momentum seul        : {_sh(m):+.2f}")
    print(f"  Sharpe paires seul          : {_sh(p):+.2f}")
    print(f"  Sharpe COMBO (inverse-vol)  : {_sh(combo):+.2f}")

    print("\n--- Lecture honnête ---")
    if res["sharpe"] > 0 and abs(corr) < 0.3:
        print("  Edge positif ET décorrélé du momentum -> vrai 2e pari (breadth).")
        print("  À combiner par risk-weighting SI l'edge passe le portail sur univers large.")
    elif abs(corr) < 0.3:
        print("  Décorrélé du momentum (bien) mais edge faible/négatif ici : peu de paires")
        print("  cointégrées stables sur ~80 large-caps -> plafond de données attendu.")
    else:
        print("  Corrélé au momentum ou edge absent : peu concluant sur cet univers.")
    print("  Infra réutilisable telle quelle sur un univers large sans biais de survie.")


if __name__ == "__main__":
    main()
