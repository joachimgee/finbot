"""Markdown Report Generator (Module 8).

Generates human-readable performance reports combining analytics and attribution.

- Uses PerformanceAnalyzer for metrics
- Integrates with existing PerformanceAttributor (do not duplicate)
- Supports multi-strategy comparison tables

Example
-------
>>> rg = ReportGenerator()
>>> report = rg.generate_report(portfolio_returns, benchmark_returns, trades, attribution_result)
>>> rg.save_report(report, 'report.md')
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import os
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """Generate Markdown performance reports.

    Methods
    -------
    generate_report(portfolio_returns, benchmark, trades, attribution_result) -> str
        Build a comprehensive Markdown report string.
    compare_strategies(strategies_dict) -> str
        Build a Markdown table comparing multiple strategy metrics.
    save_report(report, filepath) -> None
        Save report string to a file.
    """

    def __init__(self) -> None:
        logger.info("ReportGenerator initialized")

    def generate_report(
        self,
        portfolio_returns: pd.Series,
        benchmark: Optional[pd.Series],
        trades: Optional[pd.DataFrame],
        attribution_result: Optional[Any] = None,
        metrics: Optional[Dict[str, Any]] = None,
        title: str = "Performance Report",
    ) -> str:
        """Generate a Markdown report from analytics and attribution.

        Parameters
        ----------
        portfolio_returns : pd.Series
            Portfolio periodic returns
        benchmark : pd.Series, optional
            Benchmark periodic returns
        trades : pd.DataFrame, optional
            Trades data
        attribution_result : Any, optional
            Result from PerformanceAttributor.attribute_returns
        metrics : dict, optional
            Pre-computed metrics from PerformanceAnalyzer.analyze_returns
        title : str, default 'Performance Report'

        Returns
        -------
        str
            Markdown-formatted report
        """
        lines: List[str] = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append("## Executive Summary")
        if metrics:
            ret = metrics.get('returns', {})
            risk = metrics.get('risk', {})
            ratios = metrics.get('ratios', {})
            lines.append(f"- Total Return: {ret.get('total_return_pct', 0.0):.2f}%")
            lines.append(f"- Annualized Return: {ret.get('annualized_return_pct', 0.0):.2f}%")
            lines.append(f"- Volatility (ann.): {risk.get('volatility_annual_pct', 0.0):.2f}%")
            lines.append(f"- Max Drawdown: {risk.get('max_drawdown_pct', 0.0):.2f}%")
            lines.append(f"- Sharpe: {ratios.get('sharpe_ratio', 0.0):.2f}")
            lines.append(f"- Sortino: {ratios.get('sortino_ratio', 0.0):.2f}")
            lines.append(f"- Calmar: {ratios.get('calmar_ratio', 0.0):.2f}")
        else:
            lines.append("No metrics provided.")
        lines.append("")

        if metrics and metrics.get('benchmark'):
            b = metrics['benchmark']
            lines.append("## Benchmark Comparison")
            lines.append(f"- Alpha (annual): {b.get('alpha_annual', 0.0):.4f}")
            lines.append(f"- Beta: {b.get('beta', 0.0):.4f}")
            lines.append(f"- Tracking Error: {b.get('tracking_error', 0.0):.4f}")
            lines.append("")

        if metrics and metrics.get('trades'):
            t = metrics['trades']
            lines.append("## Trade Statistics")
            lines.append(f"- Trades: {t.get('trades_count', 0)}")
            lines.append(f"- Win Rate: {t.get('win_rate_pct', 0.0):.2f}%")
            lines.append(f"- Avg Win: {t.get('avg_win', 0.0):.2f}")
            lines.append(f"- Avg Loss: {t.get('avg_loss', 0.0):.2f}")
            lines.append(f"- Profit Factor: {t.get('profit_factor', 0.0):.2f}")
            lines.append(f"- Total PnL: {t.get('total_pnl', 0.0):.2f}")
            lines.append("")

        if attribution_result is not None:
            lines.append("## Performance Attribution")
            try:
                lines.append(f"- Sentiment: {getattr(attribution_result, 'sentiment_pct', 0.0):.2f}%")
                lines.append(f"- Technical: {getattr(attribution_result, 'technical_pct', 0.0):.2f}%")
                lines.append(f"- Allocation: {getattr(attribution_result, 'allocation_pct', 0.0):.2f}%")
                lines.append(f"- Timing: {getattr(attribution_result, 'timing_pct', 0.0):.2f}%")
                lines.append(f"- Residual: {getattr(attribution_result, 'residual_pct', 0.0):.2f}%")
                lines.append(f"- Trades Analyzed: {getattr(attribution_result, 'trade_count', 0)}")
            except Exception as e:
                logger.error(f"Attribution formatting failed: {e}")
                lines.append("Attribution data unavailable.")
            lines.append("")

        lines.append("## Notes")
        lines.append("- All metrics are computed on provided returns series.")
        lines.append("- Attribution uses existing PerformanceAttributor.")

        return "\n".join(lines)

    def compare_strategies(self, strategies_dict: Dict[str, Dict[str, Any]]) -> str:
        """Build a Markdown comparison table for multiple strategies.

        strategies_dict = {
            'StrategyA': metrics_dict,
            'StrategyB': metrics_dict,
        }
        """
        headers = [
            "Strategy", "Total Return %", "Ann. Return %", "Volatility %",
            "Max DD %", "Sharpe", "Sortino", "Calmar"
        ]
        rows = ["| " + " | ".join(headers) + " |"]
        rows.append("|" + "---|" * (len(headers)) )
        for name, metrics in strategies_dict.items():
            ret = metrics.get('returns', {})
            risk = metrics.get('risk', {})
            ratios = metrics.get('ratios', {})
            rows.append(
                f"| {name} | {ret.get('total_return_pct', 0.0):.2f} | {ret.get('annualized_return_pct', 0.0):.2f} | "
                f"{risk.get('volatility_annual_pct', 0.0):.2f} | {risk.get('max_drawdown_pct', 0.0):.2f} | "
                f"{ratios.get('sharpe_ratio', 0.0):.2f} | {ratios.get('sortino_ratio', 0.0):.2f} | {ratios.get('calmar_ratio', 0.0):.2f} |"
            )
        return "\n".join(rows)

    def save_report(self, report: str, filepath: str) -> None:
        """Save report string to file (creates directory if needed)."""
        try:
            os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Report saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise

__all__ = ["ReportGenerator"]
