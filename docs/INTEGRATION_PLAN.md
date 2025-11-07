# 🗓️ Plan d'Intégration FinBot v2.0

## 📋 Vue d'ensemble

Ce document décrit le plan détaillé d'intégration des 7 forks majeurs dans FinBot v2.0, organisé en **8 phases séquentielles** avec dépendances explicites, durées estimées, et livrables clairs.

**Forks intégrés** :
1. **FinanceDatabase** : 300,000+ symboles
2. **FinanceToolkit** : 150+ ratios financiers
3. **Finance Fork** : 150 programmes (40+ indicateurs, 25+ stratégies)
4. **backtesting.py** : Framework vectorisé
5. **PyPortfolioOpt** : Mean-Variance, HRP, Black-Litterman
6. **Riskfolio-Lib** : 24 mesures de risque, NCO
7. **ML4T** : Workflows ML4Trading complets

---

## 🎯 Principes Directeurs

1. **Best-of-breed** : Utiliser les libs directement, pas de réimplémentation
2. **Wrapping minimal** : Seulement si nécessaire pour harmoniser l'API
3. **Tests first** : Chaque module livré avec tests unitaires (80%+ coverage)
4. **Documentation inline** : Docstrings Google style obligatoires
5. **Validation continue** : Chaque phase validée avant passage à la suivante

---

## 📊 Timeline Globale

```
Phase 0: Setup & Documentation          [✅ EN COURS]     1 jour
Phase 1: Data Layer                     [⏳ NEXT]        3 jours
Phase 2: Features Layer                 [⏸️ PENDING]     4 jours
Phase 3: Backtesting Layer              [⏸️ PENDING]     3 jours
Phase 4: Portfolio Layer                [⏸️ PENDING]     3 jours
Phase 5: ML Layer                       [⏸️ PENDING]     5 jours
Phase 6: Analysis Layer                 [⏸️ PENDING]     3 jours
Phase 7: API & Dashboard                [⏸️ PENDING]     4 jours
                                        ─────────────────────────
                                        TOTAL: 26 jours
```

---

## 📦 Phase 0 : Setup & Documentation

**Statut** : ✅ EN COURS  
**Durée** : 1 jour  
**Dépendances** : Aucune

### Objectif
Préparer l'infrastructure et la documentation complète avant le développement.

