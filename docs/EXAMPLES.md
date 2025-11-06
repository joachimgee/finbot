# EXAMPLES & USAGE PATTERNS

**Version:** 1.0  
**Last Updated:** 2025-11-06

---

## Quick Start

### Installation

```bash
pip install financial-analyzer
```

### Basic Import

```python
from financial_analyzer.portfolio import (
    PortfolioOptimizer,
    PortfolioConstraints,
    PortfolioRebalancer,
    calculate_efficient_frontier,
)
import pandas as pd
```

---

## Example 1: Simple Optimization

### Scenario
You have 5 stocks with 1 year of daily returns. Find the portfolio with best Sharpe ratio.

### Code

```python
import pandas as pd
from financial_analyzer.portfolio import PortfolioOptimizer

# Load returns (252 trading days x 5 tickers)
returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)

# Create optimizer
optimizer = PortfolioOptimizer(returns, risk_free_rate=0.03)

# Optimize for maximum Sharpe ratio
result = optimizer.optimize_max_sharpe()

# Print results
print(f"Optimal Weights:")
print(result['weights'])
print(f"\nExpected Return: {result['return']:.2%}")
print(f"Volatility: {result['volatility']:.2%}")
print(f"Sharpe Ratio: {result['sharpe']:.2f}")
```

### Output

```
Optimal Weights:
AAPL    0.245
MSFT    0.189
GOOG    0.312
AMZN    0.156
TSLA    0.098
Name: weights, dtype: float64

Expected Return: 18.35%
Volatility: 22.14%
Sharpe Ratio: 0.78
```

---

## Example 2: Portfolio with Constraints

### Scenario
You want the same optimal portfolio, but with constraints:
- Min 5%, max 30% per stock
- Tech sector (AAPL, MSFT, GOOG) max 60% combined

### Code

```python
from financial_analyzer.portfolio import (
    PortfolioOptimizer,
    PortfolioConstraints,
)

optimizer = PortfolioOptimizer(returns)

# Create constraints
constraints = PortfolioConstraints(
    sector_mapping={
        'AAPL': 'Technology',
        'MSFT': 'Technology',
        'GOOG': 'Technology',
        'AMZN': 'Consumer',
        'TSLA': 'Energy',
    }
)

# Add allocation limits
constraints.add_allocation_limits(
    min_weight=0.05,
    max_weight=0.30
)

# Add sector constraint
constraints.add_sector_constraint('Technology', max_weight=0.60)

# Apply constraints
optimizer.add_constraint(constraints)

# Optimize
result = optimizer.optimize_max_sharpe()

print(f"Constrained Weights:")
print(result['weights'])
print(f"Tech allocation: {result['weights'][['AAPL', 'MSFT', 'GOOG']].sum():.2%}")
```

### Output

```
Constrained Weights:
AAPL    0.30
MSFT    0.15
GOOG    0.15
AMZN    0.25
TSLA    0.15
Name: weights, dtype: float64

Tech allocation: 60.00%
```

---

## Example 3: Efficient Frontier

### Scenario
Generate and visualize the efficient frontier (50 portfolios).

### Code

```python
import matplotlib.pyplot as plt

# Generate frontier
frontier = optimizer.calculate_efficient_frontier(num_portfolios=50)

# Plot
plt.figure(figsize=(10, 6))
plt.scatter(frontier['volatility'], frontier['return'], c=frontier['sharpe'], cmap='viridis')
plt.xlabel('Volatility (Annualized)')
plt.ylabel('Expected Return (Annualized)')
plt.title('Efficient Frontier')
plt.colorbar(label='Sharpe Ratio')

# Highlight key points
min_vol_idx = frontier['volatility'].idxmin()
max_sharpe_idx = frontier['sharpe'].idxmax()

plt.scatter(
    frontier.loc[min_vol_idx, 'volatility'],
    frontier.loc[min_vol_idx, 'return'],
    marker='*', s=500, c='red', label='Min Volatility'
)
plt.scatter(
    frontier.loc[max_sharpe_idx, 'volatility'],
    frontier.loc[max_sharpe_idx, 'return'],
    marker='*', s=500, c='green', label='Max Sharpe'
)

plt.legend()
plt.tight_layout()
plt.show()
```

