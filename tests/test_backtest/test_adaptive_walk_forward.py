"""Tests for Adaptive Walk-Forward Validation module."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.adaptive_walk_forward import (
    AdaptiveWalkForward,
    DriftDetector,
    ModelRetrainer,
    PerformanceMetrics,
    RetrainEvent,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_returns():
    """Generate sample returns for testing."""
    np.random.seed(42)
    # Simulate 500 days of returns with drift
    returns_stable = np.random.normal(0.001, 0.02, 250)  # Sharpe ~1.5
    returns_drift = np.random.normal(-0.002, 0.03, 250)  # Sharpe drops
    return np.concatenate([returns_stable, returns_drift])


@pytest.fixture
def sample_returns_stable():
    """Generate stable returns without drift."""
    np.random.seed(42)
    return np.random.normal(0.001, 0.02, 500)  # Consistent Sharpe ~1.5


@pytest.fixture
def baseline_metrics():
    """Create baseline performance metrics."""
    return PerformanceMetrics(
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=-10.0,
        win_rate=55.0,
        mean_return=0.001,
        std_return=0.02,
        timestamp=datetime.now(),
    )


@pytest.fixture
def drift_detector():
    """Create DriftDetector instance."""
    return DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="combined",
        window_size=252,
    )


@pytest.fixture
def mock_retrain_callback():
    """Create mock retrain callback."""
    def callback(X, y, learning_rate=3e-4, batch_size=64, **kwargs):
        return {"loss": 0.1, "epochs": 10}
    return MagicMock(side_effect=callback)


@pytest.fixture
def model_retrainer(mock_retrain_callback):
    """Create ModelRetrainer instance."""
    return ModelRetrainer(retrain_callback=mock_retrain_callback)


@pytest.fixture
def mock_model():
    """Create mock trading model."""
    model = MagicMock()
    model.predict = MagicMock(return_value=np.array([0.5, -0.3, 0.8]))
    return model


# ============================================================================
# DRIFT DETECTOR TESTS
# ============================================================================


def test_drift_detector_init():
    """Test DriftDetector initialization."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="threshold",
        window_size=252,
    )
    
    assert detector.baseline_sharpe == 1.5
    assert detector.threshold_pct == 0.5
    assert detector.detection_method == "threshold"
    assert detector.window_size == 252


def test_drift_detector_invalid_method():
    """Test error on invalid detection method."""
    with pytest.raises(ValueError, match="Invalid detection_method"):
        DriftDetector(
            baseline_sharpe=1.5,
            threshold_pct=0.5,
            detection_method="invalid_method",
        )


def test_drift_detector_threshold_no_drift(baseline_metrics):
    """Test threshold detection with no drift."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="threshold",
    )
    
    # Current Sharpe = 1.5 (no drop)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=-10.0,
        win_rate=55.0,
        mean_return=0.001,
        std_return=0.02,
    )
    
    returns = np.random.normal(0.001, 0.02, 100)
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is False
    assert result["reason"] == "No drift detected"


def test_drift_detector_threshold_drift_detected(baseline_metrics):
    """Test threshold detection with drift."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="threshold",
    )
    
    # Current Sharpe = 0.7 (53% drop from 1.5)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=0.7,
        sortino_ratio=1.0,
        max_drawdown=-20.0,
        win_rate=45.0,
        mean_return=0.0005,
        std_return=0.025,
    )
    
    returns = np.random.normal(-0.001, 0.025, 100)
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is True
    assert "Sharpe dropped" in result["reason"]
    assert result["confidence"] > 0.5


def test_drift_detector_ttest_no_drift():
    """Test t-test detection with no drift (returns ~ 0)."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="ttest",
    )
    
    # Returns around zero (no significant drift). RNG local seedé : un t-test
    # "no drift" sur données non seedées a ~5% de faux positifs (dépend du RNG
    # global partagé entre fichiers) — source de flakiness order-dépendante.
    returns = np.random.default_rng(0).normal(0.0001, 0.02, 100)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=1.4,
        sortino_ratio=1.8,
        max_drawdown=-12.0,
        win_rate=52.0,
        mean_return=0.0001,
        std_return=0.02,
    )
    
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is False


def test_drift_detector_ttest_drift_detected():
    """Test t-test detection with significant negative returns."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="ttest",
        confidence_level=0.95,
    )
    
    # Significantly negative returns
    returns = np.random.normal(-0.01, 0.02, 100)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=0.5,
        sortino_ratio=0.8,
        max_drawdown=-25.0,
        win_rate=35.0,
        mean_return=-0.01,
        std_return=0.02,
    )
    
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is True
    assert "significantly negative" in result["reason"]
    assert "t_stat" in result["method_results"]["ttest"]
    assert "p_value" in result["method_results"]["ttest"]