### Fichiers à créer
- [x] `.github/copilot-instructions.md` (conventions v2.0)
- [ ] `docs/ARCHITECTURE.md` (ce fichier en cours)
- [ ] `docs/INTEGRATION_PLAN.md` (ce fichier)
- [ ] `docs/API_REFERENCE.md` (référence APIs)
- [ ] `requirements.txt` (dépendances complètes)
- [ ] `setup.py` (package configuration)
- [ ] `.env.example` (template variables d'environnement)

### Librairies/Forks
Aucune intégration de code, uniquement documentation.

### Tests associés
Aucun test, uniquement validation documentation.

### Livrables
- ✅ Documentation architecture complète (diagrammes, modules, flows)
- ✅ Plan d'intégration détaillé (ce document)
- ✅ Référence APIs exhaustive (signatures, exemples)
- ✅ requirements.txt avec toutes les dépendances
- ✅ setup.py pour installation package
- ✅ .env.example avec clés API nécessaires

### Validation
- [ ] Review documentation par l'équipe
- [ ] Tous les diagrammes de flow clairement lisibles
- [ ] API_REFERENCE.md couvre tous les modules planifiés
- [ ] requirements.txt installable sans erreur

---

## 📦 Phase 1 : Data Layer

**Statut** : ⏳ NEXT  
**Durée** : 3 jours  
**Dépendances** : Phase 0 complète

### Objectif
Mettre en place l'acquisition de données depuis toutes les sources externes.

### Fichiers à créer

#### Jour 1 : Universe Selection
```
src/financial_analyzer/data/
├── __init__.py
└── universe.py                          # FinanceDatabase wrapper
```

**Classes** :
- `UniverseSelector` : Wrapper FinanceDatabase
  - `select_equities(sector, industry, market_cap, country, exchange)`
  - `select_etfs(category, family)`
  - `select_funds(fund_type, family)`
  - `select_crypto(exchange)`
  - `get_all_symbols(asset_class)`

#### Jour 2 : Market Data & Fundamentals
```
src/financial_analyzer/data/
├── market_data.py                       # FinanceToolkit + yfinance
└── fundamentals.py                      # FinanceToolkit ratios
```

**Classes** :
- `MarketDataFetcher` : Wrapper FinanceToolkit/yfinance
  - `get_historical_data(tickers, start, end, interval)`
  - `get_intraday_data(tickers, interval='1m')`
  - `get_latest_price(tickers)`
  - `validate_ohlcv(df)`

- `FundamentalsProvider` : Wrapper FinanceToolkit
  - `get_all_ratios(tickers, period='quarterly')`
  - `get_income_statement(tickers)`
  - `get_balance_sheet(tickers)`
  - `get_cash_flow(tickers)`

#### Jour 3 : Alternative Data
```
src/financial_analyzer/data/
└── alternative.py                       # Finance fork scrapers
```

**Classes** :
- `AlternativeDataProvider` : Scrapers Finance fork
  - `get_news_sentiment(ticker, start, end)`
  - `get_social_sentiment(ticker, source='twitter')`
  - `get_insider_trades(ticker)`
  - `get_analyst_ratings(ticker)`

### Forks/Libs utilisés
- **FinanceDatabase** : `from financedatabase import Equities, ETFs, Funds, Cryptocurrencies`
- **FinanceToolkit** : `from financetoolkit import Toolkit`
- **yfinance** : `import yfinance as yf` (fallback)
- **Finance Fork** : Copier `scrapers/` directement

### Tests associés
```
tests/test_data/
├── __init__.py
├── test_universe.py                     # 10 tests
├── test_market_data.py                  # 15 tests
├── test_fundamentals.py                 # 12 tests
└── test_alternative.py                  # 8 tests
                                         ─────────
                                         45 tests
```

**Tests clés** :
- Mock toutes les APIs externes (FinanceToolkit, yfinance)
- Validation format OHLCV (DatetimeIndex, colonnes, no NaN)
- Validation ratios (multi-index, 150+ colonnes)
- Error handling (API timeout, invalid ticker)
- Cache fonctionnel (disk/Redis)

### Livrables
- ✅ Universe selector opérationnel (300K+ symboles)
- ✅ Market data fetcher avec fallback yfinance
- ✅ Fundamentals provider (150+ ratios)
- ✅ Alternative data scrapers (news, social, insider)
- ✅ 45 tests unitaires (80%+ coverage)
- ✅ Documentation API_REFERENCE.md mise à jour

### Validation
- [ ] Récupération OHLCV pour 10 tickers sans erreur
- [ ] Récupération 150+ ratios pour 5 tickers
- [ ] News sentiment pour AAPL sur 1 an
- [ ] Tous les tests passent (45/45)
- [ ] Coverage data/ >= 80%

---

## 📦 Phase 2 : Features Layer

**Statut** : ⏸️ PENDING  
**Durée** : 4 jours  
**Dépendances** : Phase 1 complète

### Objectif
Feature engineering complet : indicateurs techniques, ratios, alpha factors, sentiment.

### Fichiers à créer

#### Jour 1-2 : Technical Indicators
```
src/financial_analyzer/features/
├── __init__.py
└── technical.py                         # Finance fork ta_functions.py
```

**Approche** : Copier DIRECTEMENT `ta_functions.py` du fork Finance (40+ indicateurs).

**Fonctions principales** :
```python
# Trend indicators
calculate_sma(prices, window)
calculate_ema(prices, window)
calculate_macd(prices, fast, slow, signal)
calculate_adx(prices, window)

# Momentum indicators
calculate_rsi(prices, window)
calculate_stochastic(prices, k_window, d_window)
calculate_cci(prices, window)
calculate_williams_r(prices, window)

# Volatility indicators
calculate_bollinger_bands(prices, window, num_std)
calculate_atr(prices, window)
calculate_keltner_channels(prices, window)

# Volume indicators
calculate_obv(prices)
calculate_vwap(prices)
calculate_mfi(prices, window)

# 40+ indicateurs au total
```

**Wrapper** :
```python
class TechnicalFeatures:
    """Wrapper pour calculs vectorisés de tous les indicateurs."""
    
    def calculate_all_indicators(
        self,
        prices: pd.DataFrame,
        config: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        Calcule tous les indicateurs techniques.
        
        Returns:
            DataFrame avec 40+ colonnes d'indicateurs
        """
```

#### Jour 3 : Fundamental Features
```
src/financial_analyzer/features/
└── fundamental.py                       # Transform FinanceToolkit ratios
```

**Classes** :
- `FundamentalFeatures` : Transforme ratios en features ML
  - `create_fundamental_features(ratios)` : Lags, deltas, z-scores
  - `create_value_factors(ratios)` : PE, PB, EV/EBITDA
  - `create_quality_factors(ratios)` : ROE, ROA, margins
  - `create_growth_factors(ratios)` : Revenue growth, EPS growth

#### Jour 4 : Alpha Factors & Sentiment
```
src/financial_analyzer/features/
├── alpha_factors.py                     # ML4T factors
└── sentiment.py                         # FinBERT NLP
```

**Classes** :
- `AlphaFactors` : 100+ alpha factors ML4T
  - `calculate_momentum_factors(prices)` : Returns 1d, 5d, 20d, 60d
  - `calculate_value_factors(ratios)` : Value score composite
  - `calculate_quality_factors(ratios)` : Quality score composite
  - `calculate_technical_factors(prices)` : RSI, MACD z-scores

- `SentimentAnalyzer` : FinBERT NLP
  - `analyze_text(texts)` : Sentiment scores [-1, 1]
  - `analyze_news(ticker, start, end)` : Aggregate news sentiment
  - `analyze_social(ticker)` : Social media sentiment

### Forks/Libs utilisés
- **Finance Fork** : Copier `ta_functions.py` directement
- **FinanceToolkit** : Ratios déjà récupérés (Phase 1)
- **ML4T** : Implémenter alpha factors (101 Alphas paper)
- **transformers** : `from transformers import AutoTokenizer, AutoModelForSequenceClassification`
- **FinBERT** : Modèle pré-entraîné `ProsusAI/finbert`

### Tests associés
```
tests/test_features/
├── __init__.py
├── test_technical.py                    # 20 tests (1 par indicateur)
├── test_fundamental.py                  # 10 tests
├── test_alpha_factors.py                # 15 tests
└── test_sentiment.py                    # 8 tests
                                         ─────────
                                         53 tests
```

**Tests clés** :
- Validation chaque indicateur (SMA, RSI, MACD, etc.)
- Validation outputs (no NaN, correct range)
- Vectorisation (no loops Python)
- Alpha factors (momentum, value, quality, technical)
- Sentiment analysis (FinBERT predictions [-1, 1])

### Livrables
- ✅ 40+ indicateurs techniques opérationnels
- ✅ Fundamental features (value, quality, growth)
- ✅ 100+ alpha factors ML4T
- ✅ Sentiment analyzer FinBERT
- ✅ 53 tests unitaires (80%+ coverage)
- ✅ Documentation API_REFERENCE.md mise à jour

### Validation
- [ ] Calcul 40+ indicateurs pour AAPL sur 5 ans (< 1s)
- [ ] Features fundamentales pour 50 tickers
- [ ] 100+ alpha factors pour univers Russell 3000 (< 5 min)
- [ ] Sentiment analysis pour 1000 news articles (< 30s)
- [ ] Tous les tests passent (53/53)
- [ ] Coverage features/ >= 80%

---

## 📦 Phase 3 : Backtesting Layer

**Statut** : ⏸️ PENDING  
**Durée** : 3 jours  
**Dépendances** : Phase 1 (data) + Phase 2 (features) complètes

### Objectif
Intégrer backtesting.py et implémenter stratégies techniques/quantitatives.

### Fichiers à créer

#### Jour 1 : Engine & Base
```
src/financial_analyzer/backtesting/
├── __init__.py
├── engine.py                            # backtesting.py wrapper
└── strategies/
    ├── __init__.py
    └── base.py                          # BaseStrategy helpers
```

**Classes** :
- `BacktestEngine` : Wrapper backtesting.py
  - `run_backtest(data, strategy, **params)`
  - `get_metrics()`
  - `plot_results()`
  - `export_trades(path)`

- `BaseStrategy` : Helpers pour toutes nos stratégies
  - Méthodes utilitaires (crossover, position sizing, stop loss)

#### Jour 2 : Technical Strategies
```
src/financial_analyzer/backtesting/strategies/
└── technical_strategies.py              # Finance fork strategies
```

**Stratégies** (25+ du fork Finance) :
```python
class SMAStrategy(BaseStrategy):
    """SMA crossover (Golden Cross)."""

class RSIStrategy(BaseStrategy):
    """RSI overbought/oversold."""

class MACDStrategy(BaseStrategy):
    """MACD signal crossover."""

class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands mean reversion."""

class BreakoutStrategy(BaseStrategy):
    """Price breakout (ATR-based)."""

# 25+ stratégies au total
```

#### Jour 3 : Optimization
```
src/financial_analyzer/backtesting/
└── optimize.py                          # Grid search + Bayesian
```

**Classes** :
- `StrategyOptimizer` : Optimisation paramètres
  - `grid_search(data, strategy, param_grid)`
  - `bayesian_optimize(data, strategy, param_bounds)`
  - `walk_forward_optimization(data, strategy, param_grid)`

### Forks/Libs utilisés
- **backtesting.py** : `from backtesting import Backtest, Strategy`
- **Finance Fork** : Copier `strategies/` (25+ stratégies)
- **scikit-optimize** : `from skopt import gp_minimize` (Bayesian)

### Tests associés
```
tests/test_backtesting/
├── __init__.py
├── test_engine.py                       # 12 tests
├── test_technical_strategies.py         # 25 tests (1 par stratégie)
└── test_optimize.py                     # 8 tests
                                         ─────────
                                         45 tests
```

**Tests clés** :
- Mock backtesting.py (fast execution)
- Validation chaque stratégie (trades générés, metrics calculés)
- Grid search (exhaustif, best params)
- Bayesian optimization (convergence, best params)
- Walk-forward (in-sample, out-of-sample)

### Livrables
- ✅ Wrapper backtesting.py harmonisé
- ✅ 25+ stratégies techniques opérationnelles
- ✅ Grid search + Bayesian optimization
- ✅ Walk-forward optimization
- ✅ 45 tests unitaires (80%+ coverage)
- ✅ Documentation API_REFERENCE.md mise à jour

### Validation
- [ ] Backtest SMA strategy sur AAPL 5 ans (< 500ms)
- [ ] Backtest 25 stratégies sur S&P 500 (< 5 min)
- [ ] Grid search RSI params (window, overbought, oversold)
- [ ] Bayesian optimization MACD params (convergence < 50 iterations)
- [ ] Tous les tests passent (45/45)
- [ ] Coverage backtesting/ >= 80%

---

## 📦 Phase 4 : Portfolio Layer

**Statut** : ⏸️ PENDING  
**Durée** : 3 jours  
**Dépendances** : Phase 1 (data) complète

### Objectif
Optimisation de portefeuille avec PyPortfolioOpt et Riskfolio-Lib.

### Fichiers à créer

#### Jour 1 : PyPortfolioOpt Integration
```
src/financial_analyzer/portfolio/
├── __init__.py
└── optimizer.py                         # PyPortfolioOpt wrapper
```

**Classes** :
- `PortfolioOptimizer` : Wrapper PyPortfolioOpt
  - `optimize_mean_variance(prices, objective='max_sharpe')`
  - `optimize_hrp(prices)`
  - `optimize_black_litterman(prices, views)`
  - `optimize_cla(prices)`
  - `get_efficient_frontier(prices)`

#### Jour 2 : Riskfolio-Lib Integration
```
src/financial_analyzer/portfolio/
└── risk_optimizer.py                    # Riskfolio-Lib wrapper
```

**Classes** :
- `RiskOptimizer` : Wrapper Riskfolio-Lib
  - `optimize_cvar(returns, alpha=0.05)`
  - `optimize_worst_case(returns)`
  - `optimize_nco(returns)` (Nested Clustered Optimization)
  - `calculate_risk_measures(returns, weights)` (24 mesures)

#### Jour 3 : Allocation & Rebalancing
```
src/financial_analyzer/portfolio/
├── allocation.py                        # DiscreteAllocation
└── rebalancing.py                       # Rebalancing strategies
```

**Classes** :
- `DiscreteAllocator` : Conversion poids → actions
  - `allocate(weights, prices, total_value)`
  - `lp_portfolio(weights, prices, total_value)` (Linear Programming)

- `RebalancingManager` : Stratégies rebalancing
  - `threshold_rebalancing(current, target, threshold)`
  - `calendar_rebalancing(current, target, frequency)`
  - `calculate_rebalancing_cost(current, target, prices, commission)`

### Forks/Libs utilisés
- **PyPortfolioOpt** : `from pypfopt import EfficientFrontier, risk_models, expected_returns, HRPOpt, BlackLittermanModel, CLA, DiscreteAllocation`
- **Riskfolio-Lib** : `import riskfolio as rp`
- **cvxpy** : `import cvxpy as cp` (solver convex optimization)

### Tests associés
```
tests/test_portfolio/
├── __init__.py
├── test_optimizer.py                    # 15 tests
├── test_risk_optimizer.py               # 12 tests
├── test_allocation.py                   # 8 tests
└── test_rebalancing.py                  # 6 tests
                                         ─────────
                                         41 tests
```

**Tests clés** :
- Validation weights (sum=1, [0,1], no short)
- Mean-Variance (max Sharpe, min volatility)
- HRP (hierarchical clustering)
- Black-Litterman (subjective views)
- CVaR optimization (risk measures)
- Discrete allocation (integer shares, leftover cash)
- Rebalancing (threshold, calendar)

### Livrables
- ✅ PyPortfolioOpt wrapper (MV, HRP, BL, CLA)
- ✅ Riskfolio-Lib wrapper (CVaR, NCO, 24 risk measures)
- ✅ Discrete allocation (integer shares)
- ✅ Rebalancing strategies (threshold, calendar)
- ✅ 41 tests unitaires (80%+ coverage)
- ✅ Documentation API_REFERENCE.md mise à jour

### Validation
- [ ] Optimisation Mean-Variance sur 50 tickers (< 1s)
- [ ] HRP sur Russell 3000 (< 30s)
- [ ] Black-Litterman avec 10 views subjectives
- [ ] CVaR optimization (alpha=0.05) sur 100 tickers
- [ ] Discrete allocation pour $100K sur 30 tickers
- [ ] Tous les tests passent (41/41)
- [ ] Coverage portfolio/ >= 80%

---

## 📦 Phase 5 : ML Layer

**Statut** : ⏸️ PENDING  
**Durée** : 5 jours  
**Dépendances** : Phase 2 (features) complète

### Objectif
Modèles de Machine Learning pour prédictions et stratégies ML-based.

### Fichiers à créer

#### Jour 1 : Tree-Based Models
```
src/financial_analyzer/ml/
├── __init__.py
└── models/
    ├── __init__.py
    └── tree_based.py                    # XGBoost, LightGBM, RF
```

**Classes** :
- `XGBoostPredictor` : XGBoost regression/classification
- `LightGBMPredictor` : LightGBM model
- `RandomForestPredictor` : Random Forest ensemble

#### Jour 2 : Timeseries Models
```
src/financial_analyzer/ml/models/
└── timeseries.py                        # ARIMA, Prophet, LSTM
```

**Classes** :
- `ARIMAPredictor` : ARIMA forecasting
- `ProphetPredictor` : Facebook Prophet
- `LSTMPredictor` : LSTM neural network

#### Jour 3 : Neural Networks
```
src/financial_analyzer/ml/models/
└── neural_nets.py                       # LSTM, GRU, Transformer
```

**Classes** :
- `LSTMRegressor` : LSTM pour séries temporelles
- `GRURegressor` : GRU (variante LSTM)
- `TransformerPredictor` : Transformer pour finance

#### Jour 4 : Ensemble & Deep RL
```
src/financial_analyzer/ml/
├── ensemble.py                          # Model stacking/blending
└── deep_rl.py                           # DQN, PPO agents
```

**Classes** :
- `ModelEnsemble` : Stacking/blending de modèles
- `DQNAgent` : Deep Q-Network for trading
- `PPOAgent` : Proximal Policy Optimization

#### Jour 5 : Feature Selection & ML Strategies
```
src/financial_analyzer/ml/
└── feature_selection.py                 # RFE, importance-based

src/financial_analyzer/backtesting/strategies/
└── ml_strategies.py                     # ML-based strategies
```

**Classes** :
- `FeatureSelector` : Recursive Feature Elimination
- `MLPredictiveStrategy(BaseStrategy)` : Strategy basée sur ML
- `EnsembleStrategy(BaseStrategy)` : Strategy avec ensemble models

### Forks/Libs utilisés
- **scikit-learn** : `from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor`
- **XGBoost** : `from xgboost import XGBRegressor, XGBClassifier`
- **LightGBM** : `from lightgbm import LGBMRegressor, LGBMClassifier`
- **Prophet** : `from prophet import Prophet`
- **TensorFlow/Keras** : `from tensorflow.keras.models import Sequential`
- **PyTorch** : `import torch, torch.nn as nn`
- **ML4T** : Workflows ML4Trading

### Tests associés
```
tests/test_ml/
├── __init__.py
├── test_tree_based.py                   # 12 tests
├── test_timeseries.py                   # 10 tests
├── test_neural_nets.py                  # 8 tests
├── test_ensemble.py                     # 6 tests
├── test_deep_rl.py                      # 8 tests
├── test_feature_selection.py            # 5 tests
└── test_ml_strategies.py                # 10 tests
                                         ─────────
                                         59 tests
```

**Tests clés** :
- TimeSeriesSplit obligatoire (JAMAIS train_test_split)
- Validation predictions (no NaN, correct shape)
- Feature importance (ranking, selection)
- Ensemble (stacking > individual models)
- Deep RL (convergence, profit)
- ML strategies (backtest performance)

### Livrables
- ✅ XGBoost, LightGBM, Random Forest opérationnels
- ✅ ARIMA, Prophet, LSTM timeseries models
- ✅ LSTM, GRU, Transformer neural networks
- ✅ Model ensemble (stacking, blending)
- ✅ Deep RL agents (DQN, PPO)
- ✅ Feature selection (RFE, importance-based)
- ✅ ML-based strategies pour backtesting
- ✅ 59 tests unitaires (80%+ coverage)
- ✅ Documentation API_REFERENCE.md mise à jour

### Validation
- [ ] XGBoost prédiction returns sur 1000 tickers (< 5s)
- [ ] LSTM training sur 5 ans de données (< 2 min)
- [ ] Ensemble (XGBoost + RF + LSTM) meilleur que modèles individuels
- [ ] DQN agent profitable sur backtest 3 ans
- [ ] Feature selection (100 features → 20 features, performance stable)
- [ ] Tous les tests passent (59/59)
- [ ] Coverage ml/ >= 80%

---

## 📦 Phase 6 : Analysis Layer

**Statut** : ⏸️ PENDING  
**Durée** : 3 jours  
**Dépendances** : Phases 1-5 complètes

### Objectif
Compléter le module analysis avec valorisation, options, performance, risk.

### Fichiers à créer

#### Jour 1 : Valuation & Options
```
src/financial_analyzer/analysis/
├── valuation.py                         # DCF, DDM, WACC
└── options.py                           # Black-Scholes, Greeks
```

**Classes** :
- `Valuator` : Valorisation d'entreprises
  - `dcf_valuation(ticker)` : Discounted Cash Flow
  - `ddm_valuation(ticker)` : Dividend Discount Model
  - `calculate_wacc(ticker)` : Weighted Average Cost of Capital

- `OptionsAnalyzer` : Pricing et Greeks d'options
  - `black_scholes(S, K, T, r, sigma, type)`
  - `calculate_greeks(S, K, T, r, sigma)` : Delta, Gamma, Theta, Vega, Rho
  - `implied_volatility(option_price, S, K, T, r, type)`

#### Jour 2 : Performance Metrics
```
src/financial_analyzer/analysis/
└── performance.py                       # Sharpe, Sortino, Alpha, Beta
```

**Fonctions** :
```python
def calculate_sharpe_ratio(returns, risk_free_rate)
def calculate_sortino_ratio(returns, risk_free_rate, target_return)
def calculate_alpha_beta(returns, benchmark_returns, risk_free_rate)
def calculate_information_ratio(returns, benchmark_returns)
def calculate_calmar_ratio(returns, max_drawdown)
def calculate_omega_ratio(returns, threshold)
# 20+ métriques de performance
```

#### Jour 3 : Risk Metrics (déjà créé en Semaine 3)
```
src/financial_analyzer/risk/
└── metrics.py                           # VaR, CVaR, drawdown
```

**Fonctions** (déjà implémentées) :
```python
def calculate_var(returns, alpha, method)
def calculate_cvar(returns, alpha)
def calculate_max_drawdown(equity_curve)
def calculate_drawdown_duration(equity_curve)
# 15+ métriques de risque
```

### Forks/Libs utilisés
- **FinanceToolkit** : `toolkit.models.get_discounted_cash_flow()`
- **FinanceToolkit** : `toolkit.options.get_black_scholes()`
- **scipy.stats** : `from scipy.stats import norm` (Black-Scholes)
- **numpy** : Calculs vectorisés

### Tests associés
```
tests/test_analysis/
├── test_valuation.py                    # 10 tests
├── test_options.py                      # 12 tests
└── test_performance.py                  # 15 tests
                                         ─────────
                                         37 tests
```

**Note** : `test_analysis.py` (Semaine 3) déjà existant avec 40 tests pour BacktestEngine et MLPredictor.

**Tests clés** :
- DCF valuation (cashflows, WACC, terminal value)
- Black-Scholes (call/put pricing, parity)
- Greeks (Delta [0,1], Gamma convexity, Theta decay)
- Implied volatility (Newton-Raphson convergence)
- Performance metrics (Sharpe, Sortino, Alpha, Beta)

### Livrables
- ✅ Valuator (DCF, DDM, WACC) via FinanceToolkit
- ✅ OptionsAnalyzer (Black-Scholes, Greeks, IV)
- ✅ Performance metrics (20+ métriques)
- ✅ 37 nouveaux tests unitaires (80%+ coverage)
- ✅ Documentation API_REFERENCE.md mise à jour

### Validation
- [ ] DCF valuation pour AAPL (valeur intrinsèque)
- [ ] Black-Scholes pricing pour 100 options (< 1s)
- [ ] Greeks calculation (Delta hedge portfolio)
- [ ] Implied volatility pour 50 options (< 2s)
- [ ] Performance metrics pour 1000 backtests (< 10s)
- [ ] Tous les tests passent (37/37 nouveaux)
- [ ] Coverage analysis/ >= 80%

---

## 📦 Phase 7 : API & Dashboard

**Statut** : ⏸️ PENDING  
**Durée** : 4 jours  
**Dépendances** : Phases 1-6 complètes

### Objectif
Exposer toute la plateforme via REST API et créer dashboard Streamlit.

### Fichiers à créer

#### Jour 1-2 : REST API
```
src/financial_analyzer/api/
├── __init__.py
├── main.py                              # FastAPI app
├── routes/
│   ├── __init__.py
│   ├── data.py                          # /api/data/*
│   ├── backtest.py                      # /api/backtest/*
│   ├── portfolio.py                     # /api/portfolio/*
│   └── ml.py                            # /api/ml/*
└── models/
    ├── __init__.py
    ├── requests.py                      # Pydantic request models
    └── responses.py                     # Pydantic response models
```

**Endpoints principaux** :
```python
# Data
POST /api/data/universe          # Sélection symboles
POST /api/data/market-data       # Récupération OHLCV
POST /api/data/fundamentals      # Récupération ratios

# Backtest
POST /api/backtest/run           # Exécuter backtest
POST /api/backtest/optimize      # Optimiser paramètres
GET  /api/backtest/results/{id}  # Récupérer résultats

# Portfolio
POST /api/portfolio/optimize     # Optimiser portfolio
POST /api/portfolio/allocate     # Allocation discrète
POST /api/portfolio/rebalance    # Signaux rebalancing

# ML
POST /api/ml/train               # Entraîner modèle
POST /api/ml/predict             # Prédictions
GET  /api/ml/models              # Liste modèles disponibles
```

#### Jour 3-4 : Dashboard Streamlit
```
src/financial_analyzer/dashboard/
├── __init__.py
├── streamlit_app.py                     # Main app
└── components/
    ├── __init__.py
    ├── data_explorer.py                 # Data visualization
    ├── backtest_viewer.py               # Backtest results
    ├── portfolio_builder.py             # Portfolio construction
    └── ml_dashboard.py                  # ML model performance
```

**Pages dashboard** :
1. **Data Explorer** : Sélection universe, visualisation OHLCV, ratios
2. **Backtest** : Choix stratégie, paramètres, exécution, résultats
3. **Portfolio** : Optimisation, allocation, rebalancing
4. **ML Dashboard** : Entraînement, prédictions, feature importance

### Forks/Libs utilisés
- **FastAPI** : `from fastapi import FastAPI, HTTPException, BackgroundTasks`
- **Pydantic** : `from pydantic import BaseModel, Field, validator`
- **Uvicorn** : `import uvicorn` (ASGI server)
- **Streamlit** : `import streamlit as st`
- **Plotly** : `import plotly.express as px, plotly.graph_objects as go`

### Tests associés
```
tests/test_api/
├── __init__.py
├── test_main.py                         # 5 tests
├── test_data_routes.py                  # 10 tests
├── test_backtest_routes.py              # 12 tests
├── test_portfolio_routes.py             # 8 tests
└── test_ml_routes.py                    # 10 tests
                                         ─────────
                                         45 tests
```

**Tests clés** :
- `TestClient` FastAPI (HTTP requests/responses)
- Validation Pydantic models (requests, responses)
- Authentication (API keys, JWT tokens)
- Rate limiting
- Error handling (4xx, 5xx)
- Background tasks (long-running backtests)

### Livrables
- ✅ REST API FastAPI complète (15+ endpoints)
- ✅ Pydantic models pour tous les endpoints
- ✅ Dashboard Streamlit interactif (4 pages)
- ✅ Visualisations Plotly (equity curves, efficient frontier, feature importance)
- ✅ 45 tests API (80%+ coverage)
- ✅ Docker configuration (Dockerfile, docker-compose.yml)
- ✅ Documentation API (OpenAPI/Swagger auto-générée)

### Validation
- [ ] API démarre sans erreur (`uvicorn main:app`)
- [ ] Swagger UI accessible (`http://localhost:8000/docs`)
- [ ] POST /api/backtest/run pour stratégie SMA (< 5s)
- [ ] POST /api/portfolio/optimize pour 50 tickers (< 10s)
- [ ] Dashboard Streamlit accessible (`streamlit run streamlit_app.py`)
- [ ] Tous les tests passent (45/45)
- [ ] Coverage api/ + dashboard/ >= 80%

---

## 📊 Matrice de Dépendances

```
Phase 0 (Setup)
    ↓
Phase 1 (Data)
    ↓
    ├─→ Phase 2 (Features)
    │       ↓
    │       ├─→ Phase 3 (Backtesting)
    │       │       ↓
    │       └─→ Phase 5 (ML)
    │
    └─→ Phase 4 (Portfolio)
    
Phase 1-5 complètes
    ↓
Phase 6 (Analysis)
    ↓
Phase 7 (API & Dashboard)
```

**Ordre d'exécution obligatoire** :
1. Phase 0 (Setup) → **BLOQUE TOUT**
2. Phase 1 (Data) → **BLOQUE 2, 4**
3. Phase 2 (Features) → **BLOQUE 3, 5**
4. Phases 3, 4, 5 → **PARALLÉLISABLES** (si équipe multi-dev)
5. Phase 6 (Analysis) → **REQUIERT 1-5**
6. Phase 7 (API & Dashboard) → **REQUIERT 1-6**

---

## 🎯 Métriques de Succès

### Par Phase

| Phase | Tests | Coverage | Performance | Qualité |
|-------|-------|----------|-------------|---------|
| 0 | N/A | N/A | Docs lisibles | Review OK |
| 1 | 45 | ≥80% | OHLCV 10 tickers < 5s | Mocks OK |
| 2 | 53 | ≥80% | 40+ indicators < 1s | Vectorisé |
| 3 | 45 | ≥80% | Backtest 1 ticker < 500ms | 30+ metrics |
| 4 | 41 | ≥80% | Optimize 50 tickers < 1s | Weights sum=1 |
| 5 | 59 | ≥80% | ML train < 2 min | TimeSeriesSplit |
| 6 | 37 | ≥80% | DCF 1 ticker < 1s | FinanceToolkit |
| 7 | 45 | ≥80% | API response < 1s | OpenAPI docs |

### Globale

- **Tests totaux** : 325+ tests
- **Coverage globale** : ≥80%
- **Documentation** : 100% des APIs documentées
- **Performance** : Tous les benchmarks respectés
- **Qualité** : Aucun warning linter (flake8, mypy)

---

## 🚧 Risques & Mitigations

### Risques identifiés

1. **API externes indisponibles** (FinanceToolkit, yfinance)
   - **Mitigation** : Cache agressif (TTL 1h), fallbacks multiples
   
2. **Dépendances incompatibles** (versions conflits)
   - **Mitigation** : Poetry/pipenv, lock file, tests CI/CD
   
3. **Performance ML** (entraînement trop lent)
   - **Mitigation** : GPU support (CUDA), multiprocessing, early stopping
   
4. **Mémoire** (Russell 3000 × 100 features = 300K data points)
   - **Mitigation** : Chunking, lazy loading, Dask pour big data
   
5. **Complexité backtesting.py** (courbe d'apprentissage)
   - **Mitigation** : Exemples nombreux, BaseStrategy avec helpers

### Plan de contingence

Si **retard > 2 jours** sur une phase :
1. Review scope (features optionnelles → Phase 8)
2. Augmenter ressources (paire programming)
3. Réduire coverage target (80% → 70% temporairement)

Si **blocage technique majeur** :
1. Escalade équipe (daily standup)
2. Spike technique (2h max pour POC)
3. Décision GO/NO-GO sur intégration fork

---

## 📝 Checklist de Validation Finale

### Phase 0
- [ ] ARCHITECTURE.md complet et approuvé
- [ ] INTEGRATION_PLAN.md complet et approuvé
- [ ] API_REFERENCE.md complet (toutes les signatures)
- [ ] requirements.txt installable sans erreur
- [ ] setup.py configure correctement
- [ ] .env.example avec toutes les clés API

### Phase 1
- [ ] Universe selector : 300K+ symboles accessibles
- [ ] Market data : OHLCV pour 10 tickers sans erreur
- [ ] Fundamentals : 150+ ratios pour 5 tickers
- [ ] Alternative : News sentiment pour AAPL
- [ ] 45/45 tests passent, coverage ≥80%

### Phase 2
- [ ] Technical : 40+ indicateurs calculés correctement
- [ ] Fundamental : Features ML (lags, deltas, z-scores)
- [ ] Alpha factors : 100+ factors implémentés
- [ ] Sentiment : FinBERT prédictions [-1, 1]
- [ ] 53/53 tests passent, coverage ≥80%

### Phase 3
- [ ] Engine : Wrapper backtesting.py opérationnel
- [ ] Strategies : 25+ stratégies techniques
- [ ] Optimize : Grid search + Bayesian
- [ ] 45/45 tests passent, coverage ≥80%

### Phase 4
- [ ] PyPortfolioOpt : MV, HRP, BL, CLA
- [ ] Riskfolio-Lib : CVaR, NCO, 24 risk measures
- [ ] Allocation : Discrete allocation (integer shares)
- [ ] Rebalancing : Threshold + calendar
- [ ] 41/41 tests passent, coverage ≥80%

### Phase 5
- [ ] Tree-based : XGBoost, LightGBM, RF
- [ ] Timeseries : ARIMA, Prophet, LSTM
- [ ] Neural nets : LSTM, GRU, Transformer
- [ ] Ensemble : Stacking > individual models
- [ ] Deep RL : DQN, PPO agents profitables
- [ ] 59/59 tests passent, coverage ≥80%

### Phase 6
- [ ] Valuation : DCF, DDM, WACC
- [ ] Options : Black-Scholes, Greeks, IV
- [ ] Performance : 20+ métriques
- [ ] 37/37 tests passent, coverage ≥80%

### Phase 7
- [ ] API : 15+ endpoints fonctionnels
- [ ] Dashboard : 4 pages interactives
- [ ] Docker : docker-compose up sans erreur
- [ ] Documentation : OpenAPI/Swagger accessible
- [ ] 45/45 tests passent, coverage ≥80%

### Globale
- [ ] 325+ tests passent (100%)
- [ ] Coverage globale ≥80%
- [ ] 100% APIs documentées (docstrings Google style)
- [ ] Tous les benchmarks performance respectés
- [ ] Aucun warning linter (flake8, mypy, pylint)
- [ ] README.md avec quickstart, installation, examples
- [ ] CHANGELOG.md à jour

---

## 🎉 Critères de Release v2.0

### Must-have (Bloquant)
- ✅ Toutes les phases 0-7 complètes
- ✅ 325+ tests passent (100%)
- ✅ Coverage ≥80%
- ✅ Documentation complète
- ✅ API fonctionnelle
- ✅ Dashboard opérationnel

### Should-have (Important)
- ⏳ Performance benchmarks respectés
- ⏳ Docker production-ready
- ⏳ CI/CD pipeline (GitHub Actions)
- ⏳ Pre-commit hooks (black, isort, flake8)

### Nice-to-have (Optionnel)
- 🔜 Jupyter notebooks examples/
- 🔜 Video demo dashboard
- 🔜 Blog post technical deep-dive
- 🔜 PyPI package published

---

**VERSION** : 2.0  
**DATE** : 6 Novembre 2025  
**AUTEUR** : FinBot Team  
**STATUT** : ✅ Plan d'Intégration Complet (Phase 0 en cours)