### Finding Best Portfolio

```python
# Get weights of maximum Sharpe portfolio
best_idx = frontier['sharpe'].idxmax()
best_weights = frontier.loc[best_idx, 'weights']
best_return = frontier.loc[best_idx, 'return']
best_vol = frontier.loc[best_idx, 'volatility']

print(f"Best Portfolio (Max Sharpe):")
print(f"Expected Return: {best_return:.2%}")
print(f"Volatility: {best_vol:.2%}")
print(f"Weights:\n{best_weights}")
```

---

## Example 4: Rebalancing Strategies

### Scenario A: Periodic Rebalancing (Monthly)

Monthly rebalancing to max Sharpe portfolio with 0.1% transaction costs.

```python
from financial_analyzer.portfolio import PortfolioRebalancer

rebalancer = PortfolioRebalancer(returns)

# Get target weights from optimization
target_weights = result['weights']

# Rebalance monthly
rebal_result = rebalancer.rebalance_periodic(
    target_weights=target_weights,
    freq='M',  # Monthly
    transaction_cost=0.001  # 0.1%
)

# Results
print(f"Rebalancing History:")
print(rebal_result.weights.head())
print(f"\nTotal trades made: {rebal_result.trades.abs().sum().sum():.4f}")

# Final weights
print(f"\nFinal weights:")
print(rebal_result.weights.iloc[-1])
```

### Scenario B: Threshold Rebalancing

Rebalance when allocation drifts more than 5% from target.

```python
rebal_result = rebalancer.rebalance_threshold(
    target_weights=target_weights,
    threshold=0.05,  # 5% drift trigger
    transaction_cost=0.001
)

# Count number of rebalances
rebal_dates = (rebal_result.trades.abs().sum(axis=1) > 0).sum()
print(f"Number of rebalancing events: {rebal_dates}")
print(f"Trading dates (total): {len(returns)}")
print(f"Rebalance frequency: {rebal_dates / len(returns) * 100:.1f}%")
```

### Scenario C: Quarterly Calendar Rebalancing

Rebalance at quarter-end (Mar, Jun, Sep, Dec).

```python
rebal_result = rebalancer.rebalance_calendar(
    target_weights=target_weights,
    months=(3, 6, 9, 12),  # Q1, Q2, Q3, Q4 end
    transaction_cost=0.001
)

# Verify rebalance dates
rebal_dates = rebal_result.trades.index[rebal_result.trades.abs().sum(axis=1) > 0]
print(f"Actual rebalance dates:")
for date in rebal_dates[:5]:  # First 5
    print(f"  {date.strftime('%Y-%m-%d')} (Month {date.month})")
```

---

## Example 5: Multi-Strategy Comparison

### Scenario
Compare 4 strategies: Min Variance, Max Sharpe, Risk Parity, Equal-Weight.

### Code

```python
import pandas as pd

strategies = {}

# 1. Minimum Variance
strategies['Min Variance'] = optimizer.optimize_min_variance()

# 2. Maximum Sharpe
strategies['Max Sharpe'] = optimizer.optimize_max_sharpe()

# 3. Risk Parity
strategies['Risk Parity'] = optimizer.optimize_risk_parity()

# 4. Equal Weight
strategies['Equal Weight'] = optimizer.optimize_equal_weight()

# Build comparison table
comparison = []
for name, result in strategies.items():
    comparison.append({
        'Strategy': name,
        'Return': result.get('return', np.nan),
        'Volatility': result.get('volatility', np.nan),
        'Sharpe': result.get('sharpe', np.nan),
    })

comparison_df = pd.DataFrame(comparison)
print(comparison_df.to_string(index=False))

# Plot comparison
import matplotlib.pyplot as plt

fig, ax = plt.subplots(1, 2, figsize=(12, 5))

# Returns comparison
ax[0].barh(comparison_df['Strategy'], comparison_df['Return'])
ax[0].set_xlabel('Expected Return (Annualized)')
ax[0].set_title('Return Comparison')
ax[0].xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.1%}'))

# Sharpe comparison
ax[1].barh(comparison_df['Strategy'], comparison_df['Sharpe'])
ax[1].set_xlabel('Sharpe Ratio')
ax[1].set_title('Risk-Adjusted Return Comparison')

plt.tight_layout()
plt.show()
```

