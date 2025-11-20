# 🎯 PHASE 5.5 - ML & NLP ENHANCEMENT ARCHITECTURE

## MISSION PHASE 5.5

Remplacer les mocks Phase 5.4 par **vraies implémentations production-grade** :
- ✅ **Real FinBERT** sentiment (ProsusAI/finbert) au lieu de random
- ✅ **Real Feature Engineering** (114 ML factors exploitant Riskfolio insights)
- ✅ **Real Riskfolio Optimization** (NCO, HRP, CDaR au lieu de bridge simple)
- ✅ **Real Market Cap Universe** (FinanceDatabase + FinvizElite screening)
- ✅ **Advanced Portfolio Attribution** (Factor contributions)
- ✅ **LSTM/Transformer Predictions** (TensorFlow/PyTorch)

---

## 📚 INSPIRATIONS DES AUDITS LUES

### 1️⃣ **RISKFOLIO-LIB AUDIT (32 KB)**

**Insights clés** :

- **59 mesures de risque** (24 convexes + 35 pour HRP/HERC)
  - CVaR, CDaR, EVaR, RLVaR pour tail risk
  - Semivariance pour downside
- **NCO Algorithm** : HRP + Mean-Variance (combine robustness + returns)
- **Factor Models** : Risk decomposition par factor
- **Worst Case Optimization** : Robust allocation avec uncertainty sets
- **Black-Litterman** : Integration investor views + market equilibrium

**→ Phase 5.5 ADOPTION** :
```python
# Remplacer SignalPortfolioBridge MOCK
from riskfolio import Portfolio as RiskfolioPortfolio
from riskfolio import HCPortfolio

# Real optimization avec 24 risk measures
portfolio = RiskfolioPortfolio(returns=df)
weights = portfolio.optimization(
    model="Classic",
    rm="CDaR",  # Tail risk
    obj="Sharpe",
    kelly="exact",  # Log returns
    rf=0.02
)
```

---

### 2️⃣ **FINANCE PART 5 ML AUDIT (18 KB)**

**Insights clés** :

- **16 ML models** : ARIMA, Prophet, LSTM, MLP, sklearn classifiers
- **6 expected returns methods** : historical, EMA, CAPM, James-Stein, etc.
- **Feature engineering patterns** :
  - Momentum indicators (SMA, EMA, momentum ratio)
  - Mean-reversion (Bollinger Bands, z-score)
  - Volatility (ATR, rolling std)
  - Volume flows (OBV, VWAP, CMF)
- **Backtesting patterns** : Isolation Forest anomaly trading + backtrader

**→ Phase 5.5 ADOPTION** :
```python
# Real feature engineering (114 factors inspiration)
features = {
    'momentum_12m': price.pct_change(252),
    'reversion_20d': (price - sma_20) / atr,
    'volatility_20d': returns.rolling(20).std(),
    'volume_flow': obv / obv.rolling(20).mean(),
    'quality_factors': earnings_yield / leverage,
}
# All 114 factors engineered + validated with IC
```

---

### 3️⃣ **PYPORTFOLIOOPT AUDIT (34 KB)**

**Insights clés** :

- **Multiple optimization methods** :
  - EfficientFrontier (Markowitz)
  - EfficientCVaR / EfficientSemivariance / EfficientCDaR
  - HRP (Hierarchical Risk Parity)
  - CLA (Critical Line Algorithm)
- **Covariance shrinkage** : Ledoit-Wolf, OAS pour estimation robuste
- **Discrete allocation** : Convert continuous weights → integer shares
- **Risk models** : 8+ covariance estimators

**→ Phase 5.5 ADOPTION** :
```python
# Hybrid Riskfolio + PyPortfolioOpt
from pypfopt import EfficientFrontier
from pypfopt.risk_models import ledoit_wolf_shrinkage

# Shrink covariance matrix (robust estimation)
S_shrunk = ledoit_wolf_shrinkage(returns_data)

# Optimize with multiple objectives
ef = EfficientFrontier(mu, S_shrunk)
weights_sharpe = ef.max_sharpe()
weights_minvol = ef.min_volatility()
```

---

### 4️⃣ **FINANCE PART 3 TECHNICALS AUDIT (19 KB)**

**Insights clés** :

