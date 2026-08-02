"""Tests unitaires pour Walk-Forward Analyzer.

Couverture:
- WFAWindow creation
- Expanding window generation
- Rolling window generation
- Parameter optimization
- Result aggregation
- Stability analysis
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.walk_forward_analyzer import (
    WalkForwardAnalyzer,
    WFAWindow,
    WFAResult,
)


def make_test_data(tickers: tuple[str, ...] = ("AAA", "BBB"), periods: int = 200) -> Dict[str, pd.DataFrame]:
    """Generate test price data."""
    rng = np.random.default_rng(42)
    idx = pd.date_range("2024-01-01", periods=periods, freq="B")
    data: Dict[str, pd.DataFrame] = {}
    for i, t in enumerate(tickers):
        rets = rng.normal(0.0005 + 0.0001 * i, 0.01, periods)
        prices = 100 * (1 + pd.Series(rets, index=idx)).cumprod()
        data[t] = pd.DataFrame({"Close": prices})
    return data


def test_wfa_initialization():
    """Test WFA initialization and config."""
    data = make_test_data(periods=100)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.8, rolling=False)

    assert wfa.total_length == 100
    assert wfa.train_size == 80
    assert wfa.test_size == 20
    assert wfa.rolling is False


def test_expanding_window_creation():
    """Test expanding window generation."""
    data = make_test_data(periods=150)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.6, rolling=False, step_size=30)
    windows = wfa._create_windows()

    assert len(windows) > 0
    # Expanding: train should grow
    if len(windows) > 1:
        assert windows[1].train_size > windows[0].train_size


def test_rolling_window_creation():
    """Test rolling window generation."""
    data = make_test_data(periods=150)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.5, rolling=True, step_size=25)
    windows = wfa._create_windows()

    assert len(windows) > 0
    # Rolling: train size should be constant
    if len(windows) > 1:
        assert windows[0].train_size == windows[1].train_size


def test_wfa_window_properties():
    """Test WFAWindow properties."""
    data = make_test_data(periods=100)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.8, rolling=False)
    windows = wfa._create_windows()

    w = windows[0]
    assert w.train_size == 80
    assert w.test_size == 20
    assert w.train_start < w.train_end
    assert w.test_start < w.test_end
    assert w.train_end <= w.test_start


def test_run_without_param_grid():
    """Test WFA run without parameter optimization."""
    data = make_test_data(periods=120)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.7, rolling=False, step_size=30)

    result = wfa.run(param_grid={}, optimize_metric='sharpe', strategy_kwargs={'lookback_days': 20})

    assert isinstance(result, WFAResult)
    assert result.total_windows > 0
    assert 'sharpe' in result.is_metrics
    assert 'sharpe' in result.oos_metrics


def test_run_with_param_grid():
    """Test WFA run with parameter optimization."""
    data = make_test_data(periods=150)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.6, rolling=False, step_size=40)

    param_grid = {'rebalance_period': [10, 20]}

    result = wfa.run(param_grid=param_grid, optimize_metric='sharpe', strategy_kwargs={'lookback_days': 20})

    assert result.total_windows > 0
    assert len(result.window_results) == result.total_windows
    # Check param stability calculated
    assert 0.0 <= result.param_stability <= 1.0


def test_wfa_result_summary():
    """Test WFAResult summary generation."""
    result = WFAResult(
        strategy_name="TestStrategy",
        total_windows=3,
        train_periods=[],
        test_periods=[],
        is_metrics={'sharpe': 1.5, 'return': 0.12},
        oos_metrics={'sharpe': 1.2, 'return': 0.10},
        is_oos_degradation={'sharpe': 0.3, 'return': 0.02},
        param_stability=0.67,
        best_params_frequency={"{'rebalance_period': 20}": 2},
    )

    summary = result.summary()
    assert "TestStrategy" in summary
    assert "1.5000" in summary  # IS sharpe
    assert "1.2000" in summary  # OOS sharpe
    assert "0.3000" in summary  # Degradation


def test_param_stability_calculation():
    """Test parameter stability metric."""
    data = make_test_data(periods=150)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.7, rolling=False, step_size=40)

    # Use small grid to get deterministic stability
    param_grid = {'rebalance_period': [15, 25]}

    result = wfa.run(param_grid=param_grid, strategy_kwargs={'lookback_days': 20})

    # Stability should be between 0 and 1
    assert 0.0 <= result.param_stability <= 1.0
    # With small grid, should have some best params
    if result.best_params_frequency:
        assert sum(result.best_params_frequency.values()) > 0


def test_wfa_invalid_train_ratio():
    """Test WFA with invalid train_ratio raises error."""
    data = make_test_data(periods=100)

    with pytest.raises(ValueError, match="train_ratio must be between"):
        WalkForwardAnalyzer(data, train_ratio=1.5)

    with pytest.raises(ValueError, match="train_ratio must be between"):
        WalkForwardAnalyzer(data, train_ratio=0.0)


def test_wfa_empty_data():
    """Test WFA with empty data raises error."""
    with pytest.raises(ValueError, match="Data cannot be empty"):
        WalkForwardAnalyzer({}, train_ratio=0.8)


def test_degradation_metrics():
    """Test degradation calculation."""
    data = make_test_data(periods=120)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.75, rolling=False)

    result = wfa.run(param_grid={}, strategy_kwargs={'lookback_days': 20})

    # Degradation keys should match metrics keys
    assert set(result.is_oos_degradation.keys()) == set(result.is_metrics.keys())

    # Degradation = IS - OOS
    for k in result.is_metrics:
        expected_deg = result.is_metrics[k] - result.oos_metrics[k]
        assert abs(result.is_oos_degradation[k] - expected_deg) < 1e-9


def test_wfa_zero_param_grid():
    """Test WFA with empty parameter grid (no optimization)."""
    data = make_test_data(periods=100)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.8, rolling=False)
    
    result = wfa.run(param_grid={}, optimize_metric='sharpe', strategy_kwargs={'lookback_days': 20})
    
    # No params = stable defaults
    assert result.param_stability == 1.0
    assert len(result.window_results) > 0
    assert all(w['best_params'] == {} for w in result.window_results)


def test_wfa_single_window():
    """Test WFA with very short data (only 1 window possible)."""
    data = make_test_data(periods=60)
    wfa = WalkForwardAnalyzer(data, train_ratio=0.6, rolling=False, step_size=50)
    
    result = wfa.run(param_grid={}, strategy_kwargs={'lookback_days': 10})
    
    # Should have at least 1 window
    assert result.total_windows >= 1
    assert len(result.window_results) >= 1


def test_wfa_misaligned_dataframes():
    """Test WFA with DataFrames of different lengths raises error."""
    rng = np.random.default_rng(42)
    idx1 = pd.date_range("2024-01-01", periods=100, freq="B")
    idx2 = pd.date_range("2024-01-01", periods=120, freq="B")  # Different length
    
    data = {
        "AAA": pd.DataFrame({"Close": 100 * (1 + pd.Series(rng.normal(0.001, 0.01, 100), index=idx1)).cumprod()}),
        "BBB": pd.DataFrame({"Close": 100 * (1 + pd.Series(rng.normal(0.001, 0.01, 120), index=idx2)).cumprod()}),
    }
    
    with pytest.raises(ValueError, match="All DataFrames must have same length"):
        WalkForwardAnalyzer(data, train_ratio=0.8)
