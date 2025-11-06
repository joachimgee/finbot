# DEPLOYMENT & TROUBLESHOOTING GUIDE

**Version:** 1.0  
**Last Updated:** 2025-11-06

---

## Deployment Guide

### System Requirements

**Minimum:**
- Python 3.8+
- 4 GB RAM
- 1 GB disk space

**Recommended:**
- Python 3.10+
- 8 GB RAM
- 2 GB disk space

### Dependencies

```
pandas >= 1.3.0
numpy >= 1.21.0
scipy >= 1.7.0
```

### Installation

#### Via pip

```bash
pip install financial-analyzer
```

#### From source

```bash
git clone https://github.com/your-repo/financial-analyzer.git
cd financial-analyzer
pip install -e .
```

#### Development setup

```bash
git clone https://github.com/your-repo/financial-analyzer.git
cd financial-analyzer
pip install -e ".[dev]"
```

Includes testing and linting tools:
- pytest
- pytest-cov
- mypy
- black
- pylint

---

## Production Deployment

### Docker Setup

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install -e .

CMD ["python", "-m", "gunicorn", "app:app"]
```

Build and run:

```bash
docker build -t finbot-portfolio:1.0 .
docker run -p 5000:5000 finbot-portfolio:1.0
```

### Configuration

Create `config.yaml`:

```yaml
portfolio:
  risk_free_rate: 0.03
  rebalance_frequency: "M"  # Monthly
  max_portfolio_size: 100
  optimization_method: "SLSQP"

constraints:
  long_only: true
  max_herfindahl: 0.2
  min_weight: 0.05
  max_weight: 0.30

performance:
  num_frontier_points: 50
  max_optimization_time: 10  # seconds
  cache_covariance: true

logging:
  level: "INFO"
  file: "logs/portfolio.log"
  max_file_size: 10485760  # 10 MB
```

Load in code:

```python
import yaml

with open('config.yaml') as f:
    config = yaml.safe_load(f)

optimizer = PortfolioOptimizer(
    returns,
    risk_free_rate=config['portfolio']['risk_free_rate']
)
```

### Environment Variables

```bash
export FINBOT_RF_RATE=0.03
export FINBOT_LOG_LEVEL=INFO
export FINBOT_MAX_ASSETS=100
export FINBOT_CACHE_COV=true
```

Use in code:

```python
import os

rf_rate = float(os.getenv('FINBOT_RF_RATE', 0.02))
log_level = os.getenv('FINBOT_LOG_LEVEL', 'INFO')
```

### Database Setup (Optional)

Store optimization results:

```python
import sqlite3

conn = sqlite3.connect('portfolio.db')
cursor = conn.cursor()

# Create table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS optimizations (
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        method TEXT,
        return REAL,
        volatility REAL,
        sharpe REAL,
        weights TEXT
    )
''')

# Insert result
cursor.execute('''
    INSERT INTO optimizations
    (timestamp, method, return, volatility, sharpe, weights)
    VALUES (?, ?, ?, ?, ?, ?)
