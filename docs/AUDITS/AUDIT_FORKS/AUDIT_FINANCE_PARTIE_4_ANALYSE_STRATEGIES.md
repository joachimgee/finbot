# DOSSIER D'AUDIT — FINANCE (PARTIE 4) — Analyse & Stratégies de Portefeuille

Ce document cartographie de façon technique et exhaustive les dossiers `stock_analysis/` (analyses statistiques, valorisation, risque) et `portfolio_strategies/` (stratégies de trading, optimisation, backtesting) du fork « Finance ». Aucun code n'a été transformé ni exécuté; il s'agit d'une description détaillée des scripts, de leurs modèles/formules, entrées/sorties, métriques, contraintes et exemples d'usage.

Portée: `Finance-master/Finance-master/stock_analysis/` et `Finance-master/Finance-master/portfolio_strategies/`.

---

## Structure du périmètre

### stock_analysis/ (19 fichiers)

- backest_all_indicators.py
- capm_analysis.py
- earnings_call_sentiment_analysis.py
- estimating_returns.py
- intrinsic_value.py
- kelly_criterion.py
- ma_backtesting.py
- ols_regression.py
- performance_risk_analysis.py
- risk_vs_returns.py
- seasonal_stock_analysis.py
- sma_histogram.py
- sp500_cot_sentiment_analysis.py
- sp500_valuation.py
- stock_pivot_resistance.py
- stock_profit_loss.py
- stock_returns_statistical_analysis.py
- twitter_sentiment_analysis.py
- var_analysis.py
- view_stock_returns.py

### portfolio_strategies/ (26 fichiers)

- astral_timing_signals.py
- backtest_strategies.py
- backtrader_backtest.py
- best_moving_averages_analysis.py
- ema_crossover_strategy.py
- factor_analysis.py
- financial_signal_analysis.py
- geometric_brownian_motion.py
- long_hold_stats_analysis.py
- ls_dca_analysis.py
- monte_carlo.py
- moving_average_crossover_signals.py
- moving_avg_strategy.py
- optimal_portfolio.py
- optimized_bollinger_bands.py
- pairs_trading.py
- portfolio_analysis.py
- portfolio_optimization.py
- portfolio_var_simulation.py
- risk_management.py
- robinhood_bot.py
- rsi_trendline_strategy.py
- rwb_strategy.py
- sma_trading_strategy.py
- stock_spread_plotter.py
- support_resistance_finder.py

---

## Dépendances transverses

- **Données**: yfinance/pandas-datareader (Yahoo Finance), FMP API (intrinsic_value), FinViz scraping.
- **Calcul**: NumPy, pandas, scipy.optimize (optimiseurs), statsmodels (régression, cointegration).
- **Finance quantitative**: pypfopt (EfficientFrontier, expected_returns, risk_models, DiscreteAllocation), backtrader (backtesting framework).
- **ML/Statistiques**: sklearn (clustering, PCA dans factor_analysis), scipy.stats (distributions, tests).
- **Visualisation**: matplotlib, seaborn.
- **Utilitaires internes**: `tickers.py` (listes S&P500/NASDAQ/AMEX).

---

## Détail par fichier — stock_analysis/

### Valorisation & Fondamentaux

1. **intrinsic_value.py**
   - **Rôle**: Calcule la valeur intrinsèque d'un titre via DCF (Discounted Cash Flow).
   - **Entrées**: ticker (demo API FMP = AAPL seulement), taux sans risque, croissance EPS projetée (5Y, 6-10Y, 11-20Y via FinViz), FCF, dette, cash, actions en circulation, beta.
   - **Formule**:
     - Pour chaque année i=1..20: `FCF_i = FCF_{i-1} × (1 + growth_rate_i)` ; `DCF_i = FCF_i / (1 + discount)^i`.
     - `Valeur intrinsèque = (Σ DCF_i − Dette totale + Cash) / Nb_actions`.
     - Discount rate = `7 + beta × 2.5` (ou 6 si beta < 1).
   - **Sorties**: DataFrame comparant valeur intrinsèque vs prix actuel, % déviation, paramètres (FCF, dette, croissance, etc.).

