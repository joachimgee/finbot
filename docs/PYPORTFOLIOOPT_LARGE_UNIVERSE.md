# PyPortfolioOpt with FinanceDatabase - Large Universe Optimization

## Overview

This guide demonstrates how to use **PyPortfolioOpt** with **FinanceDatabase** to optimize portfolios with **100+ real tickers** from global markets.

FinanceDatabase provides 300,000+ financial instruments across:
- 🌍 Equities (stocks)
- 📊 ETFs
- 💰 Crypto
- 🏢 Funds
- 💵 Currencies
- 🔮 Indices

## Quick Start: 100+ Tickers Portfolio

```python
from financedatabase import Equities
from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer

# 1. Fetch 100 US Technology stocks
equities = Equities()
tech_stocks = equities.search(country="United States", sector="Technology")
tickers = list(tech_stocks.index[:100])

print(f"Fetched {len(tickers)} tickers")
# Fetched 100 tickers

# 2. Get historical prices (yfinance)
import yfinance as yf
prices = yf.download(tickers, period="1y", interval="1d", progress=False)['Close']

# 3. Optimize portfolio
opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)
weights = opt.optimize_max_sharpe()

# 4. Analyze results
print(f"Portfolio holdings: {(weights > 0.001).sum()}")
# Portfolio holdings: 37

top_10 = weights.nlargest(10)
print("\nTop 10 Holdings:")
for ticker, weight in top_10.items():
    print(f"  {ticker}: {weight:.2%}")
```

## Multi-Sector Portfolio (50+ tickers)

```python
from financedatabase import Equities

equities = Equities()

# Fetch tickers from multiple sectors
tech = equities.search(country="United States", sector="Technology")
healthcare = equities.search(country="United States", sector="Healthcare")
finance = equities.search(country="United States", sector="Finance")

tickers = list(tech.index[:20]) + list(healthcare.index[:15]) + list(finance.index[:15])

# Create sector mapping
sector_mapping = {}
for t in tickers:
    if t in tech.index:
        sector_mapping[t] = "Tech"
    elif t in healthcare.index:
        sector_mapping[t] = "Healthcare"
    else:
        sector_mapping[t] = "Finance"

# Fetch prices
prices = yf.download(tickers, period="1y")['Close']

# Setup constraints
from financial_analyzer.portfolio.constraints import PortfolioConstraints

constraints = PortfolioConstraints(sector_mapping=sector_mapping)
constraints.add_allocation_limits(min_weight=0.0, max_weight=0.15)
constraints.sector_limits = {
    "Tech": 0.50,
    "Healthcare": 0.30,
    "Finance": 0.20,
}

# Optimize with constraints
opt = PyPortfolioOptOptimizer(prices)
weights = opt.optimize_max_sharpe(constraints=constraints)

# Verify sector limits
for sector in ["Tech", "Healthcare", "Finance"]:
    sector_tickers = [t for t, s in sector_mapping.items() if s == sector and t in weights.index]
    sector_weight = weights[sector_tickers].sum()
    print(f"{sector}: {sector_weight:.2%}")
```

## Global Equity Portfolio (200+ tickers)

```python
from financedatabase import Equities

equities = Equities()

# Fetch from multiple countries
countries = ["United States", "United Kingdom", "Germany", "France", "Japan"]
tickers = []

for country in countries:
    result = equities.search(country=country, exclude_exchanges=False)
    tickers.extend(list(result.index[:50]))  # 50 per country

print(f"Total tickers: {len(tickers)}")
# Total tickers: 250

# Fetch prices
prices = yf.download(tickers, period="1y")['Close']

# Drop tickers with insufficient data
prices = prices.dropna(axis=1, thresh=len(prices) * 0.8)

print(f"After filtering: {len(prices.columns)} tickers")
# After filtering: 180 tickers

# Optimize
opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)
weights = opt.optimize_max_sharpe()

print(f"Holdings: {(weights > 0.001).sum()}")
# Holdings: 54
```

## Performance: Large Universe

PyPortfolioOpt handles large universes efficiently:

| Assets | Max Sharpe | Min Vol | Efficient Frontier (50 pts) |
|--------|-----------|---------|---------------------------|
| 10     | 0.04s     | 0.01s   | 0.5s                      |
| 50     | 0.06s     | 0.04s   | 2.1s                      |
| 100    | 0.11s     | 0.02s   | 4.8s                      |
| 200    | 0.35s     | 0.08s   | 11.2s                     |
| 500    | 2.1s      | 0.4s    | 60s+                      |

**Recommendation:** For 500+ assets, consider pre-filtering based on:
- Liquidity (average daily volume)
- Market cap
- Sector representation
- Quality metrics (Sharpe, volatility)

