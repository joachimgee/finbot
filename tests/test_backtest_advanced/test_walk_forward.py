"""Tests pour WalkForwardAnalyzer."""

import pytest
import numpy as np
import pandas as pd
from src.financial_analyzer.backtest_advanced.walk_forward import WalkForwardAnalyzer, walk_forward_optimize

@pytest.fixture
def simple_data():
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=500, freq='D')
    data = pd.DataFrame({
        'close': 100 * (1 + np.random.normal(0.001, 0.02, 500)).cumprod(),
        'returns': np.random.normal(0.001, 0.02, 500)
    }, index=dates)
    return data

def test_wf_init_rolling(simple_data):
    wf = WalkForwardAnalyzer(simple_data, window_type='rolling', train_size=100, test_size=20, step_size=10)
    assert wf.window_type == 'rolling'
    assert len(wf.splits) > 0

def test_wf_init_expanding(simple_data):
    wf = WalkForwardAnalyzer(simple_data, window_type='expanding', train_size=100, test_size=20, step_size=10)
    assert wf.window_type == 'expanding'
    assert len(wf.splits) > 0

def test_wf_invalid_window_type(simple_data):
    with pytest.raises(ValueError, match="window_type"):
        WalkForwardAnalyzer(simple_data, window_type='invalid')

def test_wf_data_too_small():
    dates = pd.date_range('2020-01-01', periods=50, freq='D')
    data = pd.DataFrame({'close': range(50)}, index=dates)
    with pytest.raises(ValueError, match="too small"):
        WalkForwardAnalyzer(data, train_size=100, test_size=20)

def test_wf_get_split_data(simple_data):
    wf = WalkForwardAnalyzer(simple_data, train_size=100, test_size=20, step_size=50)
    train, test = wf.get_split_data(0)
    assert len(train) == 100
    assert len(test) == 20

def test_wf_run_basic(simple_data):
    def optimize(train_data):
        return {'param': 1.0}
    def backtest(test_data, params):
        return {'total_return': 0.05, 'sharpe': 1.5}
    
    wf = WalkForwardAnalyzer(simple_data, train_size=100, test_size=20, step_size=50)
    results = wf.run(optimize, backtest, save_details=True)
    
    assert 'out_of_sample' in results
    assert 'in_sample' in results
    assert 'overfitting_ratio' in results

def test_wf_run_multiple_splits(simple_data):
    def optimize(train_data):
        return {'sma': 20}
    def backtest(test_data, params):
        return {'total_return': np.random.uniform(-0.05, 0.10), 'sharpe': np.random.uniform(0, 2)}
    
    wf = WalkForwardAnalyzer(simple_data, train_size=100, test_size=20, step_size=30)
    results = wf.run(optimize, backtest)
    
    assert results['n_splits'] > 1
    assert 'avg_return' in results['out_of_sample']

def test_wf_get_summary(simple_data):
    wf = WalkForwardAnalyzer(simple_data, train_size=100, test_size=20, step_size=50)
    summary = wf.get_summary()
    assert isinstance(summary, pd.DataFrame)
    assert len(summary) == len(wf.splits)

def test_walk_forward_optimize_convenience(simple_data):
    def optimize(train_data):
        return {}
    def backtest(test_data, params):
        return {'total_return': 0.03}
    
    results = walk_forward_optimize(simple_data, optimize, backtest, train_size=100, test_size=20)
    assert isinstance(results, dict)
    assert 'out_of_sample' in results