- **80+ technical indicators** organized by family :
  - Trend (SMA, EMA, VWAP, GMMA, HMA)
  - Momentum (RSI, MACD, CCI, Stoch, MFI, TSI)
  - Volatility (ATR, Bollinger, Keltner, ADX, SuperTrend)
  - Volume (OBV, ADL, CMF, Force Index, MFI)
  - Channels (Donchian, Pivot, CPR, Acceleration Bands)
- **Formulas consolidated** : 50+ mathematical definitions
- **TA-Lib wrapper pattern** : Unified interface for indicators

**→ Phase 5.5 ADOPTION** :
```python
# Unified indicator interface
from financial_analyzer.indicators import (
    calculate_sma, calculate_ema, calculate_rsi,
    calculate_atr, calculate_bollinger_bands,
    calculate_macd, calculate_adx
)

# Compute 114 factors using these core functions
factor_dict = {
    f'sma_12': calculate_sma(close, 12),
    f'rsi_14': calculate_rsi(close, 14),
    f'atr_14': calculate_atr(high, low, close, 14),
    # ... 111 more factors
}
```

---

## 🏗️ PHASE 5.5 STRUCTURE (8 MODULES)

```
src/financial_analyzer/
├── ml_features/                      # Module 1 : Real Feature Engineering
│   ├── __init__.py
│   ├── feature_engineer.py           # 114 ML factors (momentum, reversion, vol, quality)
│   ├── feature_validator.py          # IC validation + correlation analysis
│   ├── feature_selector.py           # Top-K by IC or RFE
│   └── tests/
│
├── sentiment/                        # Module 2 : Real FinBERT Sentiment
│   ├── __init__.py
│   ├── finbert_engine.py            # FinBERT model + inference
│   ├── news_fetcher.py              # News aggregation (NewsAPI, FinHub, etc)
│   ├── sentiment_aggregator.py       # Ensemble sentiment signals
│   └── tests/
│
├── universe/                         # Module 3 : Real Universe Selector
│   ├── __init__.py
│   ├── market_selector.py           # Top-N by market cap
│   ├── fundamental_screener.py       # P/E, ROE, dividend screens
│   ├── technical_screener.py        # Breakout, trend screens
│   └── tests/
│
├── portfolio_optimization/           # Module 4 : Real Riskfolio Integration
│   ├── __init__.py
│   ├── riskfolio_wrapper.py         # Portfolio + HCPortfolio wrappers
│   ├── optimization_strategies.py   # NCO, HRP, CDaR, BL models
│   ├── risk_decomposition.py        # Factor contribution analysis
│   └── tests/
│
├── forecasting/                      # Module 5 : LSTM/Transformer Predictions
│   ├── __init__.py
│   ├── lstm_model.py                # Multi-layer LSTM + attention
│   ├── transformer_model.py         # Transformer for long sequences
│   ├── ensemble_forecast.py         # Consensus of models
│   ├── forecast_validator.py        # Out-of-sample backtest
│   └── tests/
│
├── signal_generation_v2/             # Module 6 : Advanced Signal Fusion
│   ├── __init__.py
│   ├── multi_signal_fusion.py       # Sentiment + factors + technicals + forecast
│   ├── signal_weighting.py          # Dynamic IC-based weights
│   ├── regime_detection.py          # Market regime classification
│   └── tests/
│
├── pipeline_v2/                      # Module 7 : Enhanced Pipeline (v2)
│   ├── __init__.py
│   ├── ml_pipeline_v2.py            # Integrates all 6 modules
│   ├── live_monitoring.py           # Real-time performance tracking
│   ├── model_retraining.py          # Online learning + rebalancing
│   └── tests/
│
└── attribution_v2/                   # Module 8 : Advanced Attribution
    ├── __init__.py
    ├── factor_attribution.py        # Brinson + factor decomposition
    ├── performance_monitoring.py    # Benchmark vs strategy
    ├── risk_reporting.py            # VaR, CVaR, drawdown analysis
    └── tests/
```

---

## 📊 DETAILED MODULE SPECS

### **MODULE 1 : ML FEATURES (Feature Engineering v2)**

**File**: `ml_features/feature_engineer.py`