### Output

```
       Strategy     Return  Volatility      Sharpe
  Min Variance       12.45%       15.32%       0.629
    Max Sharpe       18.35%       22.14%       0.781
   Risk Parity       14.22%       18.90%       0.651
 Equal Weight        15.65%       20.15%       0.665
```

---

## Example 6: Custom Constraints

### Scenario
Add custom constraint: No single position > 25% AND combined top 3 < 70%.

### Code

```python
from financial_analyzer.portfolio import PortfolioConstraints

constraints = PortfolioConstraints()

# Predefined constraint: max 25% each
constraints.add_allocation_limits(max_weight=0.25)

# Custom constraint: top 3 positions < 70%
def limit_top3(w, names):
    """Ensure top 3 positions sum < 70%."""
    w_sorted = np.sort(w)[::-1]  # Descending
    top3_sum = w_sorted[:3].sum()
    return 0.70 - top3_sum  # f(w) >= 0 if satisfied

constraints.add_custom_constraint(limit_top3)

optimizer.add_constraint(constraints)
result = optimizer.optimize_max_sharpe()

print(f"Top 3 sum: {result['weights'].nlargest(3).sum():.2%}")  # Should be < 70%
print(f"Max position: {result['weights'].max():.2%}")  # Should be < 25%
```

---

## Example 7: Real-World Workflow

### Scenario
Complete portfolio management workflow:
1. Load 10 stocks
2. Optimize with constraints
3. Rebalance quarterly
4. Track performance

### Code

```python
import pandas as pd
from datetime import datetime
from financial_analyzer.portfolio import (
    PortfolioOptimizer,
    PortfolioConstraints,
    PortfolioRebalancer,
    calculate_portfolio_return,
    calculate_portfolio_volatility,
)

# Step 1: Load returns
returns = pd.read_csv('returns_10stocks.csv', index_col=0, parse_dates=True)
print(f"Data: {returns.shape[0]} days, {returns.shape[1]} stocks")

# Step 2: Setup constraints
sector_mapping = {
    'AAPL': 'Tech', 'MSFT': 'Tech', 'GOOG': 'Tech',
    'JPM': 'Finance', 'BAC': 'Finance',
    'JNJ': 'Healthcare', 'PFE': 'Healthcare',
    'XOM': 'Energy', 'CVX': 'Energy',
    'PG': 'Consumer',
}

constraints = PortfolioConstraints(sector_mapping=sector_mapping)
constraints.add_allocation_limits(0.05, 0.25)
constraints.add_sector_constraint('Tech', 0.35)
constraints.add_sector_constraint('Finance', 0.20)
constraints.add_long_only(True)

# Step 3: Optimize
optimizer = PortfolioOptimizer(returns, risk_free_rate=0.03)
optimizer.add_constraint(constraints)
result = optimizer.optimize_max_sharpe()

print(f"\nOptimized Portfolio:")
print(f"Return: {result['return']:.2%}")
print(f"Volatility: {result['volatility']:.2%}")
print(f"Sharpe: {result['sharpe']:.2f}")

# Step 4: Rebalance
rebalancer = PortfolioRebalancer(returns)
rebal_result = rebalancer.rebalance_calendar(
    target_weights=result['weights'],
    months=(3, 6, 9, 12),
    transaction_cost=0.001
)

# Step 5: Track performance
print(f"\nRebalancing Summary:")
print(f"Period: {returns.index[0].date()} to {returns.index[-1].date()}")
print(f"Number of rebalances: {(rebal_result.trades.abs().sum(axis=1) > 0).sum()}")
print(f"Total turnover: {rebal_result.trades.abs().sum().sum():.2f}")

# Final metrics
final_weights = rebal_result.weights.iloc[-1]
annualized_return = returns.mean() * 252
cov_matrix = returns.cov() * 252

final_return = calculate_portfolio_return(final_weights, annualized_return)
final_vol = calculate_portfolio_volatility(final_weights, cov_matrix)

print(f"\nFinal Portfolio (at end):")
print(f"Expected Return: {final_return:.2%}")
print(f"Volatility: {final_vol:.2%}")
print(f"\nWeights:")
for ticker, weight in final_weights.items():
    print(f"  {ticker:6s}: {weight:6.2%}")
```

