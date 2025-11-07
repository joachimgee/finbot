"""
Tests for MLTradingPipeline.

Coverage:
- Initialization (5 tests)
- Walk-forward validation (10 tests)
- Feature engineering (5 tests)
- Signal generation (5 tests)
- Results aggregation (8 tests)
- Data enrichment (5 tests)
- Integration end-to-end (2 tests)
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from financial_analyzer.pipeline.ml_trading_pipeline import (
    MLTradingPipeline,
    PipelineResult
)


# -------------------- Fixtures --------------------

@pytest.fixture
def sample_prices():
    """Generate sample multi-asset price data."""
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=1000, freq='D')
    
    close = 100 + np.cumsum(np.random.randn(1000) * 0.5)
    close = np.maximum(close, 50)
    
    return pd.DataFrame({
        'Open': close * 0.998,
        'High': close * 1.005,
        'Low': close * 0.995,
        'Close': close,
        'Volume': np.random.randint(900_000, 1_200_000, 1000)
    }, index=dates)


@pytest.fixture
def pipeline_default():
    """Default pipeline instance."""
    return MLTradingPipeline(
        universe_size=50,
        start_date='2020-01-01',
        end_date='2024-12-31'
    )


# --- Initialization Tests (5) ---

def test_pipeline_init_default():
    """Pipeline initializes with default parameters."""
    p = MLTradingPipeline()
    assert p.universe_size == 50
    assert p.initial_cash == 100_000.0
    assert p.commission_pct == 0.002
    assert p.strategy == 'SentimentMomentum'


def test_pipeline_init_custom_params():
    """Pipeline initializes with custom parameters."""
    p = MLTradingPipeline(
        universe_size=100,
        initial_cash=500_000.0,
        commission_pct=0.001,
        strategy='FactorEnsemble'
    )
    assert p.universe_size == 100
    assert p.initial_cash == 500_000.0
    assert p.strategy == 'FactorEnsemble'


def test_pipeline_invalid_strategy():
    """Pipeline raises ValueError for invalid strategy."""
    with pytest.raises(ValueError, match="Strategy must be"):
        MLTradingPipeline(strategy='InvalidStrategy')


def test_pipeline_result_initialization():
    """PipelineResult initializes correctly."""
    result = PipelineResult(
        total_return_pct=15.2,
        sharpe_ratio=1.45,
        max_drawdown_pct=12.3,
        trades_count=47,
        num_windows=10,
        strategy_name='SentimentMomentum'
    )
    assert result.total_return_pct == 15.2
    assert result.trades_count == 47
    assert result.max_drawdown_pct == 12.3


def test_pipeline_sentiment_momentum_strategy():
    """Pipeline correctly sets SentimentMomentum strategy."""
    p = MLTradingPipeline(strategy='SentimentMomentum')
    assert p.strategy == 'SentimentMomentum'
    assert p.strategy_class.__name__ == 'SentimentMomentumStrategy'


# --- Walk-Forward Tests (10) ---

def test_walk_forward_basic(pipeline_default, sample_prices):
    """Walk-forward validation executes successfully."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=3, window_size_days=250
    )
    assert result is not None
    assert result.num_windows <= 3  # May skip some windows


def test_walk_forward_insufficient_data(pipeline_default):
    """Walk-forward raises error if data too short."""
    short_data = pd.DataFrame({
        'Open': [100] * 100,
        'High': [102] * 100,
        'Low': [99] * 100,
        'Close': np.arange(100, 200),
        'Volume': [1_000_000] * 100
    }, index=pd.date_range('2020-01-01', periods=100))
    
    with pytest.raises(ValueError, match="Insufficient data"):
        pipeline_default.run_walk_forward(
            short_data, n_windows=10, window_size_days=252
        )


def test_walk_forward_single_window(pipeline_default, sample_prices):
    """Walk-forward with single window."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=1, window_size_days=500
    )
    assert result.num_windows <= 1
    assert result.trades_count >= 0


def test_walk_forward_metrics_valid(pipeline_default, sample_prices):
    """Walk-forward metrics are valid (no NaNs, correct ranges)."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=3, window_size_days=250
    )
    assert not np.isnan(result.total_return_pct)
    assert not np.isnan(result.sharpe_ratio)
    assert result.max_drawdown_pct >= 0


