# 🎯 PHASE 5.6.1 - INTEGRATION TESTING PROMPT

## CONTEXT

**Phase 5.6.1** implémente **integration tests** pour valider que TOUS les modules Phase 5.5 fonctionnent ensemble.

**Objectif** : Créer tests end-to-end qui valident le pipeline complet (data → signals → allocation → orders → reports).

**Différence avec tests actuels** :
- Tests actuels = Unit tests (testent chaque module isolément)
- Tests 5.6.1 = Integration tests (testent plusieurs modules ensemble)

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_BACKTESTING_PY.md** (45 KB) :
   - Integration testing patterns
   - Test suite organization

2. **AUDIT_ML4T_BOOK.md** (29 KB) :
   - End-to-end testing strategies

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.6.1 : INTEGRATION TESTING

Génère 5 fichiers de tests d'intégration complets :

================================================================================
1. tests/integration/test_end_to_end.py (400 LOC)
================================================================================

"""
End-to-End Integration Tests.

Tests complets du pipeline : data fetching → signal generation → 
allocation → order execution → performance reporting.

Features:
- Full pipeline execution with real data structure
- Multi-module integration validation
- Data flow verification (output of module N = input of module N+1)
- Error propagation testing
- Performance metrics validation

Example:
    >>> from financial_analyzer.pipeline import Pipeline
    >>> from financial_analyzer.data.universe import UniverseSelector
    >>> 
    >>> # Full E2E test
    >>> pipeline = Pipeline(UniverseSelector())
    >>> result = pipeline.run('2025-11-08', ['AAPL', 'MSFT'])
    >>> assert result['status'] == 'success'
    >>> assert 'allocation' in result
"""

Implement:

class TestEndToEnd:
    """
    Full end-to-end integration tests.
    
    Tests:
    1. Complete pipeline with mock data
    2. Data flow validation (module outputs)
    3. Error propagation
    4. Performance validation
    """
    
    @pytest.fixture
    def mock_pipeline(self):
        """
        Create pipeline with mocked dependencies.
        
        Returns:
            Pipeline instance with mock data sources
        """
        # Mock yfinance, NewsAPI, etc.
        pass
    
    def test_full_pipeline_success(self, mock_pipeline):
        """
        Test complete pipeline execution (happy path).
        
        Steps:
        1. Fetch data (returns, metadata)
        2. Engineer features (technical indicators)
        3. Analyze sentiment (news)
        4. Generate ML predictions (LSTM/Transformer)
        5. Fuse signals (combine all)
        6. Allocate portfolio (weights)
        7. Optimize risk (CVaR)
        8. Generate orders (BUY/SELL/HOLD)
        9. Create report (Markdown)
        
        Validate:
        - All steps complete successfully
        - Output structure correct
        - Numbers make sense (weights sum to 1, Sharpe finite)
        """
        result = mock_pipeline.run(
            run_date='2025-11-08',
            universe=['AAPL', 'MSFT', 'GOOGL'],
            optimization_method='mean_cvar'
        )
        
        # Status
        assert result['status'] in ['success', 'partial']
        
        # Data step
        assert 'steps' in result
        assert 'data' in result['steps']
        
        # Allocation
        assert 'allocation' in result
        weights = result['allocation']
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        
        # Metrics
        assert 'metrics' in result
        assert 'sharpe_ratio' in result['metrics']
        assert np.isfinite(result['metrics']['sharpe_ratio'])
        
        # Orders
        assert 'orders' in result
        assert len(result['orders']) > 0
    
    def test_pipeline_data_flow(self, mock_pipeline):
        """
        Test data flows correctly between modules.
        
        Validate:
        - DataFetcher output → FeatureEngineer input
        - FeatureEngineer output → SignalFusion input
        - SignalFusion output → EnsembleAllocator input
        - EnsembleAllocator output → RiskfolioOptimizer input
        """
        # Run pipeline
        result = mock_pipeline.run('2025-11-08', ['AAPL', 'MSFT'])
        
        # Check intermediate results stored
        cache = mock_pipeline._cache
        
        # Data fetched
        assert cache.returns is not None
        assert cache.returns.shape[0] > 0  # Has rows
        assert cache.returns.shape[1] == 2  # 2 assets
        
        # Features calculated
        assert cache.technical_features is not None
        assert 'AAPL' in cache.technical_features
        assert 'rsi' in cache.technical_features['AAPL']
        
        # Signals fused
        assert cache.fused_signals is not None
        assert 'final_score' in cache.fused_signals['AAPL']
        
        # Allocation generated
        assert cache.allocation is not None
        assert sum(cache.allocation.values()) == pytest.approx(1.0)
    
    def test_pipeline_error_propagation(self, mock_pipeline):
        """
        Test error handling & graceful degradation.
        
        Scenarios:
        - Data fetch fails → partial success
        - Sentiment fails → use technical only
        - ML prediction fails → fallback to signals
        """
        # Simulate data fetch failure
        mock_pipeline.market_data_fetcher.fetch = Mock(side_effect=Exception("API error"))
        
        result = mock_pipeline.run('2025-11-08', ['AAPL'])
        
        # Should still complete with partial status
        assert result['status'] == 'partial' or 'error' in result['errors']
    
    def test_pipeline_empty_universe(self, mock_pipeline):
        """Test pipeline with empty universe (edge case)."""
        result = mock_pipeline.run('2025-11-08', [])
        
        assert result['status'] == 'error'
        assert 'empty universe' in str(result['errors']).lower()
    
    def test_pipeline_performance_metrics(self, mock_pipeline):
        """
        Test performance metrics calculation.
        
        Validate:
        - Sharpe ratio calculated
        - Max drawdown calculated
        - Win rate calculated (if trades present)
        """
        result = mock_pipeline.run('2025-11-08', ['AAPL', 'MSFT'])
        
        metrics = result['metrics']
        
        # Required metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'total_return' in metrics
        
        # Value ranges
        assert -10 <= metrics['sharpe_ratio'] <= 10
        assert -1.0 <= metrics['max_drawdown'] <= 0.0


