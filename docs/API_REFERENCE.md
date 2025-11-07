# API REFERENCE - FinBot Portfolio Module

**Version:** 1.0 Beta  
**Last Updated:** 2025-11-06  
**Status:** Production-Ready

---

## Table of Contents

1. [PortfolioOptimizer](#portfoliooptimizer)
2. [PortfolioConstraints](#portfolioconstraints)
3. [PortfolioRebalancer](#portfoliorebalancer)
4. [Metrics Functions](#metrics-functions)
5. [Module-Level Functions](#module-level-functions)

---

## PortfolioOptimizer

### Class Definition

```python
class PortfolioOptimizer:
    """
    Mean-Variance portfolio optimizer with constraint support.
    
    Implements multiple optimization strategies:
    - Minimum variance
    - Maximum Sharpe ratio
    - Risk parity
    - Equal-weight
    - Efficient frontier generation
    """
```

### Constructor

```python
def __init__(
    self,
    returns: pd.DataFrame,
    risk_free_rate: float = 0.02,
    rebalance_freq: str = 'M',
) -> None:
    """
    Initialize optimizer with historical returns.
    
    Args:
        returns: Daily returns DataFrame (dates x tickers)
        risk_free_rate: Annual risk-free rate (default 0.02)
        rebalance_freq: Rebalancing frequency (D/W/M/Q/Y)
    
    Raises:
        ValueError: If returns is empty or index is not datetime
    
    Example:
        >>> returns = pd.DataFrame(...)
        >>> opt = PortfolioOptimizer(returns, risk_free_rate=0.03)
    """
```

### Methods

#### optimize_min_variance()

```python
def optimize_min_variance(self) -> Dict:
    """
    Optimize for minimum portfolio volatility.
    
    Returns:
        Dict with keys:
        - weights: pd.Series (optimal weights)
        - return: float (expected annual return)
        - volatility: float (portfolio volatility)
    
    Example:
        >>> result = opt.optimize_min_variance()
        >>> print(f"Volatility: {result['volatility']:.2%}")
    """
```

#### optimize_max_sharpe()

```python
def optimize_max_sharpe(self) -> Dict:
    """
    Optimize for maximum Sharpe ratio.
    
    Returns:
        Dict with keys:
        - weights: pd.Series
        - return: float
        - volatility: float
        - sharpe: float (Sharpe ratio)
    
    Note:
        This typically provides best risk-adjusted returns
    """
```

#### optimize_risk_parity()

```python
def optimize_risk_parity(self) -> Dict:
    """
    Risk parity allocation (inverse volatility weighting).
    
    Returns:
        Dict with keys:
        - weights: pd.Series
        - volatility: float
    
    Note:
        Weights inversely proportional to individual volatilities
    """
```

#### optimize_equal_weight()

```python
def optimize_equal_weight(self) -> Dict:
    """
    Equal-weighted (1/N) allocation.
    
    Returns:
        Dict with keys:
        - weights: pd.Series (1/N for each asset)
        - return: float
        - volatility: float
    """
```

#### calculate_efficient_frontier()

```python
def calculate_efficient_frontier(self, num_portfolios: int = 100) -> pd.DataFrame:
    """
    Generate efficient frontier portfolios.
    
    Args:
        num_portfolios: Number of frontier points
    
    Returns:
        DataFrame with columns:
        - return: Expected return
        - volatility: Portfolio volatility
        - sharpe: Sharpe ratio
        - weights: Optimal weights (Series)
    
    Properties:
        - Monotonic increasing volatility
        - Sorted by return
        - Computationally intensive (~5 sec for 100)
    
    Example:
        >>> frontier = opt.calculate_efficient_frontier(50)
        >>> frontier.plot(x='volatility', y='return')
    """
```

#### add_constraint()

```python
def add_constraint(self, constraint: PortfolioConstraints) -> None:
    """
    Add constraints to optimization.
    
    Args:
        constraint: PortfolioConstraints object
    
    Note:
        Constraints are merged into existing constraints
    
    Example:
        >>> pc = PortfolioConstraints()
        >>> pc.add_allocation_limits(0.05, 0.3)
        >>> opt.add_constraint(pc)
    """
```

#### set_risk_free_rate()

```python
def set_risk_free_rate(self, rate: float) -> None:
    """
    Update risk-free rate.
    
    Args:
        rate: Annual risk-free rate (must be in [-0.1, 0.5])
    
    Raises:
        ValueError: If rate outside realistic range
    """
```

---

## PortfolioConstraints

### Class Definition

```python
class PortfolioConstraints:
    """
    Declarative constraint builder for portfolio optimization.
    
    Supports:
    - Allocation limits (min/max per asset)
    - Sector constraints
    - Concentration limits (Herfindahl index)
    - Long-only enforcement
    - Custom constraints
    """
```

### Constructor

```python
def __init__(self, sector_mapping: Optional[Dict[str, str]] = None) -> None:
    """
    Initialize empty constraints.
    
    Args:
        sector_mapping: Optional {ticker: sector} mapping
    """
```

### Methods

#### add_allocation_limits()

```python
def add_allocation_limits(
    self,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    asset_ids: Optional[List[str]] = None,
) -> None:
    """
    Add global or asset-specific allocation bounds.
    
    Args:
        min_weight: Minimum weight per asset
        max_weight: Maximum weight per asset
        asset_ids: Apply only to these assets (global if None)
    
    Raises:
        ValueError: If min_weight > max_weight
    
    Example:
        >>> pc.add_allocation_limits(0.05, 0.3)  # Global: 5-30%
        >>> pc.add_allocation_limits(0.1, 0.2, asset_ids=['AAPL'])  # AAPL: 10-20%
    """
```

#### add_asset_bound()

```python
def add_asset_bound(
    self,
    asset_id: str,
    min_weight: float,
    max_weight: float,
) -> None:
    """
    Add bounds specific to single asset.
    
    Args:
        asset_id: Ticker
        min_weight: Minimum allocation
        max_weight: Maximum allocation
    """
```

#### add_sector_constraint()

```python
def add_sector_constraint(
    self,
    sector_or_limits: Union[str, Dict[str, float]],
    max_weight_or_mapping: Union[float, Dict[str, str]],
) -> None:
    """
    Add sector-level constraints.
    
    Two signatures:
    1. Single sector: add_sector_constraint("Tech", 0.3)
    2. Multiple: add_sector_constraint({"Tech": 0.3, "Finance": 0.25}, mapping_dict)
    
    Example:
        >>> pc.add_sector_constraint("Technology", max_weight=0.3)
        >>> pc.add_sector_constraint(
        ...     {"Tech": 0.3, "Finance": 0.25},
        ...     {"AAPL": "Tech", "JPM": "Finance"}
        ... )
    """
```

#### add_concentration_limit()

```python
def add_concentration_limit(self, max_herfindahl: float = 0.2) -> None:
    """
    Add Herfindahl index limit (sum of squared weights).
    
    Args:
        max_herfindahl: Max value (1/N at equal weight)
    
    Note:
        HHI = 1 for single asset, 1/N for equal weight
    
    Example:
        >>> pc.add_concentration_limit(0.15)  # Diversified portfolio
    """
```

#### add_long_only()

```python
def add_long_only(self, enabled: bool = True) -> None:
    """
    Enable/disable long-only constraint.
    
    Args:
        enabled: True for no shorting
    """
```

#### add_custom_constraint()

```python
def add_custom_constraint(self, constraint_func: Callable) -> None:
    """
    Add custom constraint function.
    
    Args:
        constraint_func: Callable(weights: np.ndarray, names: List[str]) -> float
                        Returns value >= 0 if satisfied
    
    Example:
        >>> def max_single(w, names):
        ...     return 0.4 - np.max(w)  # Max 40% in any single
        >>> pc.add_custom_constraint(max_single)
    """
```

#### build_bounds()

```python
def build_bounds(self, tickers: List[str]) -> List[Tuple[float, float]]:
    """
    Build scipy.optimize compatible bounds.
    
    Args:
        tickers: List of asset names
    
    Returns:
        List of (min, max) tuples for each ticker
    """
```

#### sector_constraints_functions()

```python
def sector_constraints_functions(self, tickers: List[str]) -> List[Callable]:
    """
    Get list of sector constraint functions.
    
    Returns:
        List of callables f(w) >= 0 if satisfied
    """
```

#### concentration_constraint_function()

```python
def concentration_constraint_function(self) -> Optional[Callable[[np.ndarray], float]]:
    """
    Get HHI constraint function.
    
    Returns:
        Callable or None if no limit set
    """
```

---

## PortfolioRebalancer

### Class Definition

```python
class PortfolioRebalancer:
    """
    Portfolio rebalancing engine supporting multiple strategies:
    - Periodic (calendar-based)
    - Threshold (drift-based)
    - Calendar (specific months)
    """
```

### Constructor

```python
def __init__(self, returns: pd.DataFrame) -> None:
    """
    Initialize rebalancer with returns history.
    
    Args:
        returns: Daily returns DataFrame
    
    Raises:
        ValueError: If returns empty or invalid
    """
```

### Methods

#### rebalance_periodic()

```python
def rebalance_periodic(
    self,
    target_weights: pd.Series,
    freq: str = 'M',
    transaction_cost: float = 0.0,
) -> RebalanceResult:
    """
    Rebalance at regular calendar intervals.
    
    Args:
        target_weights: Target allocation (sum to 1)
        freq: Pandas frequency (D/W/M/Q/Y)
        transaction_cost: Cost as % of traded amount
    
    Returns:
        RebalanceResult with:
        - weights: DataFrame of weights over time
        - trades: DataFrame of rebalancing trades
    
    Example:
        >>> weights = pd.Series({'AAPL': 0.4, 'MSFT': 0.3, 'GOOG': 0.3})
        >>> res = rebalancer.rebalance_periodic(weights, freq='M', transaction_cost=0.001)
        >>> print(res.weights.head())
    """
```

#### rebalance_threshold()

```python
def rebalance_threshold(
    self,
    target_weights: pd.Series,
    threshold: float = 0.05,
    transaction_cost: float = 0.0,
) -> RebalanceResult:
    """
    Rebalance when weight drifts beyond threshold.
    
    Args:
        target_weights: Target allocation
        threshold: Max drift (e.g., 0.05 = 5%)
        transaction_cost: Cost as % of traded amount
    
    Returns:
        RebalanceResult
    
    Example:
        >>> res = rebalancer.rebalance_threshold(weights, threshold=0.02)
        >>> print(f"Rebalanced {(res.trades.abs().sum() > 0).sum()} times")
    """
```

#### rebalance_calendar()

```python
def rebalance_calendar(
    self,
    target_weights: pd.Series,
    months: Tuple[int, ...] = (3, 6, 9, 12),
    transaction_cost: float = 0.0,
) -> RebalanceResult:
    """
    Rebalance on specific calendar months (quarterly/annual).
    
    Args:
        target_weights: Target allocation
        months: Months to rebalance (1-12)
        transaction_cost: Cost as % of traded amount
    
    Returns:
        RebalanceResult
    
    Example:
        >>> res = rebalancer.rebalance_calendar(weights, months=(3, 6, 9, 12))
        >>> res.trades.iloc[[d.month in (3,6,9,12) for d in res.trades.index]]
    """
```

---

## Metrics Functions

### Portfolio Return

```python
def calculate_portfolio_return(
    weights: pd.Series,
    mean_returns: pd.Series,
) -> float:
    """
    Calculate portfolio expected return.
    
    Args:
        weights: Asset weights (sum to 1)
        mean_returns: Expected returns (annualized)
    
    Returns:
        Portfolio expected return
    
    Formula:
        return = w^T * mu
    """
```

### Portfolio Volatility

```python
def calculate_portfolio_volatility(
    weights: pd.Series,
    cov_matrix: pd.DataFrame,
) -> float:
    """
    Calculate portfolio volatility (standard deviation).
    
    Args:
        weights: Asset weights
        cov_matrix: Covariance matrix
    
    Returns:
        Portfolio volatility
    
    Formula:
        volatility = sqrt(w^T * Σ * w)
    """
```

### Sharpe Ratio

```python
def calculate_portfolio_sharpe(
    weights: pd.Series,
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        weights: Asset weights
        mean_returns: Expected returns
        cov_matrix: Covariance matrix
        risk_free_rate: Annual rate
        periods_per_year: 252 for daily
    
    Returns:
        Sharpe ratio
    
    Formula:
        Sharpe = (return - rf) / volatility
    """
```

### Value at Risk (VaR)

```python
def calculate_var(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """
    Historical VaR at confidence level.
    
    Args:
        returns: Daily returns
        confidence: Confidence level (0.95 = 95%)
    
    Returns:
        VaR (positive, representing potential loss)
    
    Example:
        >>> var_95 = calculate_var(returns, confidence=0.95)
        >>> print(f"Max expected loss 95% of time: {var_95:.2%}")
    """
```

### Conditional VaR (CVaR)

```python
def calculate_cvar(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """
    Expected Shortfall / CVaR (average loss in tail).
    
    Args:
        returns: Daily returns
        confidence: Confidence level
    
    Returns:
        CVaR (greater than or equal to VaR)
    """
```

### Diversification Ratio

```python
def calculate_diversification_ratio(
    weights: pd.Series,
    vols: pd.Series,
    portfolio_vol: float,
) -> float:
    """
    Diversification benefit indicator.
    
    Args:
        weights: Asset weights
        vols: Individual volatilities
        portfolio_vol: Portfolio volatility
    
    Returns:
        DR >= 1 (higher = better diversification)
    
    Formula:
        DR = sum(w_i * σ_i) / σ_p
    """
```

### Herfindahl Index

```python
def calculate_herfindahl_index(weights: pd.Series) -> float:
    """
    Concentration measure.
    
    Args:
        weights: Asset weights
    
    Returns:
        HHI = sum(w_i^2)
        Range: [1/N, 1]
    """
```

---

## Module-Level Functions

### calculate_efficient_frontier()

```python
def calculate_efficient_frontier(
    returns: pd.DataFrame,
    risk_free_rate: float = 0.02,
    num_portfolios: int = 100,
    constraints: Optional[PortfolioConstraints] = None,
) -> pd.DataFrame:
    """Convenience function for efficient frontier calculation."""
```

### calculate_min_variance()

```python
def calculate_min_variance(
    returns: pd.DataFrame,
    constraints: Optional[PortfolioConstraints] = None,
) -> Dict:
    """Convenience function for minimum variance portfolio."""
```

### calculate_max_sharpe()

```python
def calculate_max_sharpe(
    returns: pd.DataFrame,
    risk_free_rate: float = 0.02,
    constraints: Optional[PortfolioConstraints] = None,
) -> Dict:
    """Convenience function for maximum Sharpe portfolio."""
```

### calculate_risk_parity()

```python
def calculate_risk_parity(returns: pd.DataFrame) -> Dict:
    """Convenience function for risk parity allocation."""
```

### calculate_equal_weight()

```python
def calculate_equal_weight(returns: pd.DataFrame) -> Dict:
    """Convenience function for 1/N allocation."""
```

### rebalance_periodic()

```python
def rebalance_periodic(
    returns: pd.DataFrame,
    target_weights: pd.Series,
    freq: str = 'M',
    transaction_cost: float = 0.0,
) -> RebalanceResult:
    """Convenience function for periodic rebalancing."""
```

### rebalance_threshold()

```python
def rebalance_threshold(
    returns: pd.DataFrame,
    target_weights: pd.Series,
    threshold: float = 0.05,
    transaction_cost: float = 0.0,
) -> RebalanceResult:
    """Convenience function for threshold rebalancing."""
```

### rebalance_calendar()

```python
def rebalance_calendar(
    returns: pd.DataFrame,
    target_weights: pd.Series,
    months: Tuple[int, ...] = (3, 6, 9, 12),
    transaction_cost: float = 0.0,
) -> RebalanceResult:
    """Convenience function for calendar rebalancing."""
```

---

## Data Types

### RebalanceResult

```python
@dataclass
class RebalanceResult:
    weights: pd.DataFrame  # Shape: (dates, tickers)
    trades: pd.DataFrame   # Shape: (dates, tickers), weight changes
```

### OptimizationResult

```python
@dataclass
class OptimizationResult:
    weights: pd.Series
    expected_return: Optional[float] = None
    volatility: Optional[float] = None
    sharpe: Optional[float] = None
```

---

## Common Usage Patterns

### Basic Optimization

```python
from financial_analyzer.portfolio import PortfolioOptimizer

# Load returns
returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)

# Optimize
optimizer = PortfolioOptimizer(returns, risk_free_rate=0.03)
result = optimizer.optimize_max_sharpe()

print(f"Weights: {result['weights']}")
print(f"Expected Return: {result['return']:.2%}")
print(f"Volatility: {result['volatility']:.2%}")
print(f"Sharpe Ratio: {result['sharpe']:.2f}")
```

### With Constraints

```python
from financial_analyzer.portfolio import (
    PortfolioOptimizer,
    PortfolioConstraints,
)

optimizer = PortfolioOptimizer(returns)
constraints = PortfolioConstraints()
constraints.add_allocation_limits(min_weight=0.05, max_weight=0.3)
constraints.add_sector_constraint("Technology", max_weight=0.3)
optimizer.add_constraint(constraints)

result = optimizer.optimize_max_sharpe()
```

### Rebalancing

```python
from financial_analyzer.portfolio import PortfolioRebalancer

rebalancer = PortfolioRebalancer(returns)
result = rebalancer.rebalance_periodic(
    target_weights=result['weights'],
    freq='Q',  # Quarterly
    transaction_cost=0.001  # 0.1%
)

print(f"Final weights: {result.weights.iloc[-1]}")
print(f"Total trades: {result.trades.abs().sum().sum()}")
```

### Efficient Frontier

```python
frontier = optimizer.calculate_efficient_frontier(num_portfolios=50)

# Plot
frontier.plot(x='volatility', y='return', kind='scatter')

# Find best point
best_idx = frontier['sharpe'].idxmax()
best_weights = frontier.loc[best_idx, 'weights']
```

---

## Error Handling

### Common Exceptions

| Exception | Cause | Solution |
|-----------|-------|----------|
| `ValueError` | Empty returns | Provide non-empty DataFrame |
| `ValueError` | min_weight > max_weight | Fix constraint bounds |
| `ValueError` | Weights don't sum to 1 | Normalize weights |
| `ValueError` | Conflicting constraints | Loosen constraints |
| `RuntimeWarning` | Optimization didn't converge | Try different initial weights |

---

## Version History

**v1.0** (2025-11-06)
- Initial release
- 5 core modules
- 65+ tests
- Full documentation

---

**For more examples, see: EXAMPLES.md**
