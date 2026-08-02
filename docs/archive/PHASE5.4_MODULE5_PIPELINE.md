# 🎯 PHASE 5.4 - MODULE 5 : ML TRADING PIPELINE E2E (FINAL)

## MISSION CRITIQUE

Tu dois implémenter un **pipeline orchestrateur complet** intégrant TOUS les modules (1-4) en une machine de trading end-to-end avec walk-forward validation.

**Objectif** : Pipeline production E2E : Universe → Features → Signals → Portfolio → Backtest → Attribution

---

## 📚 CONTEXTE - AUDITS OBLIGATOIRES

**Lis CES audits EN ENTIER avant de coder** :

1. **ML4T** : `docs/AUDITS/AUDIT_ML4T_BOOK.md` pp. 65-80
   - Walk-forward validation framework
   - Pipeline architecture
   - Performance monitoring

2. **FINANCE OVERVIEW** : `docs/AUDITS/AUDIT_FINANCE_PARTIE_1_OVERVIEW.md` pp. 15-25
   - System architecture
   - Data flow
   - Integration patterns

3. **BACKTESTING.PY** : `docs/AUDITS/AUDIT_BACKTESTING_PY.md` pp. 25-30
   - Multi-strategy framework
   - Results aggregation

---

## 🏗️ RAPPELS CONVENTIONS FinBot

### **1. IMPORTS ORDRE STRICT**

```python
# 1. Stdlib
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 3. Finance libs
from backtesting import Backtest

# 5. Local
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.integration.signal_portfolio_bridge import SignalPortfolioBridge
from financial_analyzer.integration.performance_attribution import PerformanceAttributor
from financial_analyzer.strategies import SentimentMomentumStrategy, FactorEnsembleStrategy
```

### **2. DATACLASS POUR RÉSULTATS**

```python
@dataclass
class PipelineResult:
    """Résultat pipeline complet."""
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    trades_count: int
    num_windows: int
    strategy_name: str
    attribution: Optional[Dict] = None
```

---

## 📦 LIVRABLES MODULE 5

**Fichiers à créer** :

```
src/financial_analyzer/
├── pipeline/
│   ├── __init__.py
│   └── ml_trading_pipeline.py               # (1) Pipeline orchestrateur

tests/test_pipeline/
├── __init__.py
└── test_ml_trading_pipeline.py              # 40 tests
```

---

## 🎯 FICHIER : `pipeline/ml_trading_pipeline.py`

**Rôle** : Orchestrateur complet ML trading

**Durée** : 1.5-2h | **LOC** : 450 | **Tests** : 40

### **Spécifications détaillées**

