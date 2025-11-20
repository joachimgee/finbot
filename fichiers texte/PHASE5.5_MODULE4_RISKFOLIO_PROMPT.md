# 🎯 PHASE 5.5 MODULE 4 - RISKFOLIO OPTIMIZATION PROMPT

## CONTEXT

**Module 4** implémente **portfolio optimization production-grade** avec Riskfolio-Lib.

**Objectif** : Remplacer le `SignalPortfolioBridge` mock par **vraie optimisation Riskfolio** avec :
- 59 mesures de risque (CVaR, CDaR, EVaR, RLVaR, etc.)
- 4 méthodes d'optimisation (Classic, Black-Litterman, NCO, HRP)
- Risk decomposition (factor contributions)

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_RISKFOLIO_LIB.md** (31 KB) :
   - 24 mesures de risque convexes + 35 pour HRP
   - NCO (Nested Clustered Optimization)
   - Black-Litterman model
   - Factor models & risk decomposition

2. **AUDIT_PYPORTFOLIOOPT.md** (34 KB) :
   - Efficient Frontier patterns
   - Covariance shrinkage (Ledoit-Wolf)
   - Discrete allocation

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.5 MODULE 4 : RISKFOLIO PORTFOLIO OPTIMIZATION

Génère 3 fichiers + tests complets :

================================================================================
1. src/financial_analyzer/portfolio_optimization/riskfolio_optimizer.py (300 LOC)
================================================================================

"""
Riskfolio Portfolio Optimizer - Production Grade.

Implements portfolio optimization using Riskfolio-Lib with:
- 24 convex risk measures (CVaR, CDaR, EVaR, RLVaR, etc.)
- 4 optimization methods (Classic, Black-Litterman, NCO, HRP)
- Risk decomposition by asset and factor
- Covariance shrinkage (Ledoit-Wolf)

Audit references:
- AUDIT_RISKFOLIO_LIB.md pp.1-31 (59 risk measures, NCO, factor models)
- AUDIT_PYPORTFOLIOOPT.md pp.1-34 (efficient frontier patterns)

Example:
    >>> from financial_analyzer.portfolio_optimization import RiskfolioOptimizer
    >>> 
    >>> optimizer = RiskfolioOptimizer(returns_df)
    >>> 
    >>> # Mean-CVaR optimization
    >>> weights = optimizer.optimize_mean_cvar(
    ...     expected_returns=mu,
    ...     risk_aversion=1.0
    ... )
    >>> 
    >>> # NCO (Nested Clustered Optimization)
    >>> weights_nco = optimizer.optimize_nco(
    ...     expected_returns=mu,
    ...     risk_measure='CVaR'
    ... )
    >>> 
    >>> # Risk decomposition
    >>> attribution = optimizer.risk_decomposition(weights)
"""

Implement:

