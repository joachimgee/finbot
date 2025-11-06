# DOSSIER D'AUDIT TECHNIQUE - FINANCE (PARTIE 1/5 - OVERVIEW & STRUCTURE)

================================================================================
**NOTE : Ce fork contient 183 fichiers Python répartis en 6 catégories.**
**L'audit est divisé en 5 parties pour plus de clarté.**
================================================================================

## 🎯 NOM DU FORK / PROJET
**Finance** - Collection of 150+ Python for Finance programs

## 📋 INTRODUCTION & BUT DU PROJET

**Titre officiel** : Finance - Python for Finance Programs Collection

**Description** : Collection complète de plus de 150 programmes Python pour la finance, couvrant l'acquisition de données, l'analyse technique, l'analyse fondamentale, les stratégies de trading, le machine learning et la gestion de portefeuille.

**Objectif principal** :
- Fournir des outils pratiques pour analyser les marchés financiers
- Collecter et manipuler des données boursières
- Implémenter des stratégies de trading
- Analyser les performances et le risque
- Appliquer le machine learning au trading
- Screener des actions selon critères techniques/fondamentaux

**Auteur** : shashankvemuri

**License** : MIT License

**Langage principal** : Python

**GitHub** : https://github.com/shashankvemuri/Finance

---

## 📊 STATISTIQUES GLOBALES

- **Total de fichiers Python** : 183 fichiers
- **Catégories principales** : 6
- **Indicateurs techniques** : 40+ implémentés
- **Stratégies de trading** : 25+
- **Modèles ML** : 15+
- **Sources de données** : Yahoo Finance, Finviz, TradingView, Reddit, Twitter

---

## 📂 STRUCTURE COMPLÈTE DU DÉPÔT

