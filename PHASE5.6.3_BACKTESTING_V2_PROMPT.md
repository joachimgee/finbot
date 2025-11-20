# 🎯 PHASE 5.6.3 - BACKTESTING V2 PROMPT

## 📍 STATUS ACTUEL

```
✅ Phase 5.5      : Core modules (9.88/10) - DONE
✅ Phase 5.6.1    : Integration tests (9.1/10) - DONE
✅ Phase 5.6.2    : Performance Optimization (9.7/10) - DONE
🚀 Phase 5.6.3    : Backtesting v2 - NOW
```

---

## CONTEXT

**Phase 5.6.3** implémente **Backtesting Engine v2** qui intègre Phase 5.5 COMPLÈTE avec backtesting.py :
- Sentiment analysis (FinBERT via Phase 5.5)
- Technical indicators (Phase 5.5)
- ML predictions (LSTM/Transformer via Phase 5.5)
- Signal fusion (Phase 5.5)
- Portfolio optimization (CVaR, HRP via Phase 5.5)
- Caching + Async fetcher (Phase 5.6.2)
- Database persistence (Phase 5.6.2)

**Objectif** : Valider stratégie sur données historiques, optimiser paramètres, générer rapports.

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_BACKTESTING_PY.md** (45 KB) :
   - Strategy class patterns
   - init() / next() methods
   - Optimization patterns

2. **AUDIT_ML4T_BOOK.md** (29 KB) :
   - Backtesting best practices
   - Overfitting prevention

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.6.3 : BACKTESTING ENGINE V2

Génère 3 fichiers d'intégration backtesting complets :

================================================================================
1. src/financial_analyzer/backtesting/finbot_strategy.py (600 LOC)
================================================================================

"""
FinBot Strategy - Phase 5.5 Pipeline Integration.

Stratégie backtesting.py complète utilisant TOUT le pipeline Phase 5.5:
- Sentiment analysis (SentimentAggregator from Phase 5.5)
- Technical indicators (TechnicalFeatures from Phase 5.5)
- ML predictions (LSTMPredictor/TransformerPredictor from Phase 5.5)
- Signal fusion (SignalFusion from Phase 5.5)
- Portfolio optimization (RiskfolioOptimizer from Phase 5.5)
- Caching (CacheManager from Phase 5.6.2)
- Async data fetching (AsyncFetcher from Phase 5.6.2)

Features:
- Daily rebalancing (configurable frequency)
- Risk management (position sizing, stop-loss)
- Portfolio-level optimization
- Performance attribution via phase 5.5 analytics

Example:
    >>> from backtesting import Backtest
    >>> from financial_analyzer.backtesting import FinBotStrategy
    >>> 
    >>> data = load_data(['AAPL', 'MSFT', 'GOOGL'], '2023-01-01', '2024-01-01')
    >>> bt = Backtest(data, FinBotStrategy, cash=1_000_000, commission=0.002)
    >>> stats = bt.run()
    >>> print(f"Sharpe Ratio: {stats['Sharpe Ratio']:.2f}")
"""

from backtesting import Strategy
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

