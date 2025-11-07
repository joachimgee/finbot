# DOSSIER D'AUDIT — FINANCE (PARTIE 5) — Machine Learning

Ce document cartographie de façon technique et exhaustive le dossier `machine_learning/` (16 fichiers) du fork « Finance ». Aucun code n'a été transformé ni exécuté; il s'agit d'une description détaillée des modèles ML, datasets, featurisation, entraînement, évaluation, et exemples d'usage pour prédiction de prix, clustering, régression, classification, et analyse probabiliste.

Portée: `Finance-master/Finance-master/machine_learning/`.

---

## Structure du périmètre

Le dossier contient **16 scripts Python** couvrant:

- **Séries temporelles**: ARIMA, Prophet, LSTM.
- **Réseaux de neurones**: MLP (dense), deep learning simple (TensorFlow/Keras).
- **Clustering & réduction**: PCA + KMeans, graphical lasso ETFs, clustering d'indicateurs techniques.
- **Régression & classification**: sklearn bots (Isolation Forest, classifiers), régression linéaire/non-linéaire.
- **Analyse probabiliste**: modèles stochastiques, prédiction de distributions.

Liste complète:

- arima_time_series.py
- deep_learning_bot.py
- etf_graphical_lasso.py
- kmeans_clustering.py
- lstm_prediction.py
- ml_models_accuracy.py
- neural_network_prediction.py
- pca_kmeans_clustering.py
- prophet_price_prediction.py
- quantitative_indicators_prediction.py
- sklearn_trading_bot.py
- sp500_pca_analysis.py
- stock_probabilistic_analysis.py
- stock_regression_analysis.py
- stocker_price_prediction.py
- technical_indicators_clustering.py

---

## Dépendances transverses

- **Données**: yfinance/pandas-datareader (Yahoo Finance), CSV locaux (pour sklearn_trading_bot).
- **ML frameworks**:
  - **statsmodels**: ARIMA, seasonal_decompose, adfuller (test de stationnarité), cointegration tests.
  - **TensorFlow/Keras**: Sequential, LSTM, Dense layers (deep learning).
  - **sklearn**: classifiers (RandomForest, SVM, etc.), clustering (KMeans), réduction (PCA), preprocessing (MinMaxScaler, Normalizer), pipeline, métriques (MSE, MAE, accuracy).
  - **fbprophet (Prophet)**: séries temporelles avec saisonnalité.
  - **pmdarima**: auto_arima pour sélection automatique ordres ARIMA.
  - **backtrader**: framework backtesting (sklearn_trading_bot).
  - **pyfolio**: reporting performance portefeuille (tear sheets).
- **Visualisation**: matplotlib, seaborn (certains scripts).
- **Autres**: scipy, numpy, pandas.

---

## Détail par fichier

### Séries Temporelles Classiques

1. **arima_time_series.py**
   - **Modèle**: ARIMA (AutoRegressive Integrated Moving Average).
   - **Pipeline**:
     - Téléchargement données (ticker, 10 ans).
     - Test stationnarité: Dickey-Fuller (ADF); plot rolling mean/std.
     - Décomposition saisonnière (seasonal_decompose, multiplicative).
     - Transformation log pour stabiliser variance.
     - Split train/test (90%/10%).
     - Fit ARIMA(p,d,q) avec ordres manuels (ex: 3,1,2) → `model.fit()`.
     - Forecast sur période test avec intervalles de confiance.
     - Métriques: MSE, MAE, RMSE, MAPE.
     - Auto-ARIMA (pmdarima.auto_arima) pour sélection automatique ordres via AIC.
   - **Formules ARIMA**:
     - AR(p): `y_t = c + Σ_{i=1..p} φ_i × y_{t−i} + ε_t`.
     - I(d): différenciation d fois pour stationnariser.
     - MA(q): `ε_t = Σ_{j=1..q} θ_j × ε_{t−j} + η_t`.
   - **Entrées**: ticker (AAPL), start/end dates, ordres ARIMA (p,d,q).
   - **Sorties**: plot forecast vs actual, métriques, diagnostics auto-ARIMA.

2. **prophet_price_prediction.py**
   - **Modèle**: Prophet (Facebook).
   - **Pipeline**:
     - Téléchargement données (20 ans).
     - Renommage colonnes: Date → ds, Close → y.
     - Fit Prophet avec `daily_seasonality=True`.
     - Prédiction future (30 jours) via `model.make_future_dataframe(periods=30)`.
   - **Formule Prophet (conceptuelle)**: `y(t) = trend(t) + seasonality(t) + holiday(t) + ε_t` avec trend linéaire ou logistique, seasonality Fourier.
   - **Entrées**: ticker (AAPL), fenêtre historique (20 ans), horizon forecast (30 jours).
   - **Sorties**: plot prédiction avec composantes (trend/seasonal/yearly), intervalles de confiance.

