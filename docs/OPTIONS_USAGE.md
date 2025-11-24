# Options Module - Usage Guide

## Overview

The Options module provides comprehensive options pricing and trading capabilities:
- **Black-Scholes Model**: Analytical pricing for European call/put options
- **Greeks Calculator**: First and second-order sensitivities
- **Options Strategies**: Multi-leg strategies with payoff analysis

## Quick Start

### 1. Basic Option Pricing

```python
from financial_analyzer.derivatives.options import BlackScholesModel

# Price a call option
bs = BlackScholesModel(
    S=100,      # Current stock price
    K=105,      # Strike price
    T=0.25,     # Time to expiration (3 months)
    r=0.05,     # Risk-free rate (5%)
    sigma=0.2,  # Volatility (20%)
    q=0.0       # Dividend yield (optional)
)

call_price = bs.call_price()
put_price = bs.put_price()

print(f"Call: ${call_price:.2f}")
print(f"Put: ${put_price:.2f}")

# Get full pricing details
result = bs.price()
print(f"Call intrinsic: ${result.intrinsic_call:.2f}")
print(f"Call time value: ${result.time_value_call:.2f}")

# Verify put-call parity
assert bs.verify_put_call_parity()
```

### 2. Implied Volatility

```python
# Calculate implied volatility from market price
market_call_price = 5.5
iv = bs.implied_volatility(market_call_price, option_type='call')
print(f"Implied volatility: {iv:.2%}")
```

### 3. Greeks Calculation

```python
from financial_analyzer.derivatives.options import GreeksCalculator

calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)

# Individual Greeks
delta_call = calc.delta('call')
gamma = calc.gamma()
vega = calc.vega()
theta_call = calc.theta('call')
rho_call = calc.rho('call')

print(f"Delta: {delta_call:.4f}")
print(f"Gamma: {gamma:.6f}")
print(f"Vega: ${vega:.4f} per 1% vol")
print(f"Theta: ${theta_call:.4f} per day")
print(f"Rho: ${rho_call:.4f} per 1% rate")

# All Greeks at once
greeks = calc.compute_all()
print(f"Call Delta: {greeks.delta_call:.4f}")
print(f"Put Delta: {greeks.delta_put:.4f}")
print(f"Vanna: {greeks.vanna:.6f}")
print(f"Charm: {greeks.charm:.6f}")
print(f"Vomma: {greeks.vomma:.6f}")
```

### 4. Options Strategies

#### Long Straddle (Volatility Play)

```python
from financial_analyzer.derivatives.options import OptionsStrategy

# Create straddle (buy ATM call + put)
straddle = OptionsStrategy.straddle(
    S=100, K=100, T=0.25, r=0.05, sigma=0.25
)

# Analyze payoff at expiration
payoff = straddle.payoff_at_expiry([80, 90, 100, 110, 120])
print(payoff)

# Risk metrics
max_loss = straddle.max_loss()
max_profit = straddle.max_profit()
breakevens = straddle.breakeven_points()
net_premium = straddle.net_premium()

print(f"Max loss: ${abs(max_loss):.2f}")
print(f"Max profit: {'Unlimited' if max_profit == float('inf') else f'${max_profit:.2f}'}")
print(f"Breakevens: {breakevens}")
print(f"Net premium: ${net_premium:.2f}")
```

#### Bull Call Spread

```python
# Create bull call spread (buy low strike, sell high strike)
bull_spread = OptionsStrategy.bull_call_spread(
    S=100, K_low=100, K_high=105, T=0.25, r=0.05, sigma=0.25
)

payoff = bull_spread.payoff_at_expiry([95, 100, 102.5, 105, 110])
print(f"Max profit: ${bull_spread.max_profit():.2f}")
print(f"Max loss: ${abs(bull_spread.max_loss()):.2f}")
```

#### Iron Condor (Range-Bound)