def test_drift_detector_cusum_no_drift():
    """Test CUSUM detection with stable returns."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="cusum",
        cusum_threshold=5.0,
    )
    
    # Stable returns around zero
    returns = np.random.normal(0.0, 0.02, 100)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=-10.0,
        win_rate=55.0,
        mean_return=0.0,
        std_return=0.02,
    )
    
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is False
    assert result["reason"] == "No drift detected"
    assert "cusum" in result["method_results"]
    assert "within control limits" in result["method_results"]["cusum"]["reason"]


def test_drift_detector_cusum_drift_detected():
    """Test CUSUM detection with regime change."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="cusum",
        cusum_threshold=0.5,  # Very low threshold for reliable detection
    )
    
    # Extreme regime change: shift from positive to very large negative
    returns_before = np.random.normal(0.01, 0.005, 100)
    returns_after = np.random.normal(-0.03, 0.01, 100)  # Very large negative shift
    returns = np.concatenate([returns_before, returns_after])
    
    current_metrics = PerformanceMetrics(
        sharpe_ratio=0.8,
        sortino_ratio=1.2,
        max_drawdown=-18.0,
        win_rate=42.0,
        mean_return=-0.0005,
        std_return=0.025,
    )
    
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is True
    assert "CUSUM threshold exceeded" in result["reason"]


def test_drift_detector_combined_method():
    """Test combined detection method."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="combined",
    )
    
    # Returns with multiple drift signals
    returns = np.random.normal(-0.005, 0.03, 100)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=0.6,
        sortino_ratio=0.9,
        max_drawdown=-22.0,
        win_rate=38.0,
        mean_return=-0.005,
        std_return=0.03,
    )
    
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is True
    assert "method_results" in result
    assert "threshold" in result["method_results"]
    assert "ttest" in result["method_results"]
    assert "cusum" in result["method_results"]
    assert result["confidence"] > 0.0


def test_drift_detector_reset_cusum(drift_detector):
    """Test CUSUM state reset."""
    # Trigger CUSUM accumulation
    returns = np.random.normal(-0.01, 0.02, 50)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=0.8,
        sortino_ratio=1.2,
        max_drawdown=-15.0,
        win_rate=45.0,
        mean_return=-0.01,
        std_return=0.02,
    )
    
    drift_detector.detect_drift(returns, current_metrics)
    
    # Reset should clear CUSUM state
    drift_detector.reset_cusum()
    assert drift_detector._cusum_pos == 0.0
    assert drift_detector._cusum_neg == 0.0


def test_drift_detector_insufficient_data():
    """Test drift detection with insufficient data."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="ttest",
    )
    
    # Only 5 samples (need 10+)
    returns = np.random.normal(0.0, 0.02, 5)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=-5.0,
        win_rate=55.0,
        mean_return=0.0,
        std_return=0.02,
    )
    
    result = detector.detect_drift(returns, current_metrics)
    
    assert result["is_drift"] is False
    assert result["reason"] == "No drift detected"
    assert "ttest" in result["method_results"]
    assert "Insufficient data" in result["method_results"]["ttest"]["reason"]


# ============================================================================
# MODEL RETRAINER TESTS
# ============================================================================


def test_model_retrainer_init(mock_retrain_callback):
    """Test ModelRetrainer initialization."""
    retrainer = ModelRetrainer(
        retrain_callback=mock_retrain_callback,
        learning_rate_decay=0.9,
        min_learning_rate=1e-6,
    )
    
    assert retrainer.retrain_callback == mock_retrain_callback
    assert retrainer.learning_rate_decay == 0.9
    assert retrainer.min_learning_rate == 1e-6
    assert retrainer.current_learning_rate == 3e-4
    assert retrainer.retrain_count == 0


def test_model_retrainer_retrain_success(model_retrainer):
    """Test successful retrain."""
    X = np.random.rand(100, 10)
    y = np.random.rand(100)
    
    result = model_retrainer.retrain(X, y, reason="test_drift")
    
    assert result["success"] is True
    assert result["retrain_count"] == 1
    assert result["duration"] > 0
    assert "learning_rate" in result
    assert "batch_size" in result
    assert model_retrainer.retrain_callback.called