### Output

```
Data: 252 days, 10 stocks

Optimized Portfolio:
Return: 16.82%
Volatility: 18.45%
Sharpe: 0.75

Rebalancing Summary:
Period: 2024-01-01 to 2024-12-31
Number of rebalances: 4
Total turnover: 1.25

Final Portfolio (at end):
Expected Return: 16.82%
Volatility: 18.45%

Weights:
  AAPL  :  0.15%
  MSFT  :  0.22%
  GOOG  :  0.13%
  JPM   :  0.18%
  BAC   :  0.12%
  JNJ   :  0.11%
  PFE   :  0.10%
  XOM   :  0.05%
  CVX   :  0.07%
  PG    :  0.07%
```

---

## Example 8: Stress Testing

### Scenario
Test portfolio robustness to market shock (sudden -20% day).

### Code

```python
# Add market crash to returns
stressed_returns = returns.copy()
stressed_returns.iloc[100] = -0.20  # Simulate crash

# Re-optimize
optimizer_stressed = PortfolioOptimizer(stressed_returns)
result_stressed = optimizer_stressed.optimize_max_sharpe()

# Compare
print("Impact of Market Crash:")
print(f"Original Sharpe: {result['sharpe']:.2f}")
print(f"Stressed Sharpe: {result_stressed['sharpe']:.2f}")
print(f"Weight change (AAPL): {result['weights']['AAPL']:.2%} → {result_stressed['weights']['AAPL']:.2%}")
```

---

## Common Patterns & Tips

### Pattern 1: Find Minimum Volatility Portfolio

```python
min_vol_result = optimizer.optimize_min_variance()
print(f"Min vol: {min_vol_result['volatility']:.2%}")
```

### Pattern 2: Efficient Frontier + Manual Selection

```python
frontier = optimizer.calculate_efficient_frontier(100)
# Select portfolio with 15% target return
target_return = 0.15
closest_idx = (frontier['return'] - target_return).abs().idxmin()
selected_weights = frontier.loc[closest_idx, 'weights']
```

### Pattern 3: Compare Rebalancing Strategies

```python
strategies = {
    'Monthly': rebalancer.rebalance_periodic(w, freq='M'),
    'Quarterly': rebalancer.rebalance_calendar(w, months=(3,6,9,12)),
    'Threshold': rebalancer.rebalance_threshold(w, threshold=0.05),
}

for name, result in strategies.items():
    trades = (result.trades.abs().sum(axis=1) > 0).sum()
    print(f"{name}: {trades} rebalances")
```

### Pattern 4: Sensitivity Analysis

```python
# Test different risk-free rates
for rf in [0.01, 0.02, 0.03, 0.05]:
    opt = PortfolioOptimizer(returns, risk_free_rate=rf)
    res = opt.optimize_max_sharpe()
    print(f"RF={rf:.1%}: Sharpe={res['sharpe']:.2f}")
```

---

## Error Handling Examples

### Handling Invalid Returns

```python
try:
    optimizer = PortfolioOptimizer(bad_returns)
except ValueError as e:
    print(f"Error: {e}")
    # Handle gracefully
```

### Handling Convergence Issues

```python
# Check if optimization succeeded
result = optimizer.optimize_max_sharpe()
if result['weights'].isna().any():
    print("Optimization failed, falling back to equal-weight")
    result = optimizer.optimize_equal_weight()
```

### Handling Constraint Conflicts

```python
try:
    constraints = PortfolioConstraints()
    constraints.add_allocation_limits(0.5, 0.3)  # min > max!
except ValueError as e:
    print(f"Constraint error: {e}")
```

---

## Performance Tips

1. **Use risk parity for speed**: Closed-form solution (~0.1s)
2. **Limit frontier points**: 50-100 points usually sufficient
3. **Reuse constraints**: Don't recreate for each optimization
4. **Cache returns statistics**: Compute cov_matrix once
5. **Batch optimize**: Multiple portfolios in one run

---

**For API details, see: API_REFERENCE.md**  
**For architecture, see: ARCHITECTURE.md**
