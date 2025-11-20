"""Exemple complet: backtest + optimisation + walk-forward + rapport.

Ce script peut être exécuté en local. Si yfinance n'est pas disponible ou si
l'API est limitée, fournissez vos propres DataFrames.
"""
from __future__ import annotations

import os
from typing import Dict

import numpy as np
import pandas as pd

from financial_analyzer.backtesting.backtest_runner import (
    load_data,
    run,
    optimize,
    walk_forward_analysis,
    generate_report,
)


def _make_synth_prices(tickers, periods=252):
    np.random.seed(42)
    idx = pd.date_range("2024-01-01", periods=periods, freq="B")
    out: Dict[str, pd.DataFrame] = {}
    for i, t in enumerate(tickers):
        rets = np.random.normal(0.0005 + 0.0001 * i, 0.01 + 0.002 * i, len(idx))
        prices = 100 * (1 + pd.Series(rets, index=idx)).cumprod()
        out[t] = pd.DataFrame({"Close": prices}, index=idx)
    return out


def main():
    tickers = ["AAPL", "MSFT", "GOOG"]
    start, end = "2024-01-01", "2024-12-31"

    # 1) Charger les données
    data = load_data(tickers, start, end)
    if not data:
        # fallback synthétique si yfinance indisponible
        data = _make_synth_prices(tickers)

    # 2) Backtest simple
    res = run(data, lookback_days=60, forecast_horizon=5)
    print(generate_report(res))

    # 3) Optimisation simple
    results = optimize(data)
    best = results[0]
    print("\n# Best params (grid-search):")
    sorted_metrics = dict(sorted(best.metrics.items(), key=lambda kv: kv[0]))
    for k, v in best.params.items():
        print(f"- {k}: {v}")
    for k, v in sorted_metrics.items():
        print(f"- {k}: {v:.4f}")

    # 4) Walk-forward analysis
    wfa = walk_forward_analysis(data)
    print("\n# Walk-Forward Summary:")
    print(f"Mean test return: {wfa['test_return_mean']:.4f}")
    print(f"Mean test sharpe: {wfa['test_sharpe_mean']:.4f}")

    # 5) Rapport final (markdown)
    report = generate_report(best)
    with open("finbot_backtest_report.md", "w") as f:
        f.write(report)
    print("\nReport saved to finbot_backtest_report.md")


if __name__ == "__main__":
    main()
