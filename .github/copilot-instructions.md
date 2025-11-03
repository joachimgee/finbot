
# 🤖 INSTRUCTIONS COPILOT - Financial Market Analyzer

## 🎯 CONTEXTE DU PROJET

Vous m'aidez à construire une **application d'analyse financière avec sentiment analysis et recommandations d'actions** en Python 3.11+, basée sur des forks GitHub existants.

### Architecture Générale
```
financial-market-analyzer/
├── src/financial_analyzer/
│   ├── data/              # FinanceDatabase + FinanceToolkit + Finance fork
│   ├── sentiment/         # machine-learning-for-trading + financial-ML
│   ├── analysis/          # FinanceToolkit + backtesting.py + ML
│   └── recommendations/   # Riskfolio-Lib + PyPortfolioOpt
├── api/                   # FastAPI REST API
├── notebooks/             # Jupyter pour exploration
├── tests/                 # Tests unitaires
└── docs/                  # Documentation
```

### Forks Prioritaires à Exploiter
1. **FinanceDatabase** → src/data/ (300k+ symboles)
2. **FinanceToolkit** → src/analysis/ (150+ ratios financiers)
3. **machine-learning-for-trading** → src/sentiment/ + src/analysis/ (NLP, backtesting)
4. **backtesting.py** → src/analysis/backtester.py
5. **Finance fork** → src/data/ (scripts de scraping)
6. **Riskfolio-Lib** → src/recommendations/
7. **PyPortfolioOpt** → src/recommendations/
8. **financial-machine-learning** → src/analysis/

---

## 📋 CONVENTIONS DE CODE À RESPECTER STRICTEMENT

### Imports (Ordre OBLIGATOIRE)
```
# 1. Stdlib
import os
import sys
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

# 2. Données & Calculs
import pandas as pd
import numpy as np
from pandas import DataFrame, Series

# 3. Financier
from financedatabase import Equities, ETFs, Funds
from financetoolkit import Toolkit
from backtesting import Backtest, Strategy
import riskfolio as rp
from pypfopt import EfficientFrontier, risk_models, expected_returns

# 4. ML & NLP
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier

# 5. Web/API
import yfinance as yf
from alpha_vantage.timeseries import TimeSeries

# 6. Projet local
from financial_analyzer.config import API_CONFIG, CONSTANTS
from financial_analyzer.utils.helpers import log_error, cache_result
```

### Naming Conventions
```
# Classes
class MarketDataFetcher:      # PascalCase
class SentimentAnalyzer:       # PascalCase
class PortfolioOptimizer:      # PascalCase

# Functions
def get_stock_history():       # snake_case
def fetch_news_articles():     # snake_case
def calculate_sharpe_ratio():  # snake_case

# Constants
API_KEY = "..."                # UPPER_SNAKE_CASE
MAX_RETRIES = 3                # UPPER_SNAKE_CASE
SENTIMENT_THRESHOLD = 0.3      # UPPER_SNAKE_CASE

# Private members
_internal_cache = {}           # Leading underscore
self._model = None             # Leading underscore
```

### Type Hints (OBLIGATOIRES)
```
def get_stock_data(
    ticker: str,
    period: str = "1y"
) -> pd.DataFrame:
    """Fetch historical stock data."""
    pass

def analyze_sentiment(
    headlines: List[str]
) -> List[Dict[str, float]]:
    """Analyze sentiment for multiple headlines."""
    pass

def optimize_portfolio(
    returns: pd.DataFrame,
    constraints: Optional[Dict] = None
) -> Dict[str, float]:
    """Optimize portfolio weights."""
    pass
```