class RiskfolioOptimizer:
    """
    Production-grade portfolio optimization with Riskfolio-Lib.
    
    Supports:
    - 24 risk measures (CVaR, CDaR, EVaR, RLVaR, Semivariance, etc.)
    - Optimization models (Classic, Black-Litterman, NCO, HRP)
    - Risk decomposition by asset + factor
    - Covariance shrinkage (Ledoit-Wolf, Oracle)
    
    Workflow:
    1. Load returns DataFrame (DatetimeIndex, assets as columns)
    2. Estimate covariance matrix (with shrinkage)
    3. Optimize portfolio (Classic, NCO, HRP, or Black-Litterman)
    4. Decompose risk contributions
    5. Return weights + risk breakdown
    """
    
    def __init__(
        self,
        returns: pd.DataFrame,
        covariance_method: str = 'ledoit_wolf',
        frequency: int = 252
    ):
        """
        Initialize Riskfolio optimizer.
        
        Args:
            returns: DataFrame with returns (DatetimeIndex, assets as columns)
            covariance_method: 'ledoit_wolf', 'oracle', 'hist' (default 'ledoit_wolf')
            frequency: Annual frequency (252 for daily, 52 for weekly)
        
        Raises:
            ValueError: If returns invalid or empty
        """
        # Validate returns
        # Load Riskfolio Portfolio objects
        # Estimate covariance matrix with shrinkage
        pass
    
    def optimize_mean_cvar(
        self,
        expected_returns: Optional[pd.Series] = None,
        risk_aversion: float = 1.0,
        cvar_alpha: float = 0.05
    ) -> Dict[str, float]:
        """
        Mean-CVaR optimization (Conditional Value at Risk).
        
        Minimizes:
        - return - risk_aversion * CVaR_alpha
        
        Args:
            expected_returns: Expected returns per asset (or use historical mean)
            risk_aversion: Risk aversion coefficient (default 1.0)
            cvar_alpha: CVaR confidence level (default 0.05 = 5% tail)
        
        Returns:
            Dict[asset_ticker, weight] (weights sum to 1.0)
        
        Example:
            >>> weights = optimizer.optimize_mean_cvar(
            ...     expected_returns=mu,
            ...     risk_aversion=1.0,
            ...     cvar_alpha=0.05
            ... )
        """
        # Use Riskfolio Portfolio.optimization()
        # model='Classic', rm='CVaR', obj='Utility'
        pass
    
    def optimize_mean_cdar(
        self,
        expected_returns: Optional[pd.Series] = None,
        risk_aversion: float = 1.0,
        cdar_alpha: float = 0.05
    ) -> Dict[str, float]:
        """
        Mean-CDaR optimization (Conditional Drawdown at Risk).
        
        Tail risk focus on drawdowns (more conservative than CVaR).
        
        Args:
            expected_returns: Expected returns per asset
            risk_aversion: Risk aversion coefficient
            cdar_alpha: CDaR confidence level (default 0.05)
        
        Returns:
            Dict[asset_ticker, weight]
        """
        # Use rm='CDaR'
        pass
    
    def optimize_nco(
        self,
        expected_returns: Optional[pd.Series] = None,
        risk_measure: str = 'CVaR',
        linkage: str = 'ward'
    ) -> Dict[str, float]:
        """
        Nested Clustered Optimization (NCO).
        
        Combines HRP (hierarchical clustering) + Mean-Variance optimization.
        
        Process:
        1. HRP clustering (hierarchical structure)
        2. Intra-cluster equal-weight or risk-parity
        3. Inter-cluster optimization (mean-variance on clusters)
        
        Args:
            expected_returns: Expected returns per asset
            risk_measure: Risk measure for optimization ('CVaR', 'CDaR', 'MV')
            linkage: Hierarchical clustering linkage ('ward', 'single', 'complete')
        
        Returns:
            Dict[asset_ticker, weight]
        
        Example:
            >>> weights = optimizer.optimize_nco(
            ...     expected_returns=mu,
            ...     risk_measure='CVaR',
            ...     linkage='ward'
            ... )
        """
        # Use Riskfolio HCPortfolio
        # model='NCO', rm=risk_measure
        pass
    
    def optimize_hrp(
        self,
        linkage: str = 'ward',
        rm: str = 'MV'
    ) -> Dict[str, float]:
        """
        Hierarchical Risk Parity (HRP).
        
        Pure clustering-based allocation (no optimization).
        
        Args:
            linkage: Hierarchical clustering method
            rm: Risk measure for parity ('MV', 'CVaR', 'CDaR')
        
        Returns:
            Dict[asset_ticker, weight]
        """
        # Use Riskfolio HCPortfolio
        # model='HRP'
        pass
    
    def risk_decomposition(
        self,
        weights: Dict[str, float]
    ) -> pd.DataFrame:
        """
        Decompose portfolio risk by asset and factor.
        
        Returns marginal contribution of each asset to total portfolio risk.
        
        Args:
            weights: Portfolio weights Dict[ticker, weight]
        
        Returns:
            DataFrame with columns:
            - 'asset': Asset ticker
            - 'weight': Asset weight
            - 'marginal_contribution': Marginal risk contribution
            - 'pct_of_total_risk': % of total portfolio risk
        
        Example:
            >>> attribution = optimizer.risk_decomposition(weights)
            >>> attribution.sort_values('pct_of_total_risk', ascending=False)
        """
        # Convert weights Dict to Series
        # Calculate marginal contributions (portfolio variance derivative)
        # Return attribution DataFrame
        pass
    
    def _estimate_covariance(self, method: str = 'ledoit_wolf') -> pd.DataFrame:
        """
        Estimate covariance matrix with shrinkage.
        
        Methods:
        - 'ledoit_wolf': Ledoit-Wolf shrinkage (optimal)
        - 'oracle': Oracle Approximating Shrinkage
        - 'hist': Historical (no shrinkage)
        
        Returns:
            Covariance matrix DataFrame
        """
        # Use sklearn.covariance.ledoit_wolf() or Riskfolio methods
        pass