__all__ = ['TestEndToEnd']

================================================================================
2. tests/integration/test_cross_module.py (300 LOC)
================================================================================

"""
Cross-Module Integration Tests.

Tests interactions between specific module pairs:
- Sentiment + SignalFusion
- Technical + SignalFusion
- SignalFusion + EnsembleAllocator
- EnsembleAllocator + RiskfolioOptimizer
"""

Implement 10 tests:

class TestCrossModule:
    """Test module-to-module interactions."""
    
    def test_sentiment_to_fusion(self):
        """
        Test SentimentAggregator output → SignalFusion input.
        
        Validate:
        - Sentiment structure correct
        - SignalFusion accepts sentiment
        - Fused signal includes sentiment component
        """
        pass
    
    def test_technical_to_fusion(self):
        """Test TechnicalFeatures → SignalFusion."""
        pass
    
    def test_lstm_to_fusion(self):
        """Test LSTMPredictor → SignalFusion."""
        pass
    
    def test_fusion_to_allocator(self):
        """Test SignalFusion → EnsembleAllocator."""
        pass
    
    def test_allocator_to_riskfolio(self):
        """Test EnsembleAllocator → RiskfolioOptimizer."""
        pass
    
    def test_riskfolio_to_orders(self):
        """Test RiskfolioOptimizer → OrderExecutor."""
        pass
    
    def test_orders_to_attribution(self):
        """Test OrderExecutor → PerformanceAttributor."""
        pass
    
    def test_attribution_to_report(self):
        """Test PerformanceAttributor → ReportGenerator."""
        pass
    
    def test_config_propagation(self):
        """Test config.py values used correctly across modules."""
        pass
    
    def test_logging_integration(self):
        """Test logging works across modules."""
        pass

================================================================================
3. tests/integration/test_real_data_structure.py (200 LOC)
================================================================================

"""
Real Data Structure Tests.

Tests with realistic data structures (NOT mock data values).
Use yfinance & NewsAPI structure, but with generated data.
"""

Implement 8 tests:

class TestRealDataStructure:
    """Test with real data structures."""
    
    def test_yfinance_returns_structure(self):
        """
        Test pipeline with yfinance-like DataFrame structure.
        
        Structure:
        - DatetimeIndex
        - Columns = tickers
        - Values = daily returns
        """
        pass
    
    def test_newsapi_structure(self):
        """Test with NewsAPI response structure."""
        pass
    
    def test_missing_data_handling(self):
        """Test with NaN/missing data points."""
        pass
    
    def test_different_date_ranges(self):
        """Test with misaligned date ranges."""
        pass
    
    def test_single_asset(self):
        """Test with single asset (edge case)."""
        pass
    
    def test_large_universe(self):
        """Test with 50+ assets."""
        pass
    
    def test_intraday_data(self):
        """Test with intraday (hourly) data."""
        pass
    
    def test_multi_currency(self):
        """Test with mixed currency assets."""
        pass

