# ML Module - Alpha Factor Engineering Examples

## Quick Start

### 1. Basic Factor Computation

```python
import pandas as pd
from financial_analyzer.ml import AlphaFactorEngine

# Load OHLCV data
ohlcv = pd.read_csv("AAPL_ohlcv.csv", index_col=0, parse_dates=True)

# Initialize engine
afe = AlphaFactorEngine(ohlcv)

# Compute all factors (26+)
factors_dict = afe.compute_all_factors()

# Get as DataFrame
factors_df = afe.get_factors_dataframe()
print(f"Computed {factors_df.shape[1]} factors for {factors_df.shape[0]} bars")
print(factors_df.head())
```

**Output:**
```
Computed 26 factors for 252 bars
            ROC_5    ROC_10   ROC_12   ...    OBV      VWAP
2023-01-01  0.0245   0.0456   0.0532   ...  12345.2  -0.0023
2023-01-02 -0.0123   0.0345   0.0421   ...  12567.8   0.0015
...
```

---

## 2. Factor Analysis & Ranking

```python
from financial_analyzer.ml import FactorAnalyzer

# Compute forward returns (next-day)
forward_returns = ohlcv['close'].pct_change().shift(-1)

# Initialize analyzer
fa = FactorAnalyzer(factors_df, forward_returns)

# Compute Information Coefficient (Spearman)
ic_spearman = fa.information_coefficient(method='spearman')
print(ic_spearman.sort_values(ascending=False).head(10))

# Rank top 10 factors
top10 = fa.rank_factors(top_n=10)
print(top10)
```

**Output:**
```
        Factor        IC
0     ROC_20     0.1245
1     MACD_line  0.1123
2     RSI_14     0.0987
3     ADX_14     0.0876
...
```

---

## 3. Single Factor Computation

```python
# Compute individual factors
roc_12 = afe.roc(period=12)
print(f"Factor: {roc_12.name}")
print(f"Category: {roc_12.category}")
print(f"Valid data: {roc_12.valid_data}/{len(roc_12.values)}")

# MACD (returns dict with 3 components)
macd = afe.macd(fast=12, slow=26, signal=9)
print(macd.keys())  # ['MACD', 'Signal', 'Histogram']

# Bollinger Bands (returns dict with 4 components)
bb = afe.bollinger_bands(period=20, num_std=2.0)
print(bb.keys())  # ['Upper', 'Lower', 'BandWidth', 'PctB']

# Stochastic Oscillator (returns dict with 2 components)
stoch = afe.stochastic(period=14, smooth=3)
print(stoch.keys())  # ['K', 'D']
```

---

## 4. Feature Importance (Permutation)

```python
import numpy as np
from sklearn.linear_model import Ridge
from financial_analyzer.ml import FeatureImportance

# Prepare data
X = factors_df.dropna().values
y = forward_returns.dropna().values

# Align X and y (drop first row of X for forward returns alignment)
X = X[:-1]
y = y[1:]

# Train model
model = Ridge(alpha=1.0)
model.fit(X, y)

# Compute permutation importance
fi = FeatureImportance(model, X, y, random_state=42)
importances = fi.permutation_importance(n_repeats=20)

# Sort by importance
sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)
print("Top 10 Important Features:")
for name, score in sorted_imp[:10]:
    print(f"{name}: {score:.4f}")
```

**Output:**
```
Top 10 Important Features:
Feature_3: 0.0245  # ROC_20
Feature_7: 0.0189  # MACD_line
Feature_14: 0.0156 # RSI_14
...
```

---

## 5. Multi-Asset Factor Analysis

```python
# Load data for multiple assets
assets = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
all_factors = {}

for ticker in assets:
    ohlcv = pd.read_csv(f"{ticker}_ohlcv.csv", index_col=0, parse_dates=True)
    afe = AlphaFactorEngine(ohlcv)
    factors = afe.get_factors_dataframe()
    all_factors[ticker] = factors

# Compute cross-sectional IC for each factor
cross_sectional_ic = {}
for factor_name in factors.columns:
    factor_values = pd.DataFrame({
        ticker: all_factors[ticker][factor_name]
        for ticker in assets
    })
    
    forward_rets = pd.DataFrame({
        ticker: pd.read_csv(f"{ticker}_ohlcv.csv", index_col=0, parse_dates=True)['close']
                .pct_change().shift(-1)
        for ticker in assets
    })
    
    # Compute IC for each date
    daily_ic = []
    for date in factor_values.index:
        corr = factor_values.loc[date].corr(forward_rets.loc[date], method='spearman')
        if not np.isnan(corr):
            daily_ic.append(corr)
    
    cross_sectional_ic[factor_name] = np.mean(daily_ic) if daily_ic else np.nan

# Rank factors by cross-sectional IC
ranked = pd.Series(cross_sectional_ic).sort_values(ascending=False)
print("Top 10 Cross-Sectional Factors:")
print(ranked.head(10))
```

---

## 6. Factor Stability Analysis

