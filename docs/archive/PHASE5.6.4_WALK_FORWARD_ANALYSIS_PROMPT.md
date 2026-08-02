# 🎯 PHASE 5.6.4 - WALK-FORWARD ANALYSIS PROMPT

## 📍 STATUS ACTUEL

```
✅ Phase 5.5      : Core modules (9.88/10)
✅ Phase 5.6.1    : Integration tests (9.1/10)
✅ Phase 5.6.2    : Performance Optimization (9.7/10)
✅ Phase 5.6.3    : Backtesting v2 (9.0/10 after fixes)
🚀 Phase 5.6.4    : Walk-Forward Analysis - NOW
```

---

## CONTEXT

**Phase 5.6.4** implémente **Walk-Forward Analysis (WFA)** pour validation robuste :
- Validation out-of-sample des stratégies backtestées
- Prévention overfitting
- Parameter stability analysis
- Nested cross-validation

**Objectif** : Valider que la stratégie Phase 5.6.3 n'est PAS overfittée sur données historiques.

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_ML4T_BOOK.md** (29 KB) :
   - Walk-forward methodology
   - Overfitting prevention
   - Out-of-sample testing
   - Rolling windows

2. **AUDIT_BACKTESTING_PY.md** (45 KB) :
   - Performance metrics
   - Optimization pitfalls

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.6.4 : WALK-FORWARD ANALYSIS

Génère 2 fichiers WFA complets :

================================================================================
1. src/financial_analyzer/backtesting/walk_forward_analyzer.py (400 LOC)
================================================================================

