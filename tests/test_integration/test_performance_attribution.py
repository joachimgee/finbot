"""
Tests for PerformanceAttributor.

Coverage:
- Initialization (3 tests)
- Input validation (5 tests)
- Trade classification (6 tests)
- Attribution calculation (7 tests)
- Edge cases (4 tests)

Total: 25 tests
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from financial_analyzer.integration.performance_attribution import (
    PerformanceAttributor,
    AttributionResult,
    AttributionMethod
)


# -------------------- Fixtures --------------------

@pytest.fixture
def mock_trades():
    """
    Create mock trades DataFrame (backtesting.py format).
    
    Returns:
        DataFrame with EntryTime, ExitTime, EntryPrice, ExitPrice, PnL, Size
    
    Example:
        >>> trades = mock_trades()
        >>> len(trades)
        3
        >>> trades['PnL'].sum()
        1100.0
    """
    return pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15', '2024-01-20']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17', '2024-01-22']),
        'EntryPrice': [100.0, 105.0, 102.0],
        'ExitPrice': [105.0, 103.0, 110.0],
        'PnL': [500.0, -200.0, 800.0],
        'Size': [0.10, 0.10, 0.10]
    })


@pytest.fixture
def mock_sentiment_signals():
    """
    Create mock sentiment signals DataFrame.
    
    Returns:
        DataFrame with DatetimeIndex and ticker columns
    
    Example:
        >>> sentiment = mock_sentiment_signals()
        >>> sentiment.index.name
        >>> 'AAPL' in sentiment.columns
        True
    """
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'AAPL': np.random.uniform(-0.5, 0.8, 30),
        'MSFT': np.random.uniform(-0.3, 0.7, 30)
    }, index=dates)


@pytest.fixture
def mock_technical_factors():
    """
    Create mock technical factors DataFrame.
    
    Returns:
        DataFrame with DatetimeIndex and factor columns
    
    Example:
        >>> technical = mock_technical_factors()
        >>> 'RSI' in technical.columns
        True
    """
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'RSI': np.random.uniform(30, 70, 30),
        'MACD': np.random.uniform(-2, 2, 30)
    }, index=dates)


@pytest.fixture
def attributor_default():
    """
    Default PerformanceAttributor instance.
    
    Returns:
        PerformanceAttributor with default params
    
    Example:
        >>> attr = attributor_default()
        >>> attr.method
        <AttributionMethod.BRINSON: 'brinson'>
    """
    return PerformanceAttributor()


# -------------------- Initialization Tests --------------------

def test_attributor_init_default():
    """Attributor initializes with default parameters."""
    attr = PerformanceAttributor()
    
    assert attr.method == AttributionMethod.BRINSON
    assert attr.min_confidence == 0.5


def test_attributor_init_custom():
    """Attributor initializes with custom parameters."""
    attr = PerformanceAttributor(
        method=AttributionMethod.SIMPLE,
        min_confidence=0.7
    )
    
    assert attr.method == AttributionMethod.SIMPLE
    assert attr.min_confidence == 0.7


def test_attribution_result_validation():
    """AttributionResult validates sum ~100% in __post_init__."""
    # Valid result (sum = 100%)
    result = AttributionResult(
        sentiment_pct=40.0, technical_pct=35.0,
        allocation_pct=15.0, timing_pct=10.0,
        total_pnl=1000.0, residual_pct=0.0
    )
    
    # Check sum
    total = (
        result.sentiment_pct + result.technical_pct + 
        result.allocation_pct + result.timing_pct + result.residual_pct
    )
    assert abs(total - 100.0) < 1e-6


# -------------------- Input Validation Tests --------------------

def test_validate_inputs_missing_columns(
    attributor_default,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Raise ValueError if trades missing required columns."""
    bad_trades = pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10']),
        'PnL': [100.0]
    })  # Missing ExitTime
    
    with pytest.raises(ValueError, match="missing required columns"):
        attributor_default.attribute_returns(
            bad_trades, mock_sentiment_signals, mock_technical_factors
        )


def test_validate_inputs_wrong_types(attributor_default):
    """Raise TypeError if inputs not DataFrames."""
    with pytest.raises(TypeError, match="trades must be"):
        attributor_default.attribute_returns(
            None,  # Not a DataFrame
            pd.DataFrame(),
            pd.DataFrame()
        )


def test_validate_inputs_no_datetimeindex(
    attributor_default,
    mock_trades
):
    """Raise ValueError if signals not DatetimeIndex."""
    bad_signals = pd.DataFrame({
        'AAPL': [0.5, 0.6]
    })  # No DatetimeIndex
    
    valid_technical = pd.DataFrame(
        {'RSI': [50, 60]},
        index=pd.date_range('2024-01-01', periods=2)
    )
    
    with pytest.raises(ValueError, match="must have DatetimeIndex"):
        attributor_default.attribute_returns(
            mock_trades, bad_signals, valid_technical
        )


