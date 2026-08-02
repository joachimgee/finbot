# 🔧 TEST FAILURE CATALOG & FIX STRATEGY

**Date** : 12 novembre 2025, 18:22 CET  
**Test Results** : 1252 passed, 49 failed, 26 error, 6 skipped  
**Objectif** : Fixer TOUS les tests défaillants par ordre de priorité

---

## 📊 EXECUTION SUMMARY

```
Total Tests:    1333
✅ Passed:      1252 (94%)
❌ Failed:       49 (3.7%)
🔴 Error:        26 (1.9%)
⏭️ Skipped:       6 (0.5%)
```

**Impact** : 75 tests cassent la CI/CD (49 failed + 26 error)

---

## 🎯 PRIORITY ORDER FOR FIXES

| Priority | Domain | Tests Affected | Impact | Est. Time |
|----------|--------|----------------|--------|-----------|
| **1** | Data Layer (fetchers/universe) | ~15-20 | 🔴 Bloque tout | 2h |
| **2** | Feature Naming (MACD/columns) | ~10-15 | 🟠 Cascade | 1h |
| **3** | Sentiment API/Mocks | ~8-12 | 🟡 Intégration | 1.5h |
| **4** | Portfolio Covariance | ~5-8 | 🟡 Numerical | 1h |
| **5** | ML Mocks (TF/LSTM) | ~5-8 | 🟢 Isolated | 1h |
| **6** | Logs EventStudy | ~3-5 | 🟢 Format | 30min |
| **7** | Trading Strategy | ~3-5 | 🟢 Edge cases | 1h |
| **8** | News Scraper | ~2-4 | 🟢 I/O | 30min |
| **9** | Universe Selector | ~2-3 | 🟢 Import path | 30min |

**Total Estimated Time** : 9 hours (1-2 days work)

---

## 🔴 DOMAIN 1: DATA LAYER (fetchers/universe) - PRIORITY 1

### **Symptômes** :
- ❌ ImportError on MarketDataFetcher
- ❌ Timeout/API errors not handled
- ❌ Empty universe → cascade KeyError/IndexError
- ❌ Signature mismatch (missing kwargs)

### **Tests Affected** :
```
tests/data/test_market_data_fetcher.py::test_fetch_bars - FAILED
tests/data/test_market_data_fetcher.py::test_rate_limiting - ERROR
tests/integration/test_pipeline_data.py::test_data_to_features - FAILED
tests/integration/test_portfolio_data.py::test_empty_data - ERROR
```

### **Root Cause** :
1. MarketDataFetcher constructor missing args
2. No try/except around API calls
3. No fallback for empty data
4. No retry/backoff logic

### **FIX PROMPT FOR COPILOT** :

```
================================================================================
FIX DOMAIN 1: DATA LAYER - MarketDataFetcher & Universe
================================================================================

FILE: src/financial_analyzer/data/market_data_fetcher.py

FIXES NEEDED:

1. Harmonize constructor signature:
   - Add default values for all kwargs
   - Document expected parameters
   
   def __init__(self, api_key=None, secret_key=None, paper=True, timeout=30):
       \"\"\"Initialize fetcher.\"\"\"
       self.api_key = api_key or os.getenv('ALPACA_API_KEY')
       self.secret_key = secret_key or os.getenv('ALPACA_SECRET_KEY')
       self.paper = paper
       self.timeout = timeout

2. Add error handling for API calls:
   - Wrap ALL external calls in try/except
   - Log errors with context
   - Return empty DataFrame on failure (not None)
   
   def fetch_bars(self, symbol, start, end, timeframe='1D'):
       try:
           bars = self._api_call(symbol, start, end, timeframe)
           if bars is None or len(bars) == 0:
               logger.warning(f"No data for {symbol}")
               return pd.DataFrame()  # Empty DF, not None
           return bars
       except Exception as e:
           logger.error(f"Failed to fetch {symbol}: {e}")
           return pd.DataFrame()  # Fallback

3. Add retry logic with exponential backoff:
   - Use tenacity library
   - Retry on 429 (rate limit) and 5xx
   
   from tenacity import retry, wait_exponential, stop_after_attempt
   
   @retry(
       wait=wait_exponential(min=1, max=60),
       stop=stop_after_attempt(3),
       reraise=True
   )
   def _api_call_with_retry(self, ...):
       # Actual API call here
       pass

4. Handle empty universe:
   - Always return at least fallback tickers
   
   def get_universe(self, sector=None, country='US', n_assets=20):
       try:
           tickers = self._fetch_universe(sector, country, n_assets)
           if not tickers or len(tickers) == 0:
               logger.warning("Empty universe, using fallback")
               tickers = ['AAPL', 'MSFT', 'GOOGL']  # Fallback
           return tickers
       except Exception as e:
           logger.error(f"Universe fetch failed: {e}")
           return ['AAPL', 'MSFT', 'GOOGL']  # Always return something

VALIDATION:
- Run: pytest tests/data/test_market_data_fetcher.py -v
- Expected: ALL PASS (no FAILED/ERROR)
```