__all__ = ['RiskfolioOptimizer']

================================================================================
2. src/financial_analyzer/portfolio_optimization/black_litterman.py (200 LOC)
================================================================================

"""
Black-Litterman Model - Investor Views Integration.

Combines market equilibrium (implied returns) with investor views to generate
posterior expected returns.

Audit reference:
- AUDIT_RISKFOLIO_LIB.md pp.15-18 (Black-Litterman implementation)

Example:
    >>> from financial_analyzer.portfolio_optimization import BlackLittermanModel
    >>> 
    >>> bl = BlackLittermanModel(cov_matrix, market_caps)
    >>> 
    >>> # Add absolute view: "AAPL will return 15%"
    >>> bl.add_absolute_view('AAPL', expected_return=0.15, confidence=0.8)
    >>> 
    >>> # Add relative view: "AAPL outperforms MSFT by 5%"
    >>> bl.add_relative_view('AAPL', 'MSFT', outperformance=0.05, confidence=0.6)
    >>> 
    >>> # Get posterior returns
    >>> posterior_returns = bl.get_posterior_returns()
"""

Implement:

class BlackLittermanModel:
    """
    Black-Litterman model for expected returns estimation.
    
    Integrates:
    - Market equilibrium (implied returns from market caps)
    - Investor views (absolute or relative)
    - View confidence (tau parameter)
    
    Output: Posterior expected returns (blend of equilibrium + views)
    """
    
    def __init__(
        self,
        cov_matrix: pd.DataFrame,
        market_caps: pd.Series,
        risk_free_rate: float = 0.02,
        tau: float = 0.05
    ):
        """
        Initialize Black-Litterman model.
        
        Args:
            cov_matrix: Covariance matrix of returns
            market_caps: Market capitalization per asset
            risk_free_rate: Risk-free rate (default 2%)
            tau: View confidence parameter (default 0.05)
        """
        # Calculate market equilibrium returns (reverse optimization)
        # Initialize view matrices (P, Q, Omega)
        pass
    
    def add_absolute_view(
        self,
        asset: str,
        expected_return: float,
        confidence: float = 1.0
    ):
        """
        Add absolute view: "Asset X will return Y%".
        
        Args:
            asset: Asset ticker
            expected_return: Expected return (ex: 0.15 = 15%)
            confidence: View confidence (0-1, default 1.0 = 100%)
        """
        # Add row to P matrix (picking matrix)
        # Add expected return to Q vector
        # Add confidence to Omega matrix (view covariance)
        pass
    
    def add_relative_view(
        self,
        asset1: str,
        asset2: str,
        outperformance: float,
        confidence: float = 1.0
    ):
        """
        Add relative view: "Asset1 outperforms Asset2 by X%".
        
        Args:
            asset1: First asset ticker
            asset2: Second asset ticker
            outperformance: Expected outperformance (ex: 0.05 = 5%)
            confidence: View confidence (0-1)
        """
        # Add row to P (relative picking: [1, -1, 0, ...])
        # Add outperformance to Q
        # Add confidence to Omega
        pass
    
    def get_posterior_returns(self) -> pd.Series:
        """
        Calculate posterior expected returns.
        
        Formula:
        posterior = [(tau * Sigma)^-1 + P' * Omega^-1 * P]^-1 * 
                    [(tau * Sigma)^-1 * pi + P' * Omega^-1 * Q]
        
        Where:
        - pi: Market equilibrium returns
        - Sigma: Covariance matrix
        - P: View picking matrix
        - Q: View expected returns
        - Omega: View covariance matrix
        
        Returns:
            Series of posterior expected returns per asset
        """
        # Apply Black-Litterman formula
        # Return posterior returns Series
        pass