### Deep Learning (LSTM & MLP)

3. **lstm_prediction.py**
   - **Modèle**: LSTM (Long Short-Term Memory) à 2 couches.
   - **Pipeline**:
     - Téléchargement données (10 ans).
     - Scaling MinMaxScaler(0,1).
     - Création séquences: fenêtre lookback=60 jours → prédit jour suivant.
     - Split train/test (80%/20%).
     - Architecture: `LSTM(50, return_sequences=True) → LSTM(50) → Dense(25) → Dense(1)`.
     - Compilation: `optimizer='adam', loss='mean_squared_error'`.
     - Entraînement: `batch_size=1, epochs=5` (epochs faibles, ajustable).
     - Prédiction test set + inverse transform scaler.
     - Prédiction next day: derniers 60 jours → forward pass.
   - **Formule LSTM (abstrait)**: cell state `C_t`, hidden state `h_t` avec portes (forget, input, output); capture dépendances long terme.
   - **Entrées**: ticker (user input), fenêtre 10 ans, lookback 60.
   - **Sorties**: plot train/valid/prediction, RMSE, prédiction next day.

4. **neural_network_prediction.py**
   - **Modèle**: MLP (Multi-Layer Perceptron) simple (Dense layers).
   - **Pipeline**:
     - Téléchargement données (1 an).
     - Feature engineering: `Open_Close = (Open − Close)/Open`, `High_Low = (High − Low)/Low`, `Increase_Decrease`, `Buy_Sell_on_Open`, `Buy_Sell`, `Returns`.
     - Scaling MinMaxScaler.
     - Architecture: `Dense(64, relu) → Dense(64, relu) → Dense(1)`.
     - Compilation: `optimizer='rmsprop', loss='mse'`.
     - Entraînement: `epochs=100`.
     - Prédiction pour input neutre (ex: `[[0]]`).
   - **Sorties**: prédiction prix, plot actual vs predicted.

5. **deep_learning_bot.py**
   - **Rôle**: Bot de trading ML (probablement LSTM ou MLP non-détaillé dans extrait; à lire intégralement).
   - **Approche**: entraîner modèle prédictif, générer signaux buy/sell, backtester via backtrader ou custom loop.

### Clustering & Réduction de Dimensionnalité

6. **pca_kmeans_clustering.py**
   - **Modèle**: PCA (Principal Component Analysis) + KMeans clustering.
   - **Pipeline**:
     - Téléchargement returns quotidiens pour N tickers (ex: TGT, AMZN, NFLX, PG, NSRGY, MDLZ, MRK, MSFT, AAPL).
     - Normalisation (Normalizer).
     - KMeans clustering (n_clusters=5) sur returns normalisés.
     - Réduction PCA à 2 composantes.
     - KMeans clustering sur données réduites.
     - Comparaison labels avant/après PCA.
   - **Formule PCA**: `Z = X W` où W contient eigenvectors de Cov(X); capture variance maximale en dims réduites.
   - **Formule KMeans**: minimise inertie `Σ_{i} min_μ_j ||x_i − μ_j||²`.
   - **Entrées**: liste tickers, fenêtre historique, n_clusters.
   - **Sorties**: scatter plot clusters (PCA-reduced), labels par ticker, centroids.

7. **kmeans_clustering.py**
   - **Rôle**: KMeans pur sur returns ou indicateurs (sans PCA).

8. **sp500_pca_analysis.py**
   - **Rôle**: PCA sur S&P 500 (500 tickers) pour identifier facteurs communs (market factor, sector factors).
   - **Sorties**: variance expliquée par composante, loadings, projection tickers sur PC1/PC2.

9. **technical_indicators_clustering.py**
   - **Rôle**: Clustering sur espace d'indicateurs techniques (RSI, MACD, ATR, etc.) pour segmenter titres par régime technique.

10. **etf_graphical_lasso.py**
    - **Modèle**: Graphical Lasso (sparse inverse covariance).
    - **Rôle**: Inférer réseau de dépendances conditionnelles entre ETFs (edges = partial correlations).
    - **Formule**: Graphical Lasso résout `argmin_Θ [−log det Θ + tr(S Θ) + λ||Θ||_1]` où Θ = inverse covariance.
    - **Sorties**: matrice adjacence sparse, visualisation réseau (nodes=ETFs, edges=partial corr).