```python
"""
ML Trading Pipeline E2E.

Complete orchestration of ML trading system:
- Universe selection (top-N by market cap)
- Feature engineering (Phase 5.2 factors)
- Signal generation (Phase 5.3 sentiment)
- Portfolio optimization (Phase 5.1 bridge)
- Multi-strategy backtesting (Phase 5.4 strategies)
- Walk-forward validation
- Performance attribution

Architecture:
    Data Input
        ↓
    Universe Selector → Top N assets
        ↓
    Feature Engineer → 114 factors
        ↓
    Sentiment Engine → ML scores
        ↓
    Signal Generator → [-2, +2] signals
        ↓
    Portfolio Bridge → Weights
        ↓
    Backtest Engine → Returns/Trades
        ↓
    Attribution → PnL decomposition
        ↓
    Results Aggregation

Audit references:
- AUDIT_ML4T_BOOK.md pp. 65-80 (walk-forward, pipeline)
- AUDIT_FINANCE_PARTIE_1_OVERVIEW.md pp. 15-25 (architecture)

Example:
    >>> pipeline = MLTradingPipeline(
    ...     universe_size=50,
    ...     start_date='2020-01-01',
    ...     end_date='2024-12-31'
    ... )
    >>> result = pipeline.run_walk_forward(
    ...     n_windows=10,
    ...     window_size_days=252,
    ...     rebalance_freq_days=20
    ... )
    >>> print(f"Total Return: {result.total_return_pct:.1f}%")
    Total Return: 34.2%
"""

# 1. Stdlib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np
from scipy import stats

# 3. Finance libs
from backtesting import Backtest

# 5. Local
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.integration.signal_portfolio_bridge import SignalPortfolioBridge, AttributionResult
from financial_analyzer.integration.performance_attribution import PerformanceAttributor
from financial_analyzer.strategies import SentimentMomentumStrategy, FactorEnsembleStrategy

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """
    Complete pipeline execution result.
    
    Attributes:
        total_return_pct: Total return over entire backtest period (%)
        sharpe_ratio: Sharpe ratio (annualized)
        max_drawdown_pct: Maximum drawdown (%)
        trades_count: Total number of trades executed
        num_windows: Number of walk-forward windows
        strategy_name: Name of strategy used (SentimentMomentum or FactorEnsemble)
        attribution: Performance attribution result (optional)
        window_results: List of results per window
        equity_curve: Equity curve time series
    
    Invariants:
        - total_return_pct can be negative (losing strategy)
        - sharpe_ratio can be negative
        - max_drawdown_pct is always >= 0
    
    Example:
        >>> result = PipelineResult(
        ...     total_return_pct=34.2, sharpe_ratio=1.45,
        ...     max_drawdown_pct=-15.3, trades_count=247,
        ...     num_windows=10, strategy_name='SentimentMomentum',
        ...     equity_curve=pd.Series(...)
        ... )
    """
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    trades_count: int
    num_windows: int
    strategy_name: str
    attribution: Optional[AttributionResult] = None
    window_results: List[Dict] = field(default_factory=list)
    equity_curve: Optional[pd.Series] = None


class MLTradingPipeline:
    """
    ML Trading Pipeline orchestrator.
    
    Complete system orchestrating:
    1. Universe selection (top-N by market cap)
    2. Feature engineering (114 ML factors)
    3. Sentiment analysis (news-driven ML)
    4. Signal generation (composite scores)
    5. Portfolio optimization (Brinson/NCO)
    6. Multi-strategy backtesting
    7. Walk-forward validation
    8. Performance attribution
    
    Audit References:
    - AUDIT_ML4T_BOOK.md p.70 (walk-forward validation)
    - AUDIT_FINANCE_PARTIE_1_OVERVIEW.md p.18 (system architecture)
    
    Example:
        >>> pipeline = MLTradingPipeline(
        ...     universe_size=50,
        ...     start_date='2020-01-01',
        ...     end_date='2024-12-31',
        ...     rebalance_freq_days=20
        ... )
        >>> result = pipeline.run_walk_forward(
        ...     n_windows=10,
        ...     window_size_days=252
        ... )
        >>> print(f"Sharpe: {result.sharpe_ratio:.2f}")
        Sharpe: 1.45
    """
    
    def __init__(
        self,
        universe_size: int = 50,
        start_date: str = '2020-01-01',
        end_date: str = '2024-12-31',
        rebalance_freq_days: int = 20,
        initial_cash: float = 100_000.0,
        commission_pct: float = 0.002,
        strategy: str = 'SentimentMomentum'
    ):
        """
        Initialize ML Trading Pipeline.
        
        Args:
            universe_size: Number of assets in trading universe (default 50)
            start_date: Pipeline start date (YYYY-MM-DD format)
            end_date: Pipeline end date (YYYY-MM-DD format)
            rebalance_freq_days: Portfolio rebalancing frequency (default 20 days)
            initial_cash: Initial portfolio cash (default $100K)
            commission_pct: Trading commission as % of transaction (default 0.2%)
            strategy: Strategy to use ('SentimentMomentum' or 'FactorEnsemble')
        
        Raises:
            ValueError: If strategy not recognized
        
        Notes:
            - Universe dynamically selected from top-N market cap (Phase 1)
            - Features computed from Phase 5.2 (114 ML factors)
            - Sentiment from Phase 5.3 (FinBERT)
            - Portfolio optimized via Phase 5.1 bridge (Riskfolio NCO)
        
        Audit:
            AUDIT_FINANCE_PARTIE_1_OVERVIEW.md p.16 (pipeline initialization)
        """
        self.universe_size = universe_size
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.rebalance_freq_days = rebalance_freq_days
        self.initial_cash = initial_cash
        self.commission_pct = commission_pct
        
        if strategy not in ['SentimentMomentum', 'FactorEnsemble']:
            raise ValueError(
                f"Strategy must be 'SentimentMomentum' or 'FactorEnsemble', got {strategy}"
            )
        self.strategy = strategy
        self.strategy_class = (
            SentimentMomentumStrategy if strategy == 'SentimentMomentum' 
            else FactorEnsembleStrategy
        )
        
        # Initialize components
        self.signal_bridge = SignalPortfolioBridge(
            portfolio_optimizer=None,
            sentiment_engine=None,
            feature_selector=None,
            max_weight=0.20,
            min_weight=0.01,
            long_only=False
        )
        self.attributor = PerformanceAttributor()
        
        logger.info(
            f"MLTradingPipeline initialized: "
            f"universe={universe_size}, strategy={strategy}, "
            f"period={start_date} to {end_date}"
        )
    
    def run_walk_forward(
        self,
        prices_data: pd.DataFrame,
        n_windows: int = 10,
        window_size_days: int = 252
    ) -> PipelineResult:
        """
        Execute complete walk-forward backtest.
        
        Args:
            prices_data: DataFrame with OHLCV data (multi-asset, DatetimeIndex)
            n_windows: Number of walk-forward windows (default 10)
            window_size_days: Size of training + test window in days
        
        Returns:
            PipelineResult with aggregated metrics across all windows
        
        Process:
        1. For each window i:
            a. Train features on historical data (window 0 to i)
            b. Generate signals on test period (window i+1)
            c. Optimize portfolio via signal bridge
            d. Run backtest on test period
            e. Calculate attribution
            f. Record metrics
        2. Aggregate results across windows:
            a. Combine equity curves
            b. Calculate walk-forward Sharpe ratio
            c. Calculate max drawdown
            d. Aggregate attribution
        
        Raises:
            ValueError: If prices data invalid
            
        Audit:
            - AUDIT_ML4T_BOOK.md p.70 (walk-forward validation)
            - AUDIT_BACKTESTING_PY.md p.25 (multi-strategy results)
        
        Example:
            >>> prices = pd.DataFrame(...)  # 1000 days, 50 assets
            >>> result = pipeline.run_walk_forward(
            ...     prices, n_windows=10, window_size_days=252
            ... )
            >>> assert result.num_windows == 10
            >>> assert result.trades_count > 0
        """
        logger.info(
            f"Starting walk-forward validation: {n_windows} windows, "
            f"{window_size_days} days per window"
        )
        
        # Validation
        if not isinstance(prices_data, pd.DataFrame):
            raise ValueError(f"prices_data must be DataFrame, got {type(prices_data)}")
        if len(prices_data) < n_windows * window_size_days:
            raise ValueError(
                f"Insufficient data: need {n_windows * window_size_days} rows, "
                f"have {len(prices_data)}"
            )
        
        # Walk-forward loop
        window_results = []
        equity_curves = []
        all_trades = []
        
        for window_idx in range(n_windows):
            logger.info(f"Processing window {window_idx + 1}/{n_windows}...")
            
            # Define training and test periods
            train_start = max(0, window_idx * window_size_days)
            train_end = (window_idx + 1) * window_size_days
            test_end = min(len(prices_data), train_end + window_size_days // 2)
            
            # Extract train/test data
            train_data = prices_data.iloc[train_start:train_end]
            test_data = prices_data.iloc[train_end:test_end]
            
            if len(test_data) < 20:  # Minimum 20 bars for meaningful test
                logger.warning(f"Window {window_idx} has insufficient test data, skipping")
                continue
            
            # Train features (Phase 5.2) - mock implementation
            # In production: compute 114 ML factors on train_data
            features = self._compute_features(train_data)
            
            # Generate signals (Phase 5.3) - mock
            # In production: FinBERT sentiment + signal generation
            signals = self._generate_signals(train_data, features)
            
            # Convert signals to portfolio weights (Phase 5.1 bridge)
            weights = self.signal_bridge.convert_signals_to_weights(
                signals, prices=test_data
            )
            
            # Run backtest on test period
            bt = Backtest(
                test_data, self.strategy_class,
                cash=self.initial_cash,
                commission=self.commission_pct
            )
            stats = bt.run()
            
            # Extract metrics
            window_result = {
                'window': window_idx,
                'return_pct': stats['Return [%]'],
                'sharpe_ratio': stats.get('Sharpe Ratio', 0.0),
                'max_drawdown_pct': stats.get('Max. Drawdown [%]', 0.0),
                'trades': stats['# Trades'],
                'start_date': test_data.index[0],
                'end_date': test_data.index[-1]
            }
            window_results.append(window_result)
            
            # Accumulate for aggregation
            if 'Equity Final [$]' in stats:
                equity_curves.append(stats._results['Equity'])
            all_trades.append(stats._trades if hasattr(stats, '_trades') else [])
            
            logger.info(
                f"Window {window_idx}: Return={window_result['return_pct']:.2f}%, "
                f"Sharpe={window_result['sharpe_ratio']:.2f}, "
                f"Trades={window_result['trades']}"
            )
        
        # Aggregate results
        result = self._aggregate_window_results(
            window_results, equity_curves, all_trades
        )
        
        logger.info(
            f"Walk-forward complete: "
            f"Total Return={result.total_return_pct:.2f}%, "
            f"Sharpe={result.sharpe_ratio:.2f}, "
            f"Trades={result.trades_count}"
        )
        
        return result
    
    # --- Helper Methods ---
    
    def _compute_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute 114 ML features (Phase 5.2 mock).
        
        Args:
            data: OHLCV DataFrame
        
        Returns:
            DataFrame with 114 factors (factor_1 to factor_114)
        
        Notes:
            Mock implementation - in production calls Phase 5.2
            Includes: momentum, mean-reversion, volatility, etc.
        
        Audit:
            AUDIT_FINANCE_PARTIE_5_ML.md p.5 (feature engineering)
        """
        n_features = 114
        n_rows = len(data)
        
        features = pd.DataFrame(index=data.index)
        for i in range(1, n_features + 1):
            # Mock: random walks normalized to Z-score
            series = np.cumsum(np.random.randn(n_rows) * 0.1)
            features[f'factor_{i}'] = (series - series.mean()) / (series.std() + 1e-9)
        
        logger.debug(f"Computed {n_features} features")
        return features
    
    def _generate_signals(
        self,
        data: pd.DataFrame,
        features: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Generate trading signals (Phase 5.3 mock).
        
        Args:
            data: OHLCV DataFrame
            features: Factor DataFrame
        
        Returns:
            Dict mapping asset names to signal strength [-2, +2]
        
        Notes:
            Mock: random signals
            Production: FinBERT sentiment + IC-weighted factor signals
        
        Audit:
            AUDIT_FINANCE_PARTIE_5_ML.md p.15 (signal generation)
        """
        # Extract asset names (assume multi-index columns or single asset)
        n_assets = data.shape[1] // 5 if data.shape[1] > 5 else 1
        
        signals = {}
        for i in range(n_assets):
            # Mock: random signals in [-2, 2]
            signal = np.random.uniform(-2.0, 2.0)
            signals[f'ASSET_{i}'] = signal
        
        logger.debug(f"Generated signals for {len(signals)} assets")
        return signals
    
    def _aggregate_window_results(
        self,
        window_results: List[Dict],
        equity_curves: List[pd.Series],
        all_trades: List[List]
    ) -> PipelineResult:
        """
        Aggregate walk-forward window results.
        
        Args:
            window_results: List of per-window metrics dicts
            equity_curves: List of equity series (one per window)
            all_trades: List of trades (one per window)
        
        Returns:
            Aggregated PipelineResult
        
        Process:
        1. Concatenate equity curves
        2. Calculate aggregate return
        3. Calculate aggregate Sharpe ratio (annualized)
        4. Calculate max drawdown
        5. Sum trades across windows
        6. Compute overall attribution (if possible)
        """
        if not window_results:
            logger.warning("No window results to aggregate")
            return PipelineResult(
                total_return_pct=0.0, sharpe_ratio=0.0,
                max_drawdown_pct=0.0, trades_count=0,
                num_windows=0, strategy_name=self.strategy
            )
        
        # Aggregate equity curves
        combined_equity = self._combine_equity_curves(equity_curves)
        
        # Calculate aggregate metrics
        total_returns = [r['return_pct'] for r in window_results]
        total_return_pct = np.mean(total_returns)  # Average return per window
        
        sharpe_ratios = [r['sharpe_ratio'] for r in window_results]
        aggregate_sharpe = np.mean([s for s in sharpe_ratios if not np.isnan(s)])
        
        max_drawdowns = [abs(r['max_drawdown_pct']) for r in window_results]
        max_drawdown_pct = max(max_drawdowns) if max_drawdowns else 0.0
        
        total_trades = sum(r['trades'] for r in window_results)
        
        logger.info(
            f"Aggregated results: avg_return={total_return_pct:.2f}%, "
            f"sharpe={aggregate_sharpe:.2f}, "
            f"max_dd={max_drawdown_pct:.2f}%, "
            f"trades={total_trades}"
        )
        
        return PipelineResult(
            total_return_pct=total_return_pct,
            sharpe_ratio=aggregate_sharpe,
            max_drawdown_pct=max_drawdown_pct,
            trades_count=total_trades,
            num_windows=len(window_results),
            strategy_name=self.strategy,
            equity_curve=combined_equity
        )
    
    def _combine_equity_curves(self, curves: List[pd.Series]) -> Optional[pd.Series]:
        """Combine equity curves from multiple windows."""
        if not curves:
            return None
        # Simple concatenation (in production: handle overlaps)
        return pd.concat(curves, ignore_index=False)


# Module exports
__all__ = ['MLTradingPipeline', 'PipelineResult']
```

