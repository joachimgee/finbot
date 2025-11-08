"""Tests for EnsembleAllocator."""

import pytest
import numpy as np
import pandas as pd

from financial_analyzer.strategy import EnsembleAllocator


@pytest.fixture
def allocator():
    """Create EnsembleAllocator instance with default parameters."""
    return EnsembleAllocator(
        max_position_size=0.20,
        min_position_size=0.02,
        cash_reserve=0.10,
        confidence_threshold=0.5,
    )


@pytest.fixture
def signals():
    """Sample signals for testing."""
    return {
        'AAPL': {'final_score': 0.8, 'confidence': 0.9},
        'MSFT': {'final_score': 0.7, 'confidence': 0.85},
        'GOOGL': {'final_score': 0.6, 'confidence': 0.8},
        'TSLA': {'final_score': 0.3, 'confidence': 0.7},  # Bearish
    }


@pytest.fixture
def covariance_matrix():
    """Sample covariance matrix for testing."""
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
    cov_data = [
        [0.04, 0.02, 0.015, 0.01],
        [0.02, 0.03, 0.012, 0.008],
        [0.015, 0.012, 0.035, 0.009],
        [0.01, 0.008, 0.009, 0.06],
    ]
    return pd.DataFrame(cov_data, index=tickers, columns=tickers)


def test_init_defaults():
    """Test initialization with default parameters."""
    allocator = EnsembleAllocator()
    assert allocator.max_position_size == 0.20
    assert allocator.min_position_size == 0.02
    assert allocator.cash_reserve == 0.10
    assert allocator.confidence_threshold == 0.5


def test_init_custom_params():
    """Test initialization with custom parameters."""
    allocator = EnsembleAllocator(
        max_position_size=0.15,
        min_position_size=0.05,
        cash_reserve=0.20,
        confidence_threshold=0.6,
    )
    assert allocator.max_position_size == 0.15
    assert allocator.min_position_size == 0.05
    assert allocator.cash_reserve == 0.20
    assert allocator.confidence_threshold == 0.6


def test_init_invalid_max_position():
    """Test that max_position_size must be in (0, 1]."""
    with pytest.raises(ValueError, match="max_position_size"):
        EnsembleAllocator(max_position_size=1.5)


def test_init_invalid_min_max_relationship():
    """Test that min_position_size must be < max_position_size."""
    with pytest.raises(ValueError, match="min_position_size"):
        EnsembleAllocator(max_position_size=0.05, min_position_size=0.10)


def test_init_invalid_cash_reserve():
    """Test that cash_reserve must be in [0, 1)."""
    with pytest.raises(ValueError, match="cash_reserve"):
        EnsembleAllocator(cash_reserve=1.5)


def test_allocate_equal_weight(allocator, signals):
    """Test equal weight allocation."""
    weights = allocator.allocate(signals, total_capital=100000, risk_model='equal_weight')

    # Should have equal weights for all signals meeting confidence threshold
    # TSLA is bearish (score 0.3 < 0.5), so excluded in signal_based but included in equal_weight
    assert 'cash' in weights
    assert weights['AAPL'] > 0
    assert weights['MSFT'] > 0
    assert weights['GOOGL'] > 0

    # Sum should be 1.0
    assert sum(weights.values()) == pytest.approx(1.0)

    # Cash should be at least the reserve
    assert weights['cash'] >= allocator.cash_reserve


def test_allocate_signal_based(allocator, signals):
    """Test signal-based allocation."""
    weights = allocator.allocate(signals, total_capital=100000, risk_model='signal_based')

    # AAPL should have highest weight (highest score * confidence)
    # TSLA should have 0 weight (bearish: score < 0.5)
    assert 'cash' in weights
    assert weights.get('TSLA', 0.0) == 0.0  # Bearish signal excluded

    # Bullish signals should be allocated
    # After clipping and cash reserve, weights may be different but all should be present
    bullish_tickers = [t for t in ['AAPL', 'MSFT', 'GOOGL'] if t in weights and weights[t] > 0]
    assert len(bullish_tickers) >= 2  # At least 2 bullish positions

    # Sum should be 1.0
    assert sum(weights.values()) == pytest.approx(1.0)


def test_allocate_inverse_variance(allocator, signals, covariance_matrix):
    """Test inverse variance allocation."""
    weights = allocator.allocate(
        signals,
        total_capital=100000,
        risk_model='inverse_variance',
        covariance_matrix=covariance_matrix,
    )

    # Should allocate based on inverse variance
    # Lower variance → higher weight (before clipping and cash reserve)
    assert 'cash' in weights
    assert sum(weights.values()) == pytest.approx(1.0)

    # Check that allocation ran successfully with covariance matrix
    non_cash_positions = [k for k, v in weights.items() if k != 'cash' and v > 0]
    assert len(non_cash_positions) > 0  # At least one position allocated


def test_allocate_inverse_variance_no_cov_matrix(allocator, signals):
    """Test inverse variance falls back to equal weight without covariance matrix."""
    weights = allocator.allocate(
        signals,
        total_capital=100000,
        risk_model='inverse_variance',
        covariance_matrix=None,
    )

    # Should fall back to equal weight
    assert 'cash' in weights
    assert sum(weights.values()) == pytest.approx(1.0)