### Régression & Classification (sklearn)

11. **sklearn_trading_bot.py**
    - **Modèle**: Isolation Forest (anomaly detection) pour générer signaux de trading.
    - **Pipeline**:
      - Normalisation données OHLCV.
      - Fit IsolationForest (`contamination=0.001`) → détecte outliers (potentiels reversals).
      - Stratégie: si outlier détecté ET prix > moyenne → sell ; si prix < moyenne → buy (avec cooldown).
      - Backtesting via backtrader (cerebro), intégration pyfolio (tear sheet).
   - **Formule Isolation Forest**: isole points via arbres aléatoires; anomalies = points isolés rapidement.
   - **Entrées**: ticker (AAPL), fenêtre backtesting (2018-2019), CSV data historique.
   - **Sorties**: portfolio value start/end, pyfolio tear sheet (returns, Sharpe, drawdown, etc.).

12. **ml_models_accuracy.py**
    - **Rôle**: Compare accuracy de plusieurs classifiers sklearn (RandomForest, SVM, KNN, LogisticRegression, etc.) sur classification direction (up/down).
    - **Pipeline**:
      - Features: indicateurs techniques (SMA, EMA, RSI, MACD, etc.).
      - Target: `1` si Close_t+1 > Close_t, sinon `0`.
      - Split train/test.
      - Fit N modèles, évaluer accuracy, precision, recall, F1.
   - **Sorties**: tableau comparatif accuracy par modèle, best model.

13. **stock_regression_analysis.py**
    - **Modèle**: Régression linéaire/polynomial sur prix vs temps ou vs features.
    - **Rôle**: Fit trend line, extrapolation.
    - **Sorties**: coefficients, R², résidus, plot fit.

### Analyse Probabiliste & Prédiction Quantitative

14. **stock_probabilistic_analysis.py**
    - **Rôle**: Modélisation probabiliste (ex: distributions returns, simulations MonteCarlo, estimation densité).
    - **Sorties**: histogrammes, KDE, intervalles de confiance.

15. **quantitative_indicators_prediction.py**
    - **Rôle**: Prédiction d'indicateurs quantitatifs (ex: future RSI, future volatility) via modèles ML.
    - **Pipeline**: features historiques → target = indicateur futur → fit regressor/classifier.

16. **stocker_price_prediction.py**
    - **Rôle**: Wrapper Stocker (library pour viz/prédictions simples) utilisant Prophet ou ARIMA.
    - **Sorties**: prédictions + viz interactives.

---

## Entrées / Sorties (contrats type)

### Entrées communes

- **Ticker**: symbole (str) ou liste de symboles.
- **Fenêtre temporelle**: `start`, `end` (datetime.date), ou `num_of_years` (int).
- **Hyperparamètres modèle**:
  - ARIMA: ordres (p,d,q).
  - LSTM: lookback, epochs, batch_size, layers config.
  - KMeans: n_clusters.
  - sklearn: hyperparams classifiers/regressors (via grid search optionnel).
- **Split train/test**: ratio (ex: 80%/20% ou 90%/10%).
- **Scaling**: MinMaxScaler, Normalizer, StandardScaler.

### Sorties communes

- **Prédictions**: séries temporelles prédites (DataFrame/array), prédictions next-day/next-N-days.
- **Métriques**:
  - Régression: MSE, MAE, RMSE, MAPE, R².
  - Classification: accuracy, precision, recall, F1, confusion matrix.
  - Backtesting: total return, Sharpe, Sortino, max drawdown (via pyfolio ou custom).
- **Graphiques**:
  - Séries temporelles: train/valid/prediction overlay.
  - Clustering: scatter plot (PCA-reduced), dendrograms.
  - Réseau (graphical lasso): graph edges.
  - Backtesting: equity curve, drawdown plot.
- **Modèles sauvegardés**: fichiers `.h5` (Keras), pickles sklearn (optionnel, non systématique dans scripts).

---

## Formules clés consolidées

### ARIMA

- **AR(p)**: `y_t = c + Σ_{i=1..p} φ_i × y_{t−i} + ε_t`
- **MA(q)**: `ε_t = Σ_{j=1..q} θ_j × ε_{t−j} + η_t`
- **I(d)**: différenciation d fois: `Δy_t = y_t − y_{t−1}` (répété d fois)
- **ARIMA(p,d,q)**: combinaison AR, différenciation, MA.

### Prophet