================================================================================
4. tests/integration/test_performance_benchmarks.py (200 LOC)
================================================================================

"""
Performance Benchmarks.

Tests to ensure performance meets requirements:
- Pipeline execution time < 30s for 10 assets
- Memory usage < 2GB
- No memory leaks
"""

Implement 6 tests:

class TestPerformanceBenchmarks:
    """Performance & resource usage tests."""
    
    def test_execution_time_small_universe(self):
        """Test pipeline completes in <10s for 5 assets."""
        pass
    
    def test_execution_time_large_universe(self):
        """Test pipeline completes in <60s for 50 assets."""
        pass
    
    def test_memory_usage(self):
        """Test memory usage stays under 2GB."""
        pass
    
    def test_no_memory_leaks(self):
        """Test no memory leaks after multiple runs."""
        pass
    
    def test_caching_speedup(self):
        """Test cached run is faster than first run."""
        pass
    
    def test_concurrent_runs(self):
        """Test multiple concurrent pipeline runs."""
        pass

================================================================================
5. tests/integration/test_scenarios.py (300 LOC)
================================================================================

"""
Market Scenario Tests.

Tests pipeline behavior in different market conditions:
- Bull market (all positive returns)
- Bear market (all negative returns)
- High volatility (large swings)
- Low volatility (flat market)
- Crash scenario (sudden drop)
"""

Implement 8 tests:

class TestScenarios:
    """Test various market scenarios."""
    
    def test_bull_market(self):
        """
        Test pipeline in bull market.
        
        Data:
        - All assets positive returns
        - Low volatility
        - High sentiment scores
        
        Expected:
        - High allocation (low cash reserve)
        - Positive Sharpe ratio
        - Low max drawdown
        """
        pass
    
    def test_bear_market(self):
        """Test in bear market (defensive allocation expected)."""
        pass
    
    def test_high_volatility(self):
        """Test with high vol (should reduce position sizes)."""
        pass
    
    def test_crash_scenario(self):
        """Test sudden market drop (risk management)."""
        pass
    
    def test_divergent_signals(self):
        """Test when sentiment/technical/ML disagree."""
        pass
    
    def test_all_bearish_signals(self):
        """Test when all signals bearish (expect high cash)."""
        pass
    
    def test_mixed_signals(self):
        """Test mixed bullish/bearish across assets."""
        pass
    
    def test_extreme_outliers(self):
        """Test with extreme return outliers."""
        pass

================================================================================
REQUIREMENTS
================================================================================

✅ pytest framework
✅ pytest-cov for coverage
✅ Mock ALL external APIs (yfinance, NewsAPI)
✅ Use fixtures for reusable test data
✅ All tests must be deterministic (no randomness)
✅ Type hints 100%
✅ Docstrings for each test
✅ Parametrize similar tests
✅ Target: 90%+ integration coverage

CRITICAL:
- NO real API calls (mock everything)
- Tests should run in <5 minutes total
- Each test independent (no side effects)
- Use tmp_path for file operations
- Clean up resources (files, connections)

Refs: AUDIT_BACKTESTING_PY.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `test_end_to_end.py` (400 LOC) - Full pipeline E2E
2. ✅ `test_cross_module.py` (300 LOC) - Module interactions
3. ✅ `test_real_data_structure.py` (200 LOC) - Real data structures
4. ✅ `test_performance_benchmarks.py` (200 LOC) - Performance tests
5. ✅ `test_scenarios.py` (300 LOC) - Market scenarios

**Total** : 1,400 LOC + ~40 tests

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ test_end_to_end.py (400 LOC, 8 tests)
✅ test_cross_module.py (300 LOC, 10 tests)
✅ test_real_data_structure.py (200 LOC, 8 tests)
✅ test_performance_benchmarks.py (200 LOC, 6 tests)
✅ test_scenarios.py (300 LOC, 8 tests)

Total: 1,400 LOC + 40 tests
Coverage: 90%+ integration paths
All passing: 40/40 ✅
```

---

## 🎯 PURPOSE

**Integration tests valident** :
- ✅ Modules fonctionnent ensemble
- ✅ Data flows correctly entre modules
- ✅ Errors sont gérées gracefully
- ✅ Performance acceptable
- ✅ Scenarios réalistes fonctionnent

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

**C'est Phase 5.6.1 - Integration Testing !** 🎯

**Temps estimé par Copilot : 2-3 heures** ⏱️