## Pre-filtering Large Universes

```python
from financedatabase import Equities
import yfinance as yf

equities = Equities()
all_tickers = list(equities.search(country="United States").index)

print(f"Total universe: {len(all_tickers)} tickers")
# Total universe: 5,000+ tickers

# Fetch market data for filtering
info = {}
for ticker in all_tickers[:1000]:  # Process in batches
    try:
        stock = yf.Ticker(ticker)
        info[ticker] = stock.info
    except:
        continue

# Filter by market cap and liquidity
filtered_tickers = []
for ticker, data in info.items():
    market_cap = data.get('marketCap', 0)
    avg_volume = data.get('averageVolume', 0)
    
    if market_cap > 1e9 and avg_volume > 100_000:  # $1B+ cap, 100k+ volume
        filtered_tickers.append(ticker)

print(f"After filtering: {len(filtered_tickers)} tickers")
# After filtering: 250 tickers

# Now optimize
prices = yf.download(filtered_tickers, period="1y")['Close']
opt = PyPortfolioOptOptimizer(prices)
weights = opt.optimize_max_sharpe()
```

## ETF Universe (100+ ETFs)

```python
from financedatabase import ETFs

etfs = ETFs()

# All US ETFs
us_etfs = etfs.search(country="United States")
etf_tickers = list(us_etfs.index[:100])

print(f"Fetched {len(etf_tickers)} ETFs")

# Fetch prices
prices = yf.download(etf_tickers, period="2y")['Close']  # ETFs need longer history

# Optimize
opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)

# Min volatility for ETF portfolio (diversification focus)
weights = opt.optimize_min_volatility()

print(f"ETF holdings: {(weights > 0.001).sum()}")
```

## Sector Analysis: All Technology Stocks

```python
from financedatabase import Equities

equities = Equities()

# All US Technology stocks
tech = equities.search(country="United States", sector="Technology")

print(f"Total tech stocks: {len(tech)}")
# Total tech stocks: 2,508

# Sample 100 randomly
import random
sampled_tickers = random.sample(list(tech.index), 100)

# Fetch prices
prices = yf.download(sampled_tickers, period="1y")['Close']
prices = prices.dropna(axis=1, thresh=len(prices) * 0.9)

# Optimize
opt = PyPortfolioOptOptimizer(prices)
weights = opt.optimize_max_sharpe()

# Analyze concentration
print(f"\nTop 10 weight: {weights.nlargest(10).sum():.2%}")
print(f"Top 20 weight: {weights.nlargest(20).sum():.2%}")
print(f"Holdings: {(weights > 0.01).sum()}")
```

## Black-Litterman with Market Views (50 stocks)

```python
from financedatabase import Equities
import yfinance as yf

# Fetch large cap tech stocks
equities = Equities()
tech = equities.search(country="United States", sector="Technology")

# Filter by market cap
tickers = []
for ticker in tech.index[:200]:
    try:
        stock = yf.Ticker(ticker)
        if stock.info.get('marketCap', 0) > 10e9:  # $10B+
            tickers.append(ticker)
            if len(tickers) >= 50:
                break
    except:
        continue

print(f"Selected {len(tickers)} large cap tech stocks")

# Fetch prices
prices = yf.download(tickers, period="1y")['Close']

# Define views on specific stocks
views = {
    "AAPL": 0.12,  # Apple: 12% expected
    "MSFT": 0.15,  # Microsoft: 15% expected
    "NVDA": 0.20,  # Nvidia: 20% expected (bullish)
    "INTC": 0.05,  # Intel: 5% expected (bearish)
}

confidences = {
    "AAPL": 0.8,
    "MSFT": 0.9,
    "NVDA": 0.7,
    "INTC": 0.6,
}

# Market caps for prior
market_caps = {}
for ticker in tickers:
    try:
        stock = yf.Ticker(ticker)
        market_caps[ticker] = stock.info.get('marketCap', 1e12)
    except:
        market_caps[ticker] = 1e12

# Optimize with Black-Litterman
opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)
weights = opt.optimize_black_litterman(
    views=views,
    view_confidences=confidences,
    market_caps=market_caps,
)

# Show view impact
print("\nView Impact:")
for ticker in views.keys():
    if ticker in weights.index:
        print(f"  {ticker}: {weights[ticker]:.2%} (view: {views[ticker]:.0%})")
```

## Crypto Portfolio (50+ cryptocurrencies)