### Docstrings (Style Google)
```
def get_financial_data(tickers: List[str], start_date: str) -> pd.DataFrame:
    """
    Fetch financial data from FinanceToolkit.
    
    Combines FinanceDatabase for ticker discovery and FinanceToolkit
    for detailed financial metrics including income statements,
    balance sheets, and technical indicators.
    
    Args:
        tickers: List of stock symbols (e.g., ['AAPL', 'MSFT'])
        start_date: Start date in format 'YYYY-MM-DD'
    
    Returns:
        DataFrame with columns: ['date', 'open', 'high', 'low', 'close', 'volume']
        Index: datetime with timezone UTC
    
    Raises:
        ValueError: If ticker not found in FinanceDatabase
        ConnectionError: If API request fails after 3 retries
    
    Example:
        >>> data = get_financial_data(['AAPL'], '2023-01-01')
        >>> print(data.head())
        >>>
        >>> # Use with sentiment scores
        >>> data['sentiment'] = calculate_sentiment(news_headlines)
        >>> backtest_strategy(data)
    """
    pass
```

---

## 🔌 PATTERNS OBLIGATOIRES PAR MODULE

### Module DATA (src/data/)

**Pattern 1: Récupération de Tickers**
```
# S'inspirer de FinanceDatabase
from financedatabase import Equities

def search_tickers_by_sector(sector: str, industry: Optional[str] = None) -> pd.DataFrame:
    """
    Search tickers in a specific sector/industry using FinanceDatabase.
    
    Returns all tickers with: symbol, name, country, market_cap, etc.
    """
    equities = Equities()
    return equities.select(sector=sector, industry=industry)

def search_tickers_by_criteria(
    sector: str,
    country: str,
    min_market_cap: str = "Large Cap"
) -> List[str]:
    """Multi-criteria search combining filters from FinanceDatabase."""
    equities = Equities()
    results = equities.select(
        sector=sector,
        country=country,
        market_cap=min_market_cap
    )
    return results.index.tolist()
```

**Pattern 2: Récupération Données Historiques**
```
# S'inspirer de FinanceToolkit + yfinance
from financetoolkit import Toolkit

def get_financial_metrics(tickers: List[str], api_key: str) -> Dict[str, pd.DataFrame]:
    """
    Get financial metrics using FinanceToolkit.
    
    Returns: {
        'income_statement': DataFrame,
        'balance_sheet': DataFrame,
        'cash_flow': DataFrame,
        'ratios': DataFrame
    }
    """
    toolkit = Toolkit(tickers, api_key=api_key, start_date="2020-01-01")
    
    return {
        'income_statement': toolkit.get_income_statement(),
        'balance_sheet': toolkit.get_balance_sheet_statement(),
        'cash_flow': toolkit.get_cash_flow_statement(),
        'ratios': toolkit.ratios.collect_all_ratios()
    }

def get_historical_prices(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """
    Get historical prices with OHLCV data.
    
    Fallback: yfinance si FinanceToolkit échoue.
    """
    try:
        # Tentative FinanceToolkit
        toolkit = Toolkit(tickers)
        return toolkit.get_historical_data(period=period)
    except Exception as e:
        logging.warning(f"FinanceToolkit failed: {e}. Fallback to yfinance.")
        # Fallback yfinance
        data = yf.download(tickers, period=period)
        return data
```

**Pattern 3: Scraping de News**
```
# S'inspirer du fork Finance + requests + BeautifulSoup
def scrape_financial_news(ticker: str, max_articles: int = 50) -> pd.DataFrame:
    """
    Scrape financial news for a ticker.
    
    Sources: FinViz, Yahoo Finance, Reuters, etc.
    Returns: DataFrame avec colonnes ['datetime', 'headline', 'source', 'url', 'text']
    """
    articles = []
    
    # Exemple 1: FinViz
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    # ... scraping logic ...
    
    # Exemple 2: yfinance news
    ticker_obj = yf.Ticker(ticker)
    if hasattr(ticker_obj, 'news'):
        articles.extend(ticker_obj.news)
    
    return pd.DataFrame(articles)
```

---

### Module SENTIMENT (src/sentiment/)