from financial_analyzer.pipeline import Pipeline
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.caching import CacheManager
from financial_analyzer.config import PORTFOLIO_CONFIG, STRATEGY_CONFIG
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FinBotStrategy(Strategy):
    """
    Complete backtesting strategy integrating Phase 5.5 pipeline.
    
    Parameters (optimizable):
    - rebalance_freq: Days between rebalances (default 5)
    - min_confidence: Min signal confidence (default 0.5)
    - max_pos_size: Max % per position (default 0.20)
    - stop_loss: Stop loss % (default 0.10)
    - cash_reserve: Min cash % (default 0.10)
    - use_sentiment: Include sentiment signals (default True)
    - use_technical: Include technical signals (default True)
    - use_ml: Include ML predictions (default True)
    
    Workflow:
    1. init(): Setup pipeline, universe, cache
    2. next(): Each bar
       - Check if rebalance day
       - Run pipeline (sentiment + technical + ML)
       - Fuse signals
       - Optimize allocation
       - Execute orders
       - Apply stop-losses
    """
    
    # Optimizable parameters
    rebalance_freq = 5
    min_confidence = 0.50
    max_pos_size = 0.20
    stop_loss = 0.10
    cash_reserve = 0.10
    use_sentiment = True
    use_technical = True
    use_ml = True
    
    def init(self):
        """
        Initialize strategy.
        
        Setup:
        - Pipeline instance (Phase 5.5)
        - UniverseSelector
        - CacheManager (Phase 5.6.2)
        - Tracking variables
        """
        logger.info("Initializing FinBotStrategy")
        
        # Pipeline from Phase 5.5
        try:
            self.pipeline = Pipeline(
                universe_selector=UniverseSelector(),
                lookback_days=60
            )
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}")
            raise
        
        # Cache from Phase 5.6.2
        self.cache = CacheManager()
        
        # Universe from data columns
        self.universe = list(self.data.columns)
        logger.info(f"Universe: {self.universe}")
        
        # Tracking
        self.days_since_rebalance = 0
        self.last_allocation = {}
        self.entry_prices = {}
        
        # Indicators for plots
        self.sharpe_indicator = self.I(lambda: np.nan)
    
    def next(self):
        """
        Execute strategy on each bar (daily).
        
        Steps:
        1. Increment rebalance counter
        2. If rebalance day:
           a. Run Phase 5.5 pipeline
           b. Fuse all signals
           c. Optimize allocation
           d. Execute orders
        3. Check stop-losses
        """
        self.days_since_rebalance += 1
        
        # Check stop losses every bar
        self._check_stop_losses()
        
        # Only rebalance every N days
        if self.days_since_rebalance < self.rebalance_freq:
            return
        
        logger.debug(f"Rebalancing at bar {len(self.data)}")
        self.days_since_rebalance = 0
        
        # Current date
        date_str = self.data.index[-1].strftime('%Y-%m-%d')
        
        # Run Phase 5.5 pipeline
        try:
            result = self.pipeline.run(
                run_date=date_str,
                universe=self.universe,
                use_sentiment=self.use_sentiment,
                use_technical=self.use_technical,
                use_ml=self.use_ml,
                optimization_method='mean_cvar'
            )
        except Exception as e:
            logger.warning(f"Pipeline run failed on {date_str}: {e}")
            return
        
        # Validate result
        if result['status'] != 'success' or 'allocation' not in result:
            logger.warning(f"Pipeline incomplete on {date_str}")
            return
        
        # Extract allocation + signals
        allocation = result['allocation']
        signals = result.get('signals', {})
        
        # Filter by confidence + capability flags
        allocation_filtered = {
            ticker: weight
            for ticker, weight in allocation.items()
            if ticker != 'cash' 
            and signals.get(ticker, {}).get('confidence', 0) >= self.min_confidence
        }
        
        # Cap position sizes
        allocation_capped = {
            ticker: min(weight, self.max_pos_size)
            for ticker, weight in allocation_filtered.items()
        }
        
        # Normalize weights
        total_weight = sum(allocation_capped.values())
        if total_weight > 0:
            allocation_final = {
                ticker: (weight / total_weight) * (1 - self.cash_reserve)
                for ticker, weight in allocation_capped.items()
            }
        else:
            allocation_final = {}
        
        # Execute rebalance
        self._rebalance(allocation_final)
        
        # Update indicator (for plot)
        portfolio_val = self.equity
        if portfolio_val > 0:
            self.sharpe_indicator[-1] = np.mean([
                signals.get(t, {}).get('confidence', 0.5)
                for t in self.universe
            ])
    
    def _rebalance(self, target_allocation: Dict[str, float]):
        """
        Rebalance portfolio to target allocation.
        
        Args:
            target_allocation: {ticker: weight}
        """
        portfolio_value = self.equity
        
        # Current positions
        current_positions = {}
        for ticker in self.universe:
            pos = self.position(ticker)
            if pos.size > 0:
                current_positions[ticker] = (pos.size * self.data[ticker][-1]) / portfolio_value
            else:
                current_positions[ticker] = 0.0
        
        # SELLS first (free up cash)
        for ticker in self.universe:
            current_w = current_positions.get(ticker, 0.0)
            target_w = target_allocation.get(ticker, 0.0)
            
            if current_w > target_w + 0.01:
                pos = self.position(ticker)
                if pos.size > 0:
                    # Close proportional to reduce to target
                    close_pct = (current_w - target_w) / current_w
                    pos.close(close_pct)
                    logger.debug(f"SELL {ticker}: {close_pct:.2%}")
        
        # BUYS second
        for ticker, target_w in target_allocation.items():
            current_w = current_positions.get(ticker, 0.0)
            
            if target_w > current_w + 0.01:
                notional = (target_w - current_w) * portfolio_value
                size = int(notional / self.data[ticker][-1])
                
                if size > 0:
                    self.buy(ticker, size=size)
                    self.entry_prices[ticker] = self.data[ticker][-1]
                    logger.debug(f"BUY {ticker}: {size} @ {self.data[ticker][-1]:.2f}")
    
    def _check_stop_losses(self):
        """Apply stop-losses to open positions."""
        for ticker in self.universe:
            pos = self.position(ticker)
            if pos.size == 0:
                continue
            
            entry_price = self.entry_prices.get(ticker)
            if entry_price is None:
                continue
            
            current_price = self.data[ticker][-1]
            loss_pct = (entry_price - current_price) / entry_price
            
            if loss_pct >= self.stop_loss:
                pos.close()
                logger.info(f"STOP-LOSS {ticker}: {loss_pct:.2%}")