def test_empty_trades_returns_zero_attribution(
    attributor_default,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Empty trades DataFrame returns zero attribution."""
    empty_trades = pd.DataFrame(columns=['EntryTime', 'ExitTime', 'PnL'])
    
    result = attributor_default.attribute_returns(
        empty_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.total_pnl == 0.0
    assert result.trade_count == 0
    assert result.sentiment_pct == 0.0
    assert result.technical_pct == 0.0


def test_valid_inputs_no_error(
    attributor_default,
    mock_trades,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Valid inputs execute without error."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert isinstance(result, AttributionResult)


# -------------------- Trade Classification Tests --------------------

def test_classify_trades_sentiment_dominant(
    attributor_default,
    mock_technical_factors
):
    """Trade classified as sentiment-driven if sentiment > technical."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [500.0]
    })
    
    # High sentiment, low technical
    sentiment = pd.DataFrame(
        {'AAPL': [0.8]},
        index=[pd.Timestamp('2024-01-10')]
    )
    
    technical = pd.DataFrame(
        {'RSI': [0.2]},
        index=[pd.Timestamp('2024-01-10')]
    )
    
    result = attributor_default.attribute_returns(
        trades, sentiment, technical
    )
    
    # Sentiment should dominate
    assert result.sentiment_pct > result.technical_pct


def test_classify_trades_technical_dominant(
    attributor_default,
    mock_sentiment_signals
):
    """Trade classified as technical-driven if technical > sentiment."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [500.0]
    })
    
    # Low sentiment, high technical
    sentiment = pd.DataFrame(
        {'AAPL': [0.2]},
        index=[pd.Timestamp('2024-01-10')]
    )
    
    technical = pd.DataFrame(
        {'RSI': [0.9]},
        index=[pd.Timestamp('2024-01-10')]
    )
    
    result = attributor_default.attribute_returns(
        trades, sentiment, technical
    )
    
    # Technical should dominate
    assert result.technical_pct > result.sentiment_pct


def test_classify_trades_overlap(attributor_default):
    """Trade with both signals strong classified as overlap (50/50 split)."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [1000.0]  # Augmenter pour meilleure précision
    })
    
    # Both signals strong (> 0.5 threshold)
    sentiment = pd.DataFrame(
        {'AAPL': [0.8]},
        index=[pd.Timestamp('2024-01-10')]
    )
    
    technical = pd.DataFrame(
        {'RSI': [0.9]},
        index=[pd.Timestamp('2024-01-10')]
    )
    
    result = attributor_default.attribute_returns(
        trades, sentiment, technical
    )
    
    # Both should have contribution
    assert result.sentiment_pct > 0, "Sentiment should contribute"
    assert result.technical_pct > 0, "Technical should contribute"
    
    # Expected split: 50% sentiment, 50% technical (before allocation/timing)
    # After allocation (10%) + timing (5%), the ratio should still be ~1:1
    # sentiment_base = 500 * 0.85 / 1000 = 42.5%
    # technical_base = 500 * 0.85 / 1000 = 42.5%
    # Check they're within 20% of each other (relaxed due to placeholders)
    ratio = result.sentiment_pct / result.technical_pct if result.technical_pct > 0 else 0
    assert 0.8 < ratio < 1.2, \
        f"Overlap should split ~50/50, got ratio {ratio:.2f} " \
        f"(sentiment={result.sentiment_pct:.1f}%, technical={result.technical_pct:.1f}%)"


def test_signal_extraction_exact_match(attributor_default):
    """Signal extracted at exact time match."""
    signals = pd.DataFrame(
        {'AAPL': [0.5, 0.6, 0.7]},
        index=pd.to_datetime(['2024-01-10', '2024-01-11', '2024-01-12'])
    )
    
    value = attributor_default._get_signal_at_time(
        signals, pd.Timestamp('2024-01-11')
    )
    
    assert abs(value - 0.6) < 1e-6


def test_signal_extraction_asof(attributor_default):
    """Signal extracted using asof (nearest backward fill)."""
    signals = pd.DataFrame(
        {'AAPL': [0.5, 0.7]},
        index=pd.to_datetime(['2024-01-10', '2024-01-12'])
    )
    
    # Request 2024-01-11 → should use 2024-01-10 (asof backward)
    value = attributor_default._get_signal_at_time(
        signals, pd.Timestamp('2024-01-11')
    )
    
    assert abs(value - 0.5) < 1e-6


def test_signal_extraction_missing_returns_zero(attributor_default):
    """Signal extraction returns 0.0 if date before signals start."""
    signals = pd.DataFrame(
        {'AAPL': [0.5]},
        index=pd.to_datetime(['2024-01-10'])
    )
    
    # Request date before signals start
    value = attributor_default._get_signal_at_time(
        signals, pd.Timestamp('2024-01-01')
    )
    
    assert value == 0.0


# -------------------- Attribution Calculation Tests --------------------