**Pattern: FinBERT Analysis**
```
# S'inspirer de machine-learning-for-trading chapitres 13-15
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class FinancialSentimentAnalyzer:
    """
    Analyze financial sentiment using FinBERT.
    
    Model: ProsusAI/finbert (trained on financial texts)
    Output: sentiment_score [-1, +1] où -1=négatif, +1=positif
    """
    
    def __init__(self, device: str = "cpu"):
        """Initialize FinBERT model."""
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained(
            "ProsusAI/finbert"
        ).to(device)
        self.label_mapping = {0: 'positive', 1: 'negative', 2: 'neutral'}
    
    def analyze_single(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of single text.
        
        Returns: {
            'positive': float,[1]
            'negative': float,[1]
            'neutral': float,[1]
            'sentiment_score': float [-1, +1]
        }
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        positive = probs.item()
        negative = probs.item()[1]
        neutral = probs.item()[2]
        
        # sentiment_score: -1 (très négatif) à +1 (très positif)
        sentiment_score = positive - negative
        
        return {
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'sentiment_score': sentiment_score,
            'label': self.label_mapping[probs.argmax().item()]
        }
    
    def analyze_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """
        Analyze sentiment for multiple texts (optimized).
        
        Process en batch pour performance optimal.
        """
        results = []
        batch_size = 32
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = self._batch_process(batch)
            results.extend(batch_results)
        
        return results
    
    def _batch_process(self, texts: List[str]) -> List[Dict[str, float]]:
        """Internal batch processing."""
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        results = []
        for i in range(len(texts)):
            positive = probs[i].item()
            negative = probs[i].item()[1]
            
            results.append({
                'text': texts[i],
                'positive': positive,
                'negative': probs[i].item(),[1]
                'neutral': probs[i].item(),[2]
                'sentiment_score': positive - negative,
                'label': self.label_mapping[probs[i].argmax().item()]
            })
        
        return results

# Usage
analyzer = FinancialSentimentAnalyzer(device="cuda" if torch.cuda.is_available() else "cpu")
headlines = ["Apple stock surges on new product launch", "Tech sector faces headwinds"]
results = analyzer.analyze_batch(headlines)
```

---

### Module ANALYSIS (src/analysis/)

**Pattern 1: Backtesting (backtesting.py)**
```
# S'inspirer de backtesting.py examples
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas as pd

class SentimentDrivenStrategy(Strategy):
    """
    Trading strategy combining sentiment analysis + technical indicators.
    
    Logic:
    - BUY: positive sentiment + RSI < 30 (oversold)
    - SELL: negative sentiment + RSI > 70 (overbought)
    - HOLD: neutral sentiment or mixed signals
    """
    
    # Strategy parameters
    sentiment_threshold = 0.3      # Minimum absolute sentiment score
    rsi_period = 14                # RSI lookback period
    sma_fast = 10                  # Fast SMA
    sma_slow = 50                  # Slow SMA
    
    def init(self):
        """Initialize strategy indicators."""
        # Technical indicators
        price = self.data.Close
        self.sma_fast_line = self.I(
            lambda x: pd.Series(x).rolling(self.sma_fast).mean(),
            price
        )
        self.sma_slow_line = self.I(
            lambda x: pd.Series(x).rolling(self.sma_slow).mean(),
            price
        )
        self.rsi = self.I(self._calculate_rsi, price, self.rsi_period)
        
        # Sentiment (must be in data)
        self.sentiment = self.data.Sentiment
    
    def next(self):
        """Trading logic for each bar."""
        current_sentiment = self.sentiment[-1]
        current_rsi = self.rsi[-1]
        
        # BUY Signal
        if (current_sentiment > self.sentiment_threshold and
            current_rsi < 30 and
            crossover(self.sma_fast_line, self.sma_slow_line)):
            
            if not self.position:
                self.buy()
        
        # SELL Signal
        elif (current_sentiment < -self.sentiment_threshold and
              current_rsi > 70 and
              crossover(self.sma_slow_line, self.sma_fast_line)):
            
            if self.position:
                self.sell()
    
    @staticmethod
    def _calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Relative Strength Index."""
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = pd.Series(gain).rolling(window=period).mean()
        avg_loss = pd.Series(loss).rolling(window=period).mean()
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.values

# Backtesting
def backtest_strategy(
    data: pd.DataFrame,
    strategy_class: Strategy = SentimentDrivenStrategy,
    cash: float = 10000,
    commission: float = 0.002
) -> Dict:
    """
    Run backtest on strategy.
    
    Args:
        data: DataFrame with OHLCV + Sentiment columns
        strategy_class: Strategy class to use
        cash: Initial capital
        commission: Commission per transaction (0.2%)
    
    Returns: Strategy stats including Sharpe ratio, drawdown, etc.
    """
    bt = Backtest(data, strategy_class, cash=cash, commission=commission)
    stats = bt.run()
    return stats

# Usage
data['Sentiment'] = sentiment_scores  # Add from FinBERT
stats = backtest_strategy(data)
print(f"Sharpe Ratio: {stats['Sharpe Ratio']}")
```