```python
class FeatureEngineer:
    """
    114 ML factors exploiting Riskfolio + Finance ML insights.
    
    Categories (18 factors each):
    
    1. MOMENTUM (18) :
       - Price momentum (12m, 6m, 3m, 1m)
       - Returns ratios (skew, kurtosis, VaR quantiles)
       - Acceleration (2nd derivative)
    
    2. MEAN-REVERSION (18) :
       - Bollinger deviation (distance from bands)
       - Z-scores (price vs SMA)
       - Reversals (reversal index from ADX)
    
    3. VOLATILITY (18) :
       - Rolling std (5d, 10d, 20d, 60d)
       - Parkinson volatility (H-L based, more efficient)
       - GARCH conditional volatility
    
    4. QUALITY/FUNDAMENTAL (18) :
       - Earnings yield
       - Return on equity
       - Leverage ratio
       - Cash flow quality
    
    5. TECHNICALS (18) :
       - RSI patterns (RSI14, RSI14 slope, RSI histo)
       - MACD (line, signal, histo)
       - ATR ratios
    
    6. VOLUME (18) :
       - OBV momentum
       - VWAP distance
       - Volume-price correlation
    
    Total: 6 × 18 + 10 = 114 factors
    
    Method:
    1. Compute all 114 factors
    2. Cross-sectional normalize (Z-score)
    3. Validate IC (Information Coefficient)
    4. Return factor_dict + IC_scores
    """
    
    def __init__(self, prices, fundamentals=None, max_nan_pct=0.05):
        self.prices = prices  # pd.DataFrame OHLCV multi-asset
        self.fundamentals = fundamentals  # pd.DataFrame P/E, ROE, etc
        self.max_nan_pct = max_nan_pct
    
    def compute_all_factors(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Compute 114 factors + IC scores."""
        pass
    
    def compute_momentum_factors(self) -> Dict[str, np.ndarray]:
        """18 momentum factors."""
        pass
    
    def compute_reversion_factors(self) -> Dict[str, np.ndarray]:
        """18 mean-reversion factors."""
        pass
    
    def compute_volatility_factors(self) -> Dict[str, np.ndarray]:
        """18 volatility factors."""
        pass
    
    # ... other families ...

class FeatureValidator:
    """
    Validate factors via IC (Information Coefficient).
    
    IC = correlation(factor, future_returns_1m)
    
    Selection :
    - Positive IC > 0.05
    - Top-K by |IC|
    - Orthogonalization (remove correlated)
    """
    
    def calculate_ic(self, factors: pd.DataFrame, forward_returns: pd.Series) -> pd.Series:
        """IC per factor."""
        pass
    
    def select_top_k_factors(self, ic_scores: pd.Series, k=50) -> List[str]:
        """Top-K factors by |IC|."""
        pass
```

**Audit References**:
- Finance Part 5 ML (feature engineering patterns)
- Riskfolio (factor decomposition)

---

### **MODULE 2 : SENTIMENT (Real FinBERT)**

**File**: `sentiment/finbert_engine.py`

```python
class FinBERTEngine:
    """
    Real FinBERT sentiment analysis.
    
    Model: ProsusAI/finbert (fine-tuned on financial news)
    
    Process:
    1. Fetch financial news (NewsAPI, FinHub, RSS feeds)
    2. Tokenize + encode with FinBERT
    3. Classify sentiment (positive, neutral, negative)
    4. Aggregate by ticker + time window
    5. Output sentiment_score ∈ [-1, +1]
    """
    
    def __init__(self, model_name="ProsusAI/finbert"):
        # Load FinBERT + tokenizer
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    def get_sentiment(self, text: str) -> float:
        """
        Score sentiment ∈ [-1, +1].
        
        Returns:
        --------
        sentiment : float
            -1 (negative), 0 (neutral), +1 (positive)
        """
        pass
    
    def batch_sentiment(self, texts: List[str]) -> List[float]:
        """Batch inference (GPU optimized)."""
        pass

class NewsFetcher:
    """
    Fetch financial news for sentiment.
    
    Sources:
    - NewsAPI.org (headlines + summaries)
    - FinHub (financial news, earnings)
    - Reuters RSS
    - Bloomberg API (if available)
    """
    
    def fetch_news(self, ticker: str, window_days=7) -> List[Dict]:
        """
        Fetch recent news for ticker.
        
        Returns:
        --------
        [{
            'title': '...',
            'source': '...',
            'timestamp': datetime,
            'url': '...'
        }]
        """
        pass

class SentimentAggregator:
    """
    Aggregate news sentiment into signal.
    
    Method:
    1. Fetch N articles (last 7 days)
    2. Score each with FinBERT
    3. Aggregate: weighted mean (recent > old) or median
    4. Combine with previous signal (EMA smoothing)
    5. Output: sentiment_score + confidence + count
    """
    
    def aggregate_sentiment(self, ticker: str, window_days=7) -> Dict:
        """
        Aggregated sentiment with confidence.
        
        Returns:
        --------
        {
            'sentiment_score': 0.35,  # [-1, 1]
            'confidence': 0.78,        # [0, 1]
            'article_count': 12,
            'sources': ['Reuters', 'Bloomberg', ...]
        }
        """
        pass
```