def test_model_retrainer_hyperparameter_adaptation(model_retrainer):
    """Test hyperparameter adaptation over multiple retrains."""
    X = np.random.rand(100, 10)
    y = np.random.rand(100)
    
    initial_lr = model_retrainer.current_learning_rate
    initial_bs = model_retrainer.current_batch_size
    
    # First retrain
    result1 = model_retrainer.retrain(X, y, reason="drift_1")
    lr_after_1 = model_retrainer.current_learning_rate
    bs_after_1 = model_retrainer.current_batch_size
    
    # LR should decay, batch size should grow
    assert lr_after_1 < initial_lr
    assert bs_after_1 > initial_bs
    
    # Second retrain
    result2 = model_retrainer.retrain(X, y, reason="drift_2")
    lr_after_2 = model_retrainer.current_learning_rate
    bs_after_2 = model_retrainer.current_batch_size
    
    assert lr_after_2 < lr_after_1
    assert bs_after_2 > bs_after_1
    assert result2["retrain_count"] == 2


def test_model_retrainer_min_learning_rate():
    """Test learning rate respects minimum."""
    callback = MagicMock(return_value={"loss": 0.1})
    retrainer = ModelRetrainer(
        retrain_callback=callback,
        learning_rate_decay=0.5,
        min_learning_rate=1e-5,
    )
    
    X = np.random.rand(50, 10)
    y = np.random.rand(50)
    
    # Retrain multiple times to hit min LR
    for _ in range(20):
        retrainer.retrain(X, y, reason="test")
    
    # LR should not go below min
    assert retrainer.current_learning_rate >= 1e-5


def test_model_retrainer_max_batch_size():
    """Test batch size respects maximum."""
    callback = MagicMock(return_value={"loss": 0.1})
    retrainer = ModelRetrainer(
        retrain_callback=callback,
        batch_size_growth=2.0,
        max_batch_size=256,
    )
    
    X = np.random.rand(50, 10)
    y = np.random.rand(50)
    
    # Retrain multiple times to hit max batch size
    for _ in range(10):
        retrainer.retrain(X, y, reason="test")
    
    # Batch size should not exceed max
    assert retrainer.current_batch_size <= 256


def test_model_retrainer_callback_failure():
    """Test handling of callback failure."""
    def failing_callback(*args, **kwargs):
        raise RuntimeError("Training failed")
    
    retrainer = ModelRetrainer(retrain_callback=failing_callback)
    
    X = np.random.rand(50, 10)
    y = np.random.rand(50)
    
    result = retrainer.retrain(X, y, reason="test_fail")
    
    assert result["success"] is False
    assert "error" in result
    assert "Training failed" in result["error"]


# ============================================================================
# PERFORMANCE METRICS TESTS
# ============================================================================


def test_performance_metrics_creation():
    """Test PerformanceMetrics dataclass creation."""
    metrics = PerformanceMetrics(
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=-15.0,
        win_rate=55.0,
        mean_return=0.001,
        std_return=0.02,
    )
    
    assert metrics.sharpe_ratio == 1.5
    assert metrics.sortino_ratio == 2.0
    assert metrics.max_drawdown == -15.0
    assert metrics.win_rate == 55.0
    assert isinstance(metrics.timestamp, datetime)


# ============================================================================
# RETRAIN EVENT TESTS
# ============================================================================


def test_retrain_event_creation(baseline_metrics):
    """Test RetrainEvent dataclass creation."""
    event = RetrainEvent(
        timestamp=datetime.now(),
        trigger_reason="sharpe_drop",
        metrics_before=baseline_metrics,
        retrain_duration=120.5,
    )
    
    assert event.trigger_reason == "sharpe_drop"
    assert event.metrics_before == baseline_metrics
    assert event.retrain_duration == 120.5
    assert event.metrics_after is None


# ============================================================================
# ADAPTIVE WALK-FORWARD TESTS
# ============================================================================


def test_adaptive_walk_forward_init(mock_model, mock_retrain_callback):
    """Test AdaptiveWalkForward initialization."""
    awf = AdaptiveWalkForward(
        model=mock_model,
        baseline_sharpe=1.5,
        retrain_callback=mock_retrain_callback,
        retrain_threshold=0.5,
        window_size=252,
        step_size=21,
    )
    
    assert awf.model == mock_model
    assert awf.baseline_sharpe == 1.5
    assert awf.window_size == 252
    assert awf.step_size == 21
    assert isinstance(awf.drift_detector, DriftDetector)
    assert isinstance(awf.model_retrainer, ModelRetrainer)
    assert len(awf.performance_history) == 0
    assert len(awf.retrain_events) == 0