__all__ = ['BlackLittermanModel']

================================================================================
3. TESTS (25 TOTAL)
================================================================================

tests/test_portfolio_optimization/test_riskfolio_optimizer.py (15 tests)
- test_init_default()
- test_init_invalid_returns()
- test_optimize_mean_cvar_basic()
- test_optimize_mean_cvar_weights_sum_to_one()
- test_optimize_mean_cdar_basic()
- test_optimize_nco_basic()
- test_optimize_nco_different_linkages()
- test_optimize_hrp_basic()
- test_risk_decomposition_basic()
- test_risk_decomposition_sum_to_one()
- test_covariance_estimation_ledoit_wolf()
- test_covariance_estimation_oracle()
- test_empty_returns()
- test_single_asset()
- test_negative_weights_constraint()

tests/test_portfolio_optimization/test_black_litterman.py (10 tests)
- test_init_default()
- test_add_absolute_view()
- test_add_relative_view()
- test_multiple_views()
- test_get_posterior_returns_shape()
- test_posterior_returns_blend_equilibrium_and_views()
- test_view_confidence_impact()
- test_no_views_returns_equilibrium()
- test_invalid_asset_raises()
- test_tau_parameter_effect()

================================================================================
REQUIREMENTS
================================================================================

✅ All 2 files implement exact specifications above
✅ Type hints 100%
✅ Google/NumPy docstrings 100%
✅ 25 tests total (15 + 10)
✅ All tests passing 100%
✅ Logging at info/warning/error levels
✅ Error handling with try/except + logging
✅ Zero Pylance errors
✅ Production-ready code

CRITICAL NOTES:
- Use Riskfolio-Lib Portfolio and HCPortfolio classes
- Import: from riskfolio import Portfolio, HCPortfolio
- Covariance shrinkage: sklearn.covariance.ledoit_wolf() or Riskfolio methods
- Risk measures: 'MV', 'CVaR', 'CDaR', 'EVaR', 'RLVaR', etc.
- NCO uses HCPortfolio with model='NCO'
- Black-Litterman uses reverse optimization for equilibrium returns
- All tests mock Portfolio objects (no real optimization in tests)

Refs: AUDIT_RISKFOLIO_LIB.md, AUDIT_PYPORTFOLIOOPT.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `riskfolio_optimizer.py` (300 LOC) - Full optimization suite
2. ✅ `black_litterman.py` (200 LOC) - Investor views integration
3. ✅ 2 test files (25 tests total: 15 + 10)

**Key features:**
- 24+ risk measures (CVaR, CDaR, EVaR, RLVaR)
- 4 optimization methods (Classic, NCO, HRP, Black-Litterman)
- Covariance shrinkage (Ledoit-Wolf)
- Risk decomposition (marginal contributions)
- Black-Litterman absolute & relative views

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ riskfolio_optimizer.py (300 LOC)
✅ black_litterman.py (200 LOC)
✅ test_riskfolio_optimizer.py (15 tests)
✅ test_black_litterman.py (10 tests)

Total: 500 LOC + 25 tests
All passing: 25/25 ✅
```

---

## 🎯 MODULE 4 COMPLEXITY

**Module 4 est le plus technique** :
- Mathématiques avancées (optimisation convexe)
- Matrix operations (covariance, shrinkage)
- Black-Litterman formula (posterior estimation)

**Attendu** : 1.5-2h de génération par Copilot (vs 1h pour modules précédents)

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

This is the **most advanced module** of Phase 5.5! 💪