**Audit References**:
- Finance Part 5 ML (sentiment patterns)

---

### **MODULE 3 : UNIVERSE SELECTOR (Real Market Cap)**

**File**: `universe/market_selector.py`

```python
class MarketSelector:
    """
    Select trading universe via fundamental + technical screens.
    
    Data sources:
    - FinanceDatabase (tickers + metadata)
    - FinvizElite (screener, fundamentals)
    - yfinance (market cap, volumes)
    
    Process:
    1. Start with S&P 500 / Russell 1000
    2. Filter by market cap (mid-cap to large-cap)
    3. Filter by liquidity (average volume > $5M)
    4. Filter by fundamentals (P/E, ROE, debt)
    5. Filter by technicals (above 200-SMA, not broken)
    6. Return top-N universe (typically 50-100)
    """
    
    def __init__(self, index="SP500", min_marketcap_usd=1e9, min_volume_usd=5e6):
        self.index = index
        self.min_marketcap = min_marketcap_usd
        self.min_volume = min_volume_usd
    
    def get_universe(self, n_assets=50) -> List[str]:
        """
        Get top-N assets by market cap + liquidity.
        
        Returns:
        --------
        List of tickers (sorted by market cap desc)
        """
        from financedatabase import Equities
        
        # Fetch equities
        equities = Equities()
        df_equities = equities.select()
        
        # Filter by market cap, volume, fundamentals
        filtered = df_equities[
            (df_equities['marketcap'] >= self.min_marketcap)
            & (df_equities['volume'] * df_equities['price'] >= self.min_volume)
        ]
        
        # Sort by market cap descending
        filtered = filtered.sort_values('marketcap', ascending=False)
        
        return filtered.index[:n_assets].tolist()

class FundamentalScreener:
    """
    Screen assets by fundamental metrics.
    
    Criteria:
    - P/E ratio (10-20)
    - ROE > 10%
    - Debt/Equity < 2
    - Dividend yield > 1% (optional)
    """
    
    def screen(self, tickers: List[str]) -> List[str]:
        """Filter tickers by fundamental quality."""
        pass

class TechnicalScreener:
    """
    Screen assets by technical criteria.
    
    Criteria:
    - Price > SMA200 (in uptrend)
    - RSI not extreme (30-70)
    - Not in strong downtrend
    """
    
    def screen(self, tickers: List[str]) -> List[str]:
        """Filter by technical health."""
        pass
```

**Audit References**:
- FinanceDatabase audit

---

### **MODULE 4 : PORTFOLIO OPTIMIZATION v2 (Riskfolio)**

**File**: `portfolio_optimization/riskfolio_wrapper.py`