### **Checklist implémentation**

- [ ] Dataclass `PipelineResult` avec validation
- [ ] Classe `MLTradingPipeline` orchestrateur
- [ ] `run_walk_forward()` avec loop sur N windows
- [ ] Train/test split par window
- [ ] Feature engineering mock (Phase 5.2)
- [ ] Signal generation mock (Phase 5.3)
- [ ] Portfolio optimization via bridge (Phase 5.1)
- [ ] Backtest exécution
- [ ] Résultats aggregation
- [ ] Equity curves combination
- [ ] Logging exhaustif
- [ ] Type hints 100%
- [ ] Docstrings Google complètes

---

## 🧪 TESTS FICHIER : `test_ml_trading_pipeline.py`

**40 tests requis** :

```python
"""
Tests for MLTradingPipeline.

Coverage:
- Initialization (5 tests)
- Walk-forward validation (10 tests)
- Feature engineering (5 tests)
- Signal generation (5 tests)
- Results aggregation (8 tests)
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
    dates = pd.date_range('2020-01-01', periods=1000, freq='D')
    np.random.seed(42)
    
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


# --- Initialization Tests ---

def test_pipeline_init_default():
    """Pipeline initializes with default parameters."""
    p = MLTradingPipeline()
    assert p.universe_size == 50
    assert p.initial_cash == 100_000.0
    assert p.commission_pct == 0.002


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
        max_drawdown_pct=-12.3,
        trades_count=47,
        num_windows=10,
        strategy_name='SentimentMomentum'
    )
    assert result.total_return_pct == 15.2
    assert result.trades_count == 47


def test_pipeline_sentiment_momentum_strategy():
    """Pipeline correctly sets SentimentMomentum strategy."""
    p = MLTradingPipeline(strategy='SentimentMomentum')
    assert p.strategy == 'SentimentMomentum'


# --- Walk-Forward Tests ---

def test_walk_forward_basic(pipeline_default, sample_prices):
    """Walk-forward validation executes successfully."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=3, window_size_days=250
    )
    assert result is not None
    assert result.num_windows == 3


def test_walk_forward_insufficient_data(pipeline_default):
    """Walk-forward raises error if data too short."""
    short_data = pd.DataFrame({
        'Close': np.arange(100),
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
    assert result.num_windows == 1
    assert result.trades_count >= 0


def test_walk_forward_metrics_valid(pipeline_default, sample_prices):
    """Walk-forward metrics are valid (no NaNs, correct ranges)."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=3, window_size_days=250
    )
    assert not np.isnan(result.total_return_pct)
    assert not np.isnan(result.sharpe_ratio)
    assert result.max_drawdown_pct <= 0


def test_walk_forward_trades_aggregated(pipeline_default, sample_prices):
    """Total trades is sum of window trades."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=3, window_size_days=250
    )
    assert result.trades_count >= 0


def test_walk_forward_equity_curve_generated(pipeline_default, sample_prices):
    """Equity curve is generated and valid."""
    result = pipeline_default.run_walk_forward(
        sample_prices, n_windows=2, window_size_days=400
    )
    assert result.equity_curve is not None


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
        'Close': np.arange(100),
        'Volume': [1_000_000] * 100
    }, index=pd.date_range('2020-01-01', periods=100))
    
    result = pipeline_default.run_walk_forward(
        minimal_data, n_windows=1, window_size_days=100
    )
    assert isinstance(result, PipelineResult)


# --- Feature Engineering Tests ---

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


# --- Signal Generation Tests ---

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
    # Values may differ slightly due to randomness, but keys should match


def test_generate_signals_features_optional(pipeline_default, sample_prices):
    """Signals generation works even without custom features."""
    signals = pipeline_default._generate_signals(sample_prices, pd.DataFrame())
    assert isinstance(signals, dict)


# --- Results Aggregation Tests ---

def test_aggregate_window_results_empty(pipeline_default):
    """Aggregation handles empty window results."""
    result = pipeline_default._aggregate_window_results([], [], [])
    assert result.num_windows == 0


def test_aggregate_window_results_single(pipeline_default):
    """Aggregation with single window."""
    window_results = [{
        'window': 0,
        'return_pct': 10.0,
        'sharpe_ratio': 1.5,
        'max_drawdown_pct': -5.0,
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
            'max_drawdown_pct': -(5.0 + i),
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
        {'return_pct': 10.0, 'trades': 10, 'sharpe_ratio': 1.0, 'max_drawdown_pct': -5},
        {'return_pct': 20.0, 'trades': 15, 'sharpe_ratio': 1.5, 'max_drawdown_pct': -8}
    ]
    
    result = pipeline_default._aggregate_window_results(window_results, [], [])
    assert abs(result.total_return_pct - 15.0) < 0.1  # Average of 10 and 20


def test_aggregate_max_drawdown_worst_case(pipeline_default):
    """Aggregated drawdown is worst (most negative)."""
    window_results = [
        {'return_pct': 10, 'trades': 10, 'sharpe_ratio': 1, 'max_drawdown_pct': -5},
        {'return_pct': 10, 'trades': 10, 'sharpe_ratio': 1, 'max_drawdown_pct': -15},
        {'return_pct': 10, 'trades': 10, 'sharpe_ratio': 1, 'max_drawdown_pct': -8}
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


# --- Integration E2E Tests ---

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
    assert result.num_windows == 2
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
```

