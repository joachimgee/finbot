"""Example: Complete Walk-Forward Analysis.

Demonstrates:
1. Load historical data (or generate synthetic)
2. Run walk-forward analysis (expanding/rolling)
3. Compare in-sample vs out-of-sample
4. Check parameter stability
5. Export results to markdown

Usage:
    python examples/run_walk_forward_analysis.py

Output:
    - Console logs with detailed per-window metrics
    - wfa_report.md with full analysis
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from financial_analyzer.backtest.walk_forward_analyzer import (
    WalkForwardAnalyzer,
    WFAResult,
)
from financial_analyzer.backtest.finbot_strategy import FinBotBacktester, RiskConfig
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def _make_synthetic_data(tickers: list[str], periods: int = 504) -> Dict[str, pd.DataFrame]:
    """Create synthetic OHLC data for demo.

    Generates random walk prices with different drift/volatility per ticker.

    Args:
        tickers: List of ticker symbols
        periods: Number of periods (business days)

    Returns:
        Dict[ticker, DataFrame with 'Close' column and datetime index]

    Example:
        >>> data = _make_synthetic_data(['AAPL', 'MSFT'], periods=252)
        >>> print(data['AAPL'].head())
    """
    np.random.seed(42)
    dates = pd.date_range('2022-01-01', periods=periods, freq='B')

    data: Dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(tickers):
        # Different drift per ticker (simulate different asset returns)
        drift = 0.0003 + 0.0001 * i
        vol = 0.01 + 0.002 * i

        returns = np.random.normal(drift, vol, periods)
        prices = 100 * (1 + pd.Series(returns)).cumprod()

        data[ticker] = pd.DataFrame({'Close': prices.values}, index=dates)

    logger.info(f"Generated synthetic data: {len(tickers)} tickers, {periods} periods")
    return data


def run_expanding_window_wfa(price_data: Dict[str, pd.DataFrame]) -> None:
    """Run expanding window WFA (train grows, test fixed).

    Args:
        price_data: Dictionary of price DataFrames
    """
    logger.info("\n" + "=" * 70)
    logger.info("EXPANDING WINDOW WALK-FORWARD ANALYSIS")
    logger.info("=" * 70)

    wfa = WalkForwardAnalyzer(data=price_data, train_ratio=0.75, rolling=False, step_size=50)

    logger.info("\nConfiguration:")
    logger.info(f"  - Window type: Expanding")
    logger.info(f"  - Train ratio: 75%")
    logger.info(f"  - Step size: 50 bars")
    logger.info(f"  - Total length: {wfa.total_length}")

    # Run WFA with parameter grid
    param_grid = {
        'rebalance_period': [10, 20, 30],
        'max_position': [0.15, 0.2, 0.25],
    }

    logger.info(f"\nParameter grid: {param_grid}")
    logger.info("Running WFA (this may take a minute)...")

    results = wfa.run(
        strategy_class=FinBotBacktester,
        param_grid=param_grid,
        optimize_metric='sharpe',
        strategy_kwargs={'lookback_days': 60, 'forecast_horizon': 5},
    )

    logger.info("\n" + results.summary())

    # Per-window details
    logger.info("\nPer-Window Breakdown:")
    for w in results.window_results:
        logger.info(
            f"  Window {w['window_id']}: "
            f"IS Sharpe={w['is_sharpe']:.2f}, "
            f"OOS Sharpe={w['oos_sharpe']:.2f}, "
            f"Deg={w['is_sharpe'] - w['oos_sharpe']:.2f}, "
            f"Params={w['best_params']}"
        )

    _export_report(results, "wfa_expanding_report.md")


def run_rolling_window_wfa(price_data: Dict[str, pd.DataFrame]) -> None:
    """Run rolling window WFA (train fixed, rolls forward).

    Args:
        price_data: Dictionary of price DataFrames
    """
    logger.info("\n" + "=" * 70)
    logger.info("ROLLING WINDOW WALK-FORWARD ANALYSIS")
    logger.info("=" * 70)

    wfa = WalkForwardAnalyzer(data=price_data, train_ratio=0.7, rolling=True, step_size=60)

    logger.info("\nConfiguration:")
    logger.info(f"  - Window type: Rolling")
    logger.info(f"  - Train ratio: 70%")
    logger.info(f"  - Step size: 60 bars")
    logger.info(f"  - Total length: {wfa.total_length}")

    # Simpler grid for rolling (fewer windows typically)
    param_grid = {'rebalance_period': [15, 25]}

    logger.info(f"\nParameter grid: {param_grid}")
    logger.info("Running WFA...")

    results = wfa.run(
        strategy_class=FinBotBacktester,
        param_grid=param_grid,
        optimize_metric='sharpe',
        strategy_kwargs={'lookback_days': 60},
    )

    logger.info("\n" + results.summary())

    logger.info("\nPer-Window Breakdown:")
    for w in results.window_results:
        logger.info(
            f"  Window {w['window_id']}: "
            f"IS Sharpe={w['is_sharpe']:.2f}, "
            f"OOS Sharpe={w['oos_sharpe']:.2f}, "
            f"Params={w['best_params']}"
        )

    _export_report(results, "wfa_rolling_report.md")


def run_no_optimization_wfa(price_data: Dict[str, pd.DataFrame]) -> None:
    """Run WFA without parameter optimization (default params).

    Args:
        price_data: Dictionary of price DataFrames
    """
    logger.info("\n" + "=" * 70)
    logger.info("WALK-FORWARD ANALYSIS (NO OPTIMIZATION)")
    logger.info("=" * 70)

    wfa = WalkForwardAnalyzer(data=price_data, train_ratio=0.8, rolling=False)

    logger.info("\nConfiguration:")
    logger.info(f"  - Window type: Expanding")
    logger.info(f"  - Train ratio: 80%")
    logger.info(f"  - No parameter optimization (defaults)")

    results = wfa.run(
        strategy_class=FinBotBacktester,
        param_grid={},  # Empty grid = use defaults
        optimize_metric='sharpe',
    )

    logger.info("\n" + results.summary())

    _export_report(results, "wfa_no_opt_report.md")


def _export_report(results: WFAResult, filename: str) -> None:
    """Export WFA results to markdown report.

    Args:
        results: WFAResult object
        filename: Output filename
    """
    report_lines = [
        "# Walk-Forward Analysis Report",
        "",
        f"**Strategy:** {results.strategy_name}",
        f"**Total Windows:** {results.total_windows}",
        "",
        "---",
        "",
        "## Summary Metrics",
        "",
        "### In-Sample Performance",
        "",
    ]

    for k, v in results.is_metrics.items():
        report_lines.append(f"- **{k}**: {v:.4f}")

    report_lines.extend(
        [
            "",
            "### Out-of-Sample Performance",
            "",
        ]
    )

    for k, v in results.oos_metrics.items():
        report_lines.append(f"- **{k}**: {v:.4f}")

    report_lines.extend(
        [
            "",
            "### Degradation (IS - OOS)",
            "",
        ]
    )

    for k, v in results.is_oos_degradation.items():
        is_val = results.is_metrics.get(k, 1.0)
        pct = abs(v) / abs(is_val) * 100 if is_val != 0 else 0.0
        report_lines.append(f"- **{k}**: {v:.4f} ({pct:.1f}% degradation)")

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Robustness Analysis",
            "",
            f"**Parameter Stability:** {results.param_stability:.1%}",
            "",
            "**Most Frequent Parameters:**",
            "",
        ]
    )

    for params_str, count in results.best_params_frequency.items():
        report_lines.append(f"- {params_str}: {count} windows")

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Interpretation Guidelines",
            "",
            "### Parameter Stability",
            "- **> 70%**: Robust parameters across windows",
            "- **50-70%**: Moderate stability, some regime changes",
            "- **< 50%**: High variability, potential overfitting",
            "",
            "### Degradation",
            "- **< 10%**: Excellent generalization",
            "- **10-20%**: Acceptable generalization",
            "- **> 20%**: Poor generalization, overfitting likely",
            "",
            "### Out-of-Sample Sharpe",
            "- **> 1.5**: Strong performance",
            "- **1.0-1.5**: Good performance",
            "- **0.5-1.0**: Acceptable performance",
            "- **< 0.5**: Weak performance",
            "",
            "---",
            "",
            "## Per-Window Results",
            "",
            "| Window | Train Period | Test Period | IS Sharpe | OOS Sharpe | Degradation |",
            "|--------|--------------|-------------|-----------|------------|-------------|",
        ]
    )

    for w in results.window_results:
        train_start, train_end = w['train_period']
        test_start, test_end = w['test_period']
        is_s = w['is_sharpe']
        oos_s = w['oos_sharpe']
        deg = is_s - oos_s

        report_lines.append(
            f"| {w['window_id']} | {train_start.strftime('%Y-%m-%d')} to {train_end.strftime('%Y-%m-%d')} | "
            f"{test_start.strftime('%Y-%m-%d')} to {test_end.strftime('%Y-%m-%d')} | "
            f"{is_s:.2f} | {oos_s:.2f} | {deg:.2f} |"
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            f"*Report generated by FinBot WFA Engine - {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ]
    )

    report = "\n".join(report_lines)

    with open(filename, 'w') as f:
        f.write(report)

    logger.info(f"✓ Report exported to: {filename}")


def main() -> None:
    """Run complete WFA workflow with multiple configurations."""
    logger.info("=" * 70)
    logger.info("FINBOT WALK-FORWARD ANALYSIS - COMPREHENSIVE EXAMPLE")
    logger.info("=" * 70)

    # 1. Create synthetic data
    logger.info("\n1. Creating synthetic price data...")
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
    price_data = _make_synthetic_data(tickers, periods=504)
    logger.info(
        f"✓ Data created: {len(price_data)} assets, "
        f"{len(next(iter(price_data.values())))} periods "
        f"({next(iter(price_data.values())).index[0].strftime('%Y-%m-%d')} to "
        f"{next(iter(price_data.values())).index[-1].strftime('%Y-%m-%d')})"
    )

    # 2. Run expanding window WFA
    run_expanding_window_wfa(price_data)

    # 3. Run rolling window WFA
    run_rolling_window_wfa(price_data)

    # 4. Run without optimization (baseline)
    run_no_optimization_wfa(price_data)

    # Final summary
    logger.info("\n" + "=" * 70)
    logger.info("ANALYSIS COMPLETE!")
    logger.info("=" * 70)
    logger.info("\nGenerated reports:")
    logger.info("  - wfa_expanding_report.md (expanding window)")
    logger.info("  - wfa_rolling_report.md (rolling window)")
    logger.info("  - wfa_no_opt_report.md (no optimization baseline)")
    logger.info("\nKey Takeaways:")
    logger.info("  1. Compare IS vs OOS metrics to detect overfitting")
    logger.info("  2. Parameter stability > 70% indicates robust strategy")
    logger.info("  3. Degradation < 10% suggests good generalization")
    logger.info("  4. OOS Sharpe > 1.0 indicates profitable strategy")
    logger.info("\n" + "=" * 70)


if __name__ == '__main__':
    main()