```python
class RiskfolioOptimizer:
    """
    Production-grade portfolio optimization using Riskfolio-Lib.
    
    Supports:
    - 24 risk measures (CVaR, CDaR, EVaR, RLVaR, Semivariance, etc.)
    - Optimization models (Classic, Black-Litterman, Factor Model)
    - Hierarchical approaches (HRP, HERC, NCO)
    - Risk decomposition by asset + factor
    
    Workflow:
    1. Load prices + fundamentals
    2. Calculate expected returns (CAPM + sentiment adjustment)
    3. Estimate covariance (Ledoit-Wolf shrinkage)
    4. Optimize portfolio (NCO or CDaR-based)
    5. Decompose risk contributions
    6. Return weights + risk breakdown
    """
    
    def __init__(self, prices: pd.DataFrame, fundamentals: pd.DataFrame = None):
        self.prices = prices
        self.fundamentals = fundamentals
        self.portfolio = None
        self.hc_portfolio = None
    
    def optimize_nco(self, expected_returns=None, risk_measure='CVaR', **kwargs) -> Dict[str, float]:
        """
        Nested Clustered Optimization (best for diversification).
        
        Process:
        1. HRP clustering (hierarchical structure)
        2. Intra-cluster equal-weight (or risk-parity)
        3. Inter-cluster optimization (mean-variance on clusters)
        
        Returns:
        --------
        weights : Dict[str, float]
            {ticker: weight}
        """
        import riskfolio as rp
        
        self.hc_portfolio = rp.HCPortfolio(returns=self.prices)
        weights = self.hc_portfolio.optimize(
            model='NCO',
            rm=risk_measure,
            obj='Sharpe',
            cvxopt_sol=False
        )
        
        return weights
    
    def optimize_mean_cdar(self, expected_returns, risk_aversion=1) -> Dict[str, float]:
        """
        Mean-CDaR optimization (tail risk focus).
        
        Minimizes:
        - return - risk_aversion * CDaR_95
        """
        import riskfolio as rp
        
        self.portfolio = rp.Portfolio(returns=self.prices)
        self.portfolio.expected_returns = expected_returns
        
        weights = self.portfolio.optimization(
            model='Classic',
            rm='CDaR',
            obj='Utility',
            kelly=None,
            rf=0.02,
            l=risk_aversion
        )
        
        return weights
    
    def risk_decomposition(self, weights: Dict[str, float]) -> pd.DataFrame:
        """
        Decompose portfolio risk by asset and factor.
        
        Returns:
        --------
        attribution : DataFrame
            {asset: [marginal_contribution, % of total_risk]}
        """
        pass

class BlackLittermannModel:
    """
    Integrate investor views with market equilibrium.
    
    Views:
    - Absolute: "AAPL will return 15%"
    - Relative: "AAPL outperforms MSFT by 5%"
    
    Posterior returns = market_implied + views_adjustment
    """
    
    def __init__(self, cov_matrix: pd.DataFrame, market_caps: pd.Series):
        import riskfolio as rp
        self.bl = rp.BlackLittermanModel(
            cov_matrix=cov_matrix,
            pi="market",
            market_caps=market_caps
        )
    
    def add_view(self, view_type='absolute', **kwargs):
        """Add absolute or relative view."""
        pass
    
    def get_posterior_weights(self) -> Dict[str, float]:
        """Posterior portfolio incorporating views."""
        pass
```

**Audit References**:
- Riskfolio-Lib audit (59 risk measures, NCO, CDaR, BL)
- PyPortfolioOpt audit (covariance shrinkage)

---

### **MODULE 5 : FORECASTING (LSTM + Transformer)**

**File**: `forecasting/lstm_model.py`

```python
class LSTMPredictor:
    """
    Multi-asset LSTM predictor for 1-day ahead returns.
    
    Architecture:
    - 2-3 LSTM layers (256, 128 units)
    - Attention mechanism
    - Dense output layer → return prediction
    
    Training:
    - Lookback: 60 days
    - Batch size: 32-128
    - Optimizer: Adam
    - Loss: MSE
    - Epochs: 50-100 (with early stopping)
    
    Input shape: (batch, 60, n_assets)
    Output shape: (batch, n_assets)
    """
    
    def __init__(self, n_assets: int, lookback: int = 60, lstm_units: List[int] = [256, 128]):
        import tensorflow as tf
        
        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(lstm_units[0], return_sequences=True, input_shape=(lookback, n_assets)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.LSTM(lstm_units[1], return_sequences=False),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dense(n_assets)  # Return prediction
        ])
        
        model.compile(optimizer='adam', loss='mse')
        self.model = model
    
    def train(self, X_train, y_train, epochs=50, batch_size=32):
        """Train model."""
        self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            callbacks=[
                tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)
            ]
        )
    
    def predict(self, X_test) -> np.ndarray:
        """Predict 1-day ahead returns."""
        return self.model.predict(X_test)

class TransformerPredictor:
    """
    Transformer model for long-range dependencies.
    
    Advantages:
    - Captures multi-asset cross-correlations
    - Self-attention = interpretable weights
    - Better than LSTM for long sequences
    
    Architecture:
    - Multi-head self-attention (8 heads)
    - Feed-forward layers
    - Positional encoding
    - Output: return prediction
    """
    
    def __init__(self, n_assets: int, seq_len: int = 60, d_model: int = 64, n_heads: int = 8):
        import tensorflow as tf
        
        # Implementation using tf.keras.layers with attention
        # ... (details omitted for brevity)
        pass
```

**Audit References**:
- Finance Part 5 ML (LSTM patterns)

---

### **MODULE 6 : SIGNAL FUSION v2 (Advanced)**