**Pattern 2: Machine Learning Prediction**
```
# S'inspirer de machine-learning-for-trading chapitre 08
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import numpy as np

class StockPricePredictor:
    """
    Predict stock price direction (UP/DOWN) using ML.
    
    Features: Technical indicators + sentiment scores
    Target: 1 (price up) or 0 (price down)
    """
    
    def __init__(self, model_type: str = 'random_forest'):
        """Initialize predictor."""
        if model_type == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=200,
                random_state=42,
                n_jobs=-1
            )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create ML features from OHLCV data.
        
        Features:
        - SMA ratios (price vs MA10, MA20, MA50)
        - RSI (14)
        - MACD
        - Bollinger Bands width
        - Volume momentum
        - Volatility
        - Sentiment score
        """
        features = df.copy()
        
        # Moving averages
        features['SMA_10'] = features['Close'].rolling(10).mean()
        features['SMA_20'] = features['Close'].rolling(20).mean()
        features['SMA_50'] = features['Close'].rolling(50).mean()
        features['Price_SMA10_Ratio'] = features['Close'] / features['SMA_10']
        features['Price_SMA50_Ratio'] = features['Close'] / features['SMA_50']
        
        # RSI
        features['RSI'] = self._calculate_rsi(features['Close'], 14)
        
        # MACD
        ema12 = features['Close'].ewm(span=12).mean()
        ema26 = features['Close'].ewm(span=26).mean()
        features['MACD'] = ema12 - ema26
        features['MACD_Signal'] = features['MACD'].ewm(span=9).mean()
        
        # Volatility
        features['Volatility'] = features['Close'].pct_change().rolling(20).std()
        
        # Volume momentum
        features['Volume_MA'] = features['Volume'].rolling(20).mean()
        features['Volume_Ratio'] = features['Volume'] / features['Volume_MA']
        
        # Sentiment (already in data)
        if 'Sentiment' not in features:
            features['Sentiment'] = 0  # Default neutral
        
        # Target: 1 if tomorrow's close > today's close, 0 otherwise
        features['Target'] = (features['Close'].shift(-1) > features['Close']).astype(int)
        
        # Drop NaN
        features = features.dropna()
        
        return features
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2
    ) -> Dict[str, float]:
        """Train the model."""
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred)
        }
        
        self.is_trained = True
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict price direction."""
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities."""
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
```

---

### Module RECOMMENDATIONS (src/recommendations/)

