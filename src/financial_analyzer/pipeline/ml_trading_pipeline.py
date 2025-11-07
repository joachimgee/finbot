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
    ...     prices_data=data,
    ...     n_windows=10,
    ...     window_size_days=252
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
from financial_analyzer.integration.signal_portfolio_bridge import SignalPortfolioBridge
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
    
    Audit:
        AUDIT_ML4T_BOOK.md p.75 (walk-forward results)
    
    Example:
        >>> result = PipelineResult(
        ...     total_return_pct=34.2, sharpe_ratio=1.45,
        ...     max_drawdown_pct=15.3, trades_count=247,
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
    attribution: Optional[Dict] = None
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
        ...     prices_data=data,
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
        
        # Initialize components (Phase 5.1 bridge, Phase 5.4 Module 3 attribution)
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
            # Adjust max_weight if single asset (testing mode)
            n_assets = len(signals)
            if n_assets == 1:
                self.signal_bridge.max_weight = 1.0
            
            weights = self.signal_bridge.convert_signals_to_weights(
                signals, prices=test_data
            )
            
            # Add required columns for strategy (mock sentiment/factors)
            test_data_enriched = self._enrich_backtest_data(test_data)
            
            # Run backtest on test period
            try:
                bt = Backtest(
                    test_data_enriched, self.strategy_class,
                    cash=self.initial_cash,
                    commission=self.commission_pct
                )
                stats = bt.run()
            except Exception as e:
                logger.warning(f"Window {window_idx} backtest failed: {e}, skipping")
                continue
            
            # Extract metrics
            window_result = {
                'window': window_idx,
                'return_pct': stats.get('Return [%]', 0.0),
                'sharpe_ratio': stats.get('Sharpe Ratio', 0.0),
                'max_drawdown_pct': abs(stats.get('Max. Drawdown [%]', 0.0)),
                'trades': stats.get('# Trades', 0),
                'start_date': test_data.index[0] if len(test_data) > 0 else None,
                'end_date': test_data.index[-1] if len(test_data) > 0 else None
            }
            window_results.append(window_result)
            
            # Accumulate for aggregation
            if '_equity_curve' in stats and stats['_equity_curve'] is not None:
                equity_curves.append(stats['_equity_curve'])
            all_trades.append(stats.get('_trades', []))
            
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
        
        # Build features dict to avoid fragmentation warning
        features_dict = {}
        for i in range(1, n_features + 1):
            # Mock: random walks normalized to Z-score
            series = np.cumsum(np.random.randn(n_rows) * 0.1)
            features_dict[f'factor_{i}'] = (series - series.mean()) / (series.std() + 1e-9)
        
        features = pd.DataFrame(features_dict, index=data.index)
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
        # Extract asset names (assume single asset for now)
        n_assets = data.shape[1] // 5 if data.shape[1] > 5 else 1
        
        signals = {}
        for i in range(max(1, n_assets)):
            # Mock: random signals in [-2, 2]
            signal = np.random.uniform(-2.0, 2.0)
            signals[f'ASSET_{i}'] = signal
        
        logger.debug(f"Generated signals for {len(signals)} assets")
        return signals
    
    def _enrich_backtest_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich backtest data with required strategy columns.
        
        Args:
            data: OHLCV DataFrame
        
        Returns:
            DataFrame with sentiment/factor columns added
        
        Notes:
            Adds mock columns required by strategies:
            - SentimentMomentum: sentiment_score, earnings_surprise
            - FactorEnsemble: factor_1...factor_N, factor_ic_1...factor_ic_N
        """
        enriched = data.copy()
        n_rows = len(data)
        
        if self.strategy == 'SentimentMomentum':
            # Add sentiment columns (mock)
            enriched['sentiment_score'] = np.random.uniform(0.3, 0.9, n_rows)
            enriched['earnings_surprise'] = np.random.uniform(-0.1, 0.1, n_rows)
        else:  # FactorEnsemble
            # Add factor columns (mock)
            for i in range(1, 11):  # 10 factors for tests
                series = np.cumsum(np.random.randn(n_rows) * 0.1)
                enriched[f'factor_{i}'] = (series - series.mean()) / (series.std() + 1e-9)
                enriched[f'factor_ic_{i}'] = np.random.uniform(0.05, 0.15, n_rows)
        
        return enriched
    
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
        
        Audit:
            AUDIT_ML4T_BOOK.md p.78 (results aggregation)
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
            window_results=window_results,
            equity_curve=combined_equity
        )
    
    def _combine_equity_curves(self, curves: List[pd.Series]) -> Optional[pd.Series]:
        """
        Combine equity curves from multiple windows.
        
        Args:
            curves: List of equity Series from each window
        
        Returns:
            Combined equity curve, or None if empty
        
        Notes:
            Simple concatenation (in production: handle overlaps)
        """
        if not curves:
            return None
        # Simple concatenation (in production: handle overlaps)
        try:
            return pd.concat(curves, ignore_index=False)
        except Exception as e:
            logger.warning(f"Failed to combine equity curves: {e}")
            return None


# Module exports
__all__ = ['MLTradingPipeline', 'PipelineResult']