2. **sp500_valuation.py**
   - **Rôle**: Valorisation S&P 500 (P/E, P/B, dividend yield, etc.) via scraping/sources publiques.
   - **Sorties**: historique des ratios de valorisation du marché, comparaison avec moyennes historiques.

### Risque & Performance

3. **capm_analysis.py**
   - **Rôle**: Calcule le rendement attendu CAPM (Capital Asset Pricing Model) pour chaque ticker vs indice.
   - **Formule**: `E(R_stock) = R_f + β × (E(R_market) − R_f)`.
     - `β = Cov(R_stock, R_market) / Var(R_market)` (régression linéaire mensuelle).
   - **Entrées**: tickers NASDAQ (via `tickers_nasdaq()`), fenêtre 1 an, taux sans risque (ex: 0.02).
   - **Sorties**: impression `{ticker}: Expected Return: {value}` pour chaque symbole.

4. **performance_risk_analysis.py**
   - **Rôle**: Calcule métriques clés (beta, alpha, R², volatilité, momentum, volume moyen 60d).
   - **Formule**:
     - `β`, `α`, `R²` via régression mensuelle vs S&P 500.
     - Volatilité annualisée: `σ = STD(returns_monthly) × √12`.
     - Momentum 1Y: `∏(1 + r_i) − 1` sur 12 derniers mois.
   - **Sorties**: impression métriques.

5. **risk_vs_returns.py**
   - **Rôle**: Visualisation risque (volatilité annualisée) vs rendement (annualisé) pour portefeuille de tickers.
   - **Sorties**: scatter plot (axe X=risque, Y=rendement) + efficient frontier overlay (si inclus).

6. **var_analysis.py**
   - **Rôle**: Calcul Value-at-Risk (VaR) à 95% via:
     - Méthode historique (bootstrap): histogramme des returns, quantile 5%.
     - Méthode variance-covariance: fit distribution t-Student, `VaR = mean + z × σ`.
   - **Formule VaR (normal)**: `VaR_{0.05} = μ + Φ^{−1}(0.05) × σ` où Φ est CDF normale.
   - **Sorties**: histogramme returns, PDF ajustée, impression VaR.

7. **kelly_criterion.py**
   - **Rôle**: Calcule le Kelly Criterion pour sizing optimal de positions.
   - **Formule**: `f^* = W − (1 − W)/R` où W = win ratio (% trades gagnants), R = win/loss ratio (avg_gain / avg_loss).
   - **Entrées**: ticker, fenêtre 1 an, returns quotidiens.
   - **Sorties**: impression `Kelly Criterion: {value}%`.

8. **seasonal_stock_analysis.py**
   - **Rôle**: Analyse saisonnière des returns par mois/jour sur historique long (S&P 500); identifie patterns récurrents (ex: "sell in May").
   - **Méthode**: pivot table (rows=M-D, columns=années), statistiques (% up/down, avg return, stdev) par période glissante.
   - **Sorties**: CSV par ticker avec stats saisonnières, filtres sur seuils (ex: PctUp > 0.8).

9. **stock_returns_statistical_analysis.py**
   - **Rôle**: Statistiques descriptives sur returns (mean, median, std, skew, kurtosis, min/max, quartiles).
   - **Sorties**: DataFrame avec métriques par ticker.

10. **view_stock_returns.py / estimating_returns.py**
    - **Rôle**: Visualisation returns (histogrammes, séries temporelles), estimation de rendements futurs (méthodes simples: moyennes historiques, extrapolation linéaire).

### Backtesting & Signaux

11. **ma_backtesting.py / backest_all_indicators.py**
    - **Rôle**: Backtest simple de stratégies basées sur moyennes mobiles ou ensemble d'indicateurs (RSI, MACD, Bollinger, etc.).
    - **Logique**: génération de signaux buy/sell, calcul de returns, métriques (total return, Sharpe, max drawdown).

12. **ols_regression.py**
    - **Rôle**: Régression linéaire OLS (Ordinary Least Squares) prix vs temps ou vs variables explicatives.
    - **Sorties**: coefficients, R², prédiction, résidus.

### Autres Analyses