def test_adaptive_walk_forward_run_no_drift(mock_model, mock_retrain_callback):
    """Test walk-forward with no drift detected."""
    awf = AdaptiveWalkForward(
        model=mock_model,
        baseline_sharpe=1.5,
        retrain_callback=mock_retrain_callback,
        retrain_threshold=0.5,
        window_size=100,
        step_size=20,
    )
    
    # Generate stable POSITIVE returns (Sharpe > baseline to avoid drift)
    np.random.seed(42)
    n_samples = 300
    X = np.random.rand(n_samples, 10)
    y = np.random.rand(n_samples)
    returns = np.random.normal(0.003, 0.01, n_samples)  # High mean, low std = high Sharpe
    
    results = awf.run(X, y, returns)
    
    assert results["n_windows"] > 0
    assert results["n_retrains"] == 0  # No drift, no retrains
    assert len(awf.performance_history) > 0
    assert results["mean_sharpe"] > 0.0  # Positive Sharpe expected


def test_adaptive_walk_forward_run_with_drift(mock_model, mock_retrain_callback):
    """Test walk-forward with drift triggering retrain."""
    awf = AdaptiveWalkForward(
        model=mock_model,
        baseline_sharpe=1.5,
        retrain_callback=mock_retrain_callback,
        retrain_threshold=0.5,
        window_size=100,
        step_size=20,
        min_retrain_interval=10,  # Short interval for testing
    )
    
    # Generate returns with drift
    np.random.seed(42)
    returns_stable = np.random.normal(0.001, 0.02, 200)
    returns_drift = np.random.normal(-0.01, 0.03, 100)  # Significant drop
    returns = np.concatenate([returns_stable, returns_drift])
    
    X = np.random.rand(len(returns), 10)
    y = np.random.rand(len(returns))
    
    results = awf.run(X, y, returns)
    
    assert results["n_windows"] > 0
    assert results["n_retrains"] > 0  # Drift should trigger retrain
    assert len(awf.retrain_events) > 0
    
    # Check retrain event details
    first_event = awf.retrain_events[0]
    assert isinstance(first_event, RetrainEvent)
    assert first_event.trigger_reason is not None
    assert isinstance(first_event.metrics_before, PerformanceMetrics)


def test_adaptive_walk_forward_compute_metrics():
    """Test performance metrics computation."""
    awf = AdaptiveWalkForward(
        model=MagicMock(),
        baseline_sharpe=1.5,
        retrain_callback=lambda *args, **kwargs: {},
    )
    
    # Generate returns with known properties
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 252)
    
    metrics = awf._compute_metrics(returns, datetime.now())
    
    assert isinstance(metrics, PerformanceMetrics)
    assert metrics.sharpe_ratio > 0
    assert metrics.mean_return > 0
    assert metrics.std_return > 0
    assert 0 <= metrics.win_rate <= 100
    assert metrics.max_drawdown <= 0


def test_adaptive_walk_forward_min_retrain_interval(mock_model, mock_retrain_callback):
    """Test that minimum retrain interval is respected."""
    awf = AdaptiveWalkForward(
        model=mock_model,
        baseline_sharpe=1.5,
        retrain_callback=mock_retrain_callback,
        retrain_threshold=0.3,  # Low threshold (easy to trigger)
        window_size=50,
        step_size=10,
        min_retrain_interval=100,  # Large interval
    )
    
    # Generate returns with frequent drift
    np.random.seed(42)
    returns = np.random.normal(-0.005, 0.03, 200)  # Consistent poor performance
    
    X = np.random.rand(len(returns), 10)
    y = np.random.rand(len(returns))
    
    results = awf.run(X, y, returns)
    
    # Should have at most 1-2 retrains due to interval constraint
    assert results["n_retrains"] <= 2


def test_adaptive_walk_forward_plot_performance():
    """Test performance plotting."""
    awf = AdaptiveWalkForward(
        model=MagicMock(),
        baseline_sharpe=1.5,
        retrain_callback=lambda *args, **kwargs: {},
    )
    
    # Add some performance history
    for i in range(10):
        metrics = PerformanceMetrics(
            sharpe_ratio=1.5 - i * 0.1,
            sortino_ratio=2.0,
            max_drawdown=-10.0,
            win_rate=55.0,
            mean_return=0.001,
            std_return=0.02,
            timestamp=datetime.now() + timedelta(days=i),
        )
        awf.performance_history.append(metrics)
    
    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "performance.png"
        awf.plot_performance_history(save_path=save_path)
        
        assert save_path.exists()