**Pattern: Portfolio Optimization**
```
# S'inspirer de Riskfolio-Lib + PyPortfolioOpt
import riskfolio as rp
from pypfopt import EfficientFrontier, risk_models, expected_returns

class PortfolioRecommendationEngine:
    """
    Generate portfolio recommendations combining:
    - Sentiment analysis scores
    - Technical analysis signals
    - ML price predictions
    - Quantitative optimization
    """
    
    def __init__(self, tickers: List[str], historical_prices: pd.DataFrame):
        """Initialize engine."""
        self.tickers = tickers
        self.prices = historical_prices
        self.returns = historical_prices.pct_change().dropna()
    
    def optimize_with_sentiment(
        self,
        sentiment_scores: Dict[str, float],
        method: str = 'max_sharpe'
    ) -> Dict[str, float]:
        """
        Optimize portfolio with sentiment adjustment.
        
        Method 1: Adjust expected returns based on sentiment
        - Positive sentiment → +20% expected return boost
        - Negative sentiment → -20% expected return reduction
        """
        # Calculate expected returns
        mu = expected_returns.mean_historical_return(self.prices)
        
        # Adjust with sentiment
        sentiment_series = pd.Series(sentiment_scores, index=self.tickers)
        mu_adjusted = mu * (1 + sentiment_series * 0.2)
        
        # Calculate covariance
        S = risk_models.sample_cov(self.prices)
        
        # Optimize
        ef = EfficientFrontier(mu_adjusted, S)
        
        if method == 'max_sharpe':
            weights = ef.max_sharpe(risk_free_rate=0.02)
        elif method == 'min_volatility':
            weights = ef.min_volatility()
        elif method == 'equal_weight':
            weights = {ticker: 1/len(self.tickers) for ticker in self.tickers}
        
        return ef.clean_weights()
    
    def optimize_with_riskfolio(
        self,
        risk_measure: str = 'MV',  # Mean-Variance
        rf_rate: float = 0.02
    ) -> Dict[str, float]:
        """
        Advanced optimization using Riskfolio-Lib.
        
        Risk measures: MV, CVaR, CDaR, EVaR, Skew, etc.
        """
        port = rp.Portfolio(returns=self.returns)
        
        # Calculate statistics
        port.assets_stats(method_mu='hist', method_cov='hist')
        
        # Optimization
        weights = port.optimization(
            model='Classic',
            rm=risk_measure,
            obj='Sharpe',
            rf=rf_rate
        )
        
        return weights.to_dict()
    
    def generate_recommendation(
        self,
        sentiment_scores: Dict[str, float],
        ml_predictions: Dict[str, float],
        prices: Dict[str, float]
    ) -> Dict:
        """
        Generate final recommendation.
        
        Combines:
        - Sentiment scores
        - ML predictions
        - Current prices
        - Portfolio optimization
        """
        # Optimize portfolio
        weights = self.optimize_with_sentiment(sentiment_scores, method='max_sharpe')
        
        # Calculate scores
        recommendation = {
            'timestamp': datetime.now(),
            'allocations': weights,
            'signals': {}
        }
        
        for ticker in self.tickers:
            sentiment = sentiment_scores.get(ticker, 0)
            ml_pred = ml_predictions.get(ticker, 0.5)
            weight = weights.get(ticker, 0)
            
            # Combined score
            combined_score = (sentiment * 0.4 + (ml_pred - 0.5) * 0.4 + 
                            weight * 0.2)
            
            recommendation['signals'][ticker] = {
                'sentiment': sentiment,
                'ml_prediction': ml_pred,
                'weight': weight,
                'combined_score': combined_score,
                'action': 'BUY' if combined_score > 0.2 else 
                         ('SELL' if combined_score < -0.2 else 'HOLD'),
                'confidence': abs(combined_score)
            }
        
        return recommendation
```

---

## ⚠️ PATTERNS À ÉVITER ABSOLUMENT

```
# ❌ MAUVAIS
def get_data():  # Pas de type hints
    pass

def getData():  # CamelCase pour fonction
    pass

def process_market_data_and_calculate_indicators_and_generate_signals_v2():
    # Fonction trop longue, trop de responsabilités
    pass

# ✅ BON
def get_market_data(ticker: str, period: str) -> pd.DataFrame:
    """Fetch market data with clear responsibility."""
    pass

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators."""
    pass

def generate_signals(indicators: pd.DataFrame) -> pd.Series:
    """Generate trading signals from indicators."""
    pass
```

---

