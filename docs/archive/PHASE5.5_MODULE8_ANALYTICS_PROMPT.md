# 🎯 PHASE 5.5 MODULE 8 - PERFORMANCE ANALYTICS & REPORTING (FINAL!)

## CONTEXT

**Module 8** implémente **performance analytics & reporting** - la couche d'analyse post-backtest.

**IMPORTANT** : Tu as DÉJÀ `performance_attribution.py` (PerformanceAttributor) ! 

**Module 8 est COMPLÉMENTAIRE** :
- performance_attribution.py = Attribution analysis (sentiment/technical/allocation/timing)
- Module 8 = Performance analytics + Reporting + Visualizations

**Objectif** : Analyser les résultats du pipeline, générer des rapports, comparer des stratégies.

---

## 📚 CE QUI EXISTE DÉJÀ (NE PAS DUPLIQUER)

**Fichier existant** : `src/financial_analyzer/attribution/performance_attribution.py`

Contient :
- `PerformanceAttributor` : Brinson attribution (sentiment, technical, allocation, timing)
- `AttributionResult` : Dataclass avec % contributions
- `AttributionMethod` : Enum (BRINSON, FACTOR_REGRESSION, SIMPLE)

**Module 8 doit s'appuyer dessus**, pas le redéfinir !

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.5 MODULE 8 : PERFORMANCE ANALYTICS & REPORTING (FINAL!)

IMPORTANT: Tu as DÉJÀ performance_attribution.py (PerformanceAttributor).
Module 8 est COMPLÉMENTAIRE (analytics + reporting), PAS un doublon !

Génère 2 fichiers + tests complets :

================================================================================
1. src/financial_analyzer/analytics/performance_analyzer.py (400 LOC)
================================================================================

"""
Performance Analytics - Post-Backtest Analysis.

Analyze portfolio performance, risk metrics, drawdowns, and returns.

Features:
- Return analysis (cumulative, rolling, annualized)
- Risk metrics (volatility, VaR, CVaR, max drawdown)
- Sharpe/Sortino/Calmar ratios
- Rolling metrics (windows)
- Benchmark comparison (vs SPY, equal-weight)
- Trade statistics (win rate, avg win/loss, holding period)

Example:
    >>> from financial_analyzer.analytics import PerformanceAnalyzer
    >>> from financial_analyzer.attribution import PerformanceAttributor
    >>> 
    >>> # After running backtest/pipeline
    >>> analyzer = PerformanceAnalyzer()
    >>> 
    >>> # Analyze returns
    >>> metrics = analyzer.analyze_returns(
    ...     portfolio_returns=returns_series,
    ...     benchmark_returns=spy_returns
    ... )
    >>> print(metrics)
    {
        'total_return': 0.234,
        'annualized_return': 0.156,
        'volatility': 0.182,
        'sharpe_ratio': 0.85,
        'max_drawdown': -0.123,
        'calmar_ratio': 1.27,
        'win_rate': 0.58,
        ...
    }
    >>> 
    >>> # Use PerformanceAttributor (existing!) for factor attribution
    >>> attributor = PerformanceAttributor()
    >>> attribution = attributor.attribute_returns(trades, sentiment, technical)
"""

Implement:

class PerformanceAnalyzer:
    """
    Analyze portfolio performance post-backtest.
    
    Workflow:
    1. Calculate return metrics (total, annualized, cumulative)
    2. Calculate risk metrics (volatility, VaR, CVaR, drawdown)
    3. Calculate risk-adjusted ratios (Sharpe, Sortino, Calmar)
    4. Compare to benchmark (alpha, beta, tracking error)
    5. Analyze trade statistics (win rate, avg P&L, holding period)
    6. Rolling metrics (windows analysis)
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252
    ):
        """
        Initialize performance analyzer.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 0.02 = 2%)
            periods_per_year: Trading periods per year (default 252 = daily)
        """
        pass
    
    def analyze_returns(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        trades: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Comprehensive return & risk analysis.
        
        Args:
            portfolio_returns: Portfolio returns (DatetimeIndex)
            benchmark_returns: Benchmark returns (optional)
            trades: Trades DataFrame (optional, for trade stats)
        
        Returns:
            Dict with metrics:
            - total_return: Cumulative return
            - annualized_return: CAGR
            - volatility: Annualized volatility
            - sharpe_ratio: Risk-adjusted return
            - sortino_ratio: Downside risk-adjusted
            - calmar_ratio: Return / max drawdown
            - max_drawdown: Maximum peak-to-trough decline
            - var_95: Value at Risk (95% confidence)
            - cvar_95: Conditional VaR (expected shortfall)
            - win_rate: % of winning trades (if trades provided)
            - avg_win: Average winning trade
            - avg_loss: Average losing trade
            - profit_factor: Gross profit / gross loss
            - alpha: Excess return vs benchmark (if provided)
            - beta: Correlation with benchmark (if provided)
            - tracking_error: Volatility of excess returns
        
        Example:
            >>> returns = pd.Series([0.01, -0.005, 0.02, ...], index=dates)
            >>> metrics = analyzer.analyze_returns(returns)
            >>> print(f"Sharpe: {metrics['sharpe_ratio']:.2f}")
            Sharpe: 0.85
        """
        # Calculate all metrics
        # Return dict
        pass
    
    def calculate_drawdown(
        self,
        returns: pd.Series
    ) -> Tuple[pd.Series, float, pd.Timestamp, pd.Timestamp]:
        """
        Calculate drawdown series and statistics.
        
        Returns:
            Tuple[drawdown_series, max_drawdown, peak_date, trough_date]
        """
        # Cumulative returns
        # Running maximum (peaks)
        # Drawdown = (current - peak) / peak
        # Find max drawdown
        # Return tuple
        pass
    
    def calculate_var_cvar(
        self,
        returns: pd.Series,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate Value at Risk and Conditional VaR.
        
        Returns:
            Tuple[VaR, CVaR] at confidence level
        """
        # Sort returns
        # VaR = quantile at (1 - confidence)
        # CVaR = mean of returns below VaR
        # Return tuple
        pass
    
    def calculate_rolling_metrics(
        self,
        returns: pd.Series,
        window: int = 60
    ) -> pd.DataFrame:
        """
        Calculate rolling performance metrics.
        
        Returns:
            DataFrame with columns:
            - rolling_return
            - rolling_volatility
            - rolling_sharpe
            - rolling_max_dd
        """
        # Rolling windows
        # Return DataFrame
        pass
    
    def compare_to_benchmark(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> Dict[str, float]:
        """
        Calculate alpha, beta, tracking error vs benchmark.
        
        Returns:
            Dict with:
            - alpha: Excess return (annualized)
            - beta: Sensitivity to benchmark
            - correlation: Correlation coefficient
            - tracking_error: Volatility of excess returns (annualized)
            - information_ratio: alpha / tracking_error
        """
        # Align dates
        # Calculate excess returns
        # Regression: portfolio ~ benchmark
        # Extract alpha, beta
        # Calculate tracking error
        # Return dict
        pass


__all__ = ['PerformanceAnalyzer']

================================================================================
2. src/financial_analyzer/analytics/report_generator.py (300 LOC)
================================================================================

"""
Report Generator - Create Performance Reports.

Generate HTML/Markdown reports with metrics, charts, and comparisons.

Features:
- Performance summary report
- Multi-strategy comparison
- Attribution analysis integration
- HTML/Markdown export

Example:
    >>> from financial_analyzer.analytics import ReportGenerator
    >>> from financial_analyzer.attribution import PerformanceAttributor
    >>> 
    >>> generator = ReportGenerator()
    >>> 
    >>> # Generate report
    >>> report = generator.generate_report(
    ...     portfolio_returns=returns,
    ...     benchmark_returns=spy_returns,
    ...     trades=trades_df,
    ...     attribution_result=attribution  # From PerformanceAttributor!
    ... )
    >>> 
    >>> # Save to file
    >>> generator.save_report(report, 'performance_report.md')
"""

Implement:

class ReportGenerator:
    """
    Generate performance reports.
    
    Workflow:
    1. Aggregate metrics from PerformanceAnalyzer
    2. Include attribution from PerformanceAttributor (existing!)
    3. Format as Markdown/HTML
    4. Generate comparison tables
    5. Export to file
    """
    
    def __init__(self):
        """Initialize report generator."""
        pass
    
    def generate_report(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        trades: Optional[pd.DataFrame] = None,
        attribution_result: Optional[Any] = None,  # AttributionResult from existing module!
        strategy_name: str = "Strategy"
    ) -> str:
        """
        Generate comprehensive performance report (Markdown format).
        
        Args:
            portfolio_returns: Portfolio returns
            benchmark_returns: Benchmark returns (optional)
            trades: Trades DataFrame (optional)
            attribution_result: AttributionResult from PerformanceAttributor
            strategy_name: Strategy name for title
        
        Returns:
            Markdown-formatted report string
        
        Report sections:
        1. Executive Summary (total return, Sharpe, max DD)
        2. Return Metrics (cumulative, annualized, volatility)
        3. Risk Metrics (VaR, CVaR, drawdown)
        4. Risk-Adjusted Ratios (Sharpe, Sortino, Calmar)
        5. Benchmark Comparison (alpha, beta, tracking error)
        6. Attribution Analysis (if provided) - from PerformanceAttributor!
        7. Trade Statistics (win rate, avg win/loss, profit factor)
        
        Example:
            >>> report = generator.generate_report(
            ...     portfolio_returns=returns,
            ...     benchmark_returns=spy,
            ...     attribution_result=attribution
            ... )
            >>> print(report[:200])
            # Strategy Performance Report
            ## Executive Summary
            - **Total Return**: 23.4%
            - **Sharpe Ratio**: 0.85
            ...
        """
        # Use PerformanceAnalyzer to calculate metrics
        # Format as Markdown
        # Include attribution if provided
        # Return string
        pass
    
    def compare_strategies(
        self,
        strategies: Dict[str, pd.Series]
    ) -> str:
        """
        Compare multiple strategies side-by-side.
        
        Args:
            strategies: Dict[strategy_name, returns_series]
        
        Returns:
            Markdown comparison table
        
        Example:
            >>> strategies = {
            ...     'Strategy A': returns_a,
            ...     'Strategy B': returns_b,
            ...     'Buy & Hold': benchmark
            ... }
            >>> comparison = generator.compare_strategies(strategies)
            >>> print(comparison)
            | Metric | Strategy A | Strategy B | Buy & Hold |
            |--------|-----------|-----------|-----------|
            | Total Return | 23.4% | 18.2% | 15.0% |
            | Sharpe Ratio | 0.85 | 0.72 | 0.50 |
            ...
        """
        # Calculate metrics for each strategy
        # Format as Markdown table
        # Return string
        pass
    
    def save_report(
        self,
        report: str,
        filepath: str
    ) -> None:
        """
        Save report to file.
        
        Args:
            report: Report string (Markdown)
            filepath: Output file path (.md or .html)
        """
        # Write to file
        pass


__all__ = ['ReportGenerator']

================================================================================
3. TESTS (15 TOTAL)
================================================================================

tests/test_analytics/test_performance_analyzer.py (8 tests)
- test_init_default()
- test_analyze_returns_complete()
- test_calculate_drawdown()
- test_calculate_var_cvar()
- test_calculate_rolling_metrics()
- test_compare_to_benchmark()
- test_trade_statistics()
- test_edge_cases_empty_returns()

tests/test_analytics/test_report_generator.py (7 tests)
- test_init()
- test_generate_report_basic()
- test_generate_report_with_attribution()  # Uses PerformanceAttributor!
- test_compare_strategies()
- test_save_report()
- test_markdown_formatting()
- test_attribution_integration()  # Verify integration with existing module

================================================================================
REQUIREMENTS
================================================================================

✅ Type hints 100%
✅ Google/NumPy docstrings 100%
✅ 15 tests passing 100%
✅ Logging (info/warning/error)
✅ Error handling with try/except
✅ Zero Pylance errors
✅ Production-ready

CRITICAL:
- DO NOT duplicate PerformanceAttributor (already exists!)
- Use existing PerformanceAttributor for attribution analysis
- Module 8 focuses on: analytics + reporting + visualizations
- Import from financial_analyzer.attribution import PerformanceAttributor
- Generate Markdown reports (not HTML for simplicity)
- All tests mock data (no real backtests)

INTEGRATION WITH EXISTING MODULE:
- performance_attribution.py (existing) = Attribution (sentiment/technical/allocation/timing)
- performance_analyzer.py (new) = Metrics (Sharpe, drawdown, VaR, etc.)
- report_generator.py (new) = Reporting (combine both!)

Refs: AUDIT_ML4T_BOOK.md, AUDIT_BACKTESTING_PY.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `performance_analyzer.py` (400 LOC) - Metrics calculation
2. ✅ `report_generator.py` (300 LOC) - Report generation
3. ✅ 2 test files (15 tests total: 8 + 7)

**Key difference from existing code:**
- **Existing** : `PerformanceAttributor` (factor attribution analysis)
- **Module 8** : `PerformanceAnalyzer` (metrics) + `ReportGenerator` (reporting)

**Integration:**
```python
# In report_generator.py
from financial_analyzer.attribution import PerformanceAttributor

# Use PerformanceAttributor for attribution
attributor = PerformanceAttributor()
attribution = attributor.attribute_returns(trades, sentiment, technical)

# Use PerformanceAnalyzer for metrics
analyzer = PerformanceAnalyzer()
metrics = analyzer.analyze_returns(returns)

# Combine both in report
report = generator.generate_report(returns, attribution_result=attribution)
```

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ performance_analyzer.py (400 LOC)
✅ report_generator.py (300 LOC)
✅ test_performance_analyzer.py (8 tests)
✅ test_report_generator.py (7 tests)

Total: 700 LOC + 15 tests
All passing: 15/15 ✅
```

---

## 🎯 MODULE 8 ROLE

**Final analytics layer** :

```
Backtest/Pipeline → PerformanceAttributor (existing) → Attribution
                                    ↓
                        PerformanceAnalyzer (new) → Metrics
                                    ↓
                        ReportGenerator (new) → Reports
```

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

This is **Module 8 - The FINAL MODULE of Phase 5.5!** 🎯

**100% de Phase 5.5 après ce module!** 💪