```python
# Compute rolling IC (30-day window)
window = 30
rolling_ic = {}

for factor_name in factors_df.columns:
    ic_series = []
    for i in range(window, len(factors_df)):
        factor_window = factors_df[factor_name].iloc[i-window:i]
        return_window = forward_returns.iloc[i-window:i]
        
        # Compute IC for this window
        valid_mask = factor_window.notna() & return_window.notna()
        if valid_mask.sum() >= 10:
            corr = factor_window[valid_mask].corr(return_window[valid_mask], method='spearman')
            ic_series.append(corr)
        else:
            ic_series.append(np.nan)
    
    rolling_ic[factor_name] = ic_series

# Convert to DataFrame
rolling_ic_df = pd.DataFrame(rolling_ic, index=factors_df.index[window:])

# Compute IC stability (std of rolling IC)
ic_stability = rolling_ic_df.std()
print("Most Stable Factors (lowest std):")
print(ic_stability.sort_values().head(10))
```

---

## 7. Factor Combination Strategy

```python
# Select top factors based on IC
top_factors = fa.rank_factors(top_n=5)['Factor'].tolist()

# Create combined signal (weighted by IC)
combined_signal = pd.Series(0.0, index=factors_df.index)
for factor in top_factors:
    ic_weight = fa.information_coefficient().loc[factor]
    combined_signal += factors_df[factor] * ic_weight

# Normalize signal
combined_signal = (combined_signal - combined_signal.mean()) / combined_signal.std()

# Generate trading signals
long_threshold = 1.0
short_threshold = -1.0

positions = pd.Series(0, index=combined_signal.index)
positions[combined_signal > long_threshold] = 1
positions[combined_signal < short_threshold] = -1

print(f"Long positions: {(positions == 1).sum()}")
print(f"Short positions: {(positions == -1).sum()}")
print(f"Neutral: {(positions == 0).sum()}")
```

---

## 8. Advanced: Custom Factor Implementation

```python
class CustomAlphaFactorEngine(AlphaFactorEngine):
    """Extend AlphaFactorEngine with custom factors."""
    
    def momentum_reversal(self, short_period: int = 5, long_period: int = 20) -> FactorResult:
        """Custom momentum reversal factor."""
        close = self.ohlcv[self._colmap["close"]]
        short_mom = close.pct_change(periods=short_period)
        long_mom = close.pct_change(periods=long_period)
        reversal = short_mom - long_mom
        
        return FactorResult(
            name=f"MomReversal_{short_period}_{long_period}",
            values=reversal,
            description=f"Momentum reversal ({short_period} vs {long_period})",
            category="Momentum",
            valid_data=int(reversal.notna().sum()),
        )
    
    def volume_price_trend(self, period: int = 14) -> FactorResult:
        """Custom volume-price trend factor."""
        close = self.ohlcv[self._colmap["close"]]
        volume = self.ohlcv[self._colmap["volume"]]
        
        price_change = close.pct_change()
        vpt = (price_change * volume).rolling(window=period, min_periods=period).sum()
        
        return FactorResult(
            name=f"VPT_{period}",
            values=vpt,
            description=f"{period}-period Volume-Price Trend",
            category="Volume",
            valid_data=int(vpt.notna().sum()),
        )

# Use custom engine
custom_afe = CustomAlphaFactorEngine(ohlcv)
custom_factor1 = custom_afe.momentum_reversal(5, 20)
custom_factor2 = custom_afe.volume_price_trend(14)

print(f"Custom Factor 1: {custom_factor1.name}")
print(f"Custom Factor 2: {custom_factor2.name}")
```

---

## Performance Considerations

### Vectorization
All factor computations are **vectorized** using NumPy/Pandas:
- Single factor: **O(n)** where n = number of bars
- All factors: **O(k × n)** where k = number of factors (~26)
- IC computation: **O(m × n)** where m = number of factors

### Memory Usage
- Factor storage: `pd.Series` (efficient for time-series)
- DataFrame export: Creates full matrix (can be large for 100+ factors)
- Recommendation: Use `compute_all_factors()` dict for selective access

### Best Practices
1. **Avoid recomputation:** Cache `get_factors_dataframe()` result
2. **Filter NaN early:** Use `dropna()` before IC computation
3. **Use periods wisely:** Longer periods → more NaNs at start
4. **Batch computation:** Compute all factors once, analyze multiple times

---

## Common Pitfalls

### 1. Forward Returns Alignment
```python
# ❌ WRONG
forward_returns = ohlcv['close'].pct_change()

# ✅ CORRECT
forward_returns = ohlcv['close'].pct_change().shift(-1)
```

### 2. NaN Handling
```python
# ❌ WRONG (crashes on NaN)
ic = factors_df.corrwith(forward_returns)

# ✅ CORRECT (robust)
fa = FactorAnalyzer(factors_df, forward_returns)
ic = fa.information_coefficient()  # Handles NaN internally
```

### 3. Feature Importance Shape
```python
# ❌ WRONG (1D X)
X = factors_df['ROC_12'].values

# ✅ CORRECT (2D X)
X = factors_df.values  # or factors_df[['ROC_12', 'MACD_line']].values
```

---

## Next Steps

See [PHASE5.1_COMPLETION.md](../PHASE5.1_COMPLETION.md) for:
- Complete API reference
- Architecture details
- Performance benchmarks
- Phase 5.2 roadmap (100+ factors)

See [EXAMPLES.md](EXAMPLES.md) for:
- Portfolio optimization examples
- Backtesting workflows
- End-to-end strategies