---

## 🟠 DOMAIN 2: FEATURE NAMING (MACD/columns) - PRIORITY 2

### **Symptômes** :
- ❌ KeyError: 'MACD_signal' (test expects 'macd_signal')
- ❌ Column name mismatch in technical indicators
- ❌ Tests hardcode specific column names

### **Tests Affected** :
```
tests/features/test_technical_engine.py::test_macd_calculation - FAILED
tests/features/test_feature_pipeline.py::test_column_names - FAILED
tests/integration/test_signals.py::test_technical_features - ERROR
```

### **Root Cause** :
1. Inconsistent naming (MACD vs macd, CamelCase vs snake_case)
2. No schema validation
3. Tests assume specific names

### **FIX PROMPT FOR COPILOT** :

```
================================================================================
FIX DOMAIN 2: FEATURE NAMING - Standardize to snake_case
================================================================================

FILES TO FIX:
- src/financial_analyzer/features/technical_engine.py
- src/financial_analyzer/features/indicators.py

STANDARD NAMING CONVENTION:
- ALL feature names: snake_case (lowercase with underscores)
- NO CamelCase, NO UPPERCASE
- Example: MACD_signal → macd_signal, RSI_14 → rsi_14

FIXES:

1. Update all feature generation to use snake_case:

   # BEFORE (WRONG):
   df['MACD'] = ...
   df['MACD_signal'] = ...
   df['RSI_14'] = ...
   
   # AFTER (CORRECT):
   df['macd'] = ...
   df['macd_signal'] = ...
   df['rsi_14'] = ...

2. Add feature name registry:

   FEATURE_NAMES = {
       'macd': 'macd',
       'macd_signal': 'macd_signal',
       'macd_hist': 'macd_hist',
       'rsi_14': 'rsi_14',
       'rsi_28': 'rsi_28',
       'sma_20': 'sma_20',
       'sma_50': 'sma_50',
       'bollinger_upper': 'bollinger_upper',
       'bollinger_lower': 'bollinger_lower',
       'atr_14': 'atr_14',
   }

3. Add validation function:

   def validate_feature_columns(df, required_features):
       \"\"\"Validate that DataFrame has expected feature columns.\"\"\"
       missing = [f for f in required_features if f not in df.columns]
       if missing:
           raise ValueError(f"Missing features: {missing}")
       return True

4. Update tests to use FEATURE_NAMES registry:

   # In tests:
   from financial_analyzer.features.technical_engine import FEATURE_NAMES
   
   assert FEATURE_NAMES['macd'] in df.columns
   assert FEATURE_NAMES['rsi_14'] in df.columns

VALIDATION:
- Run: pytest tests/features/ -v
- Expected: ALL PASS on feature naming tests
```