```
Finance-master/
├── README.md                           # Documentation principale
├── LICENSE                             # Licence MIT
├── requirements.txt                    # Dépendances Python
│
├── __init__.py                         # Package init
├── ta_functions.py                     # 40+ indicateurs techniques (357 lignes)
├── tickers.py                          # Fonctions récupération tickers
│
├── FICHIERS CSV DE TICKERS            # Listes de symboles boursiers
│   ├── amex_tickers.csv               # Tickers AMEX
│   ├── nasdaq_tickers.csv             # Tickers NASDAQ
│   ├── nyse_tickers.csv               # Tickers NYSE
│   ├── russell3000_tickers.csv        # Russell 3000
│   └── s&p500_tickers.csv             # S&P 500
│
├── chromedriver                        # Driver pour web scraping
│
├── find_stocks/                        # 12 programmes de screening (PARTIE 2)
│   ├── IBD_RS_Rating.py
│   ├── correlated_stocks.py
│   ├── finviz_growth_screener.py
│   ├── fundamental_screener.py
│   ├── get_rsi_tickers.py
│   ├── green_line_values.py
│   ├── minervini_screener.py
│   ├── price_alert_email.py
│   ├── stock_news_sentiment.py
│   ├── tradingview_signals.py
│   ├── twitter_screener.py
│   └── yahoo_recommendations.py
│
├── stock_data/                         # 24 programmes d'acquisition données (PARTIE 2)
│   ├── autoscraper_finviz_data.py
│   ├── dividend_history.py
│   ├── fibonacci_retracement.py
│   ├── finviz_home_scraper.py
│   ├── finviz_insider_trades.py
│   ├── finviz_news_scraper.py
│   ├── finviz_stock_scraper.py
│   ├── fundamental_ratios.py
│   ├── get_dividend_calendar.py
│   ├── green_line_test.py
│   ├── high_dividend_yield.py
│   ├── historical_sp500_data.py
│   ├── main_indicators_one_graph.py
│   ├── main_indicators_streamlit.py
│   ├── pivots_calculator.py
│   ├── reddit_scraper.py
│   ├── send_top_movers.py
│   ├── stock_VWAP.py
│   ├── stock_data_sms.py
│   ├── stock_earnings.py
│   ├── stock_twilio_server.py
│   ├── tradingview_intraday_data.py
│   ├── tradingview_recommendations.py
│   └── yf_intraday_data.py
│
├── technical_indicators/               # 30+ visualisations indicateurs (PARTIE 3)
│   ├── accumulation_distribution_line.py
│   ├── adx.py
│   ├── aroon_oscillator.py
│   ├── average_true_range.py
│   ├── bollinger_bands.py
│   ├── chaikin_oscillator.py
│   ├── cci.py
│   ├── donchian_channel.py
│   ├── ema.py
│   ├── ichimoku_cloud.py
│   ├── keltner_channel.py
│   ├── macd.py
│   ├── money_flow_index.py
│   ├── obv.py
│   ├── parabolic_sar.py
│   ├── pivot_points.py
│   ├── price_channels.py
│   ├── rsi.py
│   ├── sma.py
│   ├── stochastic_oscillator.py
│   ├── supertrend.py
│   ├── vwap.py
│   ├── williams_r.py
│   └── ... (30+ fichiers total)
│
├── stock_analysis/                     # 20 programmes analyse stocks (PARTIE 4)
│   ├── backest_all_indicators.py      # 29784 lignes - backtest complet
│   ├── capm_analysis.py
│   ├── earnings_call_sentiment_analysis.py
│   ├── estimating_returns.py
│   ├── intrinsic_value.py
│   ├── kelly_criterion.py
│   ├── ma_backtesting.py
│   ├── ols_regression.py
│   ├── performance_risk_analysis.py
│   ├── risk_vs_returns.py
│   ├── seasonal_stock_analysis.py     # 14421 lignes
│   ├── sma_histogram.py
│   ├── sp500_cot_sentiment_analysis.py
│   ├── sp500_valuation.py
│   ├── stock_pivot_resistance.py
│   ├── stock_profit_loss.py
│   ├── stock_returns_statistical_analysis.py
│   ├── twitter_sentiment_analysis.py
│   ├── var_analysis.py
│   └── view_stock_returns.py
│
├── portfolio_strategies/               # 26 stratégies de trading (PARTIE 4)
│   ├── astral_timing_signals.py
│   ├── backtest_strategies.py
│   ├── backtrader_backtest.py
│   ├── best_moving_averages_analysis.py
│   ├── ema_crossover_strategy.py
│   ├── factor_analysis.py
│   ├── financial_signal_analysis.py
│   ├── geometric_brownian_motion.py
│   ├── long_hold_stats_analysis.py
│   ├── ls_dca_analysis.py
│   ├── monte_carlo.py
│   ├── moving_average_crossover_signals.py
│   ├── moving_avg_strategy.py
│   ├── optimal_portfolio.py
│   ├── optimized_bollinger_bands.py
│   ├── pairs_trading.py
│   ├── portfolio_analysis.py
│   ├── portfolio_optimization.py      # 9277 lignes
│   ├── portfolio_var_simulation.py
│   ├── risk_management.py
│   ├── robinhood_bot.py
│   ├── rsi_trendline_strategy.py
│   ├── rwb_strategy.py
│   ├── sma_trading_strategy.py
│   ├── stock_spread_plotter.py
│   └── support_resistance_finder.py
│
└── machine_learning/                   # 16 modèles ML (PARTIE 5)
    ├── arima_time_series.py
    ├── deep_learning_bot.py
    ├── etf_graphical_lasso.py
    ├── kmeans_clustering.py
    ├── lstm_prediction.py
    ├── ml_models_accuracy.py
    ├── neural_network_prediction.py
    ├── pca_kmeans_clustering.py
    ├── prophet_price_prediction.py
    ├── quantitative_indicators_prediction.py
    ├── sklearn_trading_bot.py
    ├── sp500_pca_analysis.py
    ├── stock_probabilistic_analysis.py
    ├── stock_regression_analysis.py
    ├── stocker_price_prediction.py
    └── technical_indicators_clustering.py
```

---

## 🔧 FICHIERS CORE - ANALYSE DÉTAILLÉE

### 1. **ta_functions.py** (357 lignes)

**Rôle** : Bibliothèque centrale contenant l'implémentation de 40+ indicateurs techniques