__all__ = ['FinBotStrategy']

================================================================================
2. src/financial_analyzer/backtesting/backtest_runner.py (400 LOC)
================================================================================

"""
Backtest Runner - Execute and analyze backtests.

Wraps backtesting.py with Phase 5.5 pipeline.

Features:
- Load historical data (yfinance)
- Run single backtest
- Parameter optimization (grid search)
- Walk-forward analysis (robust validation)
- Performance reporting (Phase 5.5 analytics)

Example:
    >>> from financial_analyzer.backtesting import BacktestRunner
    >>> 
    >>> runner = BacktestRunner()
    >>> data = runner.load_data(['AAPL', 'MSFT'], '2023-01-01', '2024-01-01')
    >>> stats = runner.run(data)
    >>> 
    >>> # Optimize
    >>> best_stats, best_params = runner.optimize(
    ...     data,
    ...     rebalance_freq=range(3, 11),
    ...     min_confidence=[0.4, 0.5, 0.6]
    ... )
"""

from backtesting import Backtest
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import yfinance as yf
import logging

from financial_analyzer.backtesting import FinBotStrategy
from financial_analyzer.analytics import PerformanceAnalyzer, ReportGenerator
from financial_analyzer.database import SessionLocal, Trade, Allocation
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class BacktestRunner:
    """Backtest execution and analysis."""
    
    def __init__(self, initial_cash: float = 1_000_000, commission: float = 0.002):
        """
        Initialize runner.
        
        Args:
            initial_cash: Starting capital
            commission: Commission per trade (0.2% default)
        """
        self.initial_cash = initial_cash
        self.commission = commission
        self.db_session = SessionLocal()
    
    def load_data(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Load historical data from yfinance.
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with OHLCV for backtesting.py
        """
        logger.info(f"Loading data for {tickers} from {start_date} to {end_date}")
        
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)
        
        if len(tickers) == 1:
            return data
        
        return data
    
    def run(
        self,
        data: pd.DataFrame,
        strategy_params: Optional[Dict] = None
    ) -> pd.Series:
        """
        Run single backtest.
        
        Args:
            data: Historical OHLCV data
            strategy_params: Override strategy parameters
        
        Returns:
            Backtest statistics
        """
        logger.info("Running backtest...")
        
        bt = Backtest(
            data,
            FinBotStrategy,
            cash=self.initial_cash,
            commission=self.commission
        )
        
        if strategy_params:
            stats = bt.run(**strategy_params)
        else:
            stats = bt.run()
        
        logger.info(f"Backtest complete. Sharpe: {stats.get('Sharpe Ratio', 'N/A'):.2f}")
        
        return stats
    
    def optimize(
        self,
        data: pd.DataFrame,
        **param_ranges
    ) -> Tuple[pd.Series, Dict]:
        """
        Optimize strategy parameters.
        
        Args:
            data: Historical data
            **param_ranges: Parameter ranges (e.g., rebalance_freq=range(3, 11))
        
        Returns:
            (best_stats, best_params)
        """
        logger.info("Starting parameter optimization...")
        
        bt = Backtest(
            data,
            FinBotStrategy,
            cash=self.initial_cash,
            commission=self.commission
        )
        
        # Run optimization (maximize Sharpe Ratio)
        stats = bt.optimize(**param_ranges, maximize='Sharpe Ratio')
        
        logger.info(f"Optimization complete. Sharpe: {stats['Sharpe Ratio']:.2f}")
        
        return stats
    
    def walk_forward_analysis(
        self,
        data: pd.DataFrame,
        train_size: int = 252,  # 1 year
        test_size: int = 63,     # 1 quarter
        step: int = 63           # Quarterly rebalance
    ) -> Dict:
        """
        Walk-forward analysis for robust validation.
        
        Splits data into train/test windows, optimizes on train,
        tests on out-of-sample test data.
        
        Args:
            data: Historical data
            train_size: Training window size (days)
            test_size: Test window size (days)
            step: Step size (days)
        
        Returns:
            {window: stats}
        """
        logger.info("Starting walk-forward analysis...")
        
        results = {}
        n_windows = (len(data) - train_size) // step
        
        for window in range(n_windows):
            start_idx = window * step
            train_end = start_idx + train_size
            test_end = train_end + test_size
            
            if test_end > len(data):
                break
            
            # Split data
            train_data = data.iloc[start_idx:train_end]
            test_data = data.iloc[train_end:test_end]
            
            logger.info(f"Window {window}: Train {train_data.index[0].date()} to "
                       f"{train_data.index[-1].date()}, Test {test_data.index[0].date()} "
                       f"to {test_data.index[-1].date()}")
            
            # Optimize on train
            bt_train = Backtest(train_data, FinBotStrategy, 
                               cash=self.initial_cash, commission=self.commission)
            optimal_params = bt_train.optimize(
                rebalance_freq=range(3, 11),
                min_confidence=[0.4, 0.5, 0.6],
                maximize='Sharpe Ratio'
            )
            
            # Test on out-of-sample
            test_stats = self.run(test_data, dict(optimal_params))
            
            results[f"window_{window}"] = {
                'optimal_params': dict(optimal_params),
                'test_stats': test_stats
            }
        
        # Aggregate results
        test_returns = [
            results[w]['test_stats']['Return [%]'] / 100
            for w in results
        ]
        
        logger.info(f"Walk-forward avg return: {np.mean(test_returns):.2%}")
        
        return results
    
    def generate_report(
        self,
        stats: pd.Series
    ) -> str:
        """
        Generate performance report.
        
        Args:
            stats: Backtest statistics
        
        Returns:
            Markdown report
        """
        logger.info("Generating report...")
        
        report_gen = ReportGenerator()
        analyzer = PerformanceAnalyzer()
        
        # Extract returns
        equity_curve = stats.get('_equity_curve')
        if equity_curve is not None:
            returns = equity_curve['Equity'].pct_change().dropna()
        else:
            returns = pd.Series()
        
        # Generate report
        report = report_gen.generate_report(
            portfolio_returns=returns,
            strategy_name="FinBot Backtest Strategy"
        )
        
        return report


__all__ = ['BacktestRunner']

================================================================================
3. examples/run_backtest_complete.py (300 LOC)
================================================================================

"""
Complete Backtest Example - Phase 5.6.3

Demonstrates:
1. Load historical data
2. Run backtest with Phase 5.5 pipeline
3. Optimize parameters
4. Walk-forward validation
5. Generate report

Usage:
    python examples/run_backtest_complete.py
"""

import logging
from financial_analyzer.backtesting import BacktestRunner
from financial_analyzer.utils.helpers import configure_logging

# Setup logging
configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run complete backtest workflow."""
    
    logger.info("="*60)
    logger.info("FINBOT BACKTEST - PHASE 5.6.3")
    logger.info("="*60)
    
    # 1. Initialize runner
    runner = BacktestRunner(initial_cash=1_000_000, commission=0.002)
    
    # 2. Load data
    logger.info("\n1. Loading historical data...")
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    data = runner.load_data(tickers, '2023-01-01', '2024-01-01')
    logger.info(f"✓ Data loaded: {data.shape}")
    
    # 3. Run single backtest
    logger.info("\n2. Running backtest (default params)...")
    stats = runner.run(data)
    
    logger.info("\n" + "="*60)
    logger.info("BACKTEST RESULTS")
    logger.info("="*60)
    logger.info(f"Return [%]:        {stats.get('Return [%]', 0):.2f}%")
    logger.info(f"Sharpe Ratio:      {stats.get('Sharpe Ratio', 0):.2f}")
    logger.info(f"Max Drawdown [%]:  {stats.get('Max. Drawdown [%]', 0):.2f}%")
    logger.info(f"Win Rate [%]:      {stats.get('Win Rate [%]', 0):.2f}%")
    
    # 4. Optimize parameters
    logger.info("\n3. Optimizing parameters...")
    best_stats, best_params = runner.optimize(
        data,
        rebalance_freq=range(3, 11, 2),
        min_confidence=[0.4, 0.5, 0.6],
        max_pos_size=[0.15, 0.20, 0.25]
    )
    
    logger.info("\n" + "="*60)
    logger.info("OPTIMIZATION RESULTS")
    logger.info("="*60)
    logger.info(f"Best parameters: {best_params}")
    logger.info(f"Sharpe Ratio:    {best_stats.get('Sharpe Ratio', 0):.2f}")
    logger.info(f"Return [%]:      {best_stats.get('Return [%]', 0):.2f}%")
    logger.info(f"Max Drawdown:    {best_stats.get('Max. Drawdown [%]', 0):.2f}%")
    
    # 5. Walk-forward analysis
    logger.info("\n4. Running walk-forward analysis...")
    wf_results = runner.walk_forward_analysis(
        data,
        train_size=252,
        test_size=63,
        step=63
    )
    
    logger.info("\n" + "="*60)
    logger.info("WALK-FORWARD ANALYSIS")
    logger.info("="*60)
    logger.info(f"Windows tested: {len(wf_results)}")
    
    # 6. Generate report
    logger.info("\n5. Generating report...")
    report = runner.generate_report(best_stats)
    
    with open('backtest_report.md', 'w') as f:
        f.write(report)
    
    logger.info("✓ Report saved: backtest_report.md")
    
    logger.info("\n" + "="*60)
    logger.info("BACKTEST COMPLETE!")
    logger.info("="*60)


if __name__ == '__main__':
    main()

================================================================================
REQUIREMENTS
================================================================================

✅ backtesting.py integration (full compatibility)
✅ Phase 5.5 pipeline integration (sentiment + technical + ML)
✅ Phase 5.6.2 cache + async integration
✅ Type hints 100%
✅ Google docstrings 100%
✅ Multi-asset portfolio support
✅ Risk management (stop-loss, position sizing)
✅ Parameter optimization (grid search)
✅ Walk-forward analysis (robust validation)
✅ Performance reporting (analytics integration)
✅ Logging throughout

CRITICAL:
- Strategy must work with Phase 5.5 pipeline imports
- Graceful fallbacks if pipeline errors
- All tests mock yfinance (no real downloads in tests)
- Example script should run successfully
- Parameters optimizable per backtesting.py API

Refs: AUDIT_BACKTESTING_PY.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `finbot_strategy.py` (600 LOC) - Strategy class
2. ✅ `backtest_runner.py` (400 LOC) - Runner utilities
3. ✅ `run_backtest_complete.py` (300 LOC) - Example

**Total** : 1,300 LOC

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ finbot_strategy.py (600 LOC)
✅ backtest_runner.py (400 LOC)
✅ run_backtest_complete.py (300 LOC)

Total: 1,300 LOC
Runnable: YES
Integration: Phase 5.5 + 5.6.2
```

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

**C'est Phase 5.6.3 - Backtesting Engine v2 !** 🎯

**Temps estimé par Copilot : 3-4 heures** ⏱️

**Livraison cible** : Dimanche 9 novembre, ~12h