**File**: `signal_generation_v2/multi_signal_fusion.py`

```python
class MultiSignalFusion:
    """
    Fuse 4 signal streams:
    1. Sentiment (FinBERT sentiment_score ∈ [-1, 1])
    2. Factors (IC-weighted composite from 114 factors)
    3. Technicals (RSI, MACD, ATR patterns)
    4. Forecast (LSTM/Transformer 1-day ahead return)
    
    Fusion method:
    - Normalize each to [-2, +2] range
    - Weight by historical Sharpe ratio
    - Compute ensemble signal
    - Output composite [-2, +2] signal
    
    Example:
    signal = 0.3 * sentiment_norm + 0.4 * factor_norm + 0.2 * technical_norm + 0.1 * forecast_norm
    """
    
    def __init__(self, sentiment_engine, feature_engineer, technical_calculator, lstm_predictor):
        self.sentiment = sentiment_engine
        self.features = feature_engineer
        self.technicals = technical_calculator
        self.lstm = lstm_predictor
    
    def fuse_signals(self, ticker: str, timestamp: datetime, weights: Dict[str, float] = None) -> float:
        """
        Compute fused signal [-2, +2].
        
        Args:
        -----
        ticker : str
        timestamp : datetime
        weights : dict or None
            Weights for [sentiment, factors, technicals, forecast]
            Default: [0.3, 0.4, 0.2, 0.1]
        
        Returns:
        --------
        signal : float ∈ [-2, +2]
        """
        # Get sentiment
        sentiment = self.sentiment.get_sentiment(ticker)  # [-1, 1]
        sentiment_norm = sentiment * 2  # [-2, 2]
        
        # Get factor signal
        factor_signal = self.features.get_factor_signal(ticker)  # [-2, 2] already
        
        # Get technical signal
        technical_signal = self.technicals.get_signal(ticker)  # [-2, 2]
        
        # Get forecast signal
        forecast_return = self.lstm.predict_next_day(ticker)  # raw return
        forecast_signal = forecast_return * 100  # Scale to [-2, 2] range
        
        # Weighted ensemble
        if weights is None:
            weights = {'sentiment': 0.3, 'factors': 0.4, 'technical': 0.2, 'forecast': 0.1}
        
        signal = (
            weights['sentiment'] * sentiment_norm +
            weights['factors'] * factor_signal +
            weights['technical'] * technical_signal +
            weights['forecast'] * forecast_signal
        )
        
        return np.clip(signal, -2, 2)

class RegimeDetection:
    """
    Detect market regime (bull, sideways, bear).
    
    Method:
    - Compute volatility regime (20-day rolling std)
    - Compute trend regime (price vs SMA200)
    - Hidden Markov Model (HMM) for regime states
    
    Output: regime ∈ {BULL, SIDEWAYS, BEAR}
    """
    
    def detect_regime(self, prices: pd.Series, vol_window: int = 20) -> str:
        """Detect market regime."""
        pass
```

---

### **MODULE 7 : PIPELINE v2 (Enhanced E2E)**

**File**: `pipeline_v2/ml_pipeline_v2.py`