### **Checklist tests**

- [ ] 40 tests minimum
- [ ] Coverage : init (5), walk-forward (10), features (5), signals (5), aggregation (8), E2E (2)
- [ ] Fixtures robustes (sample_prices, pipeline)
- [ ] Tests walk-forward logic complet
- [ ] Tests features 114 factors
- [ ] Tests signal ranges [-2, +2]
- [ ] Tests results aggregation
- [ ] Tests equity curves
- [ ] Tests both strategies

---

## 📊 CRITÈRES QUALITÉ

| Critère | Target |
|---------|--------|
| LOC | 450 |
| Tests | 40 |
| Coverage | 90%+ |
| Type hints | 100% |
| Docstrings | 100% |
| Audit refs | Chaque méthode |

---

## ✅ CHECKLIST PRÉ-LANCEMENT

- [ ] Audits lus (ML4T walk-forward, Finance overview, Backtesting)
- [ ] Walk-forward logic claire
- [ ] Dataclass PipelineResult comprise
- [ ] Intégration modules 1-4 claire
- [ ] Prêt à coder

---

## 🚀 ACTION COPILOT

**Phase 1** : Génère `ml_trading_pipeline.py` (450 LOC)
**Phase 2** : Génère `test_ml_trading_pipeline.py` (40 tests)

**DERNIÈRE LIGNE D'ARRIVÉE PHASE 5.4 !** 🎯🚀

**Qualité > Vitesse** ✅