- `y(t) = g(t) + s(t) + h(t) + ε_t` où:
  - `g(t)` = trend (linéaire ou logistique saturant).
  - `s(t)` = seasonality (Fourier series pour yearly/weekly/daily).
  - `h(t)` = holidays/events.

### LSTM (conceptuel)

- Cell state `C_t`, hidden state `h_t`.
- Portes:
  - Forget gate: `f_t = σ(W_f × [h_{t−1}, x_t] + b_f)`.
  - Input gate: `i_t = σ(W_i × [h_{t−1}, x_t] + b_i)` ; candidate `C̃_t = tanh(W_C × [h_{t−1}, x_t] + b_C)`.
  - Cell update: `C_t = f_t ⊙ C_{t−1} + i_t ⊙ C̃_t`.
  - Output gate: `o_t = σ(W_o × [h_{t−1}, x_t] + b_o)` ; `h_t = o_t ⊙ tanh(C_t)`.

### PCA

- `Z = X W` où W contient k eigenvectors de Cov(X) (ceux avec plus grandes valeurs propres).
- Variance expliquée: `λ_i / Σ λ_j`.

### KMeans

- Minimise inertie: `J = Σ_{i=1..N} min_{j=1..K} ||x_i − μ_j||²`.

### Graphical Lasso

- `argmin_Θ [−log det Θ + tr(S Θ) + λ||Θ||_1]` → inverse covariance sparse (Θ).

### Métriques

- **MSE**: `MSE = (1/N) Σ (y_i − ŷ_i)²`.
- **MAE**: `MAE = (1/N) Σ |y_i − ŷ_i|`.
- **RMSE**: `√MSE`.
- **MAPE**: `(1/N) Σ |y_i − ŷ_i| / |y_i| × 100%`.
- **Accuracy**: `(TP + TN) / (TP + TN + FP + FN)`.
- **Sharpe Ratio**: `(R_p − R_f) / σ_p`.

---

## Exemples d'usage (non-exécutés)

### ARIMA Time Series Prediction

- Ticker: AAPL, fenêtre 10 ans.
- Test stationnarité: ADF test → p-value interprétation.
- Décomposition saisonnière: trend/seasonal/residual.
- Log transform pour variance constante.
- Split train/test (90%/10%).
- Fit ARIMA(3,1,2) sur train.
- Forecast test period avec CI 95%.
- Métriques: MSE, MAE, RMSE, MAPE.
- Auto-ARIMA: sélection automatique ordres (ex: (2,1,1)).
- Sorties: plot forecast vs actual, diagnostics (ACF/PACF residuals).

### LSTM Stock Prediction

- Ticker: user input (ex: TSLA).
- Données: 10 ans, lookback 60 jours.
- Scaling: MinMaxScaler(0,1).
- Architecture: 2 LSTM layers (50 units), 2 Dense (25, 1).
- Entraînement: batch_size=1, epochs=5.
- Prédiction test set: 20% dernières données.
- Prédiction next day: derniers 60 jours → forward pass.
- Sorties: plot train/valid/pred, RMSE, predicted next day price.

### Prophet Price Prediction

- Ticker: AAPL, 20 ans historique.
- Prédiction: 30 jours futurs.
- Prophet fit avec daily seasonality.
- Sorties: plot forecast avec composantes (trend/yearly/weekly), CI 95%.

### PCA + KMeans Clustering

- Tickers: TGT, AMZN, NFLX, PG, NSRGY, MDLZ, MRK, MSFT, AAPL.
- Returns quotidiens, fenêtre plusieurs années.
- Normalisation → KMeans (5 clusters) sur returns.
- PCA → 2 composantes → KMeans sur PCA space.
- Sorties: scatter plot (PC1 vs PC2, coloré par cluster), labels par ticker, centroids.

### sklearn Trading Bot (Isolation Forest)

- Ticker: AAPL, backtest 2018-2019.
- IsolationForest (`contamination=0.001`) détecte outliers.
- Stratégie: sell si outlier + prix > avg, buy si outlier + prix < avg (cooldown 7 jours).
- Backtrader cerebro: capital initial $100k.
- Sorties: portfolio value final, pyfolio tear sheet (Sharpe, drawdown, returns distribution).

### ML Models Accuracy Comparison

- Features: SMA20/50/200, EMA12/26, RSI14, MACD, ATR, Bollinger Bands, volume ratios.
- Target: direction (1 si Close_t+1 > Close_t, 0 sinon).
- Split train/test (80%/20%).
- Modèles: RandomForest, SVM, KNN, LogisticRegression, GradientBoosting.
- Métriques: accuracy, precision, recall, F1 par modèle.
- Sortie: tableau comparatif, best model selection.