```python
class MLTradingPipelineV2:
    """
    Enhanced Phase 5.5 pipeline integrating all 6 modules.
    
    Workflow:
    1. Universe Selection → 50 assets
    2. Data Loading → 3 years OHLCV
    3. Feature Engineering → 114 ML factors + IC validation
    4. Sentiment Analysis → FinBERT on news
    5. Forecasting → LSTM returns prediction
    6. Signal Fusion → Multi-stream ensemble
    7. Portfolio Optimization → Riskfolio NCO/CDaR
    8. Backtesting → Walk-forward validation
    9. Attribution → Risk/return decomposition
    10. Monitoring → Real-time Sharpe/drawdown tracking
    
    Production features:
    - Scheduled retraining (weekly/monthly)
    - Live monitoring dashboard
    - Alert system (model drift, risk limits)
    - Automatic rebalancing
    """
    
    def __init__(self, ...):
        self.selector = MarketSelector()
        self.feature_eng = FeatureEngineer()
        self.sentiment = FinBERTEngine()
        self.lstm = LSTMPredictor()
        self.optimizer = RiskfolioOptimizer()
        self.signal_fusion = MultiSignalFusion()
        # ... etc
    
    def run_daily(self):
        """Daily pipeline execution."""
        # 1. Select universe
        universe = self.selector.get_universe(n=50)
        
        # 2. Fetch data
        prices = fetch_ohlcv(universe)
        
        # 3. Compute features
        factors, ic_scores = self.feature_eng.compute_all_factors()
        
        # 4. Get sentiment
        sentiment = self.sentiment.aggregate_sentiment(universe)
        
        # 5. Predict returns
        forecast_returns = self.lstm.predict_next_day(universe)
        
        # 6. Fuse signals
        signals = self.signal_fusion.fuse_signals(universe, timestamp=datetime.now())
        
        # 7. Optimize portfolio
        weights = self.optimizer.optimize_nco(expected_returns=forecast_returns)
        
        # 8. Execute trades (only if signal > 0.5 or rebalancing due)
        if should_trade(weights, self.current_weights):
            execute_trades(weights)
        
        return {
            'weights': weights,
            'signals': signals,
            'performance': calculate_pnl()
        }
    
    def retrain_monthly(self):
        """Retrain all models monthly."""
        # Retrain LSTM
        self.lstm.train(new_data)
        
        # Recalibrate sentiment weights
        self.sentiment.evaluate_calibration()
        
        # Update factor IC scores
        ic_scores = self.feature_eng.recalculate_ic()
        
        # Validate attribution model
        self.attributor.validate_factors()
```

---

### **MODULE 8 : ADVANCED ATTRIBUTION v2**

**File**: `attribution_v2/factor_attribution.py`

```python
class FactorAttribution:
    """
    Decompose P&L into factor contributions.
    
    Method: Brinson attribution extended to factors
    
    Return = Σ factor_i × factor_exposure_i + idiosyncratic
    
    Where:
    - factor_i : factor return (momentum premium, value premium, etc.)
    - factor_exposure_i : portfolio exposure to factor
    
    Factors tracked:
    - Market factor (beta)
    - Sentiment factor (news-driven)
    - Momentum factor
    - Value factor
    - Quality factor
    - Volatility factor
    """
    
    def decompose_pnl(self, portfolio_returns, factor_returns, factor_exposures) -> pd.DataFrame:
        """
        Brinson-Fachler attribution.
        
        Returns:
        --------
        attribution : DataFrame
            {factor: [return_contrib, exposure, active_exposure]}
        """
        pass
```

---

## 📅 PHASE 5.5 TIMELINE

| Week | Modules | Deliverables |
|------|---------|--------------|
| W1 | 1, 2, 3 | Feature Engine (114), FinBERT, Universe Selector |
| W2 | 4, 5 | Riskfolio Integration, LSTM Training |
| W3 | 6, 7 | Signal Fusion, Pipeline v2 Integration |
| W4 | 8 + Tests | Advanced Attribution, Full Test Suite |
| W5 | Validation | Walk-forward backtest, Performance report |

---

## 📈 PHASE 5.5 EXPECTED IMPROVEMENTS

| Metric | Phase 5.4 | Phase 5.5 Target | Improvement |
|--------|-----------|-----------------|------------|
| Feature quality | Mock random | Real ML (114 validated factors) | +150% |
| Sentiment integration | Mock score | Real FinBERT ensemble | +200% |
| Optimization | Simple bridge | Riskfolio NCO + CDaR | +50% |
| Portfolio Sharpe | 0.9 | 1.5+ | +67% |
| Risk control | Basic stops | CVaR + factor risk limits | +100% |
| Scalability | Single asset | Multi-universe (50+ assets) | ∞ |

---

## ✅ QUALITY CHECKLIST

- [ ] 114 ML factors validated (IC > 0.05)
- [ ] FinBERT deployed + accuracy metrics
- [ ] Riskfolio optimization live
- [ ] LSTM/Transformer models trained
- [ ] Walk-forward backtest 95%+ pass rate
- [ ] Live monitoring dashboard operational
- [ ] Documentation complete (100% docstrings)
- [ ] Type hints 100%
- [ ] Test coverage 90%+
- [ ] Production readiness checklist approved

---

## 🎯 CONCLUSION

**Phase 5.5** transforms FinBot from **mock proof-of-concept** → **production-grade ML trading system** by replacing all mock components with real, audited implementations inspired by Riskfolio, Finance ML patterns, and PyPortfolioOpt.

**Timeline**: 5 weeks | **LOC**: +3000 | **Tests**: +60 | **Score target**: **9.95/10**