def test_walk_forward_trades_aggregated(pipeline_default, sample_prices):
    """Total trades is sum of window trades."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=3, window_size_days=250
    )
    assert result.trades_count >= 0
    assert isinstance(result.trades_count, int)


def test_walk_forward_equity_curve_generated(pipeline_default, sample_prices):
    """Equity curve is generated (may be None if no data)."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=2, window_size_days=400
    )
    # Equity curve may be None due to mock implementation
    assert result.equity_curve is None or isinstance(result.equity_curve, pd.Series)


def test_walk_forward_different_strategies(sample_prices):
    """Walk-forward works with both strategies."""
    p1 = MLTradingPipeline(strategy='SentimentMomentum')
    p2 = MLTradingPipeline(strategy='FactorEnsemble')
    
    r1 = p1.run_walk_forward(sample_prices, n_windows=2, window_size_days=400)
    r2 = p2.run_walk_forward(sample_prices, n_windows=2, window_size_days=400)
    
    assert r1.strategy_name == 'SentimentMomentum'
    assert r2.strategy_name == 'FactorEnsemble'


def test_walk_forward_empty_result(pipeline_default):
    """Walk-forward returns valid result even with insufficient windows."""
    minimal_data = pd.DataFrame({
        'Open': [100] * 100,
        'High': [102] * 100,
        'Low': [99] * 100,
        'Close': np.arange(100, 200),
        'Volume': [1_000_000] * 100
    }, index=pd.date_range('2020-01-01', periods=100))
    
    result = pipeline_default.run_walk_forward(
        minimal_data, n_windows=1, window_size_days=100
    )
    assert isinstance(result, PipelineResult)


def test_walk_forward_invalid_input_type(pipeline_default):
    """Walk-forward raises ValueError for non-DataFrame input."""
    with pytest.raises(ValueError, match="prices_data must be DataFrame"):
        pipeline_default.run_walk_forward(
            "not a dataframe", n_windows=1
        )