13. **stock_pivot_resistance.py / support_resistance_finder.py (dans portfolio_strategies/)**
    - **Rôle**: Identification de niveaux de support/resistance et pivots via max/min locaux, volumes, ou formules pivots classiques.

14. **stock_profit_loss.py**
    - **Rôle**: Calcul P&L pour positions simulées (entrée/sortie + frais).

15. **earnings_call_sentiment_analysis.py / twitter_sentiment_analysis.py / sp500_cot_sentiment_analysis.py**
    - **Rôle**: Analyse de sentiment (transcripts earnings, tweets, COT reports) via NLP basique ou APIs (polarity/subjectivity).

16. **sma_histogram.py**
    - **Rôle**: Affichage histogramme de positions (SMA-based) par ticker.

---

## Détail par fichier — portfolio_strategies/

### Optimisation de Portefeuille

1. **optimal_portfolio.py**
   - **Rôle**: Optimisation Sharpe ratio (scipy.optimize.fmin) pour pondérations optimales.
   - **Formule**:
     - `Sharpe = (R_p − R_f) / σ_p` où `R_p = Σ(w_i × r_i)`, `σ_p = √(w^T Cov w)`.
   - **Contrainte**: `Σ w_i = 1`, `w_i ∈ [0, 1]`.
   - **Sorties**: poids optimaux, Sharpe optimal vs equal-weighted.

