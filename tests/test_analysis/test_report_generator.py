"""Tests for ReportGenerator (7 tests)."""
import pytest
import pandas as pd
import numpy as np
import os

from financial_analyzer.analytics.report_generator import ReportGenerator
from financial_analyzer.analytics.performance_analyzer import PerformanceAnalyzer
from financial_analyzer.integration.performance_attribution import AttributionResult


def make_returns(n=50):
    np.random.seed(42)
    idx = pd.date_range('2024-01-01', periods=n, freq='D')
    return pd.Series(np.random.randn(n)/100, index=idx)


def test_report_generator_init():
    rg = ReportGenerator()
    assert isinstance(rg, ReportGenerator)


def test_generate_report_basic():
    rg = ReportGenerator()
    analyzer = PerformanceAnalyzer()
    port = make_returns(60)
    bench = make_returns(60)
    metrics = analyzer.analyze_returns(port, bench, None)
    report = rg.generate_report(port, bench, None, None, metrics=metrics)
    assert "# Performance Report" in report
    assert "Total Return" in report


def test_generate_report_with_attribution():
    rg = ReportGenerator()
    analyzer = PerformanceAnalyzer()
    port = make_returns(60)
    metrics = analyzer.analyze_returns(port, None, None)
    attribution = AttributionResult(
        sentiment_pct=30.0,
        technical_pct=40.0,
        allocation_pct=20.0,
        timing_pct=10.0,
        total_pnl=1000.0,
        residual_pct=0.0,
        trade_count=25,
        attribution_method='brinson'
    )
    report = rg.generate_report(port, None, None, attribution_result=attribution, metrics=metrics)
    assert "Performance Attribution" in report
    assert "Sentiment:" in report


def test_compare_strategies_table():
    rg = ReportGenerator()
    analyzer = PerformanceAnalyzer()
    port = make_returns(40)
    metrics = analyzer.analyze_returns(port, None, None)
    table = rg.compare_strategies({'StratA': metrics, 'StratB': metrics})
    assert "Strategy" in table and "Total Return %" in table


def test_save_report(tmp_path):
    rg = ReportGenerator()
    report = "# Test Report\nContent"
    filepath = tmp_path / "report.md"
    rg.save_report(report, str(filepath))
    assert os.path.exists(filepath)


def test_generate_report_empty_trades():
    rg = ReportGenerator()
    analyzer = PerformanceAnalyzer()
    port = make_returns(30)
    metrics = analyzer.analyze_returns(port, None, pd.DataFrame())
    report = rg.generate_report(port, None, pd.DataFrame(), None, metrics=metrics)
    assert "Trade Statistics" not in report or "Trades:" in report


def test_generate_report_integration_with_analyzer():
    rg = ReportGenerator()
    analyzer = PerformanceAnalyzer()
    port = make_returns(55)
    metrics = analyzer.analyze_returns(port, None, None)
    report = rg.generate_report(port, None, None, None, metrics=metrics)
    assert "Sharpe" in report and "Max Drawdown" in report
