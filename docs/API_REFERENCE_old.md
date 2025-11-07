# 📚 API Reference - FinBot v2.0

## 📋 Table des matières

1. [Config Module](#config-module)
2. [Utils Module](#utils-module)
3. [Data Module](#data-module)
4. [Features Module](#features-module)
5. [Strategies Module](#strategies-module)
6. [Backtesting Module](#backtesting-module)
7. [Portfolio Module](#portfolio-module)
8. [Risk Module](#risk-module)
9. [ML Module](#ml-module)
10. [Analysis Module](#analysis-module)
11. [API Module](#api-module)
12. [Dashboard Module](#dashboard-module)

---

## Config Module

### `config.py`

Configuration centralisée de l'application.

#### Constants

##### `API_KEYS`
```python
API_KEYS: Dict[str, Optional[str]]
```
Dictionnaire des clés API pour services externes.

**Clés disponibles** :
- `'financial_modeling_prep'` : FinanceToolkit API
- `'alpha_vantage'` : Alpha Vantage API
- `'polygon'` : Polygon.io API
- `'news_api'` : NewsAPI.org API

**Exemple** :
```python
from financial_analyzer.config import API_KEYS

fmp_key = API_KEYS['financial_modeling_prep']
```

##### `TRADING_CONFIG`
```python
TRADING_CONFIG: Dict[str, Union[float, int]]
```
Configuration par défaut pour le trading.

**Paramètres** :
- `commission` : 0.002 (0.2%)
- `slippage_bps` : 5 (5 basis points)
- `initial_capital` : 10000
- `risk_free_rate` : 0.02 (2%)

**Exemple** :
```python
from financial_analyzer.config import TRADING_CONFIG

commission = TRADING_CONFIG['commission']
```

##### `ML_CONFIG`
```python
ML_CONFIG: Dict[str, Union[float, int]]
```
Configuration pour Machine Learning.

**Paramètres** :
- `test_size` : 0.2
- `n_splits` : 5 (TimeSeriesSplit)
- `random_state` : 42
- `n_jobs` : -1 (tous les CPU)

##### `CACHE_CONFIG`
```python
CACHE_CONFIG: Dict[str, Union[bool, str, int]]
```
Configuration du cache.

**Paramètres** :
- `enabled` : True
- `backend` : 'disk' ou 'redis'
- `ttl` : 3600 (1 heure)

---

## Utils Module

### `helpers.py`

Fonctions utilitaires transverses.

#### `get_logger(name: str) -> logging.Logger`

Crée un logger avec rotation de fichiers.

**Args** :
- `name` : Nom du logger (généralement `__name__`)

**Returns** :
- Logger configuré avec handlers console et fichier

**Exemple** :
```python
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)
logger.info("Début du traitement")
```

#### `validate_ohlcv(df: pd.DataFrame) -> bool`

Valide un DataFrame OHLCV.

**Args** :
- `df` : DataFrame à valider

**Returns** :
- `True` si valide, sinon lève une exception

**Raises** :
- `TypeError` : Si df n'est pas un DataFrame
- `ValueError` : Si colonnes OHLCV manquantes
- `ValueError` : Si index n'est pas DatetimeIndex
- `ValueError` : Si NaN présents

**Exemple** :
```python
from financial_analyzer.utils.helpers import validate_ohlcv

try:
    validate_ohlcv(prices_df)
    print("DataFrame valide")
except ValueError as e:
    print(f"Erreur validation: {e}")
```

#### `ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame`

Convertit l'index en DatetimeIndex avec timezone UTC.

**Args** :
- `df` : DataFrame avec index datetime-like

**Returns** :
- DataFrame avec DatetimeIndex (UTC)

**Exemple** :
```python
from financial_analyzer.utils.helpers import ensure_datetime_index

df = ensure_datetime_index(df)
assert isinstance(df.index, pd.DatetimeIndex)
```

#### `resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame`

Resample un DataFrame OHLCV.

**Args** :
- `df` : DataFrame OHLCV (D, H, M)
- `freq` : Fréquence cible ('D', 'W', 'M')

**Returns** :
- DataFrame resamplé avec agrégations correctes :
  - Open : premier
  - High : max
  - Low : min
  - Close : dernier
  - Volume : sum

**Exemple** :
```python
from financial_analyzer.utils.helpers import resample_ohlcv

daily_df = ...  # Daily OHLCV
weekly_df = resample_ohlcv(daily_df, 'W')
```

### `cache.py`

Gestion du cache disque/Redis.

#### `@cache_result(ttl: int = 3600)`

Décorateur pour mettre en cache les résultats de fonctions.

**Args** :
- `ttl` : Time-to-live en secondes (défaut 1 heure)

**Exemple** :
```python
from financial_analyzer.utils.cache import cache_result

@cache_result(ttl=7200)
def expensive_computation(ticker: str) -> pd.DataFrame:
    # Calcul coûteux...
    return result
```

#### `class CacheManager`

Gestionnaire de cache avec invalidation.

##### `__init__(backend: str = 'disk', ttl: int = 3600)`

**Args** :
- `backend` : 'disk' ou 'redis'
- `ttl` : Time-to-live par défaut

##### `get(key: str) -> Optional[Any]`

Récupère une valeur du cache.

##### `set(key: str, value: Any, ttl: Optional[int] = None)`

Stocke une valeur dans le cache.

##### `invalidate(key: str)`

Invalide une entrée du cache.

##### `clear()`

Vide tout le cache.

**Exemple** :
```python
from financial_analyzer.utils.cache import CacheManager

cache = CacheManager(backend='disk')
cache.set('aapl_prices', df, ttl=3600)
cached_df = cache.get('aapl_prices')
```

### `validators.py`

Validation de DataFrames financiers.

#### `validate_prices(df: pd.DataFrame) -> None`

Valide un DataFrame de prix.

**Args** :
- `df` : DataFrame avec colonnes OHLCV

**Raises** :
- `TypeError` : Si type incorrect
- `ValueError` : Si colonnes manquantes, NaN, index invalide

#### `validate_returns(returns: pd.Series) -> None`

Valide une Series de returns.

**Args** :
- `returns` : Series de returns

**Raises** :
- `ValueError` : Si NaN, inf, ou hors range [-1, inf]

#### `validate_weights(weights: Dict[str, float]) -> None`

Valide des poids de portfolio.

**Args** :
- `weights` : Dictionnaire {ticker: poids}

**Raises** :
- `ValueError` : Si somme != 1, ou poids hors [0, 1]

**Exemple** :
```python
from financial_analyzer.utils.validators import validate_weights

weights = {'AAPL': 0.5, 'MSFT': 0.3, 'GOOGL': 0.2}
validate_weights(weights)  # OK

weights = {'AAPL': 0.5, 'MSFT': 0.6}  # Somme = 1.1
validate_weights(weights)  # Raises ValueError
```

---

## Data Module

### `universe.py`

Wrapper FinanceDatabase pour sélection de symboles.

#### `class UniverseSelector`

##### `__init__()`

Initialise le sélecteur avec FinanceDatabase.

##### `select_equities(...) -> List[str]`

```python
def select_equities(
    self,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    market_cap: Optional[str] = None,
    country: Optional[str] = None,
    exchange: Optional[str] = None
) -> List[str]:
```

Sélectionne des actions selon critères.

**Args** :
- `sector` : Secteur (ex: 'Technology', 'Healthcare')
- `industry` : Industrie (ex: 'Software', 'Biotechnology')
- `market_cap` : 'Large Cap', 'Mid Cap', 'Small Cap'
- `country` : Code pays (ex: 'US', 'FR')
- `exchange` : Bourse (ex: 'NASDAQ', 'NYSE')

**Returns** :
- Liste de tickers (ex: `['AAPL', 'MSFT', 'GOOGL']`)

**Exemple** :
```python
from financial_analyzer.data.universe import UniverseSelector

selector = UniverseSelector()
tech_stocks = selector.select_equities(
    sector='Technology',
    market_cap='Large Cap',
    country='US'
)
print(f"Found {len(tech_stocks)} tech stocks")
```

##### `select_etfs(...) -> List[str]`

```python
def select_etfs(
    self,
    category: Optional[str] = None,
    family: Optional[str] = None
) -> List[str]:
```

Sélectionne des ETFs.

**Args** :
- `category` : Catégorie (ex: 'Equity', 'Bond', 'Commodity')
- `family` : Famille (ex: 'iShares', 'Vanguard', 'SPDR')

**Returns** :
- Liste de tickers ETF (ex: `['SPY', 'QQQ', 'IWM']`)

**Exemple** :
```python
equity_etfs = selector.select_etfs(category='Equity', family='Vanguard')
```

##### `select_funds(...) -> List[str]`

```python
def select_funds(
    self,
    fund_type: Optional[str] = None,
    category: Optional[str] = None,
    family: Optional[str] = None
) -> List[str]:
```

Sélectionne des fonds mutuels.

**Args** :
- `fund_type` : Type de fonds (ex: 'Mutual Fund', 'Index Fund', 'Money Market')
- `category` : Catégorie (ex: 'Large Blend', 'International Stock', 'Bond')
- `family` : Famille de fonds (ex: 'Fidelity', 'T. Rowe Price', 'American Funds')

**Returns** :
- Liste de tickers de fonds (ex: `['VFIAX', 'FXAIX', 'SWPPX']`)

**Exemple** :
```python
index_funds = selector.select_funds(
    fund_type='Index Fund',
    category='Large Blend',
    family='Vanguard'
)
```

##### `select_crypto(...) -> List[str]`

```python
def select_crypto(
    self,
    currency: Optional[str] = None,
    category: Optional[str] = None,
    min_market_cap: Optional[float] = None
) -> List[str]:
```

Sélectionne des cryptomonnaies.

**Args** :
- `currency` : Devise de cotation (ex: 'USD', 'EUR', 'BTC')
- `category` : Catégorie (ex: 'DeFi', 'Exchange', 'Smart Contract', 'Stablecoin')
- `min_market_cap` : Capitalisation boursière minimale en USD

**Returns** :
- Liste de symboles crypto (ex: `['BTC-USD', 'ETH-USD', 'BNB-USD']`)

**Exemple** :
```python
major_crypto = selector.select_crypto(
    currency='USD',
    min_market_cap=1_000_000_000  # 1 milliard USD
)
```

##### `select_indices(...) -> List[str]`

```python
def select_indices(
    self,
    market: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None
) -> List[str]:
```

Sélectionne des indices boursiers.

**Args** :
- `market` : Marché (ex: 'US', 'Europe', 'Asia', 'Emerging')
- `category` : Catégorie (ex: 'Broad Market', 'Sector', 'Size', 'Style')
- `region` : Région géographique (ex: 'North America', 'Europe', 'Asia-Pacific')

**Returns** :
- Liste de symboles d'indices (ex: `['^GSPC', '^DJI', '^IXIC']`)

**Exemple** :
```python
us_indices = selector.select_indices(
    market='US',
    category='Broad Market'
)
# Retourne ['^GSPC' (S&P 500), '^DJI' (Dow Jones), '^IXIC' (NASDAQ)]
```

---

### `market_data.py`
- `category` : Catégorie (ex: 'Equity', 'Bond', 'Commodity')
- `family` : Famille (ex: 'iShares', 'Vanguard', 'SPDR')

**Returns** :
- Liste de tickers ETF

##### `select_funds(...) -> List[str]`

Sélectionne des fonds mutuels.

##### `select_crypto(...) -> List[str]`

Sélectionne des cryptomonnaies.

##### `get_all_symbols(asset_class: str) -> List[str]`

Récupère tous les symboles d'une classe d'actifs.

**Args** :
- `asset_class` : 'equities', 'etfs', 'funds', 'crypto', 'indices'

---

### `market_data.py`

Wrapper FinanceToolkit + yfinance pour données OHLCV.

#### `class MarketDataFetcher`

##### `__init__(api_key: Optional[str] = None)`

**Args** :
- `api_key` : Clé API FinanceToolkit (optionnelle, utilise config si None)

##### `get_historical_data(...) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]`

```python
def get_historical_data(
    self,
    tickers: Union[str, List[str]],
    start_date: str,
    end_date: str,
    interval: str = '1d'
) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
```

Récupère données historiques OHLCV.

**Args** :
- `tickers` : Ticker unique ou liste
- `start_date` : Date début ('YYYY-MM-DD')
- `end_date` : Date fin ('YYYY-MM-DD')
- `interval` : '1d', '1h', '5m', etc.

**Returns** :
- DataFrame (single ticker) ou Dict[ticker, DataFrame] (multi-ticker)
- Format : colonnes ['Open', 'High', 'Low', 'Close', 'Volume'], index DatetimeIndex

**Raises** :
- `ValueError` : Si ticker invalide ou dates incorrectes
- `ConnectionError` : Si API inaccessible

**Exemple** :
```python
from financial_analyzer.data.market_data import MarketDataFetcher

fetcher = MarketDataFetcher()

# Single ticker
aapl = fetcher.get_historical_data('AAPL', '2020-01-01', '2023-12-31')

# Multi-ticker
tickers = ['AAPL', 'MSFT', 'GOOGL']
data = fetcher.get_historical_data(tickers, '2020-01-01', '2023-12-31')
# data['AAPL'] -> DataFrame AAPL
# data['MSFT'] -> DataFrame MSFT
```

##### `get_intraday_data(...) -> pd.DataFrame`

Récupère données intraday (haute fréquence).

**Args** :
- `tickers` : Ticker(s)
- `interval` : '1m', '5m', '15m', '30m', '1h'
- `period` : '1d', '5d', '1mo'

##### `get_latest_price(tickers: Union[str, List[str]]) -> Dict[str, float]`

Récupère prix actuel (temps réel).

**Returns** :
- Dict {ticker: prix}

**Exemple** :
```python
prices = fetcher.get_latest_price(['AAPL', 'MSFT'])
# {'AAPL': 178.50, 'MSFT': 372.80}
```

##### `validate_ohlcv(df: pd.DataFrame) -> bool`

Valide format OHLCV d'un DataFrame.

---

### `fundamentals.py`

Wrapper FinanceToolkit pour ratios financiers.

#### `class FundamentalsProvider`

##### `__init__(api_key: Optional[str] = None)`

##### `get_all_ratios(...) -> pd.DataFrame`

```python
def get_all_ratios(
    self,
    tickers: Union[str, List[str]],
    period: str = 'quarterly'
) -> pd.DataFrame:
```

Récupère 150+ ratios financiers.

**Args** :
- `tickers` : Ticker(s)
- `period` : 'quarterly' ou 'annual'

**Returns** :
- DataFrame multi-index (ticker × date × ratio)
- 150+ colonnes : PE, PB, ROE, ROA, Debt/Equity, Current Ratio, Quick Ratio, Gross Margin, Operating Margin, Net Margin, Asset Turnover, Inventory Turnover, etc.

**Exemple** :
```python
from financial_analyzer.data.fundamentals import FundamentalsProvider

provider = FundamentalsProvider()
ratios = provider.get_all_ratios(['AAPL', 'MSFT'], period='quarterly')

# Accès à un ratio spécifique
aapl_pe = ratios.loc[('AAPL', slice(None)), 'PE']
```

##### `get_income_statement(...) -> pd.DataFrame`

Récupère compte de résultat.

##### `get_balance_sheet(...) -> pd.DataFrame`

Récupère bilan.

##### `get_cash_flow(...) -> pd.DataFrame`

Récupère tableau de flux de trésorerie.

##### `get_financial_metrics(...) -> pd.DataFrame`

Récupère métriques financières (EPS, Revenue, EBITDA, etc.).

---

### `alternative.py`

Scrapers pour données alternatives (Finance fork).

#### `class AlternativeDataProvider`

##### `__init__()`

##### `get_news_sentiment(...) -> pd.DataFrame`

```python
def get_news_sentiment(
    self,
    ticker: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
```

Récupère sentiment des news.

**Args** :
- `ticker` : Ticker
- `start_date` : Date début
- `end_date` : Date fin

**Returns** :
- DataFrame avec colonnes :
  - `date` : DatetimeIndex
  - `headline` : Titre de l'article
  - `source` : Source (Reuters, Bloomberg, etc.)
  - `sentiment_score` : Score [-1, 1]
  - `positive` : Probabilité sentiment positif [0, 1]
  - `negative` : Probabilité sentiment négatif [0, 1]
  - `neutral` : Probabilité sentiment neutre [0, 1]

**Exemple** :
```python
from financial_analyzer.data.alternative import AlternativeDataProvider

provider = AlternativeDataProvider()
news = provider.get_news_sentiment('AAPL', '2023-01-01', '2023-12-31')
avg_sentiment = news['sentiment_score'].mean()
```

##### `get_social_sentiment(...) -> pd.DataFrame`

Récupère sentiment des réseaux sociaux.

**Args** :
- `ticker` : Ticker
- `source` : 'twitter', 'reddit', 'stocktwits'

##### `get_insider_trades(...) -> pd.DataFrame`

Récupère transactions des insiders.

##### `get_analyst_ratings(...) -> pd.DataFrame`

Récupère recommandations des analystes.

---

## Features Module

### `technical.py`

Indicateurs techniques (Finance fork - 40+ indicateurs).

#### Trend Indicators

##### `calculate_sma(prices: pd.Series, window: int) -> pd.Series`

Simple Moving Average.

**Args** :
- `prices` : Series de prix (Close)
- `window` : Période (ex: 50, 200)

**Returns** :
- Series SMA

**Exemple** :
```python
from financial_analyzer.features.technical import calculate_sma

sma_50 = calculate_sma(df['Close'], window=50)
sma_200 = calculate_sma(df['Close'], window=200)

# Golden Cross
golden_cross = (sma_50 > sma_200) & (sma_50.shift(1) <= sma_200.shift(1))
```

##### `calculate_ema(prices: pd.Series, window: int) -> pd.Series`

Exponential Moving Average.

##### `calculate_macd(...) -> pd.DataFrame`

```python
def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> pd.DataFrame:
```

Moving Average Convergence Divergence.

**Returns** :
- DataFrame avec colonnes ['macd', 'signal', 'histogram']

**Exemple** :
```python
from financial_analyzer.features.technical import calculate_macd

macd_df = calculate_macd(df['Close'])
buy_signal = (macd_df['macd'] > macd_df['signal']) & \
             (macd_df['macd'].shift(1) <= macd_df['signal'].shift(1))
```

##### `calculate_adx(prices: pd.DataFrame, window: int = 14) -> pd.Series`

Average Directional Index (force de la tendance).

#### Momentum Indicators

##### `calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series`

Relative Strength Index.

**Returns** :
- Series RSI [0, 100]

**Exemple** :
```python
from financial_analyzer.features.technical import calculate_rsi

rsi = calculate_rsi(df['Close'], window=14)
oversold = rsi < 30
overbought = rsi > 70
```

##### `calculate_stochastic(...) -> pd.DataFrame`

```python
def calculate_stochastic(
    prices: pd.DataFrame,
    k_window: int = 14,
    d_window: int = 3
) -> pd.DataFrame:
```

Stochastic Oscillator.

**Returns** :
- DataFrame avec colonnes ['%K', '%D']

##### `calculate_cci(prices: pd.DataFrame, window: int = 20) -> pd.Series`

Commodity Channel Index.

##### `calculate_williams_r(prices: pd.DataFrame, window: int = 14) -> pd.Series`

Williams %R.

#### Volatility Indicators

##### `calculate_bollinger_bands(...) -> pd.DataFrame`

```python
def calculate_bollinger_bands(
    prices: pd.Series,
    window: int = 20,
    num_std: float = 2.0
) -> pd.DataFrame:
```

Bollinger Bands.

**Returns** :
- DataFrame avec colonnes ['middle', 'upper', 'lower']

**Exemple** :
```python
from financial_analyzer.features.technical import calculate_bollinger_bands

bb = calculate_bollinger_bands(df['Close'], window=20, num_std=2.0)
price_above_upper = df['Close'] > bb['upper']
price_below_lower = df['Close'] < bb['lower']
```

##### `calculate_atr(prices: pd.DataFrame, window: int = 14) -> pd.Series`

Average True Range.

##### `calculate_keltner_channels(...) -> pd.DataFrame`

Keltner Channels.

#### Volume Indicators

##### `calculate_obv(prices: pd.DataFrame) -> pd.Series`

On-Balance Volume.

##### `calculate_vwap(prices: pd.DataFrame) -> pd.Series`

Volume-Weighted Average Price.

##### `calculate_mfi(prices: pd.DataFrame, window: int = 14) -> pd.Series`

Money Flow Index.

#### Wrapper Class

##### `class TechnicalFeatures`

```python
class TechnicalFeatures:
    def calculate_all_indicators(
        self,
        prices: pd.DataFrame,
        config: Optional[Dict] = None
    ) -> pd.DataFrame:
```

Calcule TOUS les indicateurs en une fois.

**Args** :
- `prices` : DataFrame OHLCV
- `config` : Configuration optionnelle (windows, paramètres)

**Returns** :
- DataFrame avec 40+ colonnes d'indicateurs

**Exemple** :
```python
from financial_analyzer.features.technical import TechnicalFeatures

features = TechnicalFeatures()
all_indicators = features.calculate_all_indicators(df)

# all_indicators contient:
# SMA_50, SMA_200, EMA_12, EMA_26, RSI_14, MACD, MACD_signal,
# Bollinger_upper, Bollinger_lower, ATR, ADX, Stochastic_K,
# Stochastic_D, CCI, Williams_R, OBV, VWAP, MFI, etc.
```

---

### `fundamental.py`

Transformation ratios FinanceToolkit en features ML.

#### `class FundamentalFeatures`

##### `create_fundamental_features(ratios: pd.DataFrame) -> pd.DataFrame`

Transforme ratios en features ML (lags, deltas, z-scores).

**Args** :
- `ratios` : DataFrame ratios (de FundamentalsProvider)

**Returns** :
- DataFrame features ML avec :
  - Ratios originaux
  - Lags (t-1, t-4 pour quarters)
  - Deltas (variations QoQ, YoY)
  - Z-scores (normalisés)

**Exemple** :
```python
from financial_analyzer.data.fundamentals import FundamentalsProvider
from financial_analyzer.features.fundamental import FundamentalFeatures

provider = FundamentalsProvider()
ratios = provider.get_all_ratios('AAPL', period='quarterly')

features_builder = FundamentalFeatures()
ml_features = features_builder.create_fundamental_features(ratios)

# ml_features contient:
# PE, PE_lag1, PE_lag4, PE_delta_qoq, PE_delta_yoy, PE_zscore
# ROE, ROE_lag1, ROE_lag4, ROE_delta_qoq, ROE_delta_yoy, ROE_zscore
# etc. pour 150+ ratios
```

##### `create_value_factors(ratios: pd.DataFrame) -> pd.DataFrame`

Crée facteurs de value (PE, PB, EV/EBITDA, etc.).

##### `create_quality_factors(ratios: pd.DataFrame) -> pd.DataFrame`

Crée facteurs de qualité (ROE, ROA, marges, etc.).

##### `create_growth_factors(ratios: pd.DataFrame) -> pd.DataFrame`

Crée facteurs de croissance (revenue growth, EPS growth, etc.).

---

### `alpha_factors.py`

100+ alpha factors (ML4T).

#### `class AlphaFactors`

##### `calculate_momentum_factors(prices: pd.DataFrame) -> pd.DataFrame`

Facteurs de momentum.

**Returns** :
- DataFrame avec :
  - `returns_1d`, `returns_5d`, `returns_20d`, `returns_60d`, `returns_252d`
  - `momentum_12_1` : Returns month 2-12 (skip month 1)
  - `acceleration` : Différence momentum court vs long terme
  - `volume_momentum` : Variation volume

**Exemple** :
```python
from financial_analyzer.features.alpha_factors import AlphaFactors

alpha = AlphaFactors()
momentum = alpha.calculate_momentum_factors(prices_df)

# Stratégie momentum
top_momentum = momentum['returns_60d'].nlargest(20)
```

##### `calculate_value_factors(ratios: pd.DataFrame) -> pd.DataFrame`

Facteurs de value.

**Returns** :
- Composite value score basé sur PE, PB, EV/EBITDA, etc.

##### `calculate_quality_factors(ratios: pd.DataFrame) -> pd.DataFrame`

Facteurs de qualité.

**Returns** :
- Composite quality score basé sur ROE, ROA, marges, stabilité earnings

##### `calculate_technical_factors(prices: pd.DataFrame) -> pd.DataFrame`

Facteurs techniques (z-scores RSI, MACD, etc.).

---

### `sentiment.py`

Analyse sentiment avec FinBERT.

#### `class SentimentAnalyzer`

##### `__init__(model_name: str = 'ProsusAI/finbert')`

Initialise avec modèle FinBERT pré-entraîné.

##### `analyze_text(texts: List[str]) -> pd.DataFrame`

Analyse sentiment de textes.

**Args** :
- `texts` : Liste de textes (headlines, tweets, etc.)

**Returns** :
- DataFrame avec colonnes :
  - `positive` : Probabilité [0, 1]
  - `negative` : Probabilité [0, 1]
  - `neutral` : Probabilité [0, 1]
  - `score` : Sentiment score [-1, 1] = positive - negative

**Exemple** :
```python
from financial_analyzer.features.sentiment import SentimentAnalyzer

analyzer = SentimentAnalyzer()
texts = [
    "Apple reports record earnings, stock surges",
    "Tesla faces production delays, shares drop"
]
sentiment = analyzer.analyze_text(texts)
# sentiment['score'] -> [0.85, -0.72]
```

##### `analyze_news(ticker: str, start_date: str, end_date: str) -> pd.DataFrame`

Analyse sentiment agrégé des news.

**Returns** :
- DataFrame time-series avec sentiment score quotidien

##### `analyze_social(ticker: str) -> pd.DataFrame`

Analyse sentiment des réseaux sociaux.

---

## Strategies Module

### `technical/momentum.py`

Stratégies momentum (Finance fork).

#### `class SMAStrategy(BaseStrategy)`

Stratégie SMA crossover.

**Paramètres** :
- `fast_period` : Période SMA rapide (défaut 50)
- `slow_period` : Période SMA lente (défaut 200)

**Exemple** :
```python
from backtesting import Backtest
from financial_analyzer.strategies.technical.momentum import SMAStrategy

bt = Backtest(df, SMAStrategy, cash=10000, commission=0.002)
stats = bt.run(fast_period=50, slow_period=200)
print(stats)
```

#### `class EMAStrategy(BaseStrategy)`

Stratégie EMA crossover.

#### `class MACDStrategy(BaseStrategy)`

Stratégie MACD signal crossover.

**Paramètres** :
- `fast` : Période EMA rapide (défaut 12)
- `slow` : Période EMA lente (défaut 26)
- `signal` : Période signal (défaut 9)

---

### `technical/mean_reversion.py`

Stratégies mean reversion.

#### `class RSIStrategy(BaseStrategy)`

Stratégie RSI overbought/oversold.

**Paramètres** :
- `rsi_period` : Période RSI (défaut 14)
- `oversold` : Seuil oversold (défaut 30)
- `overbought` : Seuil overbought (défaut 70)

#### `class BollingerBandsStrategy(BaseStrategy)`

Stratégie Bollinger Bands mean reversion.

**Paramètres** :
- `window` : Période (défaut 20)
- `num_std` : Nombre d'écart-types (défaut 2.0)

---

### `ml_based/predictive.py`

Stratégies basées sur ML.

#### `class MLPredictiveStrategy(BaseStrategy)`

Stratégie utilisant modèle ML pour prédictions.

**Paramètres** :
- `model_path` : Chemin modèle pickle
- `threshold` : Seuil prédiction pour signal (défaut 0.02 = 2%)

**Exemple** :
```python
from backtesting import Backtest
from financial_analyzer.strategies.ml_based.predictive import MLPredictiveStrategy

bt = Backtest(df, MLPredictiveStrategy, cash=10000)
stats = bt.run(model_path='models/xgboost.pkl', threshold=0.02)
```

---

## Backtesting Module

### `engine.py`

Wrapper backtesting.py.

#### `class BacktestEngine`

##### `run_backtest(...) -> BacktestResults`

```python
def run_backtest(
    self,
    data: pd.DataFrame,
    strategy: Type[Strategy],
    cash: float = 10000,
    commission: float = 0.002,
    **strategy_params
) -> BacktestResults:
```

Exécute un backtest.

**Args** :
- `data` : DataFrame OHLCV
- `strategy` : Classe Strategy (hérite de backtesting.Strategy)
- `cash` : Capital initial
- `commission` : Taux de commission
- `**strategy_params` : Paramètres de la stratégie

**Returns** :
- `BacktestResults` avec :
  - `metrics` : Dict 30+ métriques (Sharpe, Win Rate, Max Drawdown, etc.)
  - `trades` : DataFrame liste des trades
  - `equity_curve` : Series évolution du capital

**Exemple** :
```python
from financial_analyzer.backtesting.engine import BacktestEngine
from financial_analyzer.strategies.technical.momentum import SMAStrategy

engine = BacktestEngine()
results = engine.run_backtest(
    data=df,
    strategy=SMAStrategy,
    cash=10000,
    commission=0.002,
    fast_period=50,
    slow_period=200
)

print(f"Sharpe Ratio: {results.metrics['Sharpe Ratio']:.2f}")
print(f"Total Return: {results.metrics['Return [%]']:.2f}%")
```

##### `get_metrics() -> Dict[str, float]`

Récupère métriques du dernier backtest.

**Returns** :
- Dict avec 30+ métriques :
  - `Return [%]` : Return total
  - `Sharpe Ratio` : Ratio Sharpe
  - `Sortino Ratio` : Ratio Sortino
  - `Max Drawdown [%]` : Drawdown maximum
  - `Win Rate [%]` : Pourcentage trades gagnants
  - `# Trades` : Nombre total de trades
  - `Calmar Ratio` : Return / Max Drawdown
  - `etc.`

##### `plot_results() -> None`

Affiche graphiques interactifs Bokeh.

##### `export_trades(path: str) -> None`

Exporte trades en CSV.

---

### `optimize.py`

Optimisation paramètres stratégie.

#### `class StrategyOptimizer`

##### `grid_search(...) -> pd.DataFrame`

```python
def grid_search(
    self,
    data: pd.DataFrame,
    strategy: Type[Strategy],
    param_grid: Dict[str, List],
    metric: str = 'Sharpe Ratio'
) -> pd.DataFrame:
```

Grid search exhaustif.

**Args** :
- `data` : DataFrame OHLCV
- `strategy` : Classe Strategy
- `param_grid` : Dict de listes de valeurs à tester
- `metric` : Métrique à optimiser

**Returns** :
- DataFrame résultats triés par métrique

**Exemple** :
```python
from financial_analyzer.backtesting.optimize import StrategyOptimizer
from financial_analyzer.strategies.technical.momentum import SMAStrategy

optimizer = StrategyOptimizer()
results = optimizer.grid_search(
    data=df,
    strategy=SMAStrategy,
    param_grid={
        'fast_period': [20, 50, 100],
        'slow_period': [100, 200, 300]
    },
    metric='Sharpe Ratio'
)

best = results.iloc[0]
print(f"Best params: fast={best['fast_period']}, slow={best['slow_period']}")
print(f"Best Sharpe: {best['Sharpe Ratio']:.2f}")
```

##### `bayesian_optimize(...) -> Dict`

```python
def bayesian_optimize(
    self,
    data: pd.DataFrame,
    strategy: Type[Strategy],
    param_bounds: Dict[str, Tuple[float, float]],
    n_iterations: int = 50
) -> Dict:
```

Optimisation bayésienne (plus efficace que grid search).

**Args** :
- `param_bounds` : Dict de tuples (min, max)
- `n_iterations` : Nombre d'itérations

**Returns** :
- Dict avec best params et best metric

**Exemple** :
```python
results = optimizer.bayesian_optimize(
    data=df,
    strategy=RSIStrategy,
    param_bounds={
        'rsi_period': (5, 30),
        'oversold': (20, 35),
        'overbought': (65, 80)
    },
    n_iterations=50
)
```

##### `walk_forward_optimization(...) -> pd.DataFrame`

Walk-forward optimization (in-sample / out-of-sample).

---

## Portfolio Module

### `optimizer.py`

Wrapper PyPortfolioOpt.

#### `class PortfolioOptimizer`

##### `optimize_mean_variance(...) -> Dict[str, float]`

```python
def optimize_mean_variance(
    self,
    prices: pd.DataFrame,
    objective: str = 'max_sharpe',
    risk_free_rate: float = 0.02
) -> Dict[str, float]:
```

Optimisation Mean-Variance.

**Args** :
- `prices` : DataFrame multi-ticker (colonnes = tickers)
- `objective` : 'max_sharpe', 'min_volatility', 'max_quadratic_utility'
- `risk_free_rate` : Taux sans risque

**Returns** :
- Dict {ticker: poids} avec somme = 1

**Exemple** :
```python
from financial_analyzer.portfolio.optimizer import PortfolioOptimizer

optimizer = PortfolioOptimizer()
weights = optimizer.optimize_mean_variance(
    prices=prices_df,
    objective='max_sharpe',
    risk_free_rate=0.02
)

# weights = {'AAPL': 0.35, 'MSFT': 0.25, 'GOOGL': 0.20, ...}
```

##### `optimize_hrp(prices: pd.DataFrame) -> Dict[str, float]`

Hierarchical Risk Parity (diversification pure).

**Exemple** :
```python
weights = optimizer.optimize_hrp(prices_df)
# HRP ne nécessite pas expected returns, seulement covariance
```

##### `optimize_black_litterman(...) -> Dict[str, float]`

```python
def optimize_black_litterman(
    self,
    prices: pd.DataFrame,
    views: Dict[str, float],
    confidences: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
```

Black-Litterman avec vues subjectives.

**Args** :
- `views` : Dict {ticker: expected_return_annualized}
- `confidences` : Dict {ticker: confidence_level [0, 1]}

**Exemple** :
```python
# Market equilibrium + vues subjectives
views = {
    'AAPL': 0.15,  # Je pense AAPL fera +15% cette année
    'TSLA': -0.10  # Je pense TSLA fera -10%
}
confidences = {
    'AAPL': 0.8,   # Confiance 80%
    'TSLA': 0.6    # Confiance 60%
}

weights = optimizer.optimize_black_litterman(prices_df, views, confidences)
```

##### `get_efficient_frontier(prices: pd.DataFrame) -> pd.DataFrame`

Calcule frontière efficiente.

**Returns** :
- DataFrame avec colonnes ['Return', 'Volatility', 'Sharpe']

---

### `risk_optimizer.py`

Wrapper Riskfolio-Lib.

#### `class RiskOptimizer`

##### `optimize_cvar(...) -> Dict[str, float]`

```python
def optimize_cvar(
    self,
    returns: pd.DataFrame,
    alpha: float = 0.05,
    objective: str = 'Sharpe'
) -> Dict[str, float]:
```

Optimisation CVaR (Conditional Value at Risk).

**Args** :
- `returns` : DataFrame returns (colonnes = tickers)
- `alpha` : Niveau de confiance (0.05 = 5% worst cases)
- `objective` : 'Sharpe', 'MinRisk', 'MaxRet'

**Returns** :
- Dict {ticker: poids}

**Exemple** :
```python
from financial_analyzer.portfolio.risk_optimizer import RiskOptimizer

risk_opt = RiskOptimizer()
returns = prices_df.pct_change().dropna()

weights = risk_opt.optimize_cvar(
    returns=returns,
    alpha=0.05,  # Optimise 5% worst cases
    objective='Sharpe'
)
```

##### `optimize_worst_case(returns: pd.DataFrame) -> Dict[str, float]`

Optimisation worst-case (minimax).

##### `optimize_nco(...) -> Dict[str, float]`

Nested Clustered Optimization (HRP amélioré).

##### `calculate_risk_measures(...) -> Dict[str, float]`

```python
def calculate_risk_measures(
    self,
    returns: pd.DataFrame,
    weights: Dict[str, float]
) -> Dict[str, float]:
```

Calcule 24 mesures de risque.

**Returns** :
- Dict avec :
  - `'VaR'`, `'CVaR'`, `'EVaR'`, `'RVaR'`
  - `'Max Drawdown'`, `'Average Drawdown'`, `'Calmar Ratio'`
  - `'etc.'` (24 mesures au total)

---

### `allocation.py`

Conversion poids continus → actions entières.

#### `class DiscreteAllocator`

##### `allocate(...) -> Dict[str, int]`

```python
def allocate(
    self,
    weights: Dict[str, float],
    latest_prices: Dict[str, float],
    total_value: float
) -> Dict[str, int]:
```

Allocation discrète.

**Args** :
- `weights` : Poids continus {ticker: [0, 1]}
- `latest_prices` : Prix actuels {ticker: prix}
- `total_value` : Capital total à allouer

**Returns** :
- Dict {ticker: nb_actions_entières}
- Leftover cash inclus

**Exemple** :
```python
from financial_analyzer.portfolio.allocation import DiscreteAllocator

allocator = DiscreteAllocator()

weights = {'AAPL': 0.5, 'MSFT': 0.3, 'GOOGL': 0.2}
prices = {'AAPL': 178.50, 'MSFT': 372.80, 'GOOGL': 138.20}

allocation = allocator.allocate(weights, prices, total_value=10000)
# allocation = {'AAPL': 28, 'MSFT': 8, 'GOOGL': 14, '_leftover': 45.60}
```

##### `lp_portfolio(...) -> Dict[str, int]`

Allocation via Linear Programming (plus optimal).

---

### `rebalancing.py`

Stratégies de rebalancing.

#### `class RebalancingManager`

##### `threshold_rebalancing(...) -> bool`

```python
def threshold_rebalancing(
    self,
    current_weights: Dict[str, float],
    target_weights: Dict[str, float],
    threshold: float = 0.05
) -> bool:
```

Rebalancing si dérive > threshold.

**Returns** :
- `True` si rebalancing nécessaire

**Exemple** :
```python
from financial_analyzer.portfolio.rebalancing import RebalancingManager

manager = RebalancingManager()

current = {'AAPL': 0.55, 'MSFT': 0.25, 'GOOGL': 0.20}
target = {'AAPL': 0.50, 'MSFT': 0.30, 'GOOGL': 0.20}

needs_rebalancing = manager.threshold_rebalancing(current, target, threshold=0.05)
# True car AAPL a dérivé de 0.50 à 0.55 (> 5%)
```

##### `calendar_rebalancing(...) -> bool`

Rebalancing à fréquence fixe (monthly, quarterly).

##### `calculate_rebalancing_cost(...) -> float`

Calcule coût du rebalancing (commissions).

---

## Risk Module

### `metrics.py`

Métriques de risque et performance.

#### `calculate_var(...) -> float`

```python
def calculate_var(
    returns: pd.Series,
    alpha: float = 0.05,
    method: str = 'historical'
) -> float:
```

Value at Risk.

**Args** :
- `returns` : Series de returns
- `alpha` : Niveau de confiance (0.05 = 95%)
- `method` : 'historical', 'parametric', 'cornish_fisher'

**Returns** :
- VaR (valeur positive)

**Exemple** :
```python
from financial_analyzer.risk.metrics import calculate_var

returns = prices_df['Close'].pct_change().dropna()
var_95 = calculate_var(returns, alpha=0.05, method='historical')
print(f"VaR 95%: {var_95:.2%}")  # Ex: "VaR 95%: 2.50%"
```

#### `calculate_cvar(...) -> float`

Conditional Value at Risk (Expected Shortfall).

#### `calculate_max_drawdown(equity_curve: pd.Series) -> float`

Maximum drawdown.

**Returns** :
- Max drawdown en valeur absolue [0, 1]

#### `calculate_sharpe_ratio(...) -> float`

```python
def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
```

Sharpe ratio.

#### `calculate_sortino_ratio(...) -> float`

Sortino ratio (pénalise seulement downside volatility).

#### `calculate_calmar_ratio(...) -> float`

Calmar ratio (annualized return / max drawdown).

---

### `stress_testing.py`

Stress testing et Monte Carlo.

#### `class StressTester`

##### `monte_carlo_simulation(...) -> np.ndarray`

```python
def monte_carlo_simulation(
    self,
    returns: pd.Series,
    n_simulations: int = 10000,
    horizon: int = 252
) -> np.ndarray:
```

Simulations Monte Carlo.

**Args** :
- `returns` : Historical returns
- `n_simulations` : Nombre de simulations
- `horizon` : Horizon (jours)

**Returns** :
- Array (n_simulations, horizon) de paths

**Exemple** :
```python
from financial_analyzer.risk.stress_testing import StressTester

tester = StressTester()
paths = tester.monte_carlo_simulation(returns, n_simulations=10000, horizon=252)

# Distribution finale
final_values = paths[:, -1]
var_95_mc = np.percentile(final_values, 5)
```

##### `worst_case_scenario(...) -> float`

Calcule perte worst-case pour un portfolio.

---

## ML Module

### `models/tree_based.py`

Modèles tree-based.

#### `class XGBoostPredictor`

##### `__init__(params: Optional[Dict] = None)`

##### `fit(X: pd.DataFrame, y: pd.Series) -> None`

Entraînement du modèle.

##### `predict(X: pd.DataFrame) -> np.ndarray`

Prédictions.

##### `evaluate(X: pd.DataFrame, y: pd.Series) -> Dict[str, float]`

Évaluation (MAE, RMSE, R²).

**Exemple** :
```python
from financial_analyzer.ml.models.tree_based import XGBoostPredictor
from sklearn.model_selection import TimeSeriesSplit

model = XGBoostPredictor(params={'n_estimators': 300, 'max_depth': 5})

tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    model.fit(X_train, y_train)
    metrics = model.evaluate(X_test, y_test)
    print(f"RMSE: {metrics['rmse']:.4f}, R²: {metrics['r2']:.4f}")
```

##### `get_feature_importance() -> pd.Series`

Feature importance.

---

### `ensemble.py`

Ensembles de modèles.

#### `class ModelEnsemble`

##### `__init__(models: List, method: str = 'average')`

**Args** :
- `models` : Liste de modèles
- `method` : 'average', 'weighted', 'stacking'

##### `fit(X: pd.DataFrame, y: pd.Series) -> None`

Entraîne tous les modèles.

##### `predict(X: pd.DataFrame) -> np.ndarray`

Prédictions agrégées.

**Exemple** :
```python
from financial_analyzer.ml.ensemble import ModelEnsemble
from financial_analyzer.ml.models.tree_based import XGBoostPredictor, RandomForestPredictor

model1 = XGBoostPredictor()
model2 = RandomForestPredictor()
model3 = LightGBMPredictor()

ensemble = ModelEnsemble(models=[model1, model2, model3], method='average')
ensemble.fit(X_train, y_train)
predictions = ensemble.predict(X_test)
```

---

## Analysis Module

### `backtester.py` ✅

BacktestEngine (Semaine 3).

Voir tests/test_analysis.py pour exemples complets.

#### `class BacktestEngine`

Moteur de backtesting avec multi-ticker support.

**Features** :
- Stratégies : sentiment, momentum, mean-reversion
- Multi-ticker avec rebalancing
- Commission & slippage réalistes
- 15+ métriques de performance
- Export CSV

**Exemple** (voir tests) :
```python
from financial_analyzer.analysis.backtester import BacktestEngine

engine = BacktestEngine(
    initial_capital=10000,
    commission_rate=0.002,
    slippage_bps=5,
    strategy='momentum'
)

engine.setup(prices_df, sentiment_df)
results = engine.backtest()

metrics = engine.calculate_metrics()
print(f"Sharpe: {metrics['sharpe_ratio']:.2f}")
```

---

### `ml_predictor.py` ✅

MLPredictor (Semaine 3).

#### `class MLPredictor`

Prédicteur ML avec feature engineering complet.

**Features** :
- Feature engineering (RSI, MACD, Bollinger, sentiment, ratios)
- Multiple models (RF, XGBoost, GradientBoosting)
- TimeSeriesSplit CV
- GridSearchCV
- Métriques (MAE, RMSE, R², MAPE)
- Feature importance
- Persistence (pickle)

**Exemple** (voir tests) :
```python
from financial_analyzer.analysis.ml_predictor import MLPredictor, MLPredictorConfig

config = MLPredictorConfig(
    model_type='xgboost',
    prediction_horizon=5,
    use_gridsearch=True
)

predictor = MLPredictor(config)
X, y = predictor.prepare_features(prices_df, sentiment_df, ratios_df)

predictor.train(X, y)
predictions = predictor.predict(X_test)
metrics = predictor.evaluate(X_test, y_test)
```

---

### `valuation.py`

Valorisation d'entreprises (FinanceToolkit).

#### `class Valuator`

##### `dcf_valuation(ticker: str) -> float`

Discounted Cash Flow valuation.

**Returns** :
- Valeur intrinsèque par action

**Exemple** :
```python
from financial_analyzer.analysis.valuation import Valuator

valuator = Valuator(api_key=API_KEY)
intrinsic_value = valuator.dcf_valuation('AAPL')
current_price = 178.50

if intrinsic_value > current_price:
    print(f"Undervalued! Intrinsic: ${intrinsic_value:.2f}, Current: ${current_price:.2f}")
```

##### `ddm_valuation(ticker: str) -> float`

Dividend Discount Model.

##### `calculate_wacc(ticker: str) -> float`

Weighted Average Cost of Capital.

---

### `options.py`

Pricing et Greeks d'options (FinanceToolkit + scipy).

#### `class OptionsAnalyzer`

##### `black_scholes(...) -> float`

```python
def black_scholes(
    self,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = 'call'
) -> float:
```

Black-Scholes pricing.

**Args** :
- `S` : Spot price
- `K` : Strike price
- `T` : Time to maturity (années)
- `r` : Risk-free rate
- `sigma` : Volatility (annualisée)
- `option_type` : 'call' ou 'put'

**Returns** :
- Prix théorique de l'option

**Exemple** :
```python
from financial_analyzer.analysis.options import OptionsAnalyzer

analyzer = OptionsAnalyzer()

call_price = analyzer.black_scholes(
    S=100,      # Stock à $100
    K=105,      # Strike $105
    T=0.25,     # 3 mois
    r=0.02,     # 2% risk-free
    sigma=0.25, # 25% volatility
    option_type='call'
)
print(f"Call price: ${call_price:.2f}")
```

##### `calculate_greeks(...) -> Dict[str, float]`

```python
def calculate_greeks(
    self,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float
) -> Dict[str, float]:
```

Calcule Greeks (Delta, Gamma, Theta, Vega, Rho).

**Returns** :
- Dict avec 5 Greeks

**Exemple** :
```python
greeks = analyzer.calculate_greeks(S=100, K=105, T=0.25, r=0.02, sigma=0.25)
print(f"Delta: {greeks['delta']:.4f}")  # Ex: 0.4567
print(f"Gamma: {greeks['gamma']:.4f}")  # Ex: 0.0234
```

##### `implied_volatility(...) -> float`

```python
def implied_volatility(
    self,
    option_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = 'call'
) -> float:
```

Calcule volatilité implicite (Newton-Raphson).

---

### `performance.py`

Métriques de performance.

#### Functions

Voir `risk/metrics.py` pour métriques de risque.

##### `calculate_sharpe_ratio(...) -> float`

(Déjà documenté dans risk/metrics.py)

##### `calculate_sortino_ratio(...) -> float`

##### `calculate_alpha_beta(...) -> Tuple[float, float]`

```python
def calculate_alpha_beta(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.02
) -> Tuple[float, float]:
```

Calcule Alpha et Beta vs benchmark.

**Exemple** :
```python
from financial_analyzer.analysis.performance import calculate_alpha_beta

portfolio_returns = ...
sp500_returns = ...

alpha, beta = calculate_alpha_beta(portfolio_returns, sp500_returns)
print(f"Alpha: {alpha:.2%}, Beta: {beta:.2f}")
# Ex: "Alpha: 3.50%, Beta: 1.15"
```

---

## API Module

### `main.py`

Application FastAPI.

#### `app = FastAPI(title="FinBot API v2.0")`

Application principale.

**Endpoints disponibles** :
- `/docs` : Documentation Swagger UI
- `/redoc` : Documentation ReDoc
- `/api/data/*` : Endpoints data
- `/api/backtest/*` : Endpoints backtesting
- `/api/portfolio/*` : Endpoints portfolio
- `/api/ml/*` : Endpoints ML

---

### `routes/backtest.py`

Endpoints backtesting.

#### `POST /api/backtest/run`

```python
@router.post("/run")
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
```

Exécute un backtest.

**Request Body** :
```json
{
    "tickers": ["AAPL", "MSFT"],
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "strategy": "momentum",
    "strategy_params": {
        "sma_fast": 50,
        "sma_slow": 200
    },
    "cash": 10000,
    "commission": 0.002
}
```

**Response** :
```json
{
    "backtest_id": "uuid-1234",
    "metrics": {
        "Return [%]": 45.2,
        "Sharpe Ratio": 1.85,
        "Max Drawdown [%]": -15.3,
        "Win Rate [%]": 58.5
    },
    "equity_curve": [...],
    "trades": [...]
}
```

---

### `routes/portfolio.py`

Endpoints portfolio optimization.

#### `POST /api/portfolio/optimize`

Optimise un portfolio.

**Request Body** :
```json
{
    "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN"],
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "method": "mean_variance",
    "objective": "max_sharpe"
}
```

**Response** :
```json
{
    "weights": {
        "AAPL": 0.35,
        "MSFT": 0.28,
        "GOOGL": 0.22,
        "AMZN": 0.15
    },
    "expected_return": 0.18,
    "volatility": 0.21,
    "sharpe_ratio": 0.86
}
```

---

## Dashboard Module

### `streamlit_app.py`

Application Streamlit principale avec interface multi-pages.

#### Structure de l'Application

```python
import streamlit as st
from financial_analyzer.dashboard.components import (
    data_explorer,
    backtest_viewer,
    portfolio_builder,
    ml_dashboard
)

st.set_page_config(
    page_title="FinBot v2.0",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Navigation
page = st.sidebar.selectbox("📊 Navigation", [
    "Data Explorer",
    "Backtest",
    "Portfolio Builder",
    "ML Dashboard"
])

if page == "Data Explorer":
    data_explorer.render()
elif page == "Backtest":
    backtest_viewer.render()
elif page == "Portfolio Builder":
    portfolio_builder.render()
elif page == "ML Dashboard":
    ml_dashboard.render()
```

#### Pages Disponibles

1. **Data Explorer** : Sélection universe, visualisation OHLCV/ratios, analyse exploratoire
2. **Backtest** : Configuration et exécution backtests, visualisation résultats
3. **Portfolio Builder** : Construction et optimisation portfolio, efficient frontier
4. **ML Dashboard** : Entraînement et évaluation modèles ML, feature importance

**Lancement** :
```bash
streamlit run src/financial_analyzer/dashboard/streamlit_app.py
# Ou via CLI
finbot dashboard --port 8501
```

---

### `components/`

Composants réutilisables pour le dashboard.

#### `data_explorer.py`

Interface pour explorer les données de marché.

##### `render()`

```python
def render():
    """Affiche la page Data Explorer."""
```

**Fonctionnalités** :
- Sélection universe (sector, market cap, exchange)
- Choix période historique (start/end dates)
- Visualisation OHLCV (candlestick charts)
- Visualisation indicateurs techniques (SMA, RSI, MACD, Bollinger)
- Visualisation ratios fondamentaux (PE, PB, ROE, Debt/Equity)
- Téléchargement données (CSV/Excel)
- Comparaison multi-tickers

**Exemple UI** :
```python
# Sidebar
sector = st.sidebar.selectbox("Sector", ["Technology", "Healthcare", ...])
tickers = st.sidebar.multiselect("Tickers", universe)
start_date = st.sidebar.date_input("Start Date")
end_date = st.sidebar.date_input("End Date")

# Main area
tab1, tab2, tab3 = st.tabs(["📈 OHLCV", "📊 Technical", "💼 Fundamentals"])

with tab1:
    st.plotly_chart(candlestick_chart, use_container_width=True)
    
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(rsi_chart)
    with col2:
        st.plotly_chart(macd_chart)

with tab3:
    st.dataframe(ratios_table, use_container_width=True)
```

---

#### `backtest_viewer.py`

Interface pour configurer et visualiser backtests.

##### `render()`

```python
def render():
    """Affiche la page Backtest."""
```

**Fonctionnalités** :
- Configuration stratégie (technical, quantitative, ml_based)
- Paramètres stratégie (SMA windows, RSI thresholds, etc.)
- Paramètres backtest (commission, slippage, capital initial)
- Exécution backtest (bouton "Run Backtest")
- Visualisation equity curve (line chart)
- Tableau métriques (Sharpe, Sortino, Max DD, Win Rate, etc.)
- Liste trades (entry/exit dates, PnL, duration)
- Visualisation drawdown (underwater plot)
- Comparaison multi-stratégies
- Export résultats (CSV, JSON)

**Exemple UI** :
```python
# Configuration
with st.expander("⚙️ Strategy Configuration", expanded=True):
    strategy_type = st.selectbox("Strategy", ["SMA Crossover", "RSI Mean Reversion", ...])
    
    if strategy_type == "SMA Crossover":
        col1, col2 = st.columns(2)
        with col1:
            sma_fast = st.slider("Fast SMA", 10, 100, 50)
        with col2:
            sma_slow = st.slider("Slow SMA", 100, 300, 200)

# Exécution
if st.button("🚀 Run Backtest", type="primary"):
    with st.spinner("Running backtest..."):
        results = engine.run_backtest(data, strategy, **params)
    
    # Métriques
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sharpe Ratio", f"{results.sharpe_ratio:.2f}")
    col2.metric("Total Return", f"{results.total_return:.1%}")
    col3.metric("Max Drawdown", f"{results.max_drawdown:.1%}")
    col4.metric("Win Rate", f"{results.win_rate:.1%}")
    
    # Equity curve
    st.plotly_chart(equity_curve_chart, use_container_width=True)
```

---

#### `portfolio_builder.py`

Interface pour construire et optimiser des portfolios.

##### `render()`

```python
def render():
    """Affiche la page Portfolio Builder."""
```

**Fonctionnalités** :
- Sélection tickers (multi-select)
- Choix période historique
- Choix méthode optimisation (Mean-Variance, HRP, Black-Litterman, CVaR)
- Configuration contraintes (min/max weights, sector constraints)
- Visualisation efficient frontier
- Tableau poids optimaux (pie chart)
- Métriques portfolio (expected return, volatility, Sharpe)
- Allocation discrète (capital disponible → nb actions)
- Backtesting portfolio (performance historique)
- Rebalancing simulation (daily/weekly/monthly)
- Export allocation (CSV)

**Exemple UI** :
```python
# Sélection
tickers = st.multiselect("Select Tickers", universe, default=["AAPL", "MSFT", "GOOGL"])

# Optimisation
optimizer_type = st.selectbox("Optimizer", [
    "Mean-Variance (Max Sharpe)",
    "Hierarchical Risk Parity",
    "Black-Litterman",
    "CVaR Optimization"
])

if st.button("⚡ Optimize Portfolio"):
    weights = optimizer.optimize(prices, method=optimizer_type)
    
    # Visualisations
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Efficient frontier
        st.plotly_chart(efficient_frontier_chart)
    
    with col2:
        # Weights pie chart
        st.plotly_chart(weights_pie_chart)
    
    # Allocation discrète
    st.subheader("📊 Discrete Allocation")
    capital = st.number_input("Available Capital ($)", value=10000)
    allocation = allocator.allocate(weights, latest_prices, capital)
    st.dataframe(allocation_table)
```

---

#### `ml_dashboard.py`

Interface pour entraîner et évaluer des modèles ML.

##### `render()`

```python
def render():
    """Affiche la page ML Dashboard."""
```

**Fonctionnalités** :
- Sélection ticker(s)
- Choix features (technical, fundamental, alpha factors, sentiment)
- Configuration cible (returns 1d, 5d, 20d ou classification up/down)
- Choix modèle (RandomForest, XGBoost, LightGBM, LSTM)
- Hyperparamètres modèle (sliders, inputs)
- Entraînement (bouton "Train Model" avec progress bar)
- Métriques évaluation (MAE, RMSE, R², MAPE, Accuracy)
- Visualisation prédictions vs actuals (scatter plot, line chart)
- Feature importance (bar chart)
- Confusion matrix (classification)
- Backtest des signaux ML (conversion prédictions → trades)
- Export modèle (pickle, joblib)
- Chargement modèle pré-entraîné

**Exemple UI** :
```python
# Configuration
with st.expander("🧠 Model Configuration", expanded=True):
    model_type = st.selectbox("Model", ["XGBoost", "RandomForest", "LightGBM", "LSTM"])
    target_type = st.radio("Target", ["Regression (Returns)", "Classification (Up/Down)"])
    
    # Features
    st.multiselect("Technical Indicators", ["SMA", "RSI", "MACD", "Bollinger", ...])
    st.multiselect("Fundamental Ratios", ["PE", "PB", "ROE", "Debt/Equity", ...])

# Entraînement
if st.button("🚀 Train Model", type="primary"):
    with st.spinner("Training model..."):
        predictor = MLPredictor(model_type=model_type)
        predictor.train(X_train, y_train)
        metrics = predictor.evaluate(X_test, y_test)
    
    # Métriques
    col1, col2, col3 = st.columns(3)
    col1.metric("R² Score", f"{metrics['r2']:.4f}")
    col2.metric("RMSE", f"{metrics['rmse']:.6f}")
    col3.metric("MAPE", f"{metrics['mape']:.2%}")
    
    # Feature importance
    st.plotly_chart(feature_importance_chart, use_container_width=True)
    
    # Prédictions
    st.plotly_chart(predictions_chart, use_container_width=True)
```

---

## 📝 Conventions Générales

### Type Hints

**TOUJOURS utiliser** type hints complets :

```python
def my_function(
    prices: pd.DataFrame,
    window: int,
    threshold: Optional[float] = None
) -> pd.Series:
    """..."""
```

### Docstrings

**Format Google Style obligatoire** :

```python
def calculate_metric(returns: pd.Series, benchmark: pd.Series) -> float:
    """
    Calculate performance metric.
    
    Args:
        returns: Strategy returns
        benchmark: Benchmark returns
    
    Returns:
        Metric value
    
    Raises:
        ValueError: If returns length mismatch
    
    Example:
        >>> returns = pd.Series([0.01, 0.02, -0.01])
        >>> benchmark = pd.Series([0.005, 0.015, -0.005])
        >>> metric = calculate_metric(returns, benchmark)
        >>> print(f"{metric:.2f}")
        1.25
    """
```

### Error Handling

**Toujours valider inputs** :

```python
if not isinstance(prices, pd.DataFrame):
    raise TypeError(f"prices must be DataFrame, got {type(prices)}")

if prices.empty:
    raise ValueError("prices DataFrame is empty")

try:
    result = external_api_call()
except ConnectionError as e:
    logger.warning(f"API failed, using cache: {e}")
    result = load_from_cache()
```

---

**VERSION** : 2.0  
**DATE** : 6 Novembre 2025  
**AUTEUR** : FinBot Team  
**STATUT** : ✅ API Reference Complète (Partie 1/2)

*Note: Cette référence API couvre tous les modules principaux. Pour des détails spécifiques sur les 40+ indicateurs techniques, 25+ stratégies, et 100+ alpha factors, consulter les audits dans `docs/AUDITS/`.*