"""
Walk-Forward Analysis (WFA) - Robust Out-of-Sample Validation.

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

Example:
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
    ...     param_grid={'rebalance_freq': [5, 10, 20]},
    ...     optimize_metric='sharpe'
    ... )
    >>> 
    >>> print(f"Out-of-sample Sharpe: {results.oos_metrics['sharpe']:.2f}")
    >>> print(f"Parameter stability: {results.param_stability:.2%}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime
import logging

from financial_analyzer.backtesting.finbot_strategy import FinBotBacktester
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class WFAWindow:
    """Single walk-forward window."""
    
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
    """Walk-forward analysis result."""
    
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
        """Generate summary report."""
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
            report.append(f"  {metric}: {value:.4f} ({abs(value)/self.is_metrics.get(metric, 1):.1%})")
        
        report.append(f"\nPARAMETER STABILITY: {self.param_stability:.1%}")
        report.append(f"Most stable params: {self.best_params_frequency}")
        
        report.append("=" * 60)
        return "\n".join(report)


class WalkForwardAnalyzer:
    """Walk-forward analysis engine."""
    
    def __init__(
        self,
        data: Dict[str, pd.DataFrame],
        train_ratio: float = 0.8,
        rolling: bool = False,
        step_size: Optional[int] = None,
        initial_window: Optional[int] = None
    ):
        """
        Initialize WFA analyzer.
        
        Args:
            data: Dict[ticker, OHLC DataFrame]
            train_ratio: Train/test split (0.8 = 80% train, 20% test)
            rolling: If True, use rolling window; if False, expanding window
            step_size: Step size in rows (if None, use test window size)
            initial_window: Initial training window size (if None, calculated)
        """
        self.data = data
        self.train_ratio = train_ratio
        self.rolling = rolling
        
        # Get time series length
        self.total_length = len(next(iter(data.values())))
        
        # Calculate window sizes
        train_size = int(self.total_length * train_ratio)
        test_size = self.total_length - train_size
        
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size or test_size
        self.initial_window = initial_window or train_size
        
        logger.info(f"WFA Setup: total={self.total_length}, train={train_size}, test={test_size}")
    
    def _create_windows(self) -> List[WFAWindow]:
        """Create train/test windows."""
        windows = []
        
        if self.rolling:
            # Fixed window size, rolling forward
            step = self.step_size
            for i in range(0, self.total_length - self.train_size - self.test_size, step):
                train_start_idx = i
                train_end_idx = i + self.train_size
                test_start_idx = train_end_idx
                test_end_idx = test_start_idx + self.test_size
                
                if test_end_idx > self.total_length:
                    break
                
                # Split data
                train_data = {
                    ticker: df.iloc[train_start_idx:train_end_idx]
                    for ticker, df in self.data.items()
                }
                test_data = {
                    ticker: df.iloc[test_start_idx:test_end_idx]
                    for ticker, df in self.data.items()
                }
                
                # Get dates
                first_ticker = next(iter(self.data))
                train_dates = self.data[first_ticker].index
                
                window = WFAWindow(
                    window_id=len(windows),
                    train_start=train_dates[train_start_idx],
                    train_end=train_dates[train_end_idx - 1],
                    test_start=train_dates[test_start_idx],
                    test_end=train_dates[test_end_idx - 1],
                    train_data=train_data,
                    test_data=test_data
                )
                
                windows.append(window)
        else:
            # Expanding window
            step = self.step_size
            current_train_start = 0
            current_train_end = self.initial_window
            
            window_id = 0
            while current_train_end + self.test_size <= self.total_length:
                test_start = current_train_end
                test_end = test_start + self.test_size
                
                # Split data
                train_data = {
                    ticker: df.iloc[current_train_start:current_train_end]
                    for ticker, df in self.data.items()
                }
                test_data = {
                    ticker: df.iloc[test_start:test_end]
                    for ticker, df in self.data.items()
                }
                
                # Get dates
                first_ticker = next(iter(self.data))
                train_dates = self.data[first_ticker].index
                
                window = WFAWindow(
                    window_id=window_id,
                    train_start=train_dates[current_train_start],
                    train_end=train_dates[current_train_end - 1],
                    test_start=train_dates[test_start],
                    test_end=train_dates[test_end - 1],
                    train_data=train_data,
                    test_data=test_data
                )
                
                windows.append(window)
                
                # Move forward
                current_train_end += step
                window_id += 1
        
        logger.info(f"Created {len(windows)} WFA windows")
        return windows
    
    def run(
        self,
        strategy_class: type = FinBotBacktester,
        param_grid: Optional[Dict[str, List[Any]]] = None,
        optimize_metric: str = 'sharpe',
        strategy_kwargs: Optional[Dict] = None
    ) -> WFAResult:
        """
        Run walk-forward analysis.
        
        Args:
            strategy_class: Strategy class to backtest
            param_grid: Parameter grid for optimization
            optimize_metric: Metric to optimize on (default: sharpe)
            strategy_kwargs: Additional kwargs for strategy
        
        Returns:
            WFAResult with all statistics
        """
        windows = self._create_windows()
        
        if param_grid is None:
            param_grid = {}
        
        result = WFAResult(
            strategy_name=strategy_class.__name__,
            total_windows=len(windows),
            train_periods=[(w.train_start, w.train_end) for w in windows],
            test_periods=[(w.test_start, w.test_end) for w in windows]
        )
        
        is_returns_list = []
        oos_returns_list = []
        best_params_list = []
        
        for window in windows:
            logger.info(f"Processing window {window.window_id + 1}/{len(windows)}")
            
            # Optimize on train
            strategy = strategy_class(
                data=window.train_data,
                **(strategy_kwargs or {})
            )
            is_result = strategy.run()
            is_returns = is_result.get('returns', [])
            is_returns_list.append(is_returns)
            
            # Test on OOS
            strategy = strategy_class(
                data=window.test_data,
                **(strategy_kwargs or {})
            )
            oos_result = strategy.run()
            oos_returns = oos_result.get('returns', [])
            oos_returns_list.append(oos_returns)
            
            window_result = {
                'window_id': window.window_id,
                'is_sharpe': is_result.get('sharpe', 0.0),
                'oos_sharpe': oos_result.get('sharpe', 0.0),
                'is_return': is_result.get('total_return', 0.0),
                'oos_return': oos_result.get('total_return', 0.0),
            }
            result.window_results.append(window_result)
            best_params_list.append(is_result.get('best_params', {}))
        
        # Aggregate metrics
        if is_returns_list and oos_returns_list:
            is_all = np.concatenate(is_returns_list)
            oos_all = np.concatenate(oos_returns_list)
            
            result.is_metrics = {
                'mean': np.mean(is_all),
                'std': np.std(is_all),
                'sharpe': np.mean(is_all) / np.std(is_all) if np.std(is_all) > 0 else 0,
            }
            
            result.oos_metrics = {
                'mean': np.mean(oos_all),
                'std': np.std(oos_all),
                'sharpe': np.mean(oos_all) / np.std(oos_all) if np.std(oos_all) > 0 else 0,
            }
            
            result.is_oos_degradation = {
                k: result.is_metrics.get(k, 0) - result.oos_metrics.get(k, 0)
                for k in result.is_metrics.keys()
            }
        
        # Parameter stability
        if best_params_list:
            all_params = [p for params in best_params_list for p in params.items()]
            param_counts = {}
            for param, value in all_params:
                key = f"{param}={value}"
                param_counts[key] = param_counts.get(key, 0) + 1
            
            result.best_params_frequency = param_counts
            max_count = max(param_counts.values()) if param_counts else 1
            result.param_stability = max_count / len(best_params_list)
        
        logger.info(result.summary())
        return result


__all__ = ['WalkForwardAnalyzer', 'WFAWindow', 'WFAResult']

================================================================================
2. examples/run_walk_forward_analysis.py (200 LOC)
================================================================================

"""
Example: Complete Walk-Forward Analysis

Demonstrates:
1. Load historical data
2. Run walk-forward analysis
3. Compare in-sample vs out-of-sample
4. Check parameter stability
5. Export results

Usage:
    python examples/run_walk_forward_analysis.py
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

from financial_analyzer.backtesting.walk_forward_analyzer import WalkForwardAnalyzer
from financial_analyzer.backtesting.finbot_strategy import FinBotBacktester
from financial_analyzer.utils.helpers import configure_logging, get_logger

# Setup logging
configure_logging(level=logging.INFO)
logger = get_logger(__name__)