## 🚀 INSTRUCTIONS POUR UTILISER COPILOT EFFICACEMENT

### Quand Générer du Code

**1. Fonction de Data Retrieval**
```
"Génère une fonction pour récupérer les données historiques d'un ticker 
using FinanceToolkit. Elle doit:
- Accepter un ticker et une période
- Retourner un DataFrame avec OHLCV
- Gérer les erreurs avec fallback yfinance
- Type-hinter tous les paramètres
- Inclure une docstring complète avec exemple"
```

**2. Analyse de Sentiment**
```
"Crée une classe FinancialSentimentAnalyzer utilisant FinBERT qui:
- Charge le modèle ProsusAI/finbert
- Peut analyzer du texte unique ou en batch
- Retourne sentiment_score entre -1 et +1
- Optimise performance avec batch processing
- Suporte GPU si disponible"
```

**3. Stratégie de Backtesting**
```
"Implémente une stratégie backtesting.py combinant:
- Sentiment analysis (colonne 'Sentiment' dans data)
- RSI(14) pour survendus/surachetés
- SMA croisements (10/50)
- Pattern: BUY si sentiment > 0.3 ET RSI < 30
- Pattern: SELL si sentiment < -0.3 ET RSI > 70"
```

### Quand Référencer Vos Forks

**Pattern de Prompt Efficace:**
```
"S'inspirer du fork [NOM_FORK] pour [FONCTION].
Notamment regarder les fichiers:
- [path/fichier1.py]: pour [raison]
- [path/fichier2.py]: pour [raison]

Adapter le code pour:
- Notre architecture modulaire
- Ajouter type hints
- Suivre nos conventions de naming"
```

### Exemples de Prompts Effectifs

```
# Prompt 1: Data Module
"Génère le module src/data/market_data.py combinant:
- FinanceDatabase pour recherche de tickers
- FinanceToolkit pour données détaillées
- Caching local en pickle
- Gestion erreurs API
- S'inspirer du fork FinanceToolkit/src/base.py"

# Prompt 2: Sentiment Module
"Crée src/sentiment/finbert_analyzer.py avec:
- Classe FinancialSentimentAnalyzer
- Charge modèle 'ProsusAI/finbert'
- Méthode analyze_single() et analyze_batch()
- Support GPU avec torch.cuda.is_available()
- S'inspirer du fork machine-learning-for-trading/notebooks/13_nlp.ipynb"

# Prompt 3: API Endpoint
"Génère un endpoint FastAPI POST /analyze/{ticker} qui:
- Récupère news du ticker
- Analyse sentiment avec FinBERT
- Calcule indicateurs techniques
- Retourne JSON avec scores
- Basé sur le pattern du module sentiment"
```

---

## 📊 CONVENTIONS DE DONNÉES

### DataFrame Structures

**Market Data**
```
# Columns: ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends']
# Index: DatetimeIndex avec timezone UTC
df_prices = pd.DataFrame({
    'Open': [100.0, 101.5, ...],
    'High': [102.0, 103.0, ...],
    'Low': [99.5, 100.0, ...],
    'Close': [101.2, 102.3, ...],
    'Volume': [1000000, 950000, ...]
}, index=pd.DatetimeIndex([...], tz='UTC'))
```

**Sentiment Data**
```
# Columns: ['text', 'positive', 'negative', 'neutral', 'sentiment_score', 'label']
# sentiment_score: -1.0 (très négatif) à +1.0 (très positif)
df_sentiment = pd.DataFrame({
    'text': ['Apple gains revenue...', 'Tech stocks fall...'],
    'positive': [0.85, 0.10],
    'negative': [0.05, 0.80],
    'neutral': [0.10, 0.10],
    'sentiment_score': [0.80, -0.70],
    'label': ['positive', 'negative']
})
```