**Features** : Tous les indicateurs techniques populaires implémentés from scratch avec pandas/numpy

#### Liste complète des indicateurs implémentés :

##### **A. MOVING AVERAGES (Moyennes mobiles)**

```python
def SMA(data, timeperiod=14):
    """
    Simple Moving Average (SMA)
    
    Formule: SMA = sum(Close[i] for i in range(n)) / n
    
    Usage:
        sma_20 = SMA(df['Close'], timeperiod=20)
    """
    return data.rolling(window=timeperiod).mean()


def EMA(data, timeperiod=12):
    """
    Exponential Moving Average (EMA)
    Donne plus de poids aux prix récents
    
    Formule: EMA(t) = Price(t) × α + EMA(t-1) × (1 - α)
             où α = 2/(timeperiod + 1)
    
    Usage:
        ema_12 = EMA(df['Close'], timeperiod=12)
    """
    ema = data.ewm(span=timeperiod, adjust=False).mean()
    return ema


def WMA(values, n):
    """
    Weighted Moving Average (WMA)
    Assignment linéaire des poids
    
    Usage:
        wma_10 = WMA(df['Close'], n=10)
    """
    return values.ewm(alpha=1/n, adjust=False).mean()
```

##### **B. VOLATILITY INDICATORS (Indicateurs de volatilité)**

```python
def ATR(high, low, close, timeperiod=14):
    """
    Average True Range (ATR)
    Mesure la volatilité du marché
    
    Formule: TR = max(H-L, |H-C_prev|, |L-C_prev|)
             ATR = WMA(TR, timeperiod)
    
    Usage:
        atr = ATR(df['High'], df['Low'], df['Close'], timeperiod=14)
        
    Interprétation:
        - ATR élevé = volatilité élevée
        - ATR faible = volatilité faible
        - Utilisé pour dimensionner les stops
    """
    data = pd.DataFrame()
    data['tr0'] = abs(high - low)
    data['tr1'] = abs(high - close.shift())
    data['tr2'] = abs(low - close.shift())
    tr = data[['tr0', 'tr1', 'tr2']].max(axis=1)
    atr = WMA(tr, timeperiod)
    return atr


def BBANDS(data, timeperiod=20, nbdevup=2, nbdevdn=2, matype=None):
    """
    Bollinger Bands (BBANDS)
    Bandes de volatilité dynamiques
    
    Formules:
        Middle Band = SMA(close, n)
        Upper Band = Middle + (k × σ)
        Lower Band = Middle - (k × σ)
        où σ = std(close, n)
    
    Usage:
        upper, middle, lower = BBANDS(df['Close'], timeperiod=20, nbdevup=2)
        
    Signaux:
        - Prix touche bande supérieure = surachat
        - Prix touche bande inférieure = survente
        - Contraction des bandes = faible volatilité (avant breakout)
        - Expansion des bandes = haute volatilité
    """
    sma = data.rolling(timeperiod).mean()
    std = data.rolling(timeperiod).std()
    bollinger_up = sma + std * nbdevup
    bollinger_down = sma - std * nbdevdn
    return bollinger_up, sma, bollinger_down
```

##### **C. MOMENTUM INDICATORS (Indicateurs de momentum)**

