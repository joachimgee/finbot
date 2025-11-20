# PyPortfolioOpt Integration

## Overview

PyPortfolioOpt is integrated as an **optional backend** for portfolio optimization in FinBot. It provides classical mean-variance optimization with additional features like Black-Litterman, efficient frontier calculation, and discrete allocation.

## Installation

```bash
pip install PyPortfolioOpt
```

Or install FinBot with optional portfolio dependencies:

```bash
pip install finbot[portfolio]
```

## Quick Start

### Basic Max Sharpe Optimization

```python
import pandas as pd
from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer

# Historical prices (DatetimeIndex, tickers as columns)
prices = pd.DataFrame(...)

# Create optimizer
opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)

# Maximize Sharpe ratio
weights = opt.optimize_max_sharpe()
print(weights)
# AAPL     0.30
# MSFT     0.25
# GOOGL    0.20
# AMZN     0.15
# TSLA     0.10
# dtype: float64
```

### Min Volatility

```python
# Minimize portfolio volatility
weights = opt.optimize_min_volatility()
```

### With Constraints

```python
from financial_analyzer.portfolio.constraints import PortfolioConstraints

# Setup constraints
constraints = PortfolioConstraints(
    sector_mapping={
        "AAPL": "Tech",
        "MSFT": "Tech",
        "GOOGL": "Tech",
        "AMZN": "Retail",
        "TSLA": "Auto",
    }
)
constraints.add_allocation_limits(min_weight=0.0, max_weight=0.3)
constraints.sector_limits = {"Tech": 0.5, "Retail": 0.3, "Auto": 0.2}
constraints.long_only_enabled = True

# Optimize with constraints
weights = opt.optimize_max_sharpe(constraints=constraints)
```

## Advanced Features

### Black-Litterman with Investor Views

```python
# Define absolute views (expected returns)
views = {
    "AAPL": 0.15,  # 15% expected return
    "TSLA": 0.20,  # 20% expected return
}

# Optional: view confidences (0 to 1)
confidences = {
    "AAPL": 0.8,  # High confidence
    "TSLA": 0.5,  # Medium confidence
}

# Optional: market caps for prior
market_caps = {
    "AAPL": 3e12,
    "MSFT": 2.5e12,
    "GOOGL": 1.8e12,
    "AMZN": 1.5e12,
    "TSLA": 0.8e12,
}

# Optimize with Black-Litterman
weights = opt.optimize_black_litterman(
    views=views,
    view_confidences=confidences,
    market_caps=market_caps,
    risk_aversion=1.0,
)
```

### Efficient Frontier

```python
# Calculate efficient frontier
frontier = opt.calculate_efficient_frontier(num_portfolios=100)

print(frontier.head())
#     return  volatility    sharpe                                  weights
# 0  0.0850      0.1200    0.5417  {AAPL: 0.2, MSFT: 0.3, ...}
# 1  0.0900      0.1250    0.5600  {AAPL: 0.25, MSFT: 0.28, ...}
# ...

# Plot efficient frontier
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 6))
plt.scatter(frontier['volatility'], frontier['return'], c=frontier['sharpe'], cmap='viridis')
plt.colorbar(label='Sharpe Ratio')
plt.xlabel('Volatility')
plt.ylabel('Expected Return')
plt.title('Efficient Frontier')
plt.show()
```

### Discrete Allocation

Convert continuous weights to actual share quantities:

```python
# Continuous weights from optimization
weights = opt.optimize_max_sharpe()

# Convert to discrete allocation with $100k capital
allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=100_000)

print(allocation)
# {'AAPL': 172, 'MSFT': 60, 'GOOGL': 140, 'AMZN': 85, 'TSLA': 40}

print(f"Leftover cash: ${leftover:.2f}")
# Leftover cash: $234.56
```

## API Reference

### PyPortfolioOptOptimizer

```python
class PyPortfolioOptOptimizer:
    def __init__(
        self,
        prices: pd.DataFrame,
        risk_free_rate: float = 0.02,
        frequency: int = 252,
    ):
        """
        Initialize optimizer.
        
        Parameters
        ----------
        prices : pd.DataFrame
            Historical prices with DatetimeIndex and tickers as columns.
        risk_free_rate : float, default 0.02
            Annual risk-free rate for Sharpe calculation.
        frequency : int, default 252
            Number of periods per year for annualization.
        """
```

#### Methods

##### `optimize_max_sharpe(method, cov_method, constraints)`

Maximize Sharpe ratio.

**Parameters:**
- `method` (str): Expected returns method
  - `'mean_historical_return'` (default)
  - `'ema_historical_return'`
  - `'capm_return'`
- `cov_method` (str): Covariance method
  - `'sample_cov'` (default)
  - `'semicovariance'`
  - `'exp_cov'`
  - `'ledoit_wolf'`
  - `'oracle_approximating'`
- `constraints` (PortfolioConstraints, optional): Portfolio constraints

**Returns:** `pd.Series` with optimal weights (sum=1.0)

##### `optimize_min_volatility(cov_method, constraints)`

Minimize portfolio volatility.

**Parameters:**
- `cov_method` (str): Covariance method (same as above)
- `constraints` (PortfolioConstraints, optional): Portfolio constraints