''', (
    datetime.now(),
    'max_sharpe',
    result['return'],
    result['volatility'],
    result['sharpe'],
    json.dumps(result['weights'].to_dict())
))

conn.commit()
```

---

## Quality Assurance

### Type Checking

```bash
mypy src/financial_analyzer/portfolio/
```

Expected output: `Success: no issues found in X source files`

### Linting

```bash
pylint src/financial_analyzer/portfolio/
```

Target score: 9.0+

### Code Formatting

```bash
black src/financial_analyzer/portfolio/
```

### Test Coverage

```bash
pytest --cov=financial_analyzer.portfolio tests/
```

Target coverage: 85%+

### Running All Checks

```bash
make quality
# Or individually:
make type-check
make lint
make format
make test-coverage
```

---

## Monitoring & Logging

### Logging Setup

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/portfolio.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting optimization...")
```

### Performance Monitoring

```python
import time

start = time.time()
result = optimizer.optimize_max_sharpe()
elapsed = time.time() - start

print(f"Optimization took {elapsed:.2f}s")

# Alert if slow
if elapsed > 5.0:
    logger.warning(f"Optimization took {elapsed:.2f}s (> 5s threshold)")
```

### Memory Monitoring

```python
import psutil
import os

process = psutil.Process(os.getpid())
memory_before = process.memory_info().rss / 1024 / 1024  # MB

result = optimizer.calculate_efficient_frontier(100)

memory_after = process.memory_info().rss / 1024 / 1024
memory_used = memory_after - memory_before

print(f"Memory used: {memory_used:.1f} MB")
```

---

## Troubleshooting

### Issue 1: "ValueError: returns must be a non-empty DataFrame"

**Cause:** Returns DataFrame is empty or None

**Solutions:**
```python
# Check if empty
if returns.empty:
    print("Error: No returns data")
    return

# Verify shape
print(f"Returns shape: {returns.shape}")  # Should be (dates, tickers)

# Check for missing values
print(f"Missing values: {returns.isna().sum().sum()}")
```

### Issue 2: "Optimization did not converge"

**Cause:** SLSQP optimizer couldn't find optimal solution

**Solutions:**

```python
# 1. Loosen constraints
constraints.min_weight = 0.0  # Instead of 0.05
constraints.max_weight = 1.0  # Instead of 0.30

# 2. Improve initial guess
optimizer = PortfolioOptimizer(returns)
result_eq = optimizer.optimize_equal_weight()
# Use equal weight as starting point

# 3. Use different method (use risk_parity which has closed form)
result = optimizer.optimize_risk_parity()

# 4. Increase iterations
# (Modify source if needed - default is 1000)
```

### Issue 3: "weights don't sum to 1"

**Cause:** Numerical precision errors in optimization

**Solution:**
```python
# Always normalize after optimization
weights = result['weights']
weights = weights / weights.sum()

# Verify
assert np.isclose(weights.sum(), 1.0), "Weights don't sum to 1"
```

### Issue 4: "Sector constraint not applied"

**Cause:** Missing sector_mapping or incorrect sector names

**Solutions:**

```python
# Verify sector mapping
print(constraints.sector_mapping)
# Should show: {'AAPL': 'Tech', 'MSFT': 'Tech', ...}

# Check constraint function exists
funcs = constraints.sector_constraints_functions(tickers)
print(f"Number of sector constraints: {len(funcs)}")

# Verify sector name matches exactly
# (case-sensitive!)
constraints.add_sector_constraint("Technology", 0.3)  # Correct
constraints.add_sector_constraint("technology", 0.3)  # WRONG
```

### Issue 5: "Rebalancing produces NaN weights"

**Cause:** Returns contain NaN or extreme values

**Solutions:**

```python
# Clean returns first
returns = returns.dropna(how='all')  # Drop all-NaN rows
returns = returns.fillna(0.0)  # Fill remaining NaNs

# Check for extreme values
print(f"Max return: {returns.max().max():.2%}")
print(f"Min return: {returns.min().min():.2%}")

# Winsorize if needed (cap at ±10%)
returns = returns.clip(-0.10, 0.10)
```

### Issue 6: "Efficient frontier computation is slow"

**Cause:** Too many portfolios requested

**Solutions:**

```python
# Use fewer points
frontier = optimizer.calculate_efficient_frontier(num_portfolios=20)  # Instead of 100

# Run in parallel (if using custom wrapper)
# from multiprocessing import Pool
# with Pool(4) as p:
#     frontiers = p.map(compute_frontier, datasets)

# Cache covariance matrix if computing multiple frontiers
cov_cached = returns.cov() * 252
```

### Issue 7: "Memory error on large portfolio"

**Cause:** Too many assets or too long history

**Solutions:**

```python
# Reduce data size
returns_subset = returns.iloc[-252:]  # Last 1 year only
returns_assets = returns[['AAPL', 'MSFT', 'GOOG']]  # Fewer assets

# Use sparse matrices if implementing custom code
# from scipy.sparse import coo_matrix

# Monitor memory
import psutil
print(f"Available RAM: {psutil.virtual_memory().available / 1e9:.1f} GB")
```

### Issue 8: "Results differ between runs (non-deterministic)"

**Cause:** Floating point precision in optimization

**Solutions:**

```python
# Set seed for reproducibility (if using random initialization)
import numpy as np
np.random.seed(42)

# Use deterministic optimizer method
# SLSQP is already deterministic with same input

# Normalize inputs before optimization
returns_norm = (returns - returns.mean()) / returns.std()
```

### Issue 9: "Transaction costs too high / negative returns"

**Cause:** Rebalancing costs exceed portfolio returns

**Solutions:**

```python
# Reduce rebalancing frequency
rebal_result = rebalancer.rebalance_calendar(w, months=(3, 9))  # 2x per year

# Use threshold-based rebalancing
rebal_result = rebalancer.rebalance_threshold(w, threshold=0.10)  # 10% drift

# Reduce transaction cost estimate or negotiate with broker
transaction_cost = 0.0005  # 0.05% instead of 0.1%

# Verify costs are reasonable
total_trades = rebal_result.trades.abs().sum().sum()
total_costs = total_trades * transaction_cost
print(f"Estimated costs: {total_costs:.2%} of portfolio value")
```

### Issue 10: "Constraint conflict (infeasible)"

**Cause:** Conflicting constraints make solution impossible

**Solutions:**

```python
# Check constraint feasibility
# Min/max per asset
min_tot = len(tickers) * constraints.min_weight  # Should be <= 1
max_tot = len(tickers) * constraints.max_weight  # Should be >= 1

if min_tot > 1 or max_tot < 1:
    print("Infeasible constraints!")
    # Adjust:
    constraints.min_weight = 0.0
    constraints.max_weight = 1.0

# Check sector constraints
tech_weight = 0.3  # Max
tech_assets = ['AAPL', 'MSFT', 'GOOG']  # 3 assets
min_per_asset = 0.3 / 3  # 10% per asset minimum

# If tech max is 30% but you need 40% in tech, conflict!
# Solution: Increase tech max or reduce other constraints
```

---

## Performance Tuning

### Optimization Speed

| Action | Impact |
|--------|--------|
| Reduce frontier points | 100 → 50 |
| Use risk parity | 0.1s vs 1s for max sharpe |
| Reduce constraints | Remove custom constraints |
| Fewer assets | 100 assets vs 10 assets |
| Shorter history | 5 years vs 20 years |

### Memory Optimization

| Action | Impact |
|--------|--------|
| Reduce history | Keep last 2 years only |
| Reduce assets | Use top 50 by liquidity |
| Use float32 | Instead of float64 |
| Cache covariance | Compute once, reuse |

---

## Security

### Input Validation

```python
def validate_returns(returns):
    """Validate returns before use."""
    # Check type
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("returns must be DataFrame")
    
    # Check not empty
    if returns.empty:
        raise ValueError("returns cannot be empty")
    
    # Check values are numeric
    if not np.issubdtype(returns.dtypes, np.number):
        raise TypeError("returns must be numeric")
    
    # Check reasonable range (no returns > 100%)
    if (returns.abs() > 1.0).any().any():
        raise ValueError("returns contain values > 100%")
    
    return True

# Use
try:
    validate_returns(returns)
    optimizer = PortfolioOptimizer(returns)
except (TypeError, ValueError) as e:
    print(f"Invalid input: {e}")
```

### Output Sanitization

```python
def sanitize_weights(weights):
    """Ensure weights are valid before output."""
    # Check sum to 1
    if not np.isclose(weights.sum(), 1.0):
        weights = weights / weights.sum()
    
    # Check all non-negative
    if (weights < 0).any():
        weights = np.maximum(weights, 0)
        weights = weights / weights.sum()
    
    # Check no NaN
    if weights.isna().any():
        raise ValueError("Weights contain NaN")
    
    return weights
```

---

## Maintenance

### Regular Updates

```bash
# Check for updates
pip index versions financial-analyzer

# Update
pip install --upgrade financial-analyzer

# Verify version
python -c "import financial_analyzer; print(financial_analyzer.__version__)"
```

### Backup & Recovery

```bash
# Backup optimization results
import shutil
shutil.copytree('data/portfolio', 'backup/portfolio_2025-11-06')

# Verify backup
ls -lh backup/portfolio_2025-11-06/
```

### Health Check

```python
def health_check():
    """Verify system is working."""
    try:
        # Test imports
        from financial_analyzer.portfolio import PortfolioOptimizer
        
        # Test with dummy data
        returns = pd.DataFrame(
            np.random.randn(252, 5) * 0.01,
            columns=['A', 'B', 'C', 'D', 'E']
        )
        
        # Test optimization
        opt = PortfolioOptimizer(returns)
        result = opt.optimize_max_sharpe()
        
        # Verify result
        assert 'weights' in result
        assert np.isclose(result['weights'].sum(), 1.0)
        
        print("✓ Health check passed")
        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

health_check()
```

---

## Support & Getting Help

### Documentation

- API Reference: `API_REFERENCE.md`
- Examples: `EXAMPLES.md`
- Architecture: `ARCHITECTURE.md`

### Testing

Run full test suite:

```bash
pytest tests/test_portfolio/ -v
```

Run specific test:

```bash
pytest tests/test_portfolio/test_integration.py::TestOptimizationWorkflow -v
```

### Reporting Issues

Include:
1. Python version: `python --version`
2. Package version: `pip show financial-analyzer`
3. Error message (full traceback)
4. Minimal reproducible example
5. Data shape: `print(returns.shape)`

---

**For API details, see: API_REFERENCE.md**  
**For examples, see: EXAMPLES.md**  
**For architecture, see: ARCHITECTURE.md**