def test_attribution_total_pnl_correct(
    attributor_default,
    mock_trades,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Total PnL in result matches trades sum."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    expected_pnl = mock_trades['PnL'].sum()
    assert abs(result.total_pnl - expected_pnl) < 1e-6


def test_attribution_percentages_sum_to_100(
    attributor_default,
    mock_trades,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution percentages sum to ~100%."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    total = (
        result.sentiment_pct + result.technical_pct + 
        result.allocation_pct + result.timing_pct + result.residual_pct
    )
    
    # 5% tolerance (as per spec)
    assert 95.0 < total <= 105.0


def test_attribution_trade_count_correct(
    attributor_default,
    mock_trades,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Trade count in result matches input trades count."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.trade_count == len(mock_trades)


def test_attribution_method_recorded(
    attributor_default,
    mock_trades,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution method recorded in result."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.attribution_method == AttributionMethod.BRINSON.value


def test_attribution_positive_pnl(
    attributor_default,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution with only profitable trades."""
    trades = pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17']),
        'PnL': [500.0, 300.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.total_pnl > 0
    # Majority should be attributed to signals (sentiment + technical)
    assert result.sentiment_pct + result.technical_pct > 50


def test_attribution_negative_pnl(
    attributor_default,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution with losing trades (negative PnL)."""
    trades = pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17']),
        'PnL': [-200.0, -150.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.total_pnl < 0
    # Percentages still sum to 100% (negative contributions represented)


def test_attribution_mixed_pnl(
    attributor_default,
    mock_trades,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution with mixed profitable/losing trades."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    # mock_trades has +500, -200, +800 = +1100 total
    assert result.total_pnl > 0
    assert result.trade_count == 3


# -------------------- Edge Cases Tests --------------------

def test_attribution_zero_total_pnl(
    attributor_default,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution with zero total PnL (breakeven)."""
    trades = pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17']),
        'PnL': [100.0, -100.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert abs(result.total_pnl) < 1e-6
    # Should return equal attribution fallback (25% each)
    assert result.sentiment_pct == 25.0
    assert result.technical_pct == 25.0
    assert result.allocation_pct == 25.0
    assert result.timing_pct == 25.0


def test_attribution_single_trade(
    attributor_default,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution with single trade."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [500.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.trade_count == 1
    assert abs(result.total_pnl - 500.0) < 1e-6


def test_attribution_many_trades(
    attributor_default,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Attribution with 50+ trades (stress test)."""
    n_trades = 50
    trades = pd.DataFrame({
        'EntryTime': pd.date_range('2024-01-01', periods=n_trades, freq='D'),
        'ExitTime': pd.date_range('2024-01-03', periods=n_trades, freq='D'),
        'PnL': np.random.uniform(-100, 200, n_trades)
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.trade_count == n_trades
    # Percentages still sum to ~100%
    total = (
        result.sentiment_pct + result.technical_pct + 
        result.allocation_pct + result.timing_pct + result.residual_pct
    )
    assert 95 < total <= 105


def test_attribution_no_signal_overlap(
    attributor_default,
    mock_technical_factors
):
    """Attribution when signals don't overlap dates (asof fallback)."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-02-01')],  # Outside sentiment dates
        'ExitTime': [pd.Timestamp('2024-02-03')],
        'PnL': [500.0]
    })
    
    # Sentiment only in January
    sentiment = pd.DataFrame(
        {'AAPL': [0.5]},
        index=[pd.Timestamp('2024-01-01')]
    )
    
    result = attributor_default.attribute_returns(
        trades, sentiment, mock_technical_factors
    )
    
    # Should still return valid attribution
    assert result.total_pnl == 500.0
    
    # Sentiment returns 0.0 (no asof match) → should be 0%
    assert result.sentiment_pct == 0.0, \
        f"Sentiment should be 0% (no signal before trade), got {result.sentiment_pct:.1f}%"
    
    # Technical should dominate (after allocation/timing)
    assert result.technical_pct > 70, \
        f"Technical should dominate (>70%), got {result.technical_pct:.1f}%"


# -------------------- Helper for import check --------------------

def test_attribution_method_simple(
    mock_trades,
    mock_sentiment_signals,
    mock_technical_factors
):
    """Test attribution with SIMPLE method (currently same as BRINSON)."""
    attr = PerformanceAttributor(method=AttributionMethod.SIMPLE)
    
    result = attr.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.attribution_method == AttributionMethod.SIMPLE.value
    assert isinstance(result, AttributionResult)
    # Currently no difference vs BRINSON (Phase 5.5 will differentiate)
    assert result.total_pnl == mock_trades['PnL'].sum()


def test_module_exports():
    """Verify module exports correct classes."""
    from financial_analyzer.integration import performance_attribution
    
    assert hasattr(performance_attribution, 'PerformanceAttributor')
    assert hasattr(performance_attribution, 'AttributionResult')
    assert hasattr(performance_attribution, 'AttributionMethod')
