"""Walk-Forward Analysis (WFA) - Robust Out-of-Sample Validation.

Implements classical WFA workflow:
1. Split data into expanding/rolling windows
2. Train on in-sample (optimize parameters)
3. Test on out-of-sample (validate robustness)
4. Roll forward and repeat

Features:
- Expanding window (growing training set)
- Rolling window (fixed training set)
- Nested cross-validation
- Parameter stability metrics
- Out-of-sample statistics

QUICK START GUIDE
-----------------

1. Prepare data (Dict[str, DataFrame] with 'Close' column and aligned datetime index)
2. Create WalkForwardAnalyzer(data, train_ratio=0.8, rolling=False)
3. Call run(param_grid={'param': [values]}, optimize_metric='sharpe')
4. Analyze results.summary() + results.window_results

INTERPRETATION GUIDELINES
-------------------------

Parameter Stability:
    - > 70%: Robust parameters across windows
    - 50-70%: Moderate stability, some regime changes
    - < 50%: High variability, potential overfitting

Degradation (IS - OOS):
    - < 10%: Excellent generalization
    - 10-20%: Acceptable generalization
    - > 20%: Poor generalization, overfitting likely

Out-of-Sample Sharpe:
    - > 1.5: Strong performance
    - 1.0-1.5: Good performance
    - 0.5-1.0: Acceptable performance
    - < 0.5: Weak performance

COMMON ISSUES
-------------

"Data cannot be empty":
    Ensure data dict has values and DataFrames are not empty.

"All DataFrames must have same length":
    Check that all price data is aligned on same datetime index.
    Use pd.DataFrame.reindex() to align if needed.

"IndexError in windows":
    Check train_ratio (should be 0.5-0.9).
    Ensure sufficient data (min ~100 bars recommended).

Low param_stability:
    Consider simplifying param_grid or increasing data length.
    High variability may indicate regime changes in markets.

Example
-------
    >>> from financial_analyzer.backtesting import WalkForwardAnalyzer
    >>>
    >>> wfa = WalkForwardAnalyzer(
    ...     data=price_data,
    ...     train_ratio=0.8,
    ...     rolling=False  # Expanding window
    ... )
    >>>
    >>> results = wfa.run(
    ...     strategy_class=FinBotBacktester,
    ...     param_grid={'rebalance_period': [5, 10, 20]},
    ...     optimize_metric='sharpe'
    ... )
    >>>
    >>> print(f"Out-of-sample Sharpe: {results.oos_metrics['sharpe']:.2f}")
    >>> print(f"Parameter stability: {results.param_stability:.2%}")
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from datetime import datetime

from financial_analyzer.backtesting.finbot_strategy import FinBotBacktester, RiskConfig
from financial_analyzer.backtesting.backtest_runner import run as run_backtest, _compute_metrics
# run_backtest signature: run(data: Dict[str, DataFrame], **kwargs) -> BacktestResult
# where BacktestResult.metrics = {'sharpe': float, 'return': float, 'vol': float, 'max_dd': float}
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class WFAWindow:
    """Single walk-forward window.

    Attributes:
        window_id: Sequential window identifier
        train_start: Start date of training period
        train_end: End date of training period
        test_start: Start date of test period
        test_end: End date of test period
        train_data: Dictionary of training DataFrames per ticker
        test_data: Dictionary of test DataFrames per ticker
    """

    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_data: Dict[str, pd.DataFrame]
    test_data: Dict[str, pd.DataFrame]

    @property
    def train_size(self) -> int:
        """Number of rows in training data."""
        return len(next(iter(self.train_data.values())))

    @property
    def test_size(self) -> int:
        """Number of rows in test data."""
        return len(next(iter(self.test_data.values())))


@dataclass
class WFAResult:
    """Walk-forward analysis result.

    Attributes:
        strategy_name: Name of strategy class used
        total_windows: Number of WFA windows
        train_periods: List of (start, end) tuples for training
        test_periods: List of (start, end) tuples for testing
        window_results: Detailed results per window
        is_metrics: In-sample aggregated metrics
        oos_metrics: Out-of-sample aggregated metrics
        param_stability: Parameter stability score (0-1)
        best_params_frequency: Frequency count of best parameters
        is_oos_degradation: Degradation metrics (IS - OOS)
    """

    strategy_name: str
    total_windows: int
    train_periods: List[Tuple[datetime, datetime]]
    test_periods: List[Tuple[datetime, datetime]]

    # Per-window results
    window_results: List[Dict[str, Any]] = field(default_factory=list)

    # Aggregated metrics
    is_metrics: Dict[str, float] = field(default_factory=dict)  # In-sample
    oos_metrics: Dict[str, float] = field(default_factory=dict)  # Out-of-sample

    # Parameter stability
    param_stability: float = 0.0  # 0-1 (1 = stable)
    best_params_frequency: Dict[str, int] = field(default_factory=dict)

    # Degradation analysis
    is_oos_degradation: Dict[str, float] = field(default_factory=dict)  # IS - OOS

    def summary(self) -> str:
        """Generate summary report.

        Returns:
            Formatted string with all key metrics.
        """
        report = []
        report.append("=" * 60)
        report.append("WALK-FORWARD ANALYSIS RESULTS")
        report.append("=" * 60)
        report.append(f"Strategy: {self.strategy_name}")
        report.append(f"Windows: {self.total_windows}")
        report.append("")

        report.append("IN-SAMPLE METRICS:")
        for metric, value in self.is_metrics.items():
            report.append(f"  {metric}: {value:.4f}")

        report.append("\nOUT-OF-SAMPLE METRICS:")
        for metric, value in self.oos_metrics.items():
            report.append(f"  {metric}: {value:.4f}")

        report.append("\nDEGRADATION (IS - OOS):")
        for metric, value in self.is_oos_degradation.items():
            is_val = self.is_metrics.get(metric, 1.0)
            pct = abs(value) / abs(is_val) * 100 if is_val != 0 else 0.0
            report.append(f"  {metric}: {value:.4f} ({pct:.1f}%)")

        report.append(f"\nPARAMETER STABILITY: {self.param_stability:.1%}")
        report.append(f"Most stable params: {self.best_params_frequency}")

        report.append("=" * 60)
        return "\n".join(report)


class WalkForwardAnalyzer:
    """Walk-forward analysis engine.

    Performs robust out-of-sample validation by splitting data into
    multiple train/test windows and rolling forward.

    PERFORMANCE CONSIDERATIONS
    --------------------------

    Time Complexity:
        - Creating windows: O(n) where n = len(data)
        - Per-window optimization: O(w × c) where w = windows, c = param combinations
        - Total: O(w × c × t) where t = time to run single backtest

    Space Complexity:
        - O(n) for storing all windows (copies of data)

    Optimization Tips:
        1. Use smaller param_grid to reduce combinations (grows exponentially!)
           Example: 3 params × 3 values each = 27 combinations per window
                    10 windows × 27 combinations = 270 backtests!

        2. Use rolling windows for faster analysis (generates fewer windows)

        3. Adjust step_size to control number of windows:
           - Larger step_size = fewer windows = faster but less robust
           - Smaller step_size = more windows = slower but more robust

        4. For quick validation, start with:
           - train_ratio=0.8, rolling=False, step_size=50
           - Small param_grid (2-3 values per param max)

    Example Timing (4 tickers, 500 bars):
        - 5 windows × 9 param combos × 5s per backtest = 225s ≈ 3.75 min
        - Reduce to 3 param combos → 75s ≈ 1.25 min

    Attributes:
        data: Dictionary of OHLC DataFrames per ticker
        train_ratio: Proportion of data for training
        rolling: If True, use rolling window; else expanding
        step_size: Number of rows to step forward
        initial_window: Initial training window size
        total_length: Total length of time series
        train_size: Training window size
        test_size: Test window size
    """

    def __init__(
        self,
        data: Dict[str, pd.DataFrame],
        train_ratio: float = 0.8,
        rolling: bool = False,
        step_size: Optional[int] = None,
        initial_window: Optional[int] = None,
    ) -> None:
        """Initialize WFA analyzer.

        Args:
            data: Dict[ticker, OHLC DataFrame with 'Close' column]
            train_ratio: Train/test split (0.8 = 80% train, 20% test)
            rolling: If True, use rolling window; if False, expanding window
            step_size: Step size in rows (if None, use test window size)
            initial_window: Initial training window size (if None, calculated from train_ratio)

        Raises:
            ValueError: If data is empty or train_ratio invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
        if not 0.0 < train_ratio < 1.0:
            raise ValueError("train_ratio must be between 0 and 1")

        self.data = data
        self.train_ratio = train_ratio
        self.rolling = rolling

        # Get time series length (assume all tickers aligned)
        self.total_length = len(next(iter(data.values())))
        
        # Validate all DataFrames have same length (critical for WFA)
        lengths = {ticker: len(df) for ticker, df in data.items()}
        if not all(length == self.total_length for length in lengths.values()):
            raise ValueError(
                f"All DataFrames must have same length. Found lengths: {lengths}. "
                f"Ensure all price data is aligned on same datetime index."
            )

        # Calculate window sizes
        train_size = int(self.total_length * train_ratio)
        test_size = self.total_length - train_size

        self.train_size = train_size
        self.test_size = test_size
        # Default step_size: use half of test_size for more robust validation
        # (generates more windows, better out-of-sample coverage)
        self.step_size = step_size or max(1, test_size // 2)
        self.initial_window = initial_window or train_size

        logger.info(
            f"WFA Setup: total={self.total_length}, train={train_size}, "
            f"test={test_size}, rolling={rolling}, step={self.step_size}"
        )

    def _create_windows(self) -> List[WFAWindow]:
        """Create train/test windows based on configuration.

        Returns:
            List of WFAWindow objects.
        """
        windows: List[WFAWindow] = []
        first_ticker = next(iter(self.data))
        all_dates = self.data[first_ticker].index

        if self.rolling:
            # Fixed window size, rolling forward
            step = self.step_size
            current_train_start = 0

            while current_train_start + self.train_size + self.test_size <= self.total_length:
                train_start_idx = current_train_start
                train_end_idx = current_train_start + self.train_size
                test_start_idx = train_end_idx
                test_end_idx = test_start_idx + self.test_size

                if test_end_idx > self.total_length:
                    break

                # Split data
                train_data = {
                    ticker: df.iloc[train_start_idx:train_end_idx].copy()
                    for ticker, df in self.data.items()
                }
                test_data = {
                    ticker: df.iloc[test_start_idx:test_end_idx].copy()
                    for ticker, df in self.data.items()
                }

                window = WFAWindow(
                    window_id=len(windows),
                    train_start=all_dates[train_start_idx],
                    train_end=all_dates[train_end_idx - 1],
                    test_start=all_dates[test_start_idx],
                    test_end=all_dates[test_end_idx - 1],
                    train_data=train_data,
                    test_data=test_data,
                )

                windows.append(window)
                current_train_start += step

        else:
            # Expanding window (train grows, test window fixed)
            step = self.step_size
            current_train_start = 0
            current_train_end = self.initial_window

            window_id = 0
            while current_train_end + self.test_size <= self.total_length:
                test_start = current_train_end
                test_end = test_start + self.test_size

                # Split data
                train_data = {
                    ticker: df.iloc[current_train_start:current_train_end].copy()
                    for ticker, df in self.data.items()
                }
                test_data = {
                    ticker: df.iloc[test_start:test_end].copy() for ticker, df in self.data.items()
                }

                window = WFAWindow(
                    window_id=window_id,
                    train_start=all_dates[current_train_start],
                    train_end=all_dates[current_train_end - 1],
                    test_start=all_dates[test_start],
                    test_end=all_dates[test_end - 1],
                    train_data=train_data,
                    test_data=test_data,
                )

                windows.append(window)

                # Move forward (expanding: train grows by step)
                current_train_end += step
                window_id += 1

        logger.info(f"Created {len(windows)} WFA windows ({'rolling' if self.rolling else 'expanding'})")
        return windows

    def _optimize_params(
        self,
        train_data: Dict[str, pd.DataFrame],
        param_grid: Dict[str, List[Any]],
        optimize_metric: str,
        strategy_kwargs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Optimize parameters on training data.

        Args:
            train_data: Training data dictionary
            param_grid: Parameter grid to search
            optimize_metric: Metric to optimize (e.g., 'sharpe', 'return')
            strategy_kwargs: Base kwargs for strategy

        Returns:
            Tuple of (best_params, best_metrics)
        """
        if not param_grid:
            # No optimization, run with defaults
            try:
                result = run_backtest(train_data, **strategy_kwargs)
                metrics = result.metrics
                return {}, metrics
            except Exception as e:
                logger.warning(f"Backtest failed with defaults: {e}")
                return {}, {'sharpe': 0.0, 'return': 0.0, 'vol': 0.0, 'max_dd': 0.0}

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))

        best_score = -np.inf
        best_params: Dict[str, Any] = {}
        best_metrics: Dict[str, float] = {}

        for combo in combinations:
            params = dict(zip(param_names, combo))

            # Merge params into strategy_kwargs
            test_kwargs = strategy_kwargs.copy()

            # Handle risk-related params
            if any(k in params for k in ['max_position', 'stop_loss_pct', 'take_profit_pct', 'rebalance_period']):
                risk_cfg = RiskConfig(
                    max_position=params.get('max_position', 0.2),
                    stop_loss_pct=params.get('stop_loss_pct', 0.15),
                    take_profit_pct=params.get('take_profit_pct', 0.50),
                    rebalance_period=params.get('rebalance_period', 20),
                )
                test_kwargs['risk'] = risk_cfg

            # Update other params
            for k, v in params.items():
                if k not in ['max_position', 'stop_loss_pct', 'take_profit_pct', 'rebalance_period']:
                    test_kwargs[k] = v

            try:
                result = run_backtest(train_data, **test_kwargs)
                metrics = result.metrics
                score = metrics.get(optimize_metric, 0.0)

                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_metrics = metrics.copy()

            except Exception as e:
                logger.warning(f"Backtest failed for params {params}: {e}")
                continue

        logger.debug(f"Best params: {best_params}, {optimize_metric}={best_score:.4f}")
        return best_params, best_metrics

    def run(
        self,
        strategy_class: type = FinBotBacktester,
        param_grid: Optional[Dict[str, List[Any]]] = None,
        optimize_metric: str = 'sharpe',
        strategy_kwargs: Optional[Dict[str, Any]] = None,
    ) -> WFAResult:
        """Run walk-forward analysis.

        Args:
            strategy_class: Strategy class to backtest (unused, kept for compatibility)
            param_grid: Parameter grid for optimization (e.g., {'rebalance_period': [5, 10, 20]})
            optimize_metric: Metric to optimize on (default: 'sharpe')
            strategy_kwargs: Additional kwargs for strategy (e.g., lookback_days, initial_cash)

        Returns:
            WFAResult with all statistics

        Example:
            >>> wfa = WalkForwardAnalyzer(data, train_ratio=0.8)
            >>> result = wfa.run(
            ...     param_grid={'rebalance_period': [10, 20]},
            ...     optimize_metric='sharpe'
            ... )
            >>> print(result.summary())
        """
        windows = self._create_windows()

        if param_grid is None:
            param_grid = {}

        if strategy_kwargs is None:
            strategy_kwargs = {}

        result = WFAResult(
            strategy_name=strategy_class.__name__,
            total_windows=len(windows),
            train_periods=[(w.train_start, w.train_end) for w in windows],
            test_periods=[(w.test_start, w.test_end) for w in windows],
        )

        is_sharpe_list: List[float] = []
        is_return_list: List[float] = []
        is_vol_list: List[float] = []
        is_dd_list: List[float] = []

        oos_sharpe_list: List[float] = []
        oos_return_list: List[float] = []
        oos_vol_list: List[float] = []
        oos_dd_list: List[float] = []

        best_params_list: List[Dict[str, Any]] = []

        for window in windows:
            logger.info(f"Processing WFA window {window.window_id + 1}/{len(windows)}")

            # 1. Optimize on in-sample (train)
            best_params, is_metrics = self._optimize_params(
                window.train_data, param_grid, optimize_metric, strategy_kwargs
            )

            is_sharpe_list.append(is_metrics.get('sharpe', 0.0))
            is_return_list.append(is_metrics.get('return', 0.0))
            is_vol_list.append(is_metrics.get('vol', 0.0))
            is_dd_list.append(is_metrics.get('max_dd', 0.0))

            # 2. Test on out-of-sample (test) with best params
            test_kwargs = strategy_kwargs.copy()

            # Apply best params
            if any(k in best_params for k in ['max_position', 'stop_loss_pct', 'take_profit_pct', 'rebalance_period']):
                risk_cfg = RiskConfig(
                    max_position=best_params.get('max_position', 0.2),
                    stop_loss_pct=best_params.get('stop_loss_pct', 0.15),
                    take_profit_pct=best_params.get('take_profit_pct', 0.50),
                    rebalance_period=best_params.get('rebalance_period', 20),
                )
                test_kwargs['risk'] = risk_cfg

            for k, v in best_params.items():
                if k not in ['max_position', 'stop_loss_pct', 'take_profit_pct', 'rebalance_period']:
                    test_kwargs[k] = v

            try:
                oos_result = run_backtest(window.test_data, **test_kwargs)
                oos_metrics = oos_result.metrics
            except Exception as e:
                logger.warning(f"OOS backtest failed for window {window.window_id}: {e}")
                oos_metrics = {'sharpe': 0.0, 'return': 0.0, 'vol': 0.0, 'max_dd': 0.0}

            oos_sharpe_list.append(oos_metrics.get('sharpe', 0.0))
            oos_return_list.append(oos_metrics.get('return', 0.0))
            oos_vol_list.append(oos_metrics.get('vol', 0.0))
            oos_dd_list.append(oos_metrics.get('max_dd', 0.0))

            window_result = {
                'window_id': window.window_id,
                'train_period': (window.train_start, window.train_end),
                'test_period': (window.test_start, window.test_end),
                'best_params': best_params,
                'is_sharpe': is_metrics.get('sharpe', 0.0),
                'is_return': is_metrics.get('return', 0.0),
                'is_vol': is_metrics.get('vol', 0.0),
                'is_max_dd': is_metrics.get('max_dd', 0.0),
                'oos_sharpe': oos_metrics.get('sharpe', 0.0),
                'oos_return': oos_metrics.get('return', 0.0),
                'oos_vol': oos_metrics.get('vol', 0.0),
                'oos_max_dd': oos_metrics.get('max_dd', 0.0),
            }
            result.window_results.append(window_result)
            best_params_list.append(best_params)

        # Aggregate in-sample metrics
        result.is_metrics = {
            'sharpe': float(np.mean(is_sharpe_list)) if is_sharpe_list else 0.0,
            'return': float(np.mean(is_return_list)) if is_return_list else 0.0,
            'vol': float(np.mean(is_vol_list)) if is_vol_list else 0.0,
            'max_dd': float(np.mean(is_dd_list)) if is_dd_list else 0.0,
        }

        # Aggregate out-of-sample metrics
        result.oos_metrics = {
            'sharpe': float(np.mean(oos_sharpe_list)) if oos_sharpe_list else 0.0,
            'return': float(np.mean(oos_return_list)) if oos_return_list else 0.0,
            'vol': float(np.mean(oos_vol_list)) if oos_vol_list else 0.0,
            'max_dd': float(np.mean(oos_dd_list)) if oos_dd_list else 0.0,
        }

        # Degradation analysis
        result.is_oos_degradation = {
            k: result.is_metrics[k] - result.oos_metrics[k] for k in result.is_metrics.keys()
        }

        # Parameter stability analysis
        # Stability = 1.0 means all windows chose same parameters (robust)
        # Stability = 0.0 means every window chose different parameters (unstable)
        if best_params_list and any(best_params_list):
            # Filter out empty param dicts and convert to tuples for counting
            all_param_items = [
                tuple(sorted(params.items())) for params in best_params_list if params
            ]

            if all_param_items:
                # Count frequency of each unique param set
                from collections import Counter

                param_counts = Counter(all_param_items)
                most_common_params, max_count = param_counts.most_common(1)[0]
                
                # Stability = frequency of most common param set / total windows
                result.param_stability = max_count / len(best_params_list)

                # Store top 3 most frequent parameter sets
                result.best_params_frequency = {
                    str(dict(p_tuple)): count
                    for p_tuple, count in param_counts.most_common(3)
                }
            else:
                # All param dicts were empty → stable defaults
                result.param_stability = 1.0
                result.best_params_frequency = {"{}": len(best_params_list)}
                logger.debug("All windows used empty params (defaults) → stability = 1.0")
        else:
            # No params tracked → assume stable defaults
            result.param_stability = 1.0
            result.best_params_frequency = {"{}": len(windows) if windows else 0}
            logger.debug("No parameter tracking → assuming stable defaults (stability = 1.0)")

        logger.info(result.summary())
        return result


__all__ = ['WalkForwardAnalyzer', 'WFAWindow', 'WFAResult']