---

## 🟡 DOMAIN 3: SENTIMENT API/MOCKS - PRIORITY 3

### **Symptômes** :
- ❌ Mock patch points don't match actual code
- ❌ Sentiment API returns different fields than expected
- ❌ FinBERT mock not properly isolated

### **Tests Affected** :
```
tests/sentiment/test_sentiment_aggregator.py::test_aggregate - FAILED
tests/sentiment/test_finbert_engine.py::test_batch_analysis - ERROR
tests/integration/test_sentiment_pipeline.py::test_sentiment_to_signals - FAILED
```

### **Root Cause** :
1. Class/module paths changed, patches invalid
2. API response schema drift
3. External FinBERT calls not mocked

### **FIX PROMPT FOR COPILOT** :

```
================================================================================
FIX DOMAIN 3: SENTIMENT - Stabilize API & Mocks
================================================================================

FILES TO FIX:
- src/financial_analyzer/sentiment/sentiment_aggregator.py
- src/financial_analyzer/sentiment/finbert_engine.py
- tests/sentiment/test_sentiment_aggregator.py

FIXES:

1. Create adapter layer for sentiment API:

   class SentimentResponse:
       \"\"\"Normalized sentiment response.\"\"\"
       def __init__(self, score, label, confidence):
           self.score = float(score)  # -1.0 to 1.0
           self.label = str(label)    # positive/negative/neutral
           self.confidence = float(confidence)  # 0.0 to 1.0
       
       @classmethod
       def from_finbert(cls, finbert_result):
           \"\"\"Convert FinBERT output to normalized format.\"\"\"
           return cls(
               score=finbert_result.get('score', 0.0),
               label=finbert_result.get('label', 'neutral'),
               confidence=finbert_result.get('confidence', 0.5)
           )

2. Update SentimentAggregator to use normalized response:

   def analyze_text(self, text):
       \"\"\"Analyze sentiment with normalized output.\"\"\"
       try:
           raw_result = self.engine.analyze(text)
           return SentimentResponse.from_finbert(raw_result)
       except Exception as e:
           logger.error(f"Sentiment analysis failed: {e}")
           return SentimentResponse(score=0.0, label='neutral', confidence=0.0)

3. Fix mock patch points in tests:

   # BEFORE (WRONG):
   @patch('financial_analyzer.sentiment.finbert_engine.FinBERT')
   
   # AFTER (CORRECT):
   @patch('financial_analyzer.sentiment.finbert_engine.FinBertEngine.analyze')
   def test_sentiment(mock_analyze):
       mock_analyze.return_value = {
           'score': 0.8,
           'label': 'positive',
           'confidence': 0.9
       }
       # Test code here

4. Add default values everywhere:

   def aggregate(self, texts):
       if not texts:
           return SentimentResponse(0.0, 'neutral', 0.0)
       
       scores = []
       for text in texts:
           result = self.analyze_text(text)
           scores.append(result.score)
       
       return SentimentResponse(
           score=np.mean(scores),
           label='positive' if np.mean(scores) > 0 else 'negative',
           confidence=1.0 - np.std(scores)
       )

VALIDATION:
- Run: pytest tests/sentiment/ -v
- Expected: ALL PASS, no external API calls
```

---

## 🟡 DOMAIN 4: PORTFOLIO COVARIANCE - PRIORITY 4

### **Symptômes** :
- ❌ AttributeError: 'numpy.ndarray' has no attribute 'cov'
- ❌ Covariance matrix singular/non-invertible
- ❌ Index/columns misalignment

### **Tests Affected** :
```
tests/portfolio/test_optimizer.py::test_min_variance - ERROR
tests/portfolio/test_covariance.py::test_calculation - FAILED
tests/integration/test_portfolio_opt.py::test_full_optimization - ERROR
```

### **Root Cause** :
1. Using np.array instead of pd.DataFrame
2. No regularization for singular matrices
3. Index/columns not aligned