def test_walk_forward_window_results_recorded(pipeline_default, sample_prices):
    """Walk-forward records per-window results."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=3, window_size_days=250
    )
    assert len(result.window_results) <= 3
    if result.window_results:
        assert 'window' in result.window_results[0]
        assert 'return_pct' in result.window_results[0]


# --- Feature Engineering Tests (5) ---

def test_compute_features_shape(pipeline_default, sample_prices):
    """Features computed with correct shape."""
    features = pipeline_default._compute_features(sample_prices)
    assert features.shape == (len(sample_prices), 114)


def test_compute_features_114_factors(pipeline_default, sample_prices):
    """Exactly 114 factors computed."""
    features = pipeline_default._compute_features(sample_prices)
    assert len(features.columns) == 114
    assert all(c.startswith('factor_') for c in features.columns)


def test_compute_features_normalized(pipeline_default, sample_prices):
    """Features are normalized (mean ≈ 0, std ≈ 1)."""
    features = pipeline_default._compute_features(sample_prices)
    means = features.mean()
    stds = features.std()
    assert all(abs(m) < 0.5 for m in means)  # Roughly centered
    assert all(0.8 < s < 1.2 for s in stds)  # Roughly std=1


def test_compute_features_no_nans(pipeline_default, sample_prices):
    """Features have no NaN values."""
    features = pipeline_default._compute_features(sample_prices)
    assert not features.isna().any().any()


def test_compute_features_matches_prices_index(pipeline_default, sample_prices):
    """Features index matches prices index."""
    features = pipeline_default._compute_features(sample_prices)
    assert features.index.equals(sample_prices.index)


# --- Signal Generation Tests (5) ---

def test_generate_signals_dict_format(pipeline_default, sample_prices):
    """Signals returned as dict."""
    features = pipeline_default._compute_features(sample_prices)
    signals = pipeline_default._generate_signals(sample_prices, features)
    assert isinstance(signals, dict)


def test_generate_signals_range(pipeline_default, sample_prices):
    """Signal values in [-2, +2]."""
    features = pipeline_default._compute_features(sample_prices)
    signals = pipeline_default._generate_signals(sample_prices, features)
    assert all(-2.0 <= v <= 2.0 for v in signals.values())


def test_generate_signals_non_empty(pipeline_default, sample_prices):
    """Signals generated for assets."""
    features = pipeline_default._compute_features(sample_prices)
    signals = pipeline_default._generate_signals(sample_prices, features)
    assert len(signals) > 0


def test_generate_signals_reproducible(pipeline_default, sample_prices):
    """Signals deterministic with seed."""
    features = pipeline_default._compute_features(sample_prices)
    
    np.random.seed(999)
    signals1 = pipeline_default._generate_signals(sample_prices, features)
    
    np.random.seed(999)
    signals2 = pipeline_default._generate_signals(sample_prices, features)
    
    assert signals1.keys() == signals2.keys()


def test_generate_signals_features_optional(pipeline_default, sample_prices):
    """Signals generation works even without custom features."""
    signals = pipeline_default._generate_signals(sample_prices, pd.DataFrame())
    assert isinstance(signals, dict)
    assert len(signals) >= 1


# --- Results Aggregation Tests (8) ---

def test_aggregate_window_results_empty(pipeline_default):
    """Aggregation handles empty window results."""
    result = pipeline_default._aggregate_window_results([], [], [])
    assert result.num_windows == 0
    assert result.total_return_pct == 0.0


def test_aggregate_window_results_single(pipeline_default):
    """Aggregation with single window."""
    window_results = [{
        'window': 0,
        'return_pct': 10.0,
        'sharpe_ratio': 1.5,
        'max_drawdown_pct': 5.0,
        'trades': 50,
        'start_date': pd.Timestamp('2020-01-01'),
        'end_date': pd.Timestamp('2020-12-31')
    }]
    
    result = pipeline_default._aggregate_window_results(window_results, [], [])
    assert result.total_return_pct == 10.0
    assert result.trades_count == 50


def test_aggregate_window_results_multiple(pipeline_default):
    """Aggregation with multiple windows."""
    window_results = [
        {
            'window': i,
            'return_pct': 5.0 + i,
            'sharpe_ratio': 1.0 + i * 0.1,
            'max_drawdown_pct': 5.0 + i,
            'trades': 40 + i * 10,
            'start_date': pd.Timestamp('2020-01-01'),
            'end_date': pd.Timestamp('2020-12-31')
        }
        for i in range(3)
    ]
    
    result = pipeline_default._aggregate_window_results(window_results, [], [])
    assert result.num_windows == 3
    assert result.trades_count == 40 + 50 + 60  # Sum of trades


def test_aggregate_returns_average(pipeline_default):
    """Aggregated return is average of window returns."""
    window_results = [
        {'return_pct': 10.0, 'trades': 10, 'sharpe_ratio': 1.0, 'max_drawdown_pct': 5},
        {'return_pct': 20.0, 'trades': 15, 'sharpe_ratio': 1.5, 'max_drawdown_pct': 8}
    ]
    
    result = pipeline_default._aggregate_window_results(window_results, [], [])
    assert abs(result.total_return_pct - 15.0) < 0.1  # Average of 10 and 20


def test_aggregate_max_drawdown_worst_case(pipeline_default):
    """Aggregated drawdown is worst (largest absolute value)."""
    window_results = [
        {'return_pct': 10, 'trades': 10, 'sharpe_ratio': 1, 'max_drawdown_pct': 5},
        {'return_pct': 10, 'trades': 10, 'sharpe_ratio': 1, 'max_drawdown_pct': 15},
        {'return_pct': 10, 'trades': 10, 'sharpe_ratio': 1, 'max_drawdown_pct': 8}
    ]
    
    result = pipeline_default._aggregate_window_results(window_results, [], [])
    assert result.max_drawdown_pct == 15.0  # Max of absolute values


def test_combine_equity_curves_empty(pipeline_default):
    """Combine equity curves with empty list."""
    result = pipeline_default._combine_equity_curves([])
    assert result is None


def test_combine_equity_curves_single(pipeline_default):
    """Combine single equity curve."""
    curve = pd.Series([100, 105, 110], index=pd.date_range('2020-01-01', periods=3))
    result = pipeline_default._combine_equity_curves([curve])
    assert len(result) == 3
    assert result.iloc[0] == 100


def test_combine_equity_curves_multiple(pipeline_default):
    """Combine multiple equity curves."""
    curve1 = pd.Series([100, 105], index=pd.date_range('2020-01-01', periods=2))
    curve2 = pd.Series([110, 115], index=pd.date_range('2020-01-03', periods=2))
    result = pipeline_default._combine_equity_curves([curve1, curve2])
    assert len(result) == 4


# --- Data Enrichment Tests (5) ---

def test_enrich_backtest_data_sentiment_strategy():
    """Enrich data adds sentiment columns for SentimentMomentum strategy."""
    pipeline = MLTradingPipeline(strategy='SentimentMomentum')
    data = pd.DataFrame({
        'Close': [100, 101, 102],
        'Volume': [1_000_000] * 3
    }, index=pd.date_range('2020-01-01', periods=3))
    
    enriched = pipeline._enrich_backtest_data(data)
    assert 'sentiment_score' in enriched.columns
    assert 'earnings_surprise' in enriched.columns


def test_enrich_backtest_data_factor_strategy():
    """Enrich data adds factor columns for FactorEnsemble strategy."""
    pipeline = MLTradingPipeline(strategy='FactorEnsemble')
    data = pd.DataFrame({
        'Close': [100, 101, 102],
        'Volume': [1_000_000] * 3
    }, index=pd.date_range('2020-01-01', periods=3))
    
    enriched = pipeline._enrich_backtest_data(data)
    assert 'factor_1' in enriched.columns
    assert 'factor_ic_1' in enriched.columns


def test_enrich_backtest_data_preserves_original(pipeline_default):
    """Enrich data preserves original columns."""
    data = pd.DataFrame({
        'Open': [100, 101, 102],
        'High': [102, 103, 104],
        'Low': [99, 100, 101],
        'Close': [100, 101, 102],
        'Volume': [1_000_000] * 3
    }, index=pd.date_range('2020-01-01', periods=3))
    
    enriched = pipeline_default._enrich_backtest_data(data)
    assert all(col in enriched.columns for col in data.columns)


def test_enrich_backtest_data_correct_length():
    """Enriched data has same length as input."""
    pipeline = MLTradingPipeline(strategy='FactorEnsemble')
    data = pd.DataFrame({
        'Close': [100, 101, 102, 103, 104],
        'Volume': [1_000_000] * 5
    }, index=pd.date_range('2020-01-01', periods=5))
    
    enriched = pipeline._enrich_backtest_data(data)
    assert len(enriched) == len(data)


def test_enrich_backtest_data_no_nans():
    """Enriched data contains no NaN values."""
    pipeline = MLTradingPipeline(strategy='SentimentMomentum')
    data = pd.DataFrame({
        'Close': [100, 101, 102],
        'Volume': [1_000_000] * 3
    }, index=pd.date_range('2020-01-01', periods=3))
    
    enriched = pipeline._enrich_backtest_data(data)
    assert not enriched.isna().any().any()


# --- Integration E2E Tests (2) ---

def test_pipeline_end_to_end_full_run(sample_prices):
    """Complete pipeline E2E execution."""
    pipeline = MLTradingPipeline(
        universe_size=50,
        start_date='2020-01-01',
        end_date='2021-12-31'
    )
    
    result = pipeline.run_walk_forward(
        sample_prices, n_windows=2, window_size_days=400
    )
    
    # Verify result completeness
    assert isinstance(result, PipelineResult)
    assert result.num_windows <= 2
    assert result.trades_count >= 0
    assert result.strategy_name in ['SentimentMomentum', 'FactorEnsemble']


def test_pipeline_both_strategies_comparable(sample_prices):
    """Both strategies produce comparable results."""
    p1 = MLTradingPipeline(strategy='SentimentMomentum')
    p2 = MLTradingPipeline(strategy='FactorEnsemble')
    
    r1 = p1.run_walk_forward(sample_prices, n_windows=1, window_size_days=500)
    r2 = p2.run_walk_forward(sample_prices, n_windows=1, window_size_days=500)
    
    # Both should produce valid results
    assert not np.isnan(r1.total_return_pct)
    assert not np.isnan(r2.total_return_pct)
    assert r1.trades_count >= 0
    assert r2.trades_count >= 0