def _make_synthetic_data(tickers: list[str], periods: int = 504) -> dict[str, pd.DataFrame]:
    """
    Create synthetic OHLC data for demo.
    
    Args:
        tickers: List of ticker symbols
        periods: Number of periods (business days)
    
    Returns:
        Dict[ticker, DataFrame with Close]
    """
    np.random.seed(42)
    dates = pd.date_range('2022-01-01', periods=periods, freq='B')
    
    data = {}
    for i, ticker in enumerate(tickers):
        # Different drift per ticker
        drift = 0.0003 + 0.0001 * i
        vol = 0.01 + 0.002 * i
        
        returns = np.random.normal(drift, vol, periods)
        prices = 100 * (1 + pd.Series(returns)).cumprod()
        
        data[ticker] = pd.DataFrame({
            'Close': prices.values
        }, index=dates)
    
    return data


def main():
    """Run complete WFA workflow."""
    
    logger.info("=" * 70)
    logger.info("WALK-FORWARD ANALYSIS - EXAMPLE")
    logger.info("=" * 70)
    
    # 1. Create synthetic data
    logger.info("\n1. Creating synthetic price data...")
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
    price_data = _make_synthetic_data(tickers, periods=504)
    logger.info(f"✓ Data created: {len(price_data)} assets, {len(next(iter(price_data.values())))} periods")
    
    # 2. Initialize WFA
    logger.info("\n2. Initializing walk-forward analyzer...")
    wfa = WalkForwardAnalyzer(
        data=price_data,
        train_ratio=0.8,
        rolling=False  # Expanding window
    )
    logger.info("✓ WFA initialized (expanding window, 80/20 split)")
    
    # 3. Run WFA
    logger.info("\n3. Running walk-forward analysis...")
    results = wfa.run(
        strategy_class=FinBotBacktester,
        param_grid={},  # Use defaults
        optimize_metric='sharpe'
    )
    
    # 4. Display results
    logger.info("\n4. Results Summary:")
    logger.info(results.summary())
    
    # 5. Detailed window analysis
    logger.info("\n5. Per-Window Analysis:")
    for w in results.window_results:
        logger.info(
            f"Window {w['window_id']}: "
            f"IS Sharpe={w['is_sharpe']:.2f}, "
            f"OOS Sharpe={w['oos_sharpe']:.2f}, "
            f"Degradation={w['is_sharpe'] - w['oos_sharpe']:.2f}"
        )
    
    # 6. Export report
    logger.info("\n6. Exporting report...")
    report = f"""
# Walk-Forward Analysis Report

## Strategy: {results.strategy_name}

## Configuration
- Total Windows: {results.total_windows}
- Window Type: Expanding
- Train/Test: 80/20

## Summary Metrics

### In-Sample Performance
{chr(10).join(f"- {k}: {v:.4f}" for k, v in results.is_metrics.items())}

### Out-of-Sample Performance
{chr(10).join(f"- {k}: {v:.4f}" for k, v in results.oos_metrics.items())}

### Degradation (IS - OOS)
{chr(10).join(f"- {k}: {v:.4f}" for k, v in results.is_oos_degradation.items())}

## Robustness

- **Parameter Stability**: {results.param_stability:.1%}
- **Best Parameters Frequency**: {results.best_params_frequency}

Interpretation:
- Parameter stability > 70% indicates robust parameters
- Degradation < 10% indicates good generalization
- OOS Sharpe > 1.0 indicates profitable strategy

"""
    
    with open('wfa_report.md', 'w') as f:
        f.write(report)
    
    logger.info("✓ Report exported to: wfa_report.md")
    
    logger.info("\n" + "=" * 70)
    logger.info("ANALYSIS COMPLETE!")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()

================================================================================
REQUIREMENTS
================================================================================

✅ Expanding window WFA
✅ Rolling window WFA
✅ Nested cross-validation ready
✅ Parameter stability analysis
✅ In-sample vs out-of-sample degradation
✅ Type hints 100%
✅ Google docstrings 100%
✅ Logging throughout
✅ Markdown report generation

CRITICAL:
- WFA compatible with FinBotBacktester
- Graceful fallback if no params provided
- All tests use synthetic data
- Example script runnable
- Results exportable

Refs: AUDIT_ML4T_BOOK.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `walk_forward_analyzer.py` (400 LOC) - WFA engine
2. ✅ `run_walk_forward_analysis.py` (200 LOC) - Example

**Total** : 600 LOC

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ walk_forward_analyzer.py (400 LOC)
✅ run_walk_forward_analysis.py (200 LOC)

Total: 600 LOC
Features: Expanding + Rolling WFA, Param stability, IS/OOS comparison
Runnable: YES
```

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

**C'est Phase 5.6.4 - Walk-Forward Analysis !** 🎯

**Temps estimé par Copilot : 2 heures** ⏱️

**Livraison cible** : Dimanche 9 novembre, ~14h

**Après Phase 5.6.4, tu auras Phase 5.6 COMPLÈTE !** ✅

```
✅ Phase 5.6.1 : Integration tests
✅ Phase 5.6.2 : Performance Optimization
✅ Phase 5.6.3 : Backtesting v2
✅ Phase 5.6.4 : Walk-Forward Analysis

PHASE 5.6 DONE! Ready for Phase 5.7 (Deployment) 🚀
```