```python
# Create iron condor (short strangle + long strangle)
iron_condor = OptionsStrategy.iron_condor(
    S=100,
    K_put_low=90,    # Long put (protection)
    K_put_high=95,   # Short put
    K_call_low=105,  # Short call
    K_call_high=110, # Long call (protection)
    T=0.25, r=0.05, sigma=0.25
)

print(f"Net credit: ${abs(iron_condor.net_premium()):.2f}")
print(f"Max profit: ${iron_condor.max_profit():.2f}")
print(f"Max loss: ${abs(iron_condor.max_loss()):.2f}")
```

### 5. Manual Strategy Construction

```python
from financial_analyzer.derivatives.options import OptionLeg

# Create custom strategy manually
legs = [
    OptionLeg('call', 'long', strike=100, premium=5.0),
    OptionLeg('call', 'short', strike=110, premium=2.0, quantity=2),
    OptionLeg('call', 'long', strike=120, premium=0.5),
]

custom_strategy = OptionsStrategy(legs, name='custom_butterfly')
payoff = custom_strategy.payoff_at_expiry(range(90, 130, 5))
```

## Advanced Features

### Dividends

```python
# Price options with continuous dividend yield
bs_div = BlackScholesModel(
    S=100, K=100, T=0.25, r=0.05, sigma=0.2, q=0.03
)
call_div = bs_div.call_price()
# Call price lower with dividends
```

### Moneyness Analysis

```python
bs = BlackScholesModel(S=105, K=100, T=0.25, r=0.05, sigma=0.2)
moneyness = bs.moneyness()  # 1.05
is_itm_call = bs.is_itm('call')  # True
is_atm = bs.is_atm(tolerance=0.01)  # False
```

### Zero Time / Vol Edge Cases

```python
# At expiration (T=0)
bs_expiry = BlackScholesModel(S=110, K=100, T=0.0, r=0.05, sigma=0.2)
call = bs_expiry.call_price()  # Intrinsic value only: 10

# Zero volatility
bs_zero_vol = BlackScholesModel(S=110, K=100, T=0.25, r=0.05, sigma=0.0)
call_zero_vol = bs_zero_vol.call_price()  # Discounted intrinsic
```

## Strategy Comparison

| Strategy | Max Profit | Max Loss | Breakevens | Volatility View |
|----------|-----------|----------|------------|----------------|
| Long Straddle | Unlimited | Premium paid | 2 | High vol |
| Long Strangle | Unlimited | Premium paid | 2 | High vol |
| Butterfly | Limited | Premium paid | 2 | Low vol |
| Iron Condor | Premium received | Limited | 4 | Low vol |
| Bull Call Spread | Limited | Limited | 1 | Bullish |
| Bear Put Spread | Limited | Limited | 1 | Bearish |

## Testing & Validation

All pricing and Greeks validated against:
- **Numerical differentiation**: Delta/Gamma/Vega match finite differences
- **Put-call parity**: C - P = S*exp(-q*T) - K*exp(-r*T)
- **Implied volatility**: Recovers input vol from price
- **Edge cases**: Zero time/vol, deep ITM/OTM, dividends

## Performance Notes

- **Black-Scholes**: Analytical formulas (closed-form), no Monte Carlo
- **Greeks**: Analytical derivatives, exact values
- **Strategies**: Vectorized payoff calculations

## References

1. Black, F., & Scholes, M. (1973). *The Pricing of Options and Corporate Liabilities*. Journal of Political Economy, 81(3), 637-654.
2. Hull, J. C. (2018). *Options, Futures, and Other Derivatives* (10th ed.). Pearson.
3. Haug, E. G. (2007). *The Complete Guide to Option Pricing Formulas* (2nd ed.). McGraw-Hill.

## Next Steps

- **Backtesting**: Integrate with `OptionsBacktester` (coming soon)
- **Real data**: Connect to market data feeds for live pricing
- **Portfolio**: Combine with `PortfolioOptimizer` for multi-asset strategies