---

## Hypothèses, limites et contraintes

### Données

- **Historique**: LSTM/ARIMA nécessitent datasets longs (plusieurs années); fenêtres courtes → overfitting.
- **Stationnarité**: ARIMA suppose série stationnaire (ou rendue stationnaire par différenciation); Prophet gère non-stationnarité mieux.
- **Splits**: train/test in-sample; validation out-of-sample critique pour éviter data snooping.
- **Lookback**: LSTM (60 jours) et ARIMA ordres (p,q) sont hyperparams sensibles.

### Modèles

- **ARIMA**: linéaire, capture mal non-linéarités, sauts, structural breaks; nécessite ordres corrects (via ACF/PACF ou auto-ARIMA).
- **Prophet**: robuste pour saisonnalité/holidays, mais suppose tendance additive/multiplicative simple; peut manquer regimes complexes.
- **LSTM**: puissant pour patterns non-linéaires long-terme, mais:
  - Sensible hyperparams (layers, units, epochs, batch_size).
  - Overfitting si epochs trop élevés ou architecture trop complexe vs data.
  - Computationally expensive (GPU recommandé pour larges datasets).
- **sklearn classifiers**: risque overfitting si features trop nombreuses vs samples; nécessite feature engineering pertinent.
- **Isolation Forest**: suppose anomalies = outliers rares; threshold `contamination` à ajuster selon données.
- **PCA + KMeans**: PCA perd info (variance non capturée par PC retenus); KMeans suppose clusters sphériques/isotropes.

### Backtesting

- **Biais survivorship**: Yahoo Finance data exclut delisted tickers → overestimation perf.
- **Lookahead bias**: éviter d'utiliser info future dans features (shift correct).
- **Coûts transaction**: scripts n'incluent généralement pas frais/slippage (sauf backtrader si configuré).
- **Market impact**: petites positions OK; large positions → slippage non modélisé.

### Performance

- **Métriques**: MSE/RMSE sensibles à outliers; MAPE fail si valeurs proches zéro; Sharpe suppose returns normaux.
- **Out-of-sample**: résultats train ne garantissent pas perf future (market regime change).

---

## Croisements avec d'autres parties

- **Partie 2 (stock_data/)**: données collectées (Yahoo, FinViz) → inputs ML pipelines.
- **Partie 3 (technical_indicators/)**: indicateurs (SMA, EMA, RSI, MACD, ATR, etc.) → features pour classifiers/regressors (ml_models_accuracy, quantitative_indicators_prediction, technical_indicators_clustering).
- **Partie 4 (stock_analysis/ + portfolio_strategies/)**: métriques (returns, volatilité, Sharpe) calculées → targets ou features ML; backtesting frameworks (backtrader) réutilisés (sklearn_trading_bot).
- **ta_functions.py (racine Finance)**: TA-Lib wrappers pour calcul rapide indicateurs → feature engineering.

---

## Synthèse

Le dossier `machine_learning/` constitue une **bibliothèque exhaustive de ~16 scripts ML** couvrant:

- **Séries temporelles classiques**: ARIMA (statsmodels), Prophet (saisonnalité).
- **Deep Learning**: LSTM (TensorFlow/Keras) pour séquences, MLP pour prédiction simple.
- **Clustering & réduction**: PCA + KMeans (segmentation tickers), graphical lasso (réseau ETFs), clustering indicateurs.
- **Classification & régression**: sklearn (Isolation Forest anomaly detection, classifiers multiples pour direction), régression linéaire/poly.
- **Backtesting ML-driven**: sklearn_trading_bot (Isolation Forest + backtrader + pyfolio).
- **Analyse probabiliste**: distributions returns, simulations.

Les **formules consolidées** (ARIMA, Prophet trend/seasonality, LSTM gates, PCA eigenvectors, KMeans inertie, Graphical Lasso, métriques MSE/MAE/MAPE/Sharpe) et les **contrats d'entrées/sorties** (tickers, fenêtres, hyperparams, splits, métriques, plots) fournissent une base complète pour intégration dans FinBotX, reproduction, et extension (ex: ajout Transformers, GRU, attention mechanisms, ensemble methods, AutoML).

Les **limites** (stationnarité ARIMA, overfitting LSTM, biais backtesting, coûts transaction, market regime changes) et **hypothèses** (normalité returns, clusters sphériques KMeans, outliers Isolation Forest) sont critiques à documenter pour usage production et validation rigoureuse.