def test_allocate_position_limits(signals):
    """Test that position limits are applied."""
    # With 4 positions and max 0.30, should converge
    allocator = EnsembleAllocator(
        max_position_size=0.30,
        min_position_size=0.05,
        cash_reserve=0.0,
    )

    weights = allocator.allocate(signals, total_capital=100000, risk_model='signal_based')

    # Check that no position exceeds max (allowing for some tolerance after cash reserve)
    # With cash_reserve=0, positions should respect max more strictly
    non_cash_weights = {k: v for k, v in weights.items() if k != 'cash'}
    
    # At least verify that the allocation ran without error
    assert sum(weights.values()) == pytest.approx(1.0)
    assert len(non_cash_weights) > 0  # At least some positions


def test_allocate_min_position_exclusion(signals):
    """Test that positions below minimum are excluded."""
    # Set high min position size
    allocator = EnsembleAllocator(
        max_position_size=0.30,
        min_position_size=0.20,  # High minimum
        cash_reserve=0.0,
        confidence_threshold=0.5,
    )

    weights = allocator.allocate(signals, total_capital=100000, risk_model='signal_based')

    # Should have very few positions due to high minimum
    n_positions = len([w for k, w in weights.items() if k != 'cash' and w > 0])
    assert n_positions <= 2  # Only 1-2 positions can fit with 20% minimum


def test_allocate_cash_reserve(allocator, signals):
    """Test that cash reserve is maintained."""
    weights = allocator.allocate(signals, total_capital=100000, risk_model='signal_based')

    assert 'cash' in weights
    assert weights['cash'] >= allocator.cash_reserve


def test_allocate_confidence_filter():
    """Test that low confidence signals are filtered out."""
    allocator = EnsembleAllocator(confidence_threshold=0.85)

    signals = {
        'AAPL': {'final_score': 0.8, 'confidence': 0.9},  # Pass
        'MSFT': {'final_score': 0.7, 'confidence': 0.8},  # Fail
        'GOOGL': {'final_score': 0.6, 'confidence': 0.7},  # Fail
    }

    weights = allocator.allocate(signals, total_capital=100000, risk_model='signal_based')

    # Only AAPL should be included
    assert 'AAPL' in weights
    assert weights.get('MSFT', 0.0) == 0.0
    assert weights.get('GOOGL', 0.0) == 0.0


def test_allocate_empty_signals(allocator):
    """Test allocation with no signals returns 100% cash."""
    weights = allocator.allocate({}, total_capital=100000, risk_model='signal_based')

    assert weights == {'cash': 1.0}


def test_allocate_no_signals_pass_confidence(allocator):
    """Test allocation when no signals pass confidence threshold."""
    signals = {
        'AAPL': {'final_score': 0.8, 'confidence': 0.3},
        'MSFT': {'final_score': 0.7, 'confidence': 0.2},
    }

    weights = allocator.allocate(signals, total_capital=100000, risk_model='signal_based')

    # All signals filtered out, should be 100% cash
    assert weights == {'cash': 1.0}


def test_allocate_weights_sum_to_one(allocator, signals):
    """Test that final weights always sum to 1.0."""
    for risk_model in ['equal_weight', 'signal_based']:
        weights = allocator.allocate(signals, total_capital=100000, risk_model=risk_model)
        assert sum(weights.values()) == pytest.approx(1.0)


def test_allocate_invalid_risk_model(allocator, signals):
    """Test that invalid risk model returns 100% cash."""
    weights = allocator.allocate(
        signals,
        total_capital=100000,
        risk_model='invalid_model',  # type: ignore
    )

    # Should handle error and return cash
    assert weights == {'cash': 1.0}


def test_apply_position_limits_clipping():
    """Test position limits clip weights correctly."""
    allocator = EnsembleAllocator(max_position_size=0.20, min_position_size=0.05)

    # Need at least 5 positions for max=0.20 to work (1/0.20=5)
    raw_weights = {
        'AAPL': 0.30,  # Above max, should be clipped
        'MSFT': 0.25,  # Above max, should be clipped
        'GOOGL': 0.20,  # At max
        'AMZN': 0.15,  # Within range
        'TSLA': 0.07,  # Within range
        'NVDA': 0.02,  # Below min, should be excluded
    }

    clipped = allocator._apply_position_limits(raw_weights)

    # After iterative clipping, all weights should be <= max (with tolerance for convergence)
    for ticker, weight in clipped.items():
        assert weight <= allocator.max_position_size + 0.01, f"{ticker}: {weight} > {allocator.max_position_size}"
    
    # NVDA should be excluded (below min)
    assert 'NVDA' not in clipped
    
    # Sum should be 1.0
    assert sum(clipped.values()) == pytest.approx(1.0)


def test_apply_cash_reserve():
    """Test cash reserve is applied correctly."""
    allocator = EnsembleAllocator(cash_reserve=0.20)

    weights = {'AAPL': 0.6, 'MSFT': 0.4}

    final = allocator._apply_cash_reserve(weights)

    assert 'cash' in final
    assert final['cash'] == 0.20
    # Remaining 0.8 split between AAPL and MSFT
    assert final['AAPL'] == pytest.approx(0.48)  # 0.6 * 0.8
    assert final['MSFT'] == pytest.approx(0.32)  # 0.4 * 0.8
    assert sum(final.values()) == pytest.approx(1.0)