**Returns:** `pd.Series` with optimal weights

##### `optimize_black_litterman(views, view_confidences, cov_method, market_caps, risk_aversion, constraints)`

Black-Litterman optimization with investor views.

**Parameters:**
- `views` (dict): Absolute views `{ticker: expected_return}`
- `view_confidences` (dict, optional): Confidence per view `{ticker: confidence}` (0 to 1)
- `cov_method` (str): Covariance method
- `market_caps` (dict, optional): Market caps for prior `{ticker: market_cap}`
- `risk_aversion` (float, default 1.0): Risk aversion parameter
- `constraints` (PortfolioConstraints, optional): Portfolio constraints

**Returns:** `pd.Series` with posterior optimal weights

##### `calculate_efficient_frontier(num_portfolios, method, cov_method, constraints)`

Compute efficient frontier portfolios.

**Parameters:**
- `num_portfolios` (int, default 100): Number of portfolios on frontier
- `method` (str): Expected returns method
- `cov_method` (str): Covariance method
- `constraints` (PortfolioConstraints, optional): Portfolio constraints

**Returns:** `pd.DataFrame` with columns `['return', 'volatility', 'sharpe', 'weights']`

##### `discrete_allocation(weights, total_portfolio_value)`

Compute discrete share allocation from continuous weights.

**Parameters:**
- `weights` (pd.Series): Continuous portfolio weights (sum=1)
- `total_portfolio_value` (float): Total portfolio value in currency

**Returns:** 
- `allocation` (dict): `{ticker: number_of_shares}`
- `leftover` (float): Leftover cash after allocation

## Comparison with Other Backends

| Feature | PyPortfolioOpt | Riskfolio-Lib | Internal MV |
|---------|----------------|---------------|-------------|
| Max Sharpe | ✅ | ✅ | ✅ |
| Min Volatility | ✅ | ✅ | ✅ |
| Black-Litterman | ✅ | ❌ | ❌ |
| Efficient Frontier | ✅ | ✅ | ✅ |
| CVaR / Drawdown | ❌ | ✅ | ❌ |
| Discrete Allocation | ✅ | ❌ | ❌ |
| 24+ Risk Measures | ❌ | ✅ | ❌ |
| Performance | Fast | Medium | Fast |
| Stability | High | Medium | High |

**Recommendation:**
- Use **PyPortfolioOpt** for: Black-Litterman, discrete allocation, classical MV optimization
- Use **Riskfolio-Lib** for: CVaR, drawdown optimization, risk parity, advanced risk measures
- Use **Internal MV** for: Simple mean-variance, no external dependencies

## Integration with FinBot Pipeline

```python
from financial_analyzer.data import MarketDataFetcher
from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer

# 1. Fetch data
fetcher = MarketDataFetcher(provider="yfinance")
prices = fetcher.fetch_prices(tickers=["AAPL", "MSFT", "GOOGL"], period="1y")

# 2. Optimize
opt = PyPortfolioOptOptimizer(prices)
weights = opt.optimize_max_sharpe()

# 3. Discrete allocation
allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=50_000)

# 4. Backtest (optional)
from financial_analyzer.backtest import BacktestRunner
# ... backtest with allocation
```

## Error Handling

PyPortfolioOpt may fail under certain conditions:

```python
try:
    weights = opt.optimize_max_sharpe()
except ValueError as e:
    if "risk-free rate" in str(e):
        # All assets have returns < risk-free rate
        print("All returns below risk-free rate; try lower rf or min_volatility")
        weights = opt.optimize_min_volatility()
    else:
        raise
```

Common issues:
- **"at least one asset must exceed risk-free rate"**: Lower `risk_free_rate` or use `optimize_min_volatility()`
- **Infeasible constraints**: Sector limits too tight, try relaxing bounds
- **Singular covariance matrix**: Use shrinkage methods like `'ledoit_wolf'`

## Performance Tips

1. **Use Ledoit-Wolf shrinkage** for small sample sizes:
   ```python
   weights = opt.optimize_max_sharpe(cov_method='ledoit_wolf')
   ```

2. **Cache prices** for multiple optimizations:
   ```python
   opt = PyPortfolioOptOptimizer(prices)
   w1 = opt.optimize_max_sharpe()
   w2 = opt.optimize_min_volatility()
   # No need to reload prices
   ```

3. **Parallelize frontier calculation** (if needed):
   ```python
   frontier = opt.calculate_efficient_frontier(num_portfolios=50)
   # 50 portfolios is usually sufficient for visualization
   ```

## Testing

Run PyPortfolioOpt integration tests:

```bash
pytest tests/test_portfolio_optimization/test_pyportfolioopt_optimizer.py -v
```

Coverage: **39 tests**, all scenarios including edge cases, constraints, and comparisons.

## References

- [PyPortfolioOpt Documentation](https://pyportfolioopt.readthedocs.io/)
- [FORKS_INTEGRATION_PLAN.md](/workspaces/finbot/docs/FORKS_INTEGRATION_PLAN.md)
- [Portfolio Constraints API](/workspaces/finbot/src/financial_analyzer/portfolio/constraints.py)

## License

PyPortfolioOpt: MIT License

Compatible with FinBot's license structure.