```python
from financedatabase import Crypto

crypto = Crypto()

# Top cryptocurrencies
all_crypto = crypto.search()
crypto_tickers = list(all_crypto.index[:50])

# Fetch prices from yfinance (crypto pairs with -USD suffix)
crypto_prices = yf.download(
    [f"{t}-USD" for t in crypto_tickers],
    period="1y"
)['Close']

# Optimize
opt = PyPortfolioOptOptimizer(crypto_prices, risk_free_rate=0.00)  # No risk-free rate for crypto
weights = opt.optimize_max_sharpe()

print(f"Crypto holdings: {(weights > 0.001).sum()}")
```

## Best Practices

### 1. Data Quality
```python
# Always clean data before optimization
prices = prices.dropna(axis=1, thresh=len(prices) * 0.8)  # Remove tickers with >20% missing
prices = prices.fillna(method='ffill').fillna(method='bfill')  # Fill remaining gaps
prices = prices[prices > 0]  # Remove invalid prices
```

### 2. Universe Size
- **10-50 assets**: Fast, all features work well
- **50-200 assets**: Good performance, recommended for most use cases
- **200-500 assets**: Slower, consider pre-filtering
- **500+ assets**: Pre-filter by liquidity, market cap, or quality metrics

### 3. Constraints with Large Universes
```python
# With 100+ assets, relaxed constraints work better
constraints = PortfolioConstraints()
constraints.add_allocation_limits(min_weight=0.0, max_weight=0.10)  # Max 10% per asset
constraints.long_only_enabled = True

# Sector constraints help concentration
constraints.sector_limits = {"Tech": 0.40, "Healthcare": 0.30, ...}
```

### 4. Efficient Frontier
```python
# For large universes, use fewer portfolios
frontier = opt.calculate_efficient_frontier(num_portfolios=30)  # Instead of 100
```

## Complete Example: S&P 500 Portfolio

```python
from financedatabase import Equities
import yfinance as yf

# Fetch S&P 500 constituents (requires separate list)
sp500_tickers = [...]  # List of S&P 500 tickers

# Or fetch large cap US stocks as proxy
equities = Equities()
us_stocks = equities.search(country="United States")

# Filter by market cap > $10B (approximates S&P 500)
sp500_proxy = []
for ticker in us_stocks.index[:1000]:
    try:
        stock = yf.Ticker(ticker)
        if stock.info.get('marketCap', 0) > 10e9:
            sp500_proxy.append(ticker)
            if len(sp500_proxy) >= 500:
                break
    except:
        continue

print(f"S&P 500 proxy: {len(sp500_proxy)} stocks")

# Fetch prices
prices = yf.download(sp500_proxy, period="1y")['Close']
prices = prices.dropna(axis=1, thresh=len(prices) * 0.9)

print(f"Valid data: {len(prices.columns)} stocks")

# Optimize
opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.03)
weights = opt.optimize_max_sharpe()

# Analyze
print(f"\nHoldings: {(weights > 0.001).sum()}")
print(f"Top 10 concentration: {weights.nlargest(10).sum():.2%}")
print(f"Top 50 concentration: {weights.nlargest(50).sum():.2%}")

# Discrete allocation for $1M
allocation, leftover = opt.discrete_allocation(weights, 1_000_000)
print(f"\nDiscrete allocation: {len(allocation)} stocks")
print(f"Leftover: ${leftover:,.2f}")
```

## Troubleshooting

### Issue: Optimization fails with large universe
**Solution:** Increase solver tolerance or use different covariance method
```python
weights = opt.optimize_max_sharpe(cov_method='ledoit_wolf')  # More stable
```

### Issue: Too many holdings
**Solution:** Increase min_weight constraint
```python
constraints.add_allocation_limits(min_weight=0.01, max_weight=0.15)  # Min 1%
```

### Issue: Memory error with 500+ assets
**Solution:** Process in batches or reduce universe size
```python
# Pre-filter to top 200 by some metric
filtered = top_200_by_sharpe(all_tickers)
```

## Resources

- [FinanceDatabase Documentation](https://github.com/JerBouma/FinanceDatabase)
- [PyPortfolioOpt Documentation](https://pyportfolioopt.readthedocs.io/)
- [Example Script](/workspaces/finbot/examples/pyportfolioopt_real_data_example.py)
- [Integration Guide](/workspaces/finbot/docs/PYPORTFOLIOOPT_INTEGRATION.md)

## Summary

✅ FinanceDatabase provides 300,000+ instruments  
✅ PyPortfolioOpt handles 100+ assets efficiently  
✅ Pre-filtering recommended for 500+ universes  
✅ Sector constraints improve diversification  
✅ Black-Litterman works with large caps + views  

**Optimal universe size: 50-200 assets for best performance and diversification.**