```python
def RSI(data, timeperiod=14):
    """
    Relative Strength Index (RSI)
    Oscillateur de momentum (0-100)
    
    Formules:
        RS = Average Gain / Average Loss
        RSI = 100 - (100 / (1 + RS))
    
    Usage:
        rsi = RSI(df['Close'], timeperiod=14)
        
    Interprétation:
        - RSI > 70 = zone de surachat (overbought)
        - RSI < 30 = zone de survente (oversold)
        - Divergences RSI vs prix = signal de retournement
    """
    delta = data.diff()
    delta = delta[1:]

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=timeperiod).mean()
    avg_loss = loss.rolling(window=timeperiod).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def STOCH(high, low, close, fastk_period=14, slowk_period=3, 
          slowk_matype=0, slowd_period=3, slowd_matype=0):
    """
    Stochastic Oscillator (STOCH)
    Compare le prix de clôture à la fourchette de prix sur une période
    
    Formules:
        %K = 100 × (Close - Low_n) / (High_n - Low_n)
        %D = SMA(%K, 3)
    
    Usage:
        slowk, slowd = STOCH(df['High'], df['Low'], df['Close'])
        
    Signaux:
        - %K > 80 = surachat
        - %K < 20 = survente
        - Croisement %K au-dessus %D = signal achat
        - Croisement %K en-dessous %D = signal vente
    """
    high = high.rolling(fastk_period).max()
    low = low.rolling(fastk_period).min()

    fastk = ((close - low) / (high - low)) * 100
    fastd = fastk.rolling(slowk_period).mean()
    slowk = fastd.rolling(slowk_period).mean()

    if slowd_matype == 0:
        slowd = slowk.rolling(slowd_period).mean()
    else:
        slowd = slowk.rolling(slowd_period).apply(
            lambda x: np.convolve(x, np.ones(slowd_period), mode='valid') / slowd_period
        )

    return slowk, slowd


def CCI(high, low, close, timeperiod=14):
    """
    Commodity Channel Index (CCI)
    Mesure la déviation du prix par rapport à sa moyenne
    
    Formule:
        Typical Price = (H + L + C) / 3
        CCI = (TP - SMA(TP)) / (0.015 × Mean Deviation)
    
    Usage:
        cci = CCI(df['High'], df['Low'], df['Close'], timeperiod=14)
        
    Interprétation:
        - CCI > +100 = surachat
        - CCI < -100 = survente
        - Utilisé pour identifier cycles et retournements
    """
    typical_price = (high + low + close) / 3
    sma = typical_price.rolling(timeperiod).mean()
    mean_deviation = np.abs(typical_price - sma).rolling(timeperiod).mean()
    cci = (typical_price - sma) / (0.015 * mean_deviation)
    return cci


def MACD(data, fastperiod=12, slowperiod=26, signalperiod=9):
    """
    Moving Average Convergence Divergence (MACD)
    Indicateur de tendance et momentum
    
    Formules:
        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(MACD, 9)
        Histogram = MACD - Signal
    
    Usage:
        macd, signal, histogram = MACD(df['Close'])
        
    Signaux:
        - MACD croise au-dessus Signal = signal achat
        - MACD croise en-dessous Signal = signal vente
        - Histogram > 0 = momentum haussier
        - Divergences MACD vs prix = retournement
    """
    exp1 = data.ewm(span=fastperiod, adjust=False).mean()
    exp2 = data.ewm(span=slowperiod, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=signalperiod, adjust=False).mean()
    histogram = macd - signal
    return macd, signal, histogram


def WILLR(high, low, close, timeperiod=14):
    """
    Williams %R
    Oscillateur de momentum (0 à -100)
    
    Formule:
        %R = -100 × (High_n - Close) / (High_n - Low_n)
    
    Usage:
        willr = WILLR(df['High'], df['Low'], df['Close'], timeperiod=14)
        
    Interprétation:
        - %R > -20 = surachat
        - %R < -80 = survente
        - Inverse du Stochastic %K
    """
    highest_high = high.rolling(window=timeperiod).max()
    lowest_low = low.rolling(window=timeperiod).min()
    willr = -100 * ((highest_high - close) / (highest_high - lowest_low))
    return willr
```

##### **D. VOLUME INDICATORS (Indicateurs de volume)**