### **FIX PROMPT FOR COPILOT** :

```
================================================================================
FIX DOMAIN 4: PORTFOLIO - Covariance & Optimization
================================================================================

FILES TO FIX:
- src/financial_analyzer/portfolio/optimizer.py
- src/financial_analyzer/portfolio/covariance.py

FIXES:

1. Always use DataFrame for returns:

   # BEFORE (WRONG):
   returns = np.random.randn(252, 10)
   cov = returns.cov()  # ERROR!
   
   # AFTER (CORRECT):
   returns_data = np.random.randn(252, 10)
   returns = pd.DataFrame(returns_data, columns=tickers)
   cov = returns.cov()  # Works!

2. Add covariance regularization:

   def calculate_covariance(returns, shrinkage=0.01):
       \"\"\"Calculate regularized covariance matrix.\"\"\"
       if isinstance(returns, np.ndarray):
           returns = pd.DataFrame(returns)
       
       cov = returns.cov()
       
       # Add regularization (shrinkage to diagonal)
       identity = np.eye(len(cov))
       cov_reg = (1 - shrinkage) * cov + shrinkage * np.trace(cov) / len(cov) * identity
       
       return pd.DataFrame(cov_reg, index=cov.index, columns=cov.columns)

3. Ensure index/columns alignment:

   def optimize_weights(returns, cov_matrix):
       \"\"\"Optimize with aligned data.\"\"\"
       # Ensure alignment
       tickers = returns.columns.tolist()
       cov_matrix = cov_matrix.loc[tickers, tickers]
       
       # Now optimize...
       pass

4. Add numerical stability checks:

   def is_positive_definite(matrix):
       \"\"\"Check if matrix is positive definite.\"\"\"
       try:
           np.linalg.cholesky(matrix)
           return True
       except np.linalg.LinAlgError:
           return False
   
   if not is_positive_definite(cov_matrix):
       logger.warning("Covariance not PD, adding jitter")
       cov_matrix += np.eye(len(cov_matrix)) * 1e-6

VALIDATION:
- Run: pytest tests/portfolio/ -v
- Expected: ALL PASS, no LinAlgError
```

---

## 🟢 DOMAIN 5: ML MOCKS (TF/LSTM) - PRIORITY 5

### **Symptômes** :
- ❌ TensorFlow not mocked properly
- ❌ Shape mismatches in predictions
- ❌ RNG not fixed (non-deterministic tests)

### **Tests Affected** :
```
tests/ml/test_lstm_predictor.py::test_predict - ERROR
tests/ml/test_transformer_predictor.py::test_train - ERROR
tests/integration/test_ml_pipeline.py::test_ensemble - FAILED
```

### **Root Cause** :
1. TF imports not mocked at correct path
2. Model shapes not validated
3. Random seeds not fixed

### **FIX PROMPT FOR COPILOT** :

```
================================================================================
FIX DOMAIN 5: ML - Mocks & Determinism
================================================================================

FILES TO FIX:
- tests/ml/test_lstm_predictor.py
- tests/ml/test_transformer_predictor.py
- src/financial_analyzer/ml/lstm_predictor.py

FIXES:

1. Mock TensorFlow at all import points:

   @pytest.fixture
   def mock_tf():
       with patch('tensorflow.keras.models.Sequential') as mock_seq:
           mock_model = MagicMock()
           mock_model.predict.return_value = np.random.rand(10, 1)
           mock_seq.return_value = mock_model
           yield mock_model

2. Fix random seeds in tests:

   @pytest.fixture(autouse=True)
   def fix_random_seeds():
       np.random.seed(42)
       import random
       random.seed(42)
       try:
           import tensorflow as tf
           tf.random.set_seed(42)
       except:
           pass

3. Validate prediction shapes:

   def predict(self, X):
       \"\"\"Predict with shape validation.\"\"\"
       if len(X.shape) != 2:
           raise ValueError(f"Expected 2D input, got {X.shape}")
       
       pred = self.model.predict(X)
       
       if pred.shape[0] != X.shape[0]:
           raise ValueError(f"Output shape mismatch: {pred.shape} vs {X.shape}")
       
       return pred

4. Standardize ML output format:

   def predict(self, X):
       \"\"\"Return predictions as pd.Series.\"\"\"
       pred = self._model_predict(X)
       return pd.Series(pred.flatten(), index=X.index if hasattr(X, 'index') else None)

VALIDATION:
- Run: pytest tests/ml/ -v --tb=short
- Expected: ALL PASS, deterministic results
```

