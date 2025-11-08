"""Tests for PerformanceAnalyzer (8 tests)."""
import pytest
import pandas as pd
import numpy as np

from financial_analyzer.analytics.performance_analyzer import PerformanceAnalyzer


def make_returns(n=100):
    np.random.seed(123)
    idx = pd.date_range('2024-01-01', periods=n, freq='D')
    return pd.Series(np.random.randn(n) / 100, index=idx)


def test_init_defaults():
    analyzer = PerformanceAnalyzer()
    assert analyzer.risk_free_rate == 0.02
    assert analyzer.periods_per_year == 252


def test_init_invalid_params():
    with pytest.raises(ValueError):
        PerformanceAnalyzer(risk_free_rate=-0.01)
    with pytest.raises(ValueError):
        PerformanceAnalyzer(periods_per_year=0)


def test_analyze_returns_complete():
    analyzer = PerformanceAnalyzer()
    port = make_returns(120)
    bench = make_returns(120) * 0.8
    trades = pd.DataFrame({'PnL':[100, -50, 80]})
    result = analyzer.analyze_returns(port, bench, trades)
    assert 'returns' in result and 'risk' in result and 'ratios' in result
    assert 'benchmark' in result and 'trades' in result


def test_drawdown_calculation():
    analyzer = PerformanceAnalyzer()
    r = pd.Series([0.1, -0.2, 0.05, -0.1], index=pd.date_range('2024-01-01', periods=4))
    dd_series, max_dd, peak, trough = analyzer.calculate_drawdown(r)
    assert isinstance(dd_series, pd.Series)
    assert max_dd <= 0.0


def test_var_cvar_calculation():
    analyzer = PerformanceAnalyzer()
    r = make_returns(200)
    var, cvar = analyzer.calculate_var_cvar(r, confidence=0.95)
    assert var <= 0
    assert cvar <= 0


def test_var_cvar_invalid_confidence():
    analyzer = PerformanceAnalyzer()
    with pytest.raises(ValueError):
        analyzer.calculate_var_cvar(make_returns(100), confidence=0.5)


def test_rolling_metrics():
    analyzer = PerformanceAnalyzer()
    r = make_returns(50)
    roll = analyzer.calculate_rolling_metrics(r, window=10)
    assert set(roll.columns) == {'rolling_return','rolling_volatility'}


def test_benchmark_comparison():
    analyzer = PerformanceAnalyzer()
    port = make_returns(100)
    bench = make_returns(100) * 0.7
    comp = analyzer.compare_to_benchmark(port, bench)
    assert 'alpha_annual' in comp and 'beta' in comp and 'tracking_error' in comp


def test_trade_stats_included():
    analyzer = PerformanceAnalyzer()
    port = make_returns(60)
    trades = pd.DataFrame({'PnL':[10, -5, 8, -1, 3]})
    res = analyzer.analyze_returns(port, None, trades)
    assert 'trades' in res and res['trades']['trades_count'] == 5


def test_edge_case_empty_returns():
    analyzer = PerformanceAnalyzer()
    res = analyzer.analyze_returns(pd.Series(dtype=float), None, None)
    assert res['returns'] == {}