```python
def OBV(close, volume):
    """
    On Balance Volume (OBV)
    Utilise le flux de volume pour prédire les changements de prix
    
    Formule:
        Si Close > Close_prev: OBV = OBV_prev + Volume
        Si Close < Close_prev: OBV = OBV_prev - Volume
        Si Close = Close_prev: OBV = OBV_prev
    
    Usage:
        obv = OBV(df['Close'], df['Volume'])
        
    Interprétation:
        - OBV en hausse avec prix = confirmation tendance haussière
        - OBV en baisse avec prix = confirmation tendance baissière
        - Divergence OBV vs prix = signal de retournement
    """
    df = pd.DataFrame({'close': close, 'volume': volume})
    df['obv'] = np.where(df['close'] > df['close'].shift(1), df['volume'], 
                         np.where(df['close'] < df['close'].shift(1), -df['volume'], 0)).cumsum()
    return df['obv']


def AD(high, low, close, volume):
    """
    Chaikin A/D Line (Accumulation/Distribution)
    Indicateur basé sur le volume mesurant le flux d'argent
    
    Formule:
        CLV = ((Close - Low) - (High - Close)) / (High - Low)
        A/D = cumsum(CLV × Volume)
    
    Usage:
        ad = AD(df['High'], df['Low'], df['Close'], df['Volume'])
        
    Interprétation:
        - A/D en hausse = accumulation (achat)
        - A/D en baisse = distribution (vente)
        - Divergences avec prix = retournement potentiel
    """
    clv = ((close - low) - (high - close)) / (high - low)
    ad = (clv * volume).cumsum()
    return ad


def MFI(high, low, close, volume, timeperiod=14):
    """
    Money Flow Index (MFI)
    RSI pondéré par le volume (0-100)
    
    Formules:
        Typical Price = (H + L + C) / 3
        Raw Money Flow = TP × Volume
        Money Flow Ratio = (Positive MF sum / Negative MF sum)
        MFI = 100 - (100 / (1 + Money Flow Ratio))
    
    Usage:
        mfi = MFI(df['High'], df['Low'], df['Close'], df['Volume'])
        
    Interprétation:
        - MFI > 80 = surachat
        - MFI < 20 = survente
        - Divergences MFI vs prix = signal fort
    """
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume
    
    positive_flow = raw_money_flow.where(typical_price > typical_price.shift(1), 0)
    negative_flow = raw_money_flow.where(typical_price < typical_price.shift(1), 0)
    
    positive_mf = positive_flow.rolling(window=timeperiod).sum()
    negative_mf = negative_flow.rolling(window=timeperiod).sum()
    
    mf_ratio = positive_mf / negative_mf
    mfi = 100 - (100 / (1 + mf_ratio))
    
    return mfi
```

**INDICATEURS SUPPLÉMENTAIRES IMPLÉMENTÉS** (extraits de ta_functions.py) :
- ADX (Average Directional Index)
- Aroon Oscillator
- Chaikin Oscillator
- Donchian Channel
- Ichimoku Cloud
- Keltner Channel
- Parabolic SAR
- Pivot Points
- VWAP (Volume Weighted Average Price)
- Supertrend
- Et 20+ autres...

---

### 2. **tickers.py**

**Rôle** : Fonctions pour récupérer les listes de tickers boursiers

```python
def tickers_sp500():
    """
    Récupère la liste des 500+ tickers du S&P 500 depuis Wikipedia
    
    Returns:
        List[str]: Liste des symboles (ex: ['AAPL', 'MSFT', 'GOOGL', ...])
        
    Source: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
    """
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    html = requests.get(url).text
    df = pd.read_html(html, header=0)[0]
    tickers = df['Symbol'].tolist()
    return tickers


def tickers_nasdaq():
    """
    Récupère tous les tickers listés sur NASDAQ (~3000)
    
    Source: NASDAQ Trader official data
    Format: Fichier pipe-separated
    """
    url = 'http://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt'
    data = requests.get(url).text
    lines = data.split('\n')
    df = pd.DataFrame([sub.split("|") for sub in lines[1:-2]], 
                      columns=lines[0].split("|"))
    return df['Symbol'].tolist()


def tickers_nyse():
    """
    Récupère tous les tickers listés sur NYSE (~2800)
    
    Filtre: Exchange = 'N' (NYSE uniquement)
    """
    url = 'http://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt'
    data = requests.get(url).text
    lines = data.split('\n')
    df = pd.DataFrame([sub.split("|") for sub in lines[1:-2]], 
                      columns=lines[0].split("|"))
    nyse_df = df[df['Exchange'] == 'N']
    return nyse_df['ACT Symbol'].tolist()


def tickers_dow():
    """
    Récupère les 30 tickers du Dow Jones Industrial Average
    
    Source: Wikipedia
    """
    url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
    html = requests.get(url).text
    df = pd.read_html(html, header=0, attrs = {'id': 'constituents'})[0]
    tickers = df['Symbol'].tolist()
    return tickers


def tickers_amex():
    """
    Récupère tous les tickers listés sur AMEX (~300)
    
    Filtre: Exchange = 'A' (AMEX uniquement)
    """
    url = 'http://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt'
    data = requests.get(url).text
    lines = data.split('\n')
    df = pd.DataFrame([sub.split("|") for sub in lines[1:-2]], 
                      columns=lines[0].split("|"))
    amex_df = df[df['Exchange'] == 'A']
    return amex_df['ACT Symbol'].tolist()
```