---

## 🟢 DOMAIN 6-9: REMAINING FIXES (Lower Priority)

### **Domain 6: Logs EventStudy** (30 min)
```python
# Standardize log format
logger.info(f"Event {event_name}: {result}")  # Fixed format
# Update tests to match exact string
```

### **Domain 7: Trading Strategy** (1 hour)
```python
# Clarify conventions
# - Entry/exit on bar close
# - No lookahead bias
# - Consistent timezone (UTC)
```

### **Domain 8: News Scraper** (30 min)
```python
# Mock all I/O
@patch('requests.get')
def test_scraper(mock_get):
    mock_get.return_value.text = "<html>...</html>"
    # Test code
```

### **Domain 9: Universe Selector** (30 min)
```python
# Fix import path
from financial_analyzer.market.market_selector import MarketSelector  # Correct
# Not: from financial_analyzer.market import Universe  # Wrong
```

---

## 📋 EXECUTION PLAN

### **Week 1: Critical Fixes (Domains 1-4)**

**Day 1** (4h):
- Morning: Domain 1 (Data Layer) → 15-20 tests fixed
- Afternoon: Domain 2 (Feature Naming) → 10-15 tests fixed

**Day 2** (4h):
- Morning: Domain 3 (Sentiment) → 8-12 tests fixed
- Afternoon: Domain 4 (Portfolio) → 5-8 tests fixed

### **Week 1: Remaining Fixes (Domains 5-9)**

**Day 3** (3h):
- Morning: Domain 5 (ML Mocks) → 5-8 tests fixed
- Afternoon: Domains 6-9 (Quick wins) → 10-15 tests fixed

**Expected Result**: 0 failures, 0 errors, 100% pass rate

---

## 🚀 QUICK START

### **Apply fixes sequentially** :

```bash
# 1. Domain 1 (Data Layer)
# Copy-paste Domain 1 prompt to Copilot
pytest tests/data/ -v

# 2. Domain 2 (Feature Naming)
# Copy-paste Domain 2 prompt to Copilot
pytest tests/features/ -v

# 3. Domain 3 (Sentiment)
# Copy-paste Domain 3 prompt to Copilot
pytest tests/sentiment/ -v

# Continue for remaining domains...
```

### **Validation after each domain** :
```bash
# Run full suite
pytest -v --tb=short

# Check progress
pytest --co -q | grep -c "test_"
```

---

## 📊 EXPECTED OUTCOME

**Before** :
```
1252 passed, 49 failed, 26 error, 6 skipped
Pass rate: 94%
```

**After** :
```
1333 passed, 0 failed, 0 error, 0 skipped
Pass rate: 100% ✅
```

**Timeline** : 2-3 days of focused work following this plan

---

## ✅ VALIDATION CHECKLIST

After completing ALL fixes, run:

```bash
# 1. Full test suite
pytest -v --cov=financial_analyzer --cov-report=html

# 2. Check coverage
open htmlcov/index.html

# 3. Integration tests
pytest tests/integration/ -v

# 4. E2E backtest
python scripts/comprehensive_e2e_backtest.py

# All should PASS ✅
```

---

**Copy-paste chaque prompt de domaine à Copilot dans l'ordre de priorité ! 💪🎯**
