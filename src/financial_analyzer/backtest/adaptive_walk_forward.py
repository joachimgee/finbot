"""
Adaptive Walk-Forward Validation Module.

Implements automatic model retraining with performance drift detection:
- Rolling window validation
- Performance degradation detection (Sharpe drop, regime change)
- Auto-retrain triggers
- Hyperparameter adaptation over time

Audit:
    Inspired by QuantConnect's reality modeling and TensorTrade's adaptive strategies.
    Addresses model staleness in production (COMPARATIVE_ANALYSIS.md Priority 4).

Example:
    >>> from financial_analyzer.backtest.adaptive_walk_forward import AdaptiveWalkForward
    >>> 
    >>> # Create adaptive validator
    >>> awf = AdaptiveWalkForward(
    ...     model=trained_model,
    ...     retrain_threshold=0.5,  # Retrain when Sharpe drops 50%
    ...     window_size=252,         # 1-year rolling window
    ...     detection_method="cusum"
    ... )
    >>> 
    >>> # Run validation loop
    >>> results = awf.run(X_test, y_test, retrain_callback=lambda: retrain_model())
    >>> print(f"Retrain events: {results['n_retrains']}")
    >>> print(f"Final Sharpe: {results['final_sharpe']:.2f}")
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """
    Performance metrics for drift detection.
    
    Attributes:
        sharpe_ratio: Sharpe ratio over window
        sortino_ratio: Sortino ratio over window
        max_drawdown: Maximum drawdown (%)
        win_rate: Percentage of winning trades
        mean_return: Mean return over window
        std_return: Standard deviation of returns
        timestamp: Timestamp of metrics computation
    """

    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    mean_return: float
    std_return: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RetrainEvent:
    """
    Record of a retrain event.
    
    Attributes:
        timestamp: When retrain was triggered
        trigger_reason: Why retrain was triggered
        metrics_before: Performance before retrain
        metrics_after: Performance after retrain (optional)
        retrain_duration: Time taken to retrain (seconds)
    """

    timestamp: datetime
    trigger_reason: str
    metrics_before: PerformanceMetrics
    metrics_after: Optional[PerformanceMetrics] = None
    retrain_duration: Optional[float] = None


class DriftDetector:
    """
    Detects performance drift in trading models.
    
    Uses multiple methods to detect when model performance degrades:
    - Threshold-based: Sharpe drops below threshold
    - Statistical: t-test comparing recent vs baseline performance
    - CUSUM: Cumulative sum control chart for regime changes
    
    Args:
        baseline_sharpe: Expected Sharpe ratio (from training/validation)
        threshold_pct: Percentage drop to trigger retrain (e.g., 0.5 = 50% drop)
        detection_method: 'threshold', 'ttest', 'cusum', or 'combined'
        window_size: Rolling window for metrics computation (default: 252 = 1 year)
        cusum_threshold: CUSUM detection threshold (default: 5.0)
        confidence_level: Confidence level for t-test (default: 0.95)
    
    Example:
        >>> detector = DriftDetector(baseline_sharpe=1.5, threshold_pct=0.5)
        >>> drift = detector.detect_drift(returns_history, current_sharpe=0.7)
        >>> if drift.is_drift:
        ...     print(f"Drift detected: {drift.reason}")
    """

    def __init__(
        self,
        baseline_sharpe: float,
        threshold_pct: float = 0.5,
        detection_method: str = "combined",
        window_size: int = 252,
        cusum_threshold: float = 5.0,
        confidence_level: float = 0.95,
    ):
        """Initialize drift detector with baseline metrics."""
        self.baseline_sharpe = baseline_sharpe
        self.threshold_pct = threshold_pct
        self.detection_method = detection_method.lower()
        self.window_size = window_size
        self.cusum_threshold = cusum_threshold
        self.confidence_level = confidence_level

        # CUSUM state
        self._cusum_pos = 0.0
        self._cusum_neg = 0.0

        # Validation
        if self.detection_method not in ["threshold", "ttest", "cusum", "combined"]:
            raise ValueError(
                f"Invalid detection_method: {detection_method}. "
                "Must be 'threshold', 'ttest', 'cusum', or 'combined'."
            )

        logger.info(
            f"DriftDetector initialized: baseline_sharpe={baseline_sharpe:.2f}, "
            f"method={detection_method}, threshold={threshold_pct:.1%}"
        )

    def detect_drift(
        self,
        returns: np.ndarray,
        current_metrics: PerformanceMetrics,
    ) -> Dict[str, Any]:
        """
        Detect if performance has drifted significantly.
        
        Args:
            returns: Array of returns over detection window
            current_metrics: Current performance metrics
        
        Returns:
            Dict with keys:
                - is_drift: bool, whether drift detected
                - reason: str, explanation of drift
                - confidence: float, confidence level [0, 1]
                - method_results: dict, results from each detection method
        """
        results = {
            "is_drift": False,
            "reason": "No drift detected",
            "confidence": 0.0,
            "method_results": {},
        }

        # Method 1: Threshold-based (Sharpe drop)
        if self.detection_method in ["threshold", "combined"]:
            threshold_result = self._detect_threshold(current_metrics.sharpe_ratio)
            results["method_results"]["threshold"] = threshold_result

            if threshold_result["is_drift"]:
                results["is_drift"] = True
                results["reason"] = threshold_result["reason"]
                results["confidence"] = max(results["confidence"], threshold_result["confidence"])

        # Method 2: T-test (statistical significance)
        if self.detection_method in ["ttest", "combined"]:
            ttest_result = self._detect_ttest(returns)
            results["method_results"]["ttest"] = ttest_result

            if ttest_result["is_drift"]:
                results["is_drift"] = True
                results["reason"] = ttest_result["reason"]
                results["confidence"] = max(results["confidence"], ttest_result["confidence"])

        # Method 3: CUSUM (cumulative sum control chart)
        if self.detection_method in ["cusum", "combined"]:
            cusum_result = self._detect_cusum(returns)
            results["method_results"]["cusum"] = cusum_result

            if cusum_result["is_drift"]:
                results["is_drift"] = True
                results["reason"] = cusum_result["reason"]
                results["confidence"] = max(results["confidence"], cusum_result["confidence"])

        if results["is_drift"]:
            logger.warning(
                f"Drift detected: {results['reason']} (confidence={results['confidence']:.2%})"
            )
        else:
            logger.debug("No drift detected")

        return results

    def _detect_threshold(self, current_sharpe: float) -> Dict[str, Any]:
        """Detect drift via Sharpe threshold."""
        threshold = self.baseline_sharpe * (1 - self.threshold_pct)
        is_drift = current_sharpe < threshold

        drop_pct = (self.baseline_sharpe - current_sharpe) / self.baseline_sharpe

        return {
            "is_drift": is_drift,
            "reason": (
                f"Sharpe dropped {drop_pct:.1%} from baseline "
                f"({self.baseline_sharpe:.2f} → {current_sharpe:.2f})"
                if is_drift
                else "Sharpe above threshold"
            ),
            "confidence": min(drop_pct / self.threshold_pct, 1.0) if is_drift else 0.0,
            "current_sharpe": current_sharpe,
            "threshold": threshold,
        }

    def _detect_ttest(self, returns: np.ndarray) -> Dict[str, Any]:
        """Detect drift via t-test comparing recent returns to zero."""
        if len(returns) < 10:
            return {
                "is_drift": False,
                "reason": "Insufficient data for t-test",
                "confidence": 0.0,
            }

        # One-sample t-test: H0 = mean return is zero
        t_stat, p_value = stats.ttest_1samp(returns, 0.0)

        # Drift if returns are significantly negative
        is_drift = (t_stat < 0) and (p_value < (1 - self.confidence_level))

        return {
            "is_drift": is_drift,
            "reason": (
                f"Returns significantly negative (t={t_stat:.2f}, p={p_value:.4f})"
                if is_drift
                else "Returns not significantly different from zero"
            ),
            "confidence": (1 - p_value) if is_drift else 0.0,
            "t_stat": t_stat,
            "p_value": p_value,
        }

    def _detect_cusum(self, returns: np.ndarray) -> Dict[str, Any]:
        """
        Detect drift via CUSUM (Cumulative Sum Control Chart).
        
        CUSUM detects small shifts in mean by accumulating deviations.
        Sensitive to regime changes that threshold-based methods miss.
        """
        if len(returns) < 10:
            return {
                "is_drift": False,
                "reason": "Insufficient data for CUSUM",
                "confidence": 0.0,
            }

        # Expected mean (zero for returns)
        target_mean = 0.0
        std = np.std(returns)

        # Reset if first call
        if not hasattr(self, "_cusum_initialized"):
            self._cusum_pos = 0.0
            self._cusum_neg = 0.0
            self._cusum_initialized = True

        # Update CUSUM statistics
        for ret in returns:
            deviation = ret - target_mean

            # Positive CUSUM (detects downward shift)
            self._cusum_pos = max(0, self._cusum_pos + deviation - 0.5 * std)

            # Negative CUSUM (detects upward shift)
            self._cusum_neg = min(0, self._cusum_neg + deviation + 0.5 * std)

        # Drift if either CUSUM exceeds threshold
        is_drift = (
            abs(self._cusum_pos) > self.cusum_threshold
            or abs(self._cusum_neg) > self.cusum_threshold
        )

        return {
            "is_drift": is_drift,
            "reason": (
                f"CUSUM threshold exceeded (pos={self._cusum_pos:.2f}, "
                f"neg={self._cusum_neg:.2f}, threshold={self.cusum_threshold})"
                if is_drift
                else "CUSUM within control limits"
            ),
            "confidence": (
                min(max(abs(self._cusum_pos), abs(self._cusum_neg)) / self.cusum_threshold, 1.0)
                if is_drift
                else 0.0
            ),
            "cusum_pos": self._cusum_pos,
            "cusum_neg": self._cusum_neg,
        }

    def reset_cusum(self) -> None:
        """Reset CUSUM state (call after retrain)."""
        self._cusum_pos = 0.0
        self._cusum_neg = 0.0
        logger.debug("CUSUM state reset")


class ModelRetrainer:
    """
    Handles automatic model retraining with adaptive hyperparameters.
    
    Features:
    - Incremental training on new data window
    - Learning rate decay over time
    - Batch size adaptation
    - Early stopping based on validation metrics
    
    Args:
        retrain_callback: Function to call for retraining (receives training data)
        learning_rate_decay: Decay factor for learning rate (default: 0.9)
        min_learning_rate: Minimum learning rate (default: 1e-6)
        batch_size_growth: Growth factor for batch size (default: 1.1)
        max_batch_size: Maximum batch size (default: 1024)
        early_stopping_patience: Patience for early stopping (default: 10)
    
    Example:
        >>> def my_retrain(X, y, lr, batch_size):
        ...     model.fit(X, y, learning_rate=lr, batch_size=batch_size)
        >>> 
        >>> retrainer = ModelRetrainer(retrain_callback=my_retrain)
        >>> retrainer.retrain(X_new, y_new, reason="drift_detected")
    """

    def __init__(
        self,
        retrain_callback: Callable,
        learning_rate_decay: float = 0.9,
        min_learning_rate: float = 1e-6,
        batch_size_growth: float = 1.1,
        max_batch_size: int = 1024,
        early_stopping_patience: int = 10,
    ):
        """Initialize model retrainer with adaptive parameters."""
        self.retrain_callback = retrain_callback
        self.learning_rate_decay = learning_rate_decay
        self.min_learning_rate = min_learning_rate
        self.batch_size_growth = batch_size_growth
        self.max_batch_size = max_batch_size
        self.early_stopping_patience = early_stopping_patience

        # Adaptive state
        self.current_learning_rate = 3e-4  # Initial LR (stable-baselines3 default)
        self.current_batch_size = 64
        self.retrain_count = 0

        logger.info("ModelRetrainer initialized with adaptive hyperparameters")

    def retrain(
        self,
        X: np.ndarray,
        y: np.ndarray,
        reason: str,
        validation_data: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    ) -> Dict[str, Any]:
        """
        Retrain model with adaptive hyperparameters.
        
        Args:
            X: Training features
            y: Training labels
            reason: Reason for retrain (for logging)
            validation_data: Optional (X_val, y_val) for early stopping
        
        Returns:
            Dict with retrain results (duration, metrics, hyperparameters used)
        """
        start_time = datetime.now()
        self.retrain_count += 1

        logger.info(
            f"Starting retrain #{self.retrain_count} (reason: {reason}). "
            f"LR={self.current_learning_rate:.2e}, batch_size={self.current_batch_size}"
        )

        # Call user-provided retrain function
        try:
            retrain_result = self.retrain_callback(
                X,
                y,
                learning_rate=self.current_learning_rate,
                batch_size=self.current_batch_size,
                validation_data=validation_data,
                early_stopping_patience=self.early_stopping_patience,
            )
        except Exception as e:
            logger.error(f"Retrain failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": (datetime.now() - start_time).total_seconds(),
            }

        duration = (datetime.now() - start_time).total_seconds()

        # Adapt hyperparameters for next retrain
        self._adapt_hyperparameters()

        logger.info(
            f"Retrain #{self.retrain_count} complete in {duration:.1f}s. "
            f"Next LR={self.current_learning_rate:.2e}, "
            f"batch_size={self.current_batch_size}"
        )

        return {
            "success": True,
            "duration": duration,
            "retrain_count": self.retrain_count,
            "learning_rate": self.current_learning_rate,
            "batch_size": self.current_batch_size,
            "retrain_result": retrain_result,
        }

    def _adapt_hyperparameters(self) -> None:
        """Adapt hyperparameters based on retrain history."""
        # Decay learning rate (model should be more conservative over time)
        self.current_learning_rate = max(
            self.current_learning_rate * self.learning_rate_decay,
            self.min_learning_rate,
        )

        # Increase batch size (larger batches = more stable gradients)
        self.current_batch_size = min(
            int(self.current_batch_size * self.batch_size_growth),
            self.max_batch_size,
        )

        logger.debug(
            f"Hyperparameters adapted: LR={self.current_learning_rate:.2e}, "
            f"batch_size={self.current_batch_size}"
        )


class AdaptiveWalkForward:
    """
    Adaptive Walk-Forward Validation with auto-retrain.
    
    Main orchestrator for:
    - Rolling window validation
    - Performance drift detection
    - Automatic model retraining
    - Hyperparameter adaptation
    
    Args:
        model: Trading model to validate (must have predict() method)
        baseline_sharpe: Expected Sharpe from training/validation
        retrain_callback: Function to retrain model (receives X, y, hyperparams)
        retrain_threshold: Sharpe drop threshold for retrain (default: 0.5 = 50%)
        window_size: Rolling window size in trading days (default: 252 = 1 year)
        step_size: Step size for walk-forward (default: 21 = 1 month)
        detection_method: Drift detection method ('threshold', 'ttest', 'cusum', 'combined')
        min_retrain_interval: Minimum days between retrains (default: 63 = 3 months)
    
    Example:
        >>> from financial_analyzer.backtest import AdaptiveWalkForward
        >>> 
        >>> # Create validator
        >>> awf = AdaptiveWalkForward(
        ...     model=my_model,
        ...     baseline_sharpe=1.5,
        ...     retrain_callback=lambda X, y, **kw: my_model.fit(X, y),
        ...     retrain_threshold=0.5,
        ...     window_size=252
        ... )
        >>> 
        >>> # Run adaptive validation
        >>> results = awf.run(X_test, y_test, returns_test)
        >>> 
        >>> print(f"Retrain events: {results['n_retrains']}")
        >>> print(f"Final Sharpe: {results['final_sharpe']:.2f}")
        >>> 
        >>> # Plot drift over time
        >>> awf.plot_performance_history(save_path="drift.png")
    """

    def __init__(
        self,
        model: Any,
        baseline_sharpe: float,
        retrain_callback: Callable,
        retrain_threshold: float = 0.5,
        window_size: int = 252,
        step_size: int = 21,
        detection_method: str = "combined",
        min_retrain_interval: int = 63,
    ):
        """Initialize adaptive walk-forward validator."""
        self.model = model
        self.baseline_sharpe = baseline_sharpe
        self.retrain_callback = retrain_callback
        self.retrain_threshold = retrain_threshold
        self.window_size = window_size
        self.step_size = step_size
        self.detection_method = detection_method
        self.min_retrain_interval = min_retrain_interval

        # Initialize components
        self.drift_detector = DriftDetector(
            baseline_sharpe=baseline_sharpe,
            threshold_pct=retrain_threshold,
            detection_method=detection_method,
            window_size=window_size,
        )

        self.model_retrainer = ModelRetrainer(retrain_callback=retrain_callback)

        # History tracking
        self.performance_history: List[PerformanceMetrics] = []
        self.retrain_events: List[RetrainEvent] = []
        self.last_retrain_step = -min_retrain_interval  # Allow immediate first retrain

        logger.info(
            f"AdaptiveWalkForward initialized: baseline_sharpe={baseline_sharpe:.2f}, "
            f"threshold={retrain_threshold:.1%}, window={window_size}, step={step_size}"
        )

    def run(
        self,
        X: np.ndarray,
        y: np.ndarray,
        returns: np.ndarray,
        dates: Optional[pd.DatetimeIndex] = None,
    ) -> Dict[str, Any]:
        """
        Run adaptive walk-forward validation.
        
        Args:
            X: Feature data (n_samples, n_features)
            y: Target data (n_samples,)
            returns: Returns data for performance metrics (n_samples,)
            dates: Optional dates for time-aware validation
        
        Returns:
            Dict with validation results:
                - n_retrains: Number of retrain events
                - final_sharpe: Final Sharpe ratio
                - mean_sharpe: Mean Sharpe across windows
                - retrain_events: List of RetrainEvent objects
                - performance_history: List of PerformanceMetrics
        """
        n_samples = len(X)
        if dates is None:
            dates = pd.date_range(end=datetime.now(), periods=n_samples, freq="D")

        logger.info(
            f"Starting adaptive walk-forward on {n_samples} samples "
            f"(window={self.window_size}, step={self.step_size})"
        )

        current_step = 0
        n_windows = 0

        # Walk forward through data
        for start_idx in range(0, n_samples - self.window_size, self.step_size):
            end_idx = start_idx + self.window_size

            # Extract window
            X_window = X[start_idx:end_idx]
            y_window = y[start_idx:end_idx]
            returns_window = returns[start_idx:end_idx]

            # Compute performance metrics
            metrics = self._compute_metrics(returns_window, dates[end_idx - 1])
            self.performance_history.append(metrics)

            # Check for drift
            drift_result = self.drift_detector.detect_drift(returns_window, metrics)

            # Retrain if drift detected and sufficient time passed
            if drift_result["is_drift"]:
                steps_since_retrain = current_step - self.last_retrain_step

                if steps_since_retrain >= self.min_retrain_interval:
                    logger.warning(
                        f"Drift detected at step {current_step} "
                        f"({drift_result['reason']}). Triggering retrain..."
                    )

                    retrain_event = self._trigger_retrain(
                        X_window, y_window, drift_result["reason"], metrics
                    )
                    self.retrain_events.append(retrain_event)
                    self.last_retrain_step = current_step

                    # Reset drift detector state
                    self.drift_detector.reset_cusum()
                else:
                    logger.info(
                        f"Drift detected but skipping retrain "
                        f"(only {steps_since_retrain} steps since last retrain, "
                        f"min={self.min_retrain_interval})"
                    )

            current_step += self.step_size
            n_windows += 1

        # Compute summary statistics
        sharpe_values = [m.sharpe_ratio for m in self.performance_history]
        final_sharpe = sharpe_values[-1] if sharpe_values else 0.0
        mean_sharpe = np.mean(sharpe_values) if sharpe_values else 0.0

        results = {
            "n_windows": n_windows,
            "n_retrains": len(self.retrain_events),
            "final_sharpe": final_sharpe,
            "mean_sharpe": mean_sharpe,
            "std_sharpe": np.std(sharpe_values) if len(sharpe_values) > 1 else 0.0,
            "retrain_events": self.retrain_events,
            "performance_history": self.performance_history,
        }

        logger.info(
            f"Adaptive walk-forward complete: {n_windows} windows, "
            f"{len(self.retrain_events)} retrains, "
            f"final_sharpe={final_sharpe:.2f}, mean_sharpe={mean_sharpe:.2f}"
        )

        return results

    def _compute_metrics(
        self, returns: np.ndarray, timestamp: datetime
    ) -> PerformanceMetrics:
        """Compute performance metrics for window."""
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)

        # Sharpe ratio (annualized)
        sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0

        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else std_ret
        sortino = (mean_ret / downside_std) * np.sqrt(252) if downside_std > 0 else 0.0

        # Max drawdown
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (cum_returns - running_max) / running_max
        max_dd = np.min(drawdown) * 100

        # Win rate
        win_rate = (np.sum(returns > 0) / len(returns)) * 100 if len(returns) > 0 else 0.0

        return PerformanceMetrics(
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            win_rate=win_rate,
            mean_return=mean_ret,
            std_return=std_ret,
            timestamp=timestamp,
        )

    def _trigger_retrain(
        self,
        X: np.ndarray,
        y: np.ndarray,
        reason: str,
        metrics_before: PerformanceMetrics,
    ) -> RetrainEvent:
        """Trigger model retrain and record event."""
        retrain_result = self.model_retrainer.retrain(X, y, reason)

        event = RetrainEvent(
            timestamp=datetime.now(),
            trigger_reason=reason,
            metrics_before=metrics_before,
            retrain_duration=retrain_result.get("duration"),
        )

        return event

    def plot_performance_history(
        self, save_path: Optional[Union[str, Path]] = None
    ) -> None:
        """
        Plot performance metrics over time.
        
        Args:
            save_path: Path to save plot (optional)
        """
        if not self.performance_history:
            logger.warning("No performance history to plot")
            return

        import matplotlib.pyplot as plt

        timestamps = [m.timestamp for m in self.performance_history]
        sharpe = [m.sharpe_ratio for m in self.performance_history]
        sortino = [m.sortino_ratio for m in self.performance_history]

        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(timestamps, sharpe, label="Sharpe Ratio", linewidth=2)
        ax.plot(timestamps, sortino, label="Sortino Ratio", linewidth=2, alpha=0.7)
        ax.axhline(
            self.baseline_sharpe, color="green", linestyle="--", label="Baseline Sharpe"
        )
        ax.axhline(
            self.baseline_sharpe * (1 - self.retrain_threshold),
            color="red",
            linestyle="--",
            label="Retrain Threshold",
        )

        # Mark retrain events
        for event in self.retrain_events:
            ax.axvline(event.timestamp, color="orange", alpha=0.5, linestyle=":")

        ax.set_xlabel("Time")
        ax.set_ylabel("Ratio")
        ax.set_title("Adaptive Walk-Forward: Performance Over Time")
        ax.legend()
        ax.grid(alpha=0.3)

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Performance plot saved to {save_path}")

        plt.close(fig)