**Usage pratique** :
```python
# Obtenir tous les tickers S&P 500
sp500_list = tickers_sp500()
print(f"Nombre de tickers S&P 500: {len(sp500_list)}")  # ~505

# Obtenir tous les NASDAQ
nasdaq_list = tickers_nasdaq()
print(f"Nombre de tickers NASDAQ: {len(nasdaq_list)}")  # ~3000

# Combiner plusieurs exchanges
all_tickers = tickers_sp500() + tickers_nasdaq() + tickers_nyse()
unique_tickers = list(set(all_tickers))  # Dédupliquer
```

---

## 📦 DÉPENDANCES PRINCIPALES

D'après `requirements.txt` :

```txt
pandas>=1.3.0
numpy>=1.21.0
yfinance>=0.1.70          # Yahoo Finance data
pandas-datareader>=0.10.0 # Alternative data sources
matplotlib>=3.4.0         # Visualisations
seaborn>=0.11.0          # Visualisations statistiques
scikit-learn>=0.24.0     # Machine Learning
tensorflow>=2.6.0        # Deep Learning
keras>=2.6.0             # Neural Networks
prophet>=1.0             # Time series forecasting
beautifulsoup4>=4.9.0    # Web scraping
requests>=2.26.0         # HTTP requests
lxml>=4.6.0              # XML/HTML parsing
finvizfinance>=0.12.0    # Finviz data
tweepy>=4.0.0            # Twitter API
praw>=7.0.0              # Reddit API
selenium>=3.141.0        # Browser automation
ta-lib>=0.4.0            # Technical Analysis Library
backtrader>=1.9.0        # Backtesting framework
```

---

## 🎯 POINTS FORTS DU FORK

1. **Collection exhaustive** : 183 fichiers couvrant tous les aspects du trading
2. **Prêt à l'emploi** : Scripts standalone directement exécutables
3. **Diversité** : Techniques, fondamental, ML, sentiment, web scraping
4. **Éducatif** : Code simple et commenté pour apprendre
5. **Data sources variées** : Yahoo, Finviz, TradingView, Reddit, Twitter
6. **Indicateurs from scratch** : Implémentations pédagogiques des formules

---

## 📚 DOCUMENTATION

### Installation
```bash
git clone https://github.com/shashankvemuri/Finance.git
cd Finance
pip install -r requirements.txt
```

### Exécution d'un script
```bash
# Exemple : RSI screener
python find_stocks/get_rsi_tickers.py

# Exemple : Portfolio optimization
python portfolio_strategies/portfolio_optimization.py

# Exemple : LSTM prediction
python machine_learning/lstm_prediction.py
```

---

## 📋 PROCHAINES PARTIES DE L'AUDIT

- **PARTIE 2** : find_stocks/ + stock_data/ (Screening & Data Collection)
- **PARTIE 3** : technical_indicators/ (30+ visualisations d'indicateurs)
- **PARTIE 4** : stock_analysis/ + portfolio_strategies/ (Analyse & Stratégies)
- **PARTIE 5** : machine_learning/ (16 modèles ML/DL pour le trading)

================================================================================
FIN DE LA PARTIE 1/5 - FINANCE OVERVIEW & STRUCTURE
================================================================================