2. **portfolio_optimization.py**
   - **Rôle**: Construction frontière efficiente (Efficient Frontier) via:
     - Maximum Sharpe Ratio Portfolio.
     - Minimum Variance Portfolio.
     - Efficient Return pour rendement cible.
   - **Outils**: scipy.optimize.minimize + pypfopt (EfficientFrontier, DiscreteAllocation).
   - **Visualisation**: scatter plot frontière + random portfolios colorés par Sharpe.
   - **Sorties**: allocations (%), performance (rendement, volatilité, Sharpe), discrete allocation (nombre d'actions à acheter).

3. **portfolio_analysis.py**
   - **Rôle**: Analyse d'un portefeuille existant (métriques: rendement total, annualisé, volatilité, Sharpe, max drawdown, sortino, calmar).
   - **Formules**:
     - `Max Drawdown = max_i [(Peak_i − Valley_i) / Peak_i]`.
     - `Sortino = (R_p − R_f) / σ_downside` où `σ_downside = √(E[(r − MAR)²] si r < MAR)`.
     - `Calmar = R_annualized / Max_Drawdown`.

4. **portfolio_var_simulation.py**
   - **Rôle**: Simulation Monte Carlo de VaR portefeuille (diversifié).
   - **Méthode**: tirer N scénarios de returns (multivariate normal ou t-Student), calculer P&L, quantile 5%.

### Stratégies de Trading

5. **ema_crossover_strategy.py / moving_average_crossover_signals.py / moving_avg_strategy.py / sma_trading_strategy.py**
   - **Rôle**: Stratégies de croisement de moyennes mobiles (EMA/SMA).
   - **Signaux**: buy quand MA_courte > MA_longue ; sell inversement.
   - **Backtesting**: cumulative returns, Sharpe, max drawdown.
   - **Exemple (ema_crossover_strategy.py)**:
     - Tickers TSLA/AAPL/AMZN/NFLX, fenêtre 3 ans.
     - Positions = sign(Close − EMA20) / 3 (equal weighting).
     - Returns = position_t−1 × log_return_t.
     - Cumulative log returns → exp() − 1 pour relative returns.

6. **rsi_trendline_strategy.py**
   - **Rôle**: Stratégie RSI + trendlines (support/resistance).
   - **Signaux**: buy si RSI < 30 ET prix touche support ; sell si RSI > 70 ET résistance.

7. **rwb_strategy.py** (Red/White/Blue)
   - **Rôle**: Stratégie basée sur position relative de 3 EMAs (couleur chart: hausse=bleu, baisse=rouge, neutre=blanc).

8. **optimized_bollinger_bands.py**
   - **Rôle**: Stratégie Bollinger Bands avec optimisation de paramètres (n, k) via grid search sur Sharpe.

9. **pairs_trading.py**
   - **Rôle**: Stratégie de pairs trading (mean reversion) pour paires coïntégrées.
   - **Méthode**:
     - Test coïntégration (statsmodels.tsa.stattools.coint) → p-value < 0.05.
     - Spread = log(Price_A) − hedge_ratio × log(Price_B).
     - Z-score du spread; signaux: long spread si z < −2, short si z > 2, exit si |z| < 0.5.
   - **Sorties**: heatmap p-values, liste paires coïntégrées, backtest P&L.

10. **best_moving_averages_analysis.py**
    - **Rôle**: Teste plusieurs combinaisons de fenêtres MA (grid search), classe par Sharpe ou total return.

### Simulation & Modèles Stochastiques

11. **monte_carlo.py**
    - **Rôle**: Simulation Monte Carlo pour prévoir distribution de prix futurs (GBM).
    - **Formule**: `P_{t+1} = P_t × exp(μ Δt + σ √Δt × ε)` où ε ~ N(0,1).
    - **Paramètres**: `μ = CAGR`, `σ = annual_volatility` historiques.
    - **Sorties**: N trajectoires (ex: 1000 simulations × 252 jours), percentiles 5%/95%.

12. **geometric_brownian_motion.py**
    - **Rôle**: Implémentation GBM pour modéliser évolution prix (analogue Monte Carlo).

### Analyse de Facteurs & Signaux

13. **factor_analysis.py**
    - **Rôle**: Réduction dimensionnalité (PCA) ou clustering sur facteurs (momentum, value, size, volatility).
    - **Sorties**: composantes principales, loadings, variance expliquée.

14. **financial_signal_analysis.py**
    - **Rôle**: Agrégation/pondération de signaux multiples (MA, RSI, MACD, volume) pour scoring composite.

15. **astral_timing_signals.py**
    - **Rôle**: Signaux basés sur cycles lunaires/planétaires (approche alternative/ésoterrique).

### Backtesting Frameworks

16. **backtest_strategies.py / backtrader_backtest.py**
    - **Rôle**: Infrastructure de backtest (backtrader library ou custom).
    - **Features**: gestion positions, ordre execution, frais, slippage, equity curve, métriques (Sharpe, Sortino, drawdown).

17. **long_hold_stats_analysis.py**
    - **Rôle**: Statistiques buy-and-hold (comparaison vs stratégies actives).

18. **ls_dca_analysis.py** (Lump-Sum vs Dollar-Cost Averaging)
    - **Rôle**: Compare investissement unique vs DCA (versements périodiques).

### Gestion de Risque

19. **risk_management.py**
    - **Rôle**: Règles de sizing (Kelly, fixed fractional, volatility targeting), stops (trailing, ATR-based).

20. **robinhood_bot.py**
    - **Rôle**: Bot automatique pour Robinhood API (signaux + exécution); nécessite auth Robinhood.

### Divers

21. **stock_spread_plotter.py**
    - **Rôle**: Visualisation spreads (bid-ask, calendar spreads options).

---

## Inputs / Outputs (contrats type)

### Entrées communes

- **Tickers**: liste de symboles (str) ou single ticker.
- **Fenêtre temporelle**: `start`, `end` (datetime.date ou ISO).
- **Paramètres stratégie**: fenêtres MA (ex: 20/100), seuils RSI (30/70), facteur Bollinger (k=2), intervalle lookback, constraints optimisation.
- **Taux sans risque**: `R_f` (ex: 0.02 pour 2%).
- **Capital initial**: pour discrete allocation (ex: $10k).
- **Données externes**: API keys (FMP pour intrinsic_value), credentials Robinhood (bot).

### Sorties communes

- **DataFrames pandas**: rendements, allocations, métriques par ticker.
- **Graphiques matplotlib/seaborn**: equity curves, frontières efficientes, heatmaps (corrélation, coïntégration), histogrammes (returns, VaR).
- **Métriques quantitatives**: Sharpe, Sortino, Calmar, Max Drawdown, total return, CAGR, volatilité, beta, alpha, R², Kelly %, VaR.
- **CSV exports**: résultats backtests, allocations optimales, stats saisonnières.

---

## Formules clés consolidées

### Valorisation

- **DCF (Discounted Cash Flow)**: `V_intrinsèque = (Σ_{i=1..20} FCF_i / (1+r)^i − Dette + Cash) / Nb_actions`.

### Risque & Performance

- **CAPM**: `E(R) = R_f + β(E(R_m) − R_f)` ; `β = Cov(R_stock, R_market) / Var(R_market)`.
- **Alpha**: `α = E(R_stock) − [R_f + β(E(R_market) − R_f)]`.
- **Sharpe Ratio**: `S = (R_p − R_f) / σ_p`.
- **Sortino Ratio**: `Sortino = (R_p − R_f) / σ_downside`.
- **Calmar Ratio**: `Calmar = R_annualized / Max_Drawdown`.
- **Max Drawdown**: `MDD = max_i [(Peak_i − Valley_i) / Peak_i]`.
- **Kelly Criterion**: `f^* = W − (1−W)/R` où W=win ratio, R=win/loss ratio.
- **VaR (variance-covariance)**: `VaR_{α} = μ + z_α × σ` (ex: z_{0.05} ≈ −1.65 pour 95% CL).
- **Volatilité annualisée**: `σ_annual = σ_daily × √252` ou `σ_monthly × √12`.
- **Momentum**: `M = ∏_{i=1..n}(1 + r_i) − 1`.

### Optimisation Portefeuille

- **Rendement portefeuille**: `R_p = Σ w_i × r_i`.
- **Variance portefeuille**: `σ²_p = w^T Σ w` où Σ = matrice covariance.
- **Frontière efficiente**: ensemble de portefeuilles minimisant σ_p pour chaque niveau de R_p (ou max Sharpe).
- **Poids optimal (max Sharpe)**: résolution `argmax_w [(R_p − R_f) / σ_p]` sous contrainte `Σ w_i = 1`, `w_i ≥ 0`.

### Stratégies

- **MA Crossover**: signal = sign(MA_courte − MA_longue).
- **RSI mean reversion**: buy si RSI < 30, sell si RSI > 70.
- **Bollinger Bands**: buy si Close < BB_lower, sell si Close > BB_upper.
- **Pairs Trading (z-score)**: `z = (Spread − μ_Spread) / σ_Spread` ; long spread si z < −2, short si z > 2.
- **Monte Carlo (GBM)**: `S_{t+Δt} = S_t × exp((μ − σ²/2)Δt + σ√Δt × ε)`.

---

## Exemples d'usage (non-exécutés)

### CAPM Analysis
- Tickers: tous NASDAQ via `tickers_nasdaq()`, fenêtre 1 an.
- Calcul beta/alpha mensuel vs S&P 500.
- Sortie: impression `{ticker}: Expected Return: {value}` pour chaque symbole.

### Kelly Criterion
- Ticker: BAC, fenêtre 1 an.
- Calcul win ratio + win/loss ratio sur daily returns.
- Formule Kelly: `f^* = W − (1−W)/R`.
- Sortie: `Kelly Criterion: 15.3%` (exemple).

### VaR Analysis
- Ticker: AMD, fenêtre 9 ans.
- Méthode: histogramme returns (bootstrap), fit t-Student (variance-covariance).
- Calcul VaR 95%: quantile 5% ou `mean + z × sigma`.
- Sorties: histogramme, PDF ajustée, impression VaR.

### Intrinsic Value (DCF)
- Ticker: AAPL (demo API FMP).
- Paramètres: FCF récent, dette, cash, EPS growth 5Y/6-10Y/11-20Y (scraping FinViz), beta, discount rate.
- Calcul: 20 ans de FCF projetés, discount, soustraire dette, ajouter cash, diviser par shares outstanding.
- Sortie: tableau comparatif valeur intrinsèque vs prix actuel, % déviation.

### Portfolio Optimization (Efficient Frontier)
- Tickers: SCHB/AAPL/AMZN/TSLA/AMD/MSFT/NFLX, fenêtre depuis 2020-08.
- Calcul mean returns, covariance matrix.
- Optimisation: max Sharpe ratio + min variance (scipy.optimize.minimize).
- Génération 50k random portfolios pour visualisation.
- Frontière efficiente: courbe target return vs volatility.
- Discrete allocation: nombre d'actions pour capital donné ($10k).
- Sorties: scatter plot (volatilité vs rendement, coloré par Sharpe), allocations optimales (%), performance metrics.

### EMA Crossover Strategy
- Tickers: TSLA/AAPL/AMZN/NFLX, fenêtre 3 ans.
- Calcul EMA20, positions = sign(Close − EMA20) / 3 (equal weight).
- Returns = position_t−1 × log_return_t.
- Cumulative log returns, puis conversion relative returns.
- Sorties: charts cumulative returns par ticker, total portfolio, stats (total return, avg yearly return).

### Pairs Trading
- Tickers: AAPL/MSFT/GOOG/AMZN, fenêtre 5 ans.
- Test coïntégration (coint) pour chaque paire → p-values.
- Heatmap p-values (seuil 0.05).
- Pour paires coïntégrées: calcul spread, z-score, signaux long/short.
- Backtest: P&L sur signaux, métriques Sharpe/drawdown.

### Monte Carlo Simulation
- Ticker: NIO, fenêtre 2015-2020.
- Calcul CAGR et volatilité historiques.
- Simulation: 1000 trajectoires × 252 jours (1 an).
- Chaque jour: `P_new = P × (1 + N(μ/252, σ/√252))`.
- Sorties: chart 1000 trajectoires, DataFrame percentiles 5%/95%.

---

## Hypothèses, limites et contraintes

- **Coûts de transaction**: la plupart des backtests ne modélisent pas frais/slippage (sauf backtrader scripts).
- **Overfitting**: optimisation sur historique (in-sample) peut ne pas généraliser (out-of-sample).
- **Hypothèse normalité**: VaR variance-covariance et Monte Carlo GBM supposent distributions normales/log-normales; fat tails réelles sous-estimées.
- **Coïntégration**: paires trading suppose relation stable (peut briser en crise).
- **Modèle CAPM**: suppose marchés efficients, bêta constant; en pratique, non-linéarités/regimes multiples.
- **Kelly**: suppose W et R constants; en pratique, distribution non-stationnaire.
- **API limits**: FMP demo = AAPL seulement; Robinhood bot nécessite auth active.
- **Données**: Yahoo Finance peut avoir gaps/adjustments; FinViz scraping sujet à changements HTML.

---

## Croisements avec d'autres parties

- **Partie 2 (stock_data/)**: scripts de données (FinViz scrapers, TradingView recos) alimentent analyses (ex: fundamental_ratios → intrinsic_value).
- **Partie 3 (technical_indicators/)**: indicateurs (RSI, MACD, Bollinger, ATR) sont inputs pour stratégies (rsi_trendline_strategy, optimized_bollinger_bands, risk_management ATR stops).
- **Partie 5 (machine_learning/)**: features issues de ces analyses (returns, volatilité, beta, momentum) sont consommées par modèles ML (LSTM, sklearn bots); certains scripts (factor_analysis) font le pont avec PCA/clustering.

---

## Synthèse

Les dossiers `stock_analysis/` et `portfolio_strategies/` forment une **bibliothèque complète de ~45 scripts** couvrant:

- **Valorisation & fondamentaux**: DCF intrinsic value, CAPM, ratios S&P 500.
- **Risque & performance**: VaR, Kelly, Sharpe/Sortino/Calmar, beta/alpha/R², volatilité, momentum, saisonnalité.
- **Optimisation de portefeuille**: frontière efficiente, max Sharpe, min variance, discrete allocation (pypfopt).
- **Stratégies de trading**: MA crossovers (EMA/SMA), RSI mean reversion, Bollinger Bands optimized, pairs trading (coïntégration), RWB, best MA grid search.
- **Simulation & modèles stochastiques**: Monte Carlo (GBM), VaR simulation portfolio.
- **Backtesting**: frameworks custom + backtrader, métriques (total return, Sharpe, max drawdown), comparaison long-hold vs actif.
- **Gestion de risque**: sizing Kelly/volatility targeting, stops ATR/trailing.

Les formules consolidées ci-dessus constituent un registre complet des définitions mathématiques pour reproduction, intégration dans FinBotX, et validation de modèles.
