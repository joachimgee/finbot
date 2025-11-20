# 🎯 PHASE 5.5 MODULE 7 - PIPELINE V2 PROMPT (FINAL MODULE!)

## CONTEXT

**Module 7** implémente **unified end-to-end pipeline** orchestrating tous les modules précédents.

**Objectif** : Combiner data ingestion → feature engineering → signal fusion → portfolio allocation en une seule **production-grade pipeline**.

**Workflow complet** :
1. **Data Ingestion** : Fetch returns, news, metadata
2. **Feature Engineering** : Technical indicators (Module 1)
3. **Sentiment Analysis** : News sentiment (Module 2)
4. **Deep Learning** : Price predictions (Module 5)
5. **Signal Fusion** : Combine all signals (Module 6)
6. **Portfolio Allocation** : Generate weights (Module 6)
7. **Risk Management** : Optimize portfolio (Module 4)
8. **Execution** : Generate trading orders

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_BACKTESTING_PY.md** (45 KB) :
   - Pipeline patterns
   - Event handling
   - State management

2. **AUDIT_ML4T_BOOK.md** (29 KB) :
   - ML pipeline workflows
   - Data flow architecture

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.5 MODULE 7 : UNIFIED PIPELINE V2 (FINAL!)

Génère 2 fichiers + tests complets :

================================================================================
1. src/financial_analyzer/pipeline/pipeline.py (400 LOC)
================================================================================

"""
Unified End-to-End Trading Pipeline.

Orchestrates complete workflow:
1. Data fetching (returns, news, metadata)
2. Technical feature engineering
3. Sentiment analysis
4. Deep learning predictions
5. Signal fusion
6. Portfolio allocation
7. Risk management optimization

Features:
- Daily/weekly orchestration
- Error handling + fallbacks
- Logging + metrics tracking
- State persistence (cache)
- Incremental updates

Audit references:
- AUDIT_BACKTESTING_PY.md pp.1-50 (pipeline patterns)
- AUDIT_ML4T_BOOK.md pp.1-30 (workflow design)

Example:
    >>> from financial_analyzer.pipeline import Pipeline
    >>> from financial_analyzer.universe import UniverseSelector
    >>> 
    >>> # Initialize pipeline
    >>> pipeline = Pipeline(
    ...     universe_selector=UniverseSelector(),
    ...     lookback_days=252,
    ...     forecast_horizon=5
    ... )
    >>> 
    >>> # Run daily pipeline
    >>> result = pipeline.run(
    ...     run_date='2025-11-08',
    ...     universe=['AAPL', 'MSFT', 'GOOGL', ...],
    ...     optimization_method='mean_cvar'
    ... )
    >>> 
    >>> print(result)
    {
        'date': '2025-11-08',
        'signals': {...},              # Fused signals per asset
        'allocation': {...},           # Portfolio weights
        'risk_metrics': {...},         # Portfolio stats
        'execution_orders': [...]      # Trading orders
    }
"""

Implement:

class Pipeline:
    """
    End-to-end unified pipeline.
    
    Components:
    - DataFetcher: Load returns, news, metadata
    - FeatureEngineer: Calculate technical indicators
    - SentimentAggregator: News sentiment scores
    - LSTMPredictor/TransformerPredictor: ML predictions
    - SignalFusion: Combine signals
    - EnsembleAllocator: Portfolio weights
    - RiskfolioOptimizer: Risk-adjusted optimization
    
    Workflow:
    1. fetch_data(universe, lookback_days) → returns, metadata
    2. engineer_features(returns) → technical indicators
    3. analyze_sentiment(universe) → sentiment scores
    4. predict_returns(returns) → ML predictions
    5. fuse_signals(tech, sentiment, ml) → combined signals
    6. allocate_portfolio(signals) → weights
    7. optimize_risk(weights, returns) → final allocation
    8. generate_orders(current, target) → execution orders
    """
    
    def __init__(
        self,
        universe_selector,
        lookback_days: int = 252,
        forecast_horizon: int = 5,
        optimization_method: str = 'mean_cvar'
    ):
        """
        Initialize pipeline.
        
        Args:
            universe_selector: UniverseSelector instance
            lookback_days: Historical data window (default 252 = 1 year)
            forecast_horizon: Forward prediction window (default 5 days)
            optimization_method: Portfolio optimization ('mean_cvar', 'hrp', 'nco')
        """
        pass
    
    def run(
        self,
        run_date: str,
        universe: List[str],
        optimization_method: Optional[str] = None
    ) -> Dict:
        """
        Execute complete pipeline on run_date.
        
        Args:
            run_date: Date to run pipeline (YYYY-MM-DD format)
            universe: List of tickers to analyze
            optimization_method: Override default optimization
        
        Returns:
            Dict with keys:
            - 'date': Run date
            - 'universe': Assets analyzed
            - 'signals': Dict[ticker, signal_dict]
            - 'allocation': Dict[ticker, weight]
            - 'risk_metrics': Dict with portfolio stats
            - 'execution_orders': List of OrderSpec
            - 'status': 'success' or 'partial' or 'error'
            - 'errors': List of errors encountered
        
        Process:
        1. Fetch historical data (returns, news)
        2. Calculate technical features
        3. Analyze sentiment
        4. Generate ML predictions
        5. Fuse signals
        6. Generate allocation
        7. Optimize risk
        8. Generate execution orders
        9. Log & cache results
        """
        # Initialize result dict
        # Step 1: Fetch data
        # Step 2: Engineer features
        # Step 3: Analyze sentiment
        # Step 4: Generate predictions
        # Step 5: Fuse signals
        # Step 6: Allocate
        # Step 7: Optimize
        # Step 8: Generate orders
        # Step 9: Return result
        pass
    
    def _fetch_data(
        self,
        universe: List[str],
        lookback_days: int
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Fetch historical data + metadata.
        
        Returns:
            Tuple[returns_df, metadata_dict]
            - returns_df: (DatetimeIndex, assets as columns)
            - metadata_dict: {'ticker': {'price', 'market_cap', ...}}
        """
        # Use DataFetcher to get returns (yfinance)
        # Fetch metadata (FinanceDatabase)
        # Return both
        pass
    
    def _engineer_features(
        self,
        returns: pd.DataFrame
    ) -> Dict[str, Dict]:
        """
        Calculate technical indicators.
        
        Returns:
            Dict[ticker, {'rsi': ..., 'macd': ..., 'sma200': ...}]
        """
        # Use FeatureEngineer (Module 1)
        # Calculate RSI, MACD, SMA, Bollinger Bands
        # Return dict
        pass
    
    def _analyze_sentiment(
        self,
        universe: List[str]
    ) -> Dict[str, Dict]:
        """
        Get sentiment scores per asset.
        
        Returns:
            Dict[ticker, {'sentiment_score': ..., 'confidence': ...}]
        """
        # Use SentimentAggregator (Module 2)
        # Aggregate news sentiment for each ticker
        # Return dict
        pass
    
    def _generate_predictions(
        self,
        returns: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Generate ML predictions.
        
        Returns:
            Dict[ticker, expected_return]
        """
        # Use LSTMPredictor or TransformerPredictor (Module 5)
        # Predict next period returns
        # Return dict
        pass
    
    def _fuse_signals(
        self,
        technical: Dict,
        sentiment: Dict,
        ml_predictions: Dict
    ) -> Dict[str, Dict]:
        """
        Fuse all signals.
        
        Returns:
            Dict[ticker, {'final_score': ..., 'confidence': ..., 'divergence': ...}]
        """
        # Use SignalFusion (Module 6)
        # For each ticker, combine technical+sentiment+ml
        # Return dict
        pass
    
    def _allocate_portfolio(
        self,
        signals: Dict
    ) -> Dict[str, float]:
        """
        Generate portfolio allocation from signals.
        
        Returns:
            Dict[ticker, weight] (sums to 1.0)
        """
        # Use EnsembleAllocator (Module 6)
        # Convert signals to weights
        # Return dict
        pass
    
    def _optimize_risk(
        self,
        weights: Dict[str, float],
        returns: pd.DataFrame,
        method: str = 'mean_cvar'
    ) -> Dict[str, float]:
        """
        Optimize portfolio risk.
        
        Returns:
            Dict[ticker, optimized_weight]
        """
        # Use RiskfolioOptimizer (Module 4)
        # Optimize weights by CVaR/HRP/NCO
        # Return optimized dict
        pass
    
    def _generate_orders(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        total_capital: float = 1_000_000
    ) -> List[Dict]:
        """
        Generate execution orders.
        
        Returns:
            List of order specs:
            [
                {'ticker': 'AAPL', 'action': 'BUY', 'shares': 100, 'target_weight': 0.25},
                {'ticker': 'MSFT', 'action': 'HOLD', 'shares': 0, 'target_weight': 0.20},
                {'ticker': 'GOOGL', 'action': 'SELL', 'shares': 50, 'target_weight': 0.15},
                ...
            ]
        """
        # Compare current vs target weights
        # Generate BUY/SELL/HOLD orders
        # Return order list
        pass


__all__ = ['Pipeline']

================================================================================
2. src/financial_analyzer/pipeline/order_executor.py (200 LOC)
================================================================================

"""
Order Execution & Portfolio Tracking.

Handles order execution, position tracking, and trade recording.

Example:
    >>> from financial_analyzer.pipeline import OrderExecutor
    >>> 
    >>> executor = OrderExecutor()
    >>> 
    >>> # Execute order
    >>> result = executor.execute(
    ...     order={'ticker': 'AAPL', 'action': 'BUY', 'shares': 100},
    ...     current_price=150.0
    ... )
    >>> 
    >>> # Track positions
    >>> positions = executor.get_positions()
"""

Implement:

class OrderExecutor:
    """
    Execute orders and track portfolio.
    
    Features:
    - Order validation
    - Execution simulation (or real broker API)
    - Position tracking
    - Trade logging
    """
    
    def __init__(self, initial_capital: float = 1_000_000):
        """
        Initialize executor.
        
        Args:
            initial_capital: Starting portfolio value
        """
        pass
    
    def execute(
        self,
        order: Dict,
        current_price: float
    ) -> Dict:
        """
        Execute single order.
        
        Args:
            order: {'ticker', 'action', 'shares', 'target_weight', ...}
            current_price: Current market price
        
        Returns:
            Dict with execution details (filled, price, commission, etc.)
        """
        pass
    
    def get_positions(self) -> pd.DataFrame:
        """
        Get current positions.
        
        Returns:
            DataFrame with columns: ticker, shares, avg_price, value, pct_portfolio
        """
        pass
    
    def get_portfolio_value(self) -> Dict:
        """
        Get portfolio stats.
        
        Returns:
            Dict with total_value, cash, invested, drawdown, etc.
        """
        pass


__all__ = ['OrderExecutor']

================================================================================
3. TESTS (20 TOTAL)
================================================================================

tests/test_pipeline/test_pipeline.py (12 tests)
- test_init_default()
- test_run_complete_pipeline()
- test_run_handles_missing_data()
- test_fetch_data()
- test_engineer_features()
- test_analyze_sentiment()
- test_generate_predictions()
- test_fuse_signals()
- test_allocate_portfolio()
- test_optimize_risk()
- test_generate_orders()
- test_pipeline_error_handling()

tests/test_pipeline/test_order_executor.py (8 tests)
- test_init_default()
- test_execute_buy_order()
- test_execute_sell_order()
- test_execute_hold_order()
- test_get_positions()
- test_get_portfolio_value()
- test_portfolio_tracking()
- test_invalid_order_handling()

================================================================================
REQUIREMENTS
================================================================================

✅ Type hints 100%
✅ Google/NumPy docstrings 100%
✅ 20 tests passing 100%
✅ Logging (debug/info/warning/error)
✅ Error handling + graceful fallbacks
✅ Zero Pylance errors
✅ Production-ready
✅ All dependencies injected (not hardcoded)

CRITICAL:
- Pipeline orchestrates 1-6 modules (don't duplicate logic)
- Use composition: Pipeline HAS-A FeatureEngineer, SentimentAggregator, etc.
- Error handling: Log errors but continue (graceful degradation)
- State persistence: Cache intermediate results
- All tests mock dependencies (no real API calls)
- Returns complete Dict with status/errors/metrics

Refs: AUDIT_BACKTESTING_PY.md, AUDIT_ML4T_BOOK.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `pipeline.py` (400 LOC) - Main orchestration
2. ✅ `order_executor.py` (200 LOC) - Execution & tracking
3. ✅ 2 test files (20 tests total: 12 + 8)

**Key methods:**
- run() - Execute complete pipeline
- _fetch_data() - Load returns + metadata
- _engineer_features() - Technical indicators
- _analyze_sentiment() - News sentiment
- _generate_predictions() - ML forecasts
- _fuse_signals() - Combine signals
- _allocate_portfolio() - Weights generation
- _optimize_risk() - Risk management
- _generate_orders() - Execution orders

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ pipeline.py (400 LOC)
✅ order_executor.py (200 LOC)
✅ test_pipeline.py (12 tests)
✅ test_order_executor.py (8 tests)

Total: 600 LOC + 20 tests
All passing: 20/20 ✅
```

---

## 🎯 MODULE 7 ROLE

**Final orchestration layer** :

```
Data (yfinance, NewsAPI) ──→ Pipeline ──→ Orders ──→ Execution
                                │
                 ┌──────────────┼──────────────┐
                 ▼              ▼              ▼
            Features        Sentiment       ML Predictions
            (Module 1)       (Module 2)      (Module 5)
                 │              │              │
                 └──────────────┼──────────────┘
                                ▼
                         SignalFusion (Module 6)
                                ▼
                         EnsembleAllocator (Module 6)
                                ▼
                         RiskfolioOptimizer (Module 4)
                                ▼
                         OrderExecutor
```

---

## ⏱️ **TIMELINE**

**Attendu : 1.5-2 heures** (orchestration layer)

---

## 📊 **APRÈS MODULE 7**

| Module | Status | Progress |
|--------|--------|----------|
| 1-6 | ✅ DONE | 88% |
| 7. Pipeline | 🚀 IN PROGRESS | 13% |
| 8. Attribution | Pending | - |
| **TOTAL** | **88% DONE** | **Phase 5.5** |

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

This is **Module 7 - The ORCHESTRATION LAYER!** 🎯

Almost there - only 2 modules left after this! 💪
