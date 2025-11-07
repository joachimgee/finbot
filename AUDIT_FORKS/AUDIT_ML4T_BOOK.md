# 📚 AUDIT TECHNIQUE - MACHINE LEARNING FOR ALGORITHMIC TRADING (2ND EDITION)

================================================================================
**FORK** : machine-learning-for-trading (Stefan Jansen)
**BUT** : Comprehensive ML for Trading - Book + 150+ Jupyter Notebooks
**REPO** : https://github.com/stefan-jansen/machine-learning-for-trading
**BOOK** : [Machine Learning for Algorithmic Trading (2nd Ed, 2020)](https://www.amazon.com/Machine-Learning-Algorithmic-Trading-alternative/dp/1839217715)
**AUTHOR** : Stefan Jansen (ex-Applied AI, LLC)
**LICENSE** : Notebooks open-source
**PAGES** : 800+
**CHAPTERS** : 23 + Appendix (Alpha Factor Library)
**NOTEBOOKS** : 150+
**COMMUNITY** : https://exchange.ml4trading.io/
================================================================================

## 1. INTRODUCTION

**Machine Learning for Algorithmic Trading** (2nd Edition) est LE livre de référence pour appliquer le ML au trading algorithmique. Il couvre l'**ensemble du workflow ML4T** : de la collecte de données à l'exécution de stratégies, en passant par feature engineering, modèles supervisés/non-supervisés, NLP, deep learning et reinforcement learning.

### Points Forts Majeurs

✅ **Comprehensive** : 800+ pages, 23 chapitres, tout le pipeline ML4T
✅ **Hands-on** : 150+ Jupyter notebooks exécutés avec code complet
✅ **Data sources** : Market, fundamental, alternative (SEC filings, satellite images)
✅ **ML models** : Linear, trees, boosting, unsupervised, NLP, DL, RL
✅ **Backtesting** : Zipline customisé avec intégration ML
✅ **Recent research** : Réplication de papers 2018-2019
✅ **Production-ready** : Docker, conda environments, data pipelines
✅ **Community** : Platform dédiée https://exchange.ml4trading.io/
✅ **Updated** : 2nd Edition (2020) avec Python 3.8, Pandas 1.2, TF 2.2
✅ **Alpha factors** : Appendix avec 100+ alpha factors catalogués

### Statistiques Clés

- **Pages** : 800+
- **Notebooks** : 150+
- **Chapitres** : 23 + 1 appendix
- **Parties** : 4 (Data & Strategy, ML Fundamentals, NLP, Deep/RL Learning)
- **Data sources** : NASDAQ ITCH, Algoseek, SEC EDGAR, Quandl, yfinance, satellite images
- **ML algorithms** : 20+ (Linear, Random Forests, XGBoost, LightGBM, LSTM, CNN, GAN, DRL)
- **Alpha factors** : 100+ documented
- **GitHub stars** : 10K+
- **Community members** : 2K+

---

## 2. STRUCTURE DU LIVRE & DÉPÔT

### 4 Parties Principales

**Part 1 : From Data to Strategy Development** (Chapters 1-5)
- Data sourcing (market, fundamental, alternative)
- Feature engineering (alpha factors)
- Portfolio optimization
- Performance evaluation

**Part 2 : ML for Trading Fundamentals** (Chapters 6-13)
- ML process & workflow
- Linear models (risk factors, Fama-French)
- Time series (ARIMA, GARCH, cointegration)
- Bayesian ML (pairs trading)
- Trees & ensembles (Random Forests, XGBoost)
- Unsupervised learning (PCA, clustering)

**Part 3 : NLP for Trading** (Chapters 14-16)
- Sentiment analysis (financial news, SEC filings)
- Topic modeling (LDA, NMF)
- Word embeddings (Word2Vec, GloVe, earnings calls)

**Part 4 : Deep & Reinforcement Learning** (Chapters 17-22)
- Deep learning fundamentals (feedforward networks)
- CNN (time series → images, satellite imagery)
- RNN/LSTM (multivariate time series, sentiment)
- Autoencoders (conditional risk factors, asset pricing)
- GAN (synthetic time series data)
- Deep RL (trading agent with PPO, DQN)

### Structure du Dépôt

```
machine-learning-for-trading-main/
├── 01_machine_learning_for_trading/        # Introduction, ML4T workflow
├── 02_market_and_fundamental_data/         # NASDAQ ITCH, Algoseek, SEC filings
│   ├── 01_NASDAQ_TotalView-ITCH_Order_Book/
│   ├── 02_algoseek_intraday/
│   └── 03_sec_edgar/
├── 03_alternative_data/                    # Web scraping, earnings calls transcripts
├── 04_alpha_factor_research/               # 100+ alpha factors, backtesting
├── 05_strategy_evaluation/                 # Portfolio optimization, pyfolio
├── 06_machine_learning_process/            # Cross-validation, hyperparameter tuning
├── 07_linear_models/                       # Linear regression, Lasso, Ridge, ElasticNet
│   ├── Fama-French factors
│   └── Risk factor models
├── 08_ml4t_workflow/                       # **NEW** Full workflow, Zipline integration
├── 09_time_series_models/                  # ARIMA, GARCH, cointegration, pairs trading
├── 10_bayesian_machine_learning/           # Bayesian methods, PyMC3, dynamic Sharpe
├── 11_decision_trees_random_forests/       # Long-short strategy (Japanese stocks)
├── 12_gradient_boosting_machines/          # XGBoost, LightGBM, CatBoost, intraday ML
├── 13_unsupervised_learning/               # PCA, k-means, hierarchical clustering
├── 14_working_with_text_data/              # Sentiment analysis, VADER, TextBlob
├── 15_topic_modeling/                      # LDA, NMF for financial news
├── 16_word_embeddings/                     # Word2Vec, GloVe, earnings calls, SEC filings
├── 17_deep_learning/                       # Feedforward networks, TensorFlow 2.2, Keras
├── 18_convolutional_neural_nets/           # **PAPER REPLICATION** : Time series → images (Sezer & Ozbahoglu 2018)
│   └── Satellite image classification (land use)
├── 19_recurrent_neural_nets/               # LSTM, GRU for multivariate time series
├── 20_autoencoders_for_conditional_risk_factors/  # **PAPER REPLICATION** : Asset pricing (Gu, Kelly, Xiu 2019)
├── 21_gans_for_synthetic_time_series/      # **PAPER REPLICATION** : TimeGAN (Yoon et al. 2019)
├── 22_deep_reinforcement_learning/         # PPO, DQN, DDPG for trading agent
├── 23_next_steps/                          # Deployment, production, next steps
├── 24_alpha_factor_library/                # **APPENDIX** : 100+ alpha factors catalog
├── data/                                   # Data download & preprocessing scripts
├── installation/                           # Docker, conda environments
├── figures/                                # Color charts from book
├── assets/                                 # Book cover, images
├── utils.py                                # Utility functions
└── README.md
```

---

## 3. CHAPITRES DÉTAILLÉS

### Part 1: Data to Strategy Development

#### Chapter 01 : ML for Trading - From Idea to Execution

**Topics** :
- Industry trends : Rise of ML in finance
- ML4T workflow diagram
- Use cases : alpha generation, risk management, execution

**Notebooks** : Introduction, workflow overview

---

#### Chapter 02 : Market & Fundamental Data

**Topics** :
- Trading infrastructure (exchanges, order types)
- NASDAQ TotalView ITCH protocol
  - Tick-by-tick order book reconstruction
  - 10+ GB files, binary format parsing
- Algoseek minute bars
  - OHLCV + bid/ask + volume imbalance
  - 2TB+ historical data
- SEC EDGAR filings
  - XBRL parsing (eXtensible Business Reporting Language)
  - 10-K, 10-Q financial statements
  - Fundamental ratios (P/E, P/B, ROE)

**Notebooks** :
- `01_NASDAQ_TotalView-ITCH_Order_Book/` : Parse ITCH binary, reconstruct LOB
- `02_algoseek_intraday/` : Load minute bars, feature engineering
- `03_sec_edgar/` : Download SEC filings, parse XBRL, extract financials

**Data sources** :
- NASDAQ : https://www.nasdaq.com/solutions/nasdaq-totalview
- Algoseek : https://www.algoseek.com/ml4t-book-data.html
- SEC EDGAR : https://www.sec.gov/edgar/searchedgar/companysearch.html

---

#### Chapter 03 : Alternative Data

**Topics** :
- Alternative data categories :
  - Social media (Twitter, Reddit, StockTwits)
  - News sentiment (Bloomberg, Reuters)
  - Web traffic (SimilarWeb)
  - Satellite imagery (Planet Labs)
  - Credit card transactions (Second Measure)
- Data evaluation criteria
- Web scraping techniques

**Notebooks** :
- Scrape earnings call transcripts (SeekingAlpha)
- Parse HTML, extract text
- Store in databases (SQLite, PostgreSQL)

**Tools** :
- BeautifulSoup, Scrapy
- Selenium (dynamic pages)
- PRAW (Reddit API)
- Tweepy (Twitter API)

---

#### Chapter 04 : Alpha Factor Research

**Topics** :
- Alpha factor definition
- Factor evaluation : IC, t-stat, turnover
- Quantiles analysis
- Alphalens integration

**100+ Alpha Factors** (from Appendix 24) :
- Momentum : 20+ factors (price momentum, volume momentum, RSI variants)
- Value : 15+ factors (P/E, P/B, EV/EBITDA, FCF yield)
- Quality : 10+ factors (ROE, ROIC, profit margins, accruals)
- Volatility : 8+ factors (realized vol, ATR, Bollinger %B)
- Volume : 5+ factors (OBV, Chaikin Money Flow, VWAP)
- Technical : 20+ factors (MACD, Stochastic, Williams %R)
- Fundamental : 15+ factors (earnings quality, growth rates)
- Statistical : 10+ factors (mean reversion, cointegration)

**Notebooks** :
- Factor creation from OHLCV + fundamentals
- Alphalens reports (tear sheets)
- Factor combination (weighted average, ML ensemble)

---

#### Chapter 05 : Portfolio Optimization & Performance

**Topics** :
- Mean-variance optimization (Markowitz)
- Risk parity
- Black-Litterman
- Performance metrics :
  - Sharpe, Sortino, Calmar, Omega
  - Max Drawdown, VaR, CVaR
  - Alpha, Beta, Information Ratio
- pyfolio integration

**Notebooks** :
- Portfolio construction from alpha signals
- Backtesting with pyfolio
- Tear sheets (returns, positions, transactions)
- Risk analysis (drawdown, rolling metrics)

**Tools** :
- pyfolio, empyrical, alphalens
- cvxpy (optimization)

---

### Part 2: ML Fundamentals

#### Chapter 06 : ML Process

**Topics** :
- Data prep (cleaning, outliers, missing values)
- Train/validation/test split
- Cross-validation for time series (walk-forward, purging, embargo)
- Hyperparameter tuning (grid search, random search, Bayesian optimization)
- Model evaluation (precision, recall, F1, ROC-AUC)

**Notebooks** :
- sklearn pipelines
- TimeSeriesSplit, PurgedKFold
- Optuna for Bayesian optimization

---

#### Chapter 07 : Linear Models

**Topics** :
- Linear regression, Ridge, Lasso, ElasticNet
- Fama-French 3-factor, 5-factor models
- Risk factor extraction
- Feature importance (coefficients)

**Notebooks** :
- Fama-French factor construction
- Risk-adjusted returns (alpha, beta)
- Factor exposure analysis

**Formulas** :

**Fama-French 3-Factor Model** :

$$
R_i - R_f = \alpha_i + \beta_{MKT}(R_M - R_f) + \beta_{SMB} SMB + \beta_{HML} HML + \epsilon_i
$$

où :
- $R_i$ = return de l'actif $i$
- $R_f$ = risk-free rate
- $R_M$ = market return
- $SMB$ = Small Minus Big (size factor)
- $HML$ = High Minus Low (value factor)

---

#### Chapter 08 : ML4T Workflow (NEW!)

**Topics** :
- Full workflow : Data → Features → Model → Strategy → Backtest
- Zipline integration with ML predictions
- Custom `Pipeline` API
- Alpha factor library usage

**Notebooks** :
- End-to-end ML strategy
- Zipline + sklearn + pyfolio
- Walk-forward optimization

**Key innovation** : Zipline customisé pour accepter ML predictions comme alpha factors.

---

#### Chapter 09 : Time Series Models

**Topics** :
- ARIMA, SARIMA for price forecasting
- GARCH for volatility forecasting
- Cointegration testing (Engle-Granger, Johansen)
- Pairs trading strategy

**Notebooks** :
- ARIMA parameter selection (ACF, PACF)
- GARCH(1,1) volatility modeling
- Cointegration pairs identification
- Pairs trading backtest (hedge ratio, z-score)

**Formulas** :

**GARCH(1,1)** :

$$
\begin{aligned}
r_t &= \mu + \epsilon_t \\
\epsilon_t &= \sigma_t z_t, \quad z_t \sim N(0,1) \\
\sigma_t^2 &= \omega + \alpha \epsilon_{t-1}^2 + \beta \sigma_{t-1}^2
\end{aligned}
$$

**Pairs Trading z-score** :

$$
z_t = \frac{(P_1 - \beta P_2)_t - \mu}{\sigma}
$$

Enter long when $z < -2$, exit when $z > 0$.

---

#### Chapter 10 : Bayesian ML

**Topics** :
- Bayesian inference with PyMC3
- Dynamic Sharpe ratio
- Pairs trading with Bayesian hedge ratio
- Markov Chain Monte Carlo (MCMC)

**Notebooks** :
- PyMC3 models
- Posterior sampling
- Credible intervals

**Formula** :

**Bayes' Theorem** :

$$
P(\theta | D) = \frac{P(D | \theta) P(\theta)}{P(D)}
$$

---

#### Chapter 11 : Decision Trees & Random Forests

**Topics** :
- Decision trees (CART algorithm)
- Random Forests ensemble
- Feature importance (Gini, permutation)
- **Long-short strategy for Japanese stocks**

**Notebooks** :
- sklearn DecisionTreeClassifier, RandomForestClassifier
- Feature engineering (100+ technical indicators)
- Walk-forward backtest
- Position sizing (equal-weighted, risk-parity)

---

#### Chapter 12 : Gradient Boosting Machines

**Topics** :
- XGBoost, LightGBM, CatBoost
- Hyperparameter tuning
- Early stopping
- **Intraday ML strategy with minute data**

**Notebooks** :
- Algoseek minute bars preprocessing
- Feature engineering (lag features, volume imbalance, bid-ask spread)
- XGBoost training (classification : up/down/neutral)
- Backtesting intraday strategy

**Performance** :
- LightGBM : ~10x faster than XGBoost
- CatBoost : Native categorical support

---

#### Chapter 13 : Unsupervised Learning

**Topics** :
- PCA (dimensionality reduction)
- K-means clustering (sector rotation)
- Hierarchical clustering (dendrograms)
- t-SNE, UMAP (visualization)

**Notebooks** :
- PCA for risk factor extraction
- K-means for stock clustering
- Hierarchical clustering for portfolio construction

**Formula** :

**PCA** :

$$
\mathbf{Z} = \mathbf{X} \mathbf{W}
$$

où $\mathbf{W}$ sont les eigenvectors de la covariance matrix $\mathbf{X}^T \mathbf{X}$.

---

### Part 3: NLP for Trading

#### Chapter 14 : Text Data & Sentiment Analysis

**Topics** :
- Text preprocessing (tokenization, lemmatization, stopwords)
- Bag of Words, TF-IDF
- Sentiment analysis :
  - VADER (lexicon-based)
  - TextBlob
  - FinBERT (transformer-based)
- Financial news sentiment → returns prediction

**Notebooks** :
- Scrape financial news (Reuters, Bloomberg API)
- Sentiment scoring
- Event study : CAR (Cumulative Abnormal Returns)

**Tools** :
- NLTK, spaCy
- VADER, TextBlob
- transformers (Hugging Face)

---

#### Chapter 15 : Topic Modeling

**Topics** :
- Latent Dirichlet Allocation (LDA)
- Non-negative Matrix Factorization (NMF)
- Topic coherence metrics
- Financial news summarization

**Notebooks** :
- LDA with Gensim
- NMF with sklearn
- Topic visualization (pyLDAvis)

**Formula** :

**LDA** : Each document is a mixture of topics, each topic is a mixture of words.

$$
P(w | d) = \sum_{k=1}^K P(w | z=k) P(z=k | d)
$$

---

#### Chapter 16 : Word Embeddings

**Topics** :
- Word2Vec (Skip-gram, CBOW)
- GloVe
- Earnings call transcripts analysis
- SEC filings (10-K, 8-K) embeddings
- Document similarity

**Notebooks** :
- Train Word2Vec on earnings calls
- Semantic similarity (cosine distance)
- Predict stock returns from text embeddings

**Formula** :

**Word2Vec Skip-gram objective** :

$$
\max_{\theta} \frac{1}{T} \sum_{t=1}^T \sum_{-c \leq j \leq c, j \neq 0} \log P(w_{t+j} | w_t; \theta)
$$

---

### Part 4: Deep & Reinforcement Learning

#### Chapter 17 : Deep Learning Fundamentals

**Topics** :
- Feedforward neural networks
- Activation functions (ReLU, ELU, Swish)
- Backpropagation, gradient descent
- Dropout, batch normalization
- TensorFlow 2.2, Keras

**Notebooks** :
- Build feedforward network for return prediction
- Hyperparameter tuning (layers, units, learning rate)
- TensorBoard visualization

---

#### Chapter 18 : CNN for Financial Time Series

**Topics** :
- **PAPER REPLICATION** : "Algorithmic Financial Trading with Deep CNNs: Time Series to Image Conversion Approach" (Sezer & Ozbahoglu, 2018)
- Convert time series → images (Gramian Angular Fields, GASF/GADF)
- CNN architecture (Conv2D → MaxPooling → Dense)
- Satellite image classification (land use prediction for commodities)

**Notebooks** :
- Time series → image conversion (pyts library)
- CNN training (TensorFlow/Keras)
- Backtesting CNN predictions

**Use case** : Predicting agricultural commodities prices from satellite images of crop land.

---

#### Chapter 19 : RNN for Multivariate Time Series

**Topics** :
- RNN, LSTM, GRU architectures
- Sequence-to-sequence models
- Multivariate time series prediction
- Sentiment + price combined

**Notebooks** :
- LSTM for next-day return prediction
- Multivariate input (OHLCV + sentiment + fundamentals)
- Attention mechanism

**Formula** :

**LSTM Cell** :

$$
\begin{aligned}
f_t &= \sigma(W_f [h_{t-1}, x_t] + b_f) \\
i_t &= \sigma(W_i [h_{t-1}, x_t] + b_i) \\
\tilde{C}_t &= \tanh(W_C [h_{t-1}, x_t] + b_C) \\
C_t &= f_t \odot C_{t-1} + i_t \odot \tilde{C}_t \\
o_t &= \sigma(W_o [h_{t-1}, x_t] + b_o) \\
h_t &= o_t \odot \tanh(C_t)
\end{aligned}
$$

---

#### Chapter 20 : Autoencoders for Asset Pricing

**Topics** :
- **PAPER REPLICATION** : "Autoencoder Asset Pricing Models" (Gu, Kelly, Xiu, 2019)
- Conditional risk factors
- Beta extraction from characteristics
- Non-linear asset pricing

**Notebooks** :
- Autoencoder architecture (encoder → bottleneck → decoder)
- Extract latent factors
- Asset pricing model evaluation

**Formula** :

**Autoencoder objective** :

$$
\min_{\theta, \phi} \mathbb{E}_{x \sim p(x)} [ \|x - d_\phi(e_\theta(x))\|^2 ]
$$

où $e_\theta$ = encoder, $d_\phi$ = decoder.

---

#### Chapter 21 : GANs for Synthetic Time Series

**Topics** :
- **PAPER REPLICATION** : "Time-series Generative Adversarial Networks" (Yoon et al., 2019)
- TimeGAN architecture
- Generate synthetic OHLCV data
- Data augmentation for ML models

**Notebooks** :
- TimeGAN training
- Evaluate synthetic data quality (discriminative score, predictive score)
- Use synthetic data to augment training set

**Formula** :

**GAN objective** :

$$
\min_G \max_D \mathbb{E}_{x \sim p_{data}} [\log D(x)] + \mathbb{E}_{z \sim p_z} [\log(1 - D(G(z)))]
$$

---

#### Chapter 22 : Deep Reinforcement Learning

**Topics** :
- RL fundamentals (MDP, Bellman equation)
- Q-learning, DQN
- Policy gradient methods (REINFORCE, PPO)
- Actor-Critic (A2C, A3C, DDPG)
- **Build trading agent**

**Notebooks** :
- Environment : OpenAI Gym wrapper for trading
- DQN agent (TensorFlow)
- PPO agent (stable-baselines3)
- Train on historical data
- Evaluate on test set

**Formula** :

**Bellman Equation** :

$$
Q(s, a) = r + \gamma \max_{a'} Q(s', a')
$$

**PPO objective** :

$$
L^{CLIP}(\theta) = \mathbb{E}_t \left[ \min\left( r_t(\theta) \hat{A}_t, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon) \hat{A}_t \right) \right]
$$

---

#### Chapter 23 : Next Steps

**Topics** :
- Deployment considerations
- Model monitoring
- Production infrastructure
- Risk management
- Regulatory considerations

---

#### Chapter 24 : Appendix - Alpha Factor Library

**100+ Alpha Factors catalogued** :

Categories :
1. **Momentum** (20 factors)
2. **Value** (15 factors)
3. **Quality** (10 factors)
4. **Volatility** (8 factors)
5. **Volume** (5 factors)
6. **Technical** (20 factors)
7. **Fundamental** (15 factors)
8. **Statistical** (10 factors)

Chaque factor inclut :
- Formula
- Rationale
- Expected holding period
- Expected IC
- References

---

## 4. DATA SOURCES

### Market Data

1. **NASDAQ TotalView ITCH**
   - Tick-by-tick order book data
   - 10+ GB per day
   - Binary format, custom parser

2. **Algoseek Minute Bars**
   - 2TB+ historical database
   - Equities, ETFs
   - OHLCV + bid/ask + volume imbalance
   - Available [here](https://www.algoseek.com/ml4t-book-data.html)

3. **Yahoo Finance** (yfinance)
   - Free daily OHLCV
   - Adjustments for splits/dividends

4. **Quandl**
   - Economic data, alternative data
   - Some datasets free

### Fundamental Data

1. **SEC EDGAR**
   - 10-K, 10-Q filings (quarterly/annual)
   - XBRL format
   - Free via edgar.sec.gov

2. **Compustat**
   - Standardized fundamental data
   - Paid (Wharton Research Data Services)

### Alternative Data

1. **Earnings Call Transcripts**
   - SeekingAlpha scraping
   - Quarterly earnings calls

2. **Financial News**
   - Reuters, Bloomberg APIs
   - News sentiment

3. **Satellite Images**
   - Planet Labs
   - Classify crop land, retail traffic, etc.

4. **Social Media**
   - Twitter (Tweepy)
   - Reddit (PRAW)
   - StockTwits API

---

## 5. ML MODELS COVERED

### Supervised Learning

1. **Linear Models**
   - Linear Regression
   - Ridge, Lasso, ElasticNet
   - Logistic Regression

2. **Tree-Based**
   - Decision Trees
   - Random Forests
   - XGBoost, LightGBM, CatBoost

3. **Deep Learning**
   - Feedforward Neural Networks
   - CNN (for images & time series)
   - RNN, LSTM, GRU
   - Autoencoders

### Unsupervised Learning

1. **Dimensionality Reduction**
   - PCA
   - t-SNE, UMAP

2. **Clustering**
   - K-means
   - Hierarchical clustering
   - DBSCAN

3. **Topic Modeling**
   - LDA
   - NMF

### Generative Models

1. **GANs**
   - TimeGAN (synthetic time series)

2. **VAE**
   - Variational Autoencoders

### Reinforcement Learning

1. **Value-Based**
   - Q-learning
   - DQN, DDQN

2. **Policy-Based**
   - REINFORCE
   - PPO (Proximal Policy Optimization)

3. **Actor-Critic**
   - A2C, A3C
   - DDPG

---

## 6. TOOLS & LIBRARIES

### Data

- **pandas** : DataFrames
- **numpy** : Numerical computing
- **yfinance** : Yahoo Finance API
- **pandas-datareader** : Multiple data sources
- **quandl** : Quandl API

### ML

- **scikit-learn** : Classical ML
- **xgboost** : Gradient boosting
- **lightgbm** : Fast gradient boosting
- **catboost** : Gradient boosting with categorical support
- **tensorflow** : Deep learning
- **keras** : High-level neural networks API
- **pytorch** : Alternative DL framework
- **stable-baselines3** : RL algorithms

### NLP

- **nltk** : Text preprocessing
- **spacy** : NLP pipeline
- **gensim** : Topic modeling, Word2Vec
- **transformers** : BERT, GPT models (Hugging Face)

### Backtesting

- **zipline-reloaded** : Quantopian backtesting engine (customized)
- **pyfolio-reloaded** : Performance analysis
- **alphalens-reloaded** : Alpha factor analysis
- **empyrical-reloaded** : Financial metrics

### Visualization

- **matplotlib** : Basic plots
- **seaborn** : Statistical visualization
- **plotly** : Interactive plots
- **bokeh** : Web-based visualization

### Bayesian

- **PyMC3** : Bayesian inference

### Optimization

- **cvxpy** : Convex optimization
- **scipy.optimize** : Optimization algorithms

---

## 7. INSTALLATION

### Docker (Recommended)

```bash
# Build image
docker build -t ml4t .

# Run Jupyter
docker run -p 8888:8888 ml4t

# Or enter container
docker run -it ml4t bash
```

### Conda Environments

Multiple environments fournis :
- `ml4t-base.yml` : Base environment (Python 3.8, pandas, numpy)
- `ml4t-zipline.yml` : Zipline environment (Python 3.6 for compatibility)
- `ml4t-dl.yml` : Deep learning (TensorFlow 2.2, Keras)
- `ml4t-rl.yml` : Reinforcement learning (stable-baselines3)

```bash
# Create environment
conda env create -f installation/ml4t-base.yml

# Activate
conda activate ml4t

# Install Zipline separately (Python 3.6)
conda env create -f installation/ml4t-zipline.yml
conda activate ml4t-zipline
```

### Data Download

```bash
# Run data download scripts
cd data/
python download_data.py
```

Data sources :
- Yahoo Finance (yfinance)
- Quandl
- SEC EDGAR
- Custom scrapers

---

## 8. EXEMPLES D'UTILISATION

### Example 1 : Alpha Factor Research

```python
import pandas as pd
from alphalens import performance as perf
from alphalens import plotting
from alphalens import tears

# Load price data
prices = pd.read_csv("prices.csv", index_col=0, parse_dates=True)

# Compute momentum factor (20-day return)
factor = prices.pct_change(20)

# Create forward returns (1-day, 5-day, 20-day)
forward_returns = pd.concat({
    '1D': prices.pct_change(1).shift(-1),
    '5D': prices.pct_change(5).shift(-5),
    '20D': prices.pct_change(20).shift(-20)
}, axis=1)

# Get alphalens formatted data
factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
    factor=factor.stack(),
    prices=prices,
    quantiles=5,
    periods=(1, 5, 20)
)

# Generate tear sheet
tears.create_full_tear_sheet(factor_data)
```

### Example 2 : ML Strategy with Zipline

```python
from zipline import run_algorithm
from zipline.api import order_target_percent, record, symbol
import pandas as pd

# Train ML model
model = xgboost.XGBClassifier()
model.fit(X_train, y_train)

# Zipline algorithm
def initialize(context):
    context.model = model
    context.universe = [symbol('AAPL'), symbol('MSFT'), symbol('GOOGL')]

def handle_data(context, data):
    # Get features
    features = compute_features(context, data)
    
    # Predict
    predictions = context.model.predict_proba(features)[:, 1]
    
    # Allocate
    for i, stock in enumerate(context.universe):
        weight = predictions[i] / predictions.sum()
        order_target_percent(stock, weight)
    
    # Record
    record(predictions=predictions.mean())

# Run backtest
results = run_algorithm(
    start=pd.Timestamp('2020-01-01'),
    end=pd.Timestamp('2021-01-01'),
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000
)

# Analyze with pyfolio
import pyfolio as pf
returns, positions, transactions = pf.utils.extract_rets_pos_txn_from_zipline(results)
pf.create_full_tear_sheet(returns, positions=positions, transactions=transactions)
```

### Example 3 : LSTM for Return Prediction

```python
import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

# Prepare sequences
def create_sequences(data, seq_length=60):
    X, y = [], []
    for i in range(seq_length, len(data)):
        X.append(data[i-seq_length:i])
        y.append(data[i, 3])  # Close price
    return np.array(X), np.array(y)

X_train, y_train = create_sequences(train_data, seq_length=60)

# Build LSTM model
model = Sequential([
    LSTM(50, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
    Dropout(0.2),
    LSTM(50, return_sequences=False),
    Dropout(0.2),
    Dense(25),
    Dense(1)
])

model.compile(optimizer='adam', loss='mse')

# Train
model.fit(X_train, y_train, batch_size=32, epochs=50, validation_split=0.2)

# Predict
predictions = model.predict(X_test)
```

---

## 9. PAPER REPLICATIONS

### 1. Sezer & Ozbahoglu (2018)
**"Algorithmic Financial Trading with Deep CNNs: Time Series to Image Conversion Approach"**
- Chapter 18
- Convert OHLCV → images (Gramian Angular Fields)
- Train CNN
- Predict next-day return

### 2. Gu, Kelly, Xiu (2019)
**"Autoencoder Asset Pricing Models"**
- Chapter 20
- Extract conditional risk factors
- Non-linear asset pricing
- Beats Fama-French models

### 3. Yoon, Jarrett, van der Schaar (2019)
**"Time-series Generative Adversarial Networks"**
- Chapter 21
- TimeGAN architecture
- Synthetic time series generation
- Data augmentation

---

## 10. POINTS FORTS & LIMITATIONS

### ✅ Points Forts

1. **Comprehensive** : Tout le workflow ML4T, 800+ pages
2. **Hands-on** : 150+ notebooks exécutés
3. **Production-ready** : Docker, conda, data pipelines
4. **Recent** : 2nd edition (2020), TF 2.2, Pandas 1.2
5. **Research** : Réplications de papers top journals
6. **Community** : Platform dédiée https://exchange.ml4trading.io/
7. **Alpha factors** : 100+ catalogués dans appendix
8. **Data diversity** : Market, fundamental, alternative (satellite!)
9. **Backtesting** : Zipline customisé avec ML integration
10. **Author expertise** : Stefan Jansen (Applied AI, quantitative trading)

### ⚠️ Limitations

1. **Complexité** : 800 pages, courbe d'apprentissage raide
2. **Data access** : Certaines data sources payantes (Algoseek, Compustat)
3. **Zipline deprecated** : Quantopian fermé, zipline-reloaded fork
4. **Python only** : Pas de C++/Julia/R
5. **Pas de live trading** : Backtesting uniquement, pas d'execution live
6. **Dependencies** : Nombreuses librairies, conflicts possibles
7. **GPU recommended** : Deep learning lent sans GPU
8. **Overfitting risk** : Nombreux exemples sur mêmes datasets
9. **Transaction costs** : Souvent simplifiés dans backtests
10. **Market regime** : Stratégies peuvent ne pas généraliser

### 💡 Cas d'Usage Idéaux

- **Learning** : Apprendre ML for trading de A à Z
- **Research** : Tester nouvelles idées, replicate papers
- **Strategy development** : Prototyper stratégies ML
- **Feature engineering** : 100+ alpha factors catalog
- **Academic** : Thèse, mémoire, publications
- **Interviews** : Préparer quant/data science interviews
- **Transition** : De traditional quant → ML quant

---

## 11. RESSOURCES

### Book

- **Amazon** : https://www.amazon.com/Machine-Learning-Algorithmic-Trading-alternative/dp/1839217715
- **GitHub** : https://github.com/stefan-jansen/machine-learning-for-trading
- **Website** : https://ml4trading.io

### Community

- **ML4T Exchange** : https://exchange.ml4trading.io/ (2K+ members)
- **GitHub Issues** : https://github.com/stefan-jansen/machine-learning-for-trading/issues
- **LinkedIn** : Stefan Jansen profile

### Data

- **Algoseek** : https://www.algoseek.com/ml4t-book-data.html
- **SEC EDGAR** : https://www.sec.gov/edgar/
- **Quandl** : https://www.quandl.com/

### Papers Replicated

- Sezer & Ozbahoglu (2018) : CNN for time series
- Gu, Kelly, Xiu (2019) : Autoencoders for asset pricing
- Yoon et al. (2019) : TimeGAN

### Related Books

- "Advances in Financial Machine Learning" (Marcos López de Prado)
- "Machine Learning and Data Science Blueprints for Finance" (Hariom Tatsat)

================================================================================
FIN DE L'AUDIT - MACHINE LEARNING FOR ALGORITHMIC TRADING
================================================================================