def test_adaptive_walk_forward_plot_no_history():
    """Test plotting with no performance history."""
    awf = AdaptiveWalkForward(
        model=MagicMock(),
        baseline_sharpe=1.5,
        retrain_callback=lambda *args, **kwargs: {},
    )
    
    # Should not raise error
    awf.plot_performance_history()


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.slow
def test_full_adaptive_workflow(mock_model, mock_retrain_callback):
    """Test complete adaptive walk-forward workflow."""
    awf = AdaptiveWalkForward(
        model=mock_model,
        baseline_sharpe=1.5,
        retrain_callback=mock_retrain_callback,
        retrain_threshold=0.5,
        window_size=126,
        step_size=21,
        detection_method="combined",
        min_retrain_interval=42,
    )
    
    # Generate 2 years of data with regime change
    np.random.seed(42)
    returns_bull = np.random.normal(0.002, 0.015, 252)
    returns_bear = np.random.normal(-0.003, 0.035, 252)
    returns = np.concatenate([returns_bull, returns_bear])
    
    X = np.random.rand(len(returns), 20)
    y = np.random.rand(len(returns))
    dates = pd.date_range(end=datetime.now(), periods=len(returns), freq="D")
    
    results = awf.run(X, y, returns, dates=dates)
    
    # Validate results
    assert results["n_windows"] > 0
    assert len(awf.performance_history) == results["n_windows"]
    assert isinstance(results["final_sharpe"], (int, float))
    assert isinstance(results["mean_sharpe"], (int, float))
    assert isinstance(results["std_sharpe"], (int, float))
    
    # Check retrain events if any occurred
    if results["n_retrains"] > 0:
        for event in awf.retrain_events:
            assert isinstance(event, RetrainEvent)
            assert event.trigger_reason is not None
            assert isinstance(event.metrics_before, PerformanceMetrics)


@pytest.mark.slow
def test_adaptive_walk_forward_with_dates(mock_model, mock_retrain_callback):
    """Test walk-forward with explicit date handling."""
    awf = AdaptiveWalkForward(
        model=mock_model,
        baseline_sharpe=1.5,
        retrain_callback=mock_retrain_callback,
        window_size=100,
        step_size=20,
    )
    
    # Generate data with dates
    np.random.seed(42)
    n_samples = 300
    X = np.random.rand(n_samples, 10)
    y = np.random.rand(n_samples)
    returns = np.random.normal(0.001, 0.02, n_samples)
    dates = pd.date_range(start="2023-01-01", periods=n_samples, freq="D")
    
    results = awf.run(X, y, returns, dates=dates)
    
    # Check that timestamps in performance history match dates
    for metrics in awf.performance_history:
        assert isinstance(metrics.timestamp, datetime)


# ============================================================================
# EDGE CASES
# ============================================================================


def test_adaptive_walk_forward_small_dataset(mock_model, mock_retrain_callback):
    """Test with dataset smaller than window size."""
    awf = AdaptiveWalkForward(
        model=mock_model,
        baseline_sharpe=1.5,
        retrain_callback=mock_retrain_callback,
        window_size=200,
        step_size=50,
    )
    
    # Only 150 samples (less than window)
    X = np.random.rand(150, 10)
    y = np.random.rand(150)
    returns = np.random.normal(0.001, 0.02, 150)
    
    results = awf.run(X, y, returns)
    
    # Should have 0 windows since data < window_size
    assert results["n_windows"] == 0
    assert results["n_retrains"] == 0


def test_drift_detector_zero_std_returns():
    """Test drift detection with zero std returns (edge case)."""
    detector = DriftDetector(
        baseline_sharpe=1.5,
        threshold_pct=0.5,
        detection_method="threshold",
    )
    
    # All returns are identical (std = 0)
    returns = np.full(100, 0.001)
    current_metrics = PerformanceMetrics(
        sharpe_ratio=0.0,  # Division by zero → Sharpe = 0
        sortino_ratio=0.0,
        max_drawdown=0.0,
        win_rate=100.0,
        mean_return=0.001,
        std_return=0.0,
    )
    
    result = detector.detect_drift(returns, current_metrics)
    
    # Sharpe 0 < threshold (0.75) → drift detected
    assert result["is_drift"] is True


def test_model_retrainer_with_validation_data(mock_retrain_callback):
    """Test retrain with validation data."""
    retrainer = ModelRetrainer(retrain_callback=mock_retrain_callback)
    
    X = np.random.rand(100, 10)
    y = np.random.rand(100)
    X_val = np.random.rand(30, 10)
    y_val = np.random.rand(30)
    
    result = retrainer.retrain(
        X, y,
        reason="test",
        validation_data=(X_val, y_val)
    )
    
    assert result["success"] is True
    assert mock_retrain_callback.called
    
    # Check that validation data was passed
    call_kwargs = mock_retrain_callback.call_args[1]
    assert "validation_data" in call_kwargs
    assert call_kwargs["validation_data"] == (X_val, y_val)