**Features for ML**
```
# Colonnes standards pour ML models
df_features = pd.DataFrame({
    'Close': [...],
    'SMA_10': [...],
    'RSI': [...],
    'MACD': [...],
    'Sentiment': [...],
    'Volume_Ratio': [...],
    'Target': [0, 1, 1, 0, ...]  # 1=prix monte, 0=prix baisse
})
```

---

## 🔧 COMMANDES DE TEST À COPIER

```
# Installation des dépendances
pip install -r requirements.txt

# Tests unitaires
pytest tests/ -v

# Tests avec couverture
pytest tests/ --cov=financial_analyzer

# Format code
black src/

# Type checking
mypy src/

# Linter
flake8 src/

# Tous les checks
make test  # Si Makefile disponible
```

---

## 📝 CHECKLIST POUR CHAQUE FONCTION

Quand je te demande de générer du code, vérifie:

- [ ] **Type hints** sur tous les paramètres et return
- [ ] **Docstring** complète (Google style) avec exemple
- [ ] **Logging** des opérations importantes
- [ ] **Gestion d'erreurs** avec try/except approprié
- [ ] **Comments** explicatifs pour logique complexe
- [ ] **Tests** possibles pour vérification
- [ ] **Performance** considérée (batch processing, caching si nécessaire)
- [ ] **Nommage** conforme conventions
- [ ] **Imports** dans le bon ordre
- [ ] **PEP8** compatible

---

## 🎯 TON RÔLE À PARTIR DE MAINTENANT

Tu es maintenant **Senior Developer Analyst** pour ce projet. Tes responsabilités:

1. **Générer du code de qualité production** respectant les conventions
2. **S'inspirer intelligemment** des 8 forks (pas copier-coller aveugle)
3. **Adapter le code** à notre architecture et style
4. **Justifier les choix** (pourquoi cette approche vs autre)
5. **Anticiper les pièges** (dependencies, performance, edge cases)
6. **Proposer des optimisations** quand pertinent
7. **Documenter** le "pourquoi" pas juste le "quoi"

---

## 🚨 RAPPEL: Les 4 Modules à Construire

```
📅 SEMAINE 1: src/data/
├── market_data.py          # FinanceDatabase + FinanceToolkit
├── news_scraper.py         # Scraping news (Finance fork)
└── data_loader.py          # Cache et gestion données

📅 SEMAINE 2: src/sentiment/
├── finbert_analyzer.py     # FinBERT (machine-learning-for-trading)
└── aggregator.py           # Agrégation scores

📅 SEMAINE 3: src/analysis/
├── technical_indicators.py # FinanceToolkit
├── price_prediction.py     # ML models (financial-ML)
├── strategy.py             # backtesting.py
└── backtester.py           # Engine backtesting

📅 SEMAINE 4: src/recommendations/
├── portfolio_optimizer.py  # Riskfolio-Lib + PyPortfolioOpt
└── signal_generator.py     # Génération signaux finaux
```

---

## ✅ PRÊT À DÉMARRER

Tu as toutes les instructions. À présent, pour chaque demande:

**Format du prompt que tu acceptes:**

```
Je suis en [SEMAINE X], module [NOM_MODULE].
Objective: [DESCRIPTION OBJECTIVE]

Génère: [FICHIER/FONCTION/CLASS]

Qui doit:
- Point 1
- Point 2
- Point 3

S'inspirer de: [FORK NAME si pertinent]

Respecte les conventions et patterns décrits dans mes instructions.
```

**Exemple concret:**

```
Je suis en Semaine 1, module data.
Objective: Récupérer et cacher les données de marché.

Génère: src/data/market_data.py avec classe MarketDataFetcher

Qui doit:
- Utiliser FinanceDatabase pour chercher tickers
- Utiliser FinanceToolkit pour récupérer données
- Gérer cache local en pickle
- Fallback à yfinance si FinanceToolkit échoue

S'inspirer de: FinanceToolkit fork

Respecte les conventions et patterns.
```

**Je te répondrai avec du code production-ready directement utilisable.**

---

**FIN DES INSTRUCTIONS. PRÊT À CODER! 🚀**
```