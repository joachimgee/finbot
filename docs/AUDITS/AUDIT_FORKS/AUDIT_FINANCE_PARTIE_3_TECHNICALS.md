# DOSSIER D'AUDIT — FINANCE (PARTIE 3) — Indicateurs Techniques

Ce document cartographie de façon technique et exhaustive le dossier `technical_indicators/` (~80+ fichiers) du fork « Finance ». Aucun code n'a été transformé ni exécuté; il s'agit d'un registre détaillé des indicateurs, de leurs formules mathématiques, paramètres, signatures de calcul, dépendances, modes de visualisation et exemples d'usage.

Portée: `Finance-master/Finance-master/technical_indicators/`.

---

## Structure du périmètre

Le dossier contient **~80+ scripts Python**, chacun implémentant un indicateur ou une famille d'indicateurs (moyennes mobiles, oscillateurs, channels, ratios volume/price, momentum, volatilité, etc.). La plupart suivent un patron commun:

1. Import yfinance/pandas/matplotlib (+ `ta_functions` via `sys.path.append(parent_dir)` pour réutiliser TA-Lib wrappers).
2. Téléchargement de données historiques (ticker, start, end).
3. Calcul de l'indicateur (formule manuelle ou appel à `ta_functions`).
4. Visualisation (line charts et/ou candlestick + indicateur en sous-plot).

Liste complète des fichiers (ordre alphabétique):

- EMA.py, EMA_volume.py
- EWMA.py, EWMA_Double.py, EWMA_Triple.py
- GANN_lines_angles.py
- GMMA.py
- MACD.py
- MA_high_low.py
- MFI.py
- PVI.py, PVT.py
- ROC.py, ROI.py
- RSI.py, RSI_BollingerBands.py
- SMA.py
- TRIMA.py, TWAP.py, VWAP.py
- WMA.py, WSMA.py
- Z_Score_Indicator.py
- absolute_price_oscillator.py
- acceleration_bands.py
- accum_dist_line.py
- aroon.py, aroon_oscillator.py
- avg_directional_index.py
- avg_true_range.py
- balance_of_power.py
- beta_indicator.py
- bollinger_bands.py, bollinger_bandwidth.py
- breadth_indicator.py
- candle_abs_returns.py
- central_pivot_range_cpr.py
- chaikin_money_flow.py, chaikin_oscillator.py
- commodity_channel_index.py
- correlation_coeff.py, covariance.py
- detrended_price_oscillator.py
- donchain_channel.py
- double_exp_moving_avg.py
- dynamic_momentum_index.py
- ease_of_movement.py
- force_index.py
- geometric_return_indicator.py
- golden_death_cross.py
- high_minus_low.py
- hull_moving_average.py
- keltners_channels.py
- linear_regression.py, linear_regression_slope.py
- linear_weighted_moving_average.py
- mcclellan_oscillator.py
- momentum.py
- moving_average_envelopes.py, moving_average_high_low.py, moving_average_ribbon.py, moving_avg_env.py
- moving_linear_regression.py
- new_highs_new_lows.py
- pivot_point.py
- price_channels.py, price_relative.py
- realised_volatility.py
- relative_volatility_index.py
- smoothed_moving_average.py
- speed_resistance_lines.py
- standard_deviation_volatility.py
- stochastic_RSI.py, stochastic_fast.py, stochastic_full.py, stochastic_slow.py
- super_trend.py
- true_strength_index.py
- ultimate_oscillator.py
- variance_indicator.py
- volume_price_confirmation_Indicator.py
- volume_weighted_moving_average.py

---

## Dépendances transverses

- **Données**: yfinance (`yf.download(ticker, start, end)` avec `pdr_override()`), pandas.
- **Calcul**: NumPy, pandas; TA-Lib wrappers via `ta_functions.py` (RSI, MACD, EMA, ATR, CCI, OBV, Stochastiques, etc.).
- **Visualisation**: matplotlib.pyplot, mplfinance.original_flavor.candlestick_ohlc, matplotlib.dates pour formatage.
- **Pattern commun**: la plupart des scripts sont des démonstrations autonomes avec:
  - Saisie hardcodée (ticker/dates).
  - Calcul manuel de l'indicateur (formule explicite).
  - Alternative: appel `ta.INDICATOR(...)` quand disponible (via TA-Lib).
  - Affichage multi-subplot (prix + indicateur + volume optionnel).

---

## Classification par famille d'indicateurs

### Moyennes Mobiles (Trend-Following)

1. **SMA (Simple Moving Average)**: `SMA_n = (Σ_{i=0..n-1} Close_i) / n`.
2. **EMA (Exponential Moving Average)**: `EMA_t = α × Close_t + (1−α) × EMA_{t−1}` où `α = 2/(n+1)`.
3. **WMA (Weighted Moving Average)**: poids linéaires décroissants.
4. **WSMA (Wilder's Smoothed Moving Average)**: lissage Wilder (EMA modifié).
5. **TRIMA (Triangular Moving Average)**: SMA d'une SMA (double lissage).
6. **TWAP (Time-Weighted Average Price)**: moyenne simple des prix sur fenêtre intraday.
7. **VWAP (Volume-Weighted Average Price)**: `VWAP = Σ(Price × Volume) / Σ(Volume)` (rolling).
8. **HMA (Hull Moving Average)**: combinaison WMA de périodes différentes pour réduire lag.
9. **GMMA (Guppy Multiple Moving Average)**: superposition de plusieurs EMA (courtes + longues) pour visualiser trends multiples.
10. **EMA_volume**: EMA pondéré par volume (hybride VWAP/EMA).
11. **EWMA, EWMA_Double, EWMA_Triple**: EMA simple, double, triple (pour réduire lag).
12. **Linear Weighted Moving Average**: analogue WMA avec calcul vectorisé.
13. **Smoothed Moving Average**: variante Wilder's.
14. **Moving Average Envelopes**: bandes à +/− x% de MA.
15. **Moving Average Ribbon**: affichage de N MAs de périodes croissantes.
16. **MA_high_low**: MAs séparées pour High et Low.

### Oscillateurs de Momentum

1. **RSI (Relative Strength Index)**: `RSI = 100 − 100/(1 + RS)` où `RS = AVG_Gain / AVG_Loss` sur n périodes.
   - Seuils: 70 (overbought), 30 (oversold).
2. **Stochastic Oscillator**:
   - **Fast**: `%K = 100 × (Close − Low_n) / (High_n − Low_n)` ; `%D = SMA(%K, s)`.
   - **Slow**: `%K_slow = %D_fast` ; `%D_slow = SMA(%K_slow, s)`.
   - **Full**: paramétrage custom de fast/slow.
3. **Stochastic RSI**: `Stoch_RSI = (RSI − LL_RSI_n) / (HH_RSI_n − LL_RSI_n)`.
4. **MACD (Moving Average Convergence Divergence)**:
   - MACD Line: `EMA_12 − EMA_26`.
   - Signal Line: `EMA_9(MACD)`.
   - Histogram: `MACD − Signal`.
5. **ROC (Rate of Change)**: `ROC = 100 × (Close_t − Close_{t−n}) / Close_{t−n}`.
6. **Momentum**: `Momentum = Close_t − Close_{t−n}`.
7. **CCI (Commodity Channel Index)**: `CCI = (TP − SMA_TP) / (0.015 × STD_TP)` où `TP = (H+L+C)/3`.
8. **True Strength Index (TSI)**: double EMA du momentum relatif normalisé.
9. **Dynamic Momentum Index**: RSI adaptatif (période varie avec volatilité).
10. **MFI (Money Flow Index)**: RSI basé sur volume: `MF = TP × Volume` ; ratio MF+ / MF−.
11. **Balance of Power (BOP)**: `BOP = (Close − Open) / (High − Low)` (raw pression achat/vente).
12. **Chaikin Oscillator**: `MACD(ADL, 3, 10)` appliqué à l'Accumulation/Distribution Line.
13. **Aroon**: `Aroon_Up = 100 × (n − days_since_high) / n` ; `Aroon_Down = 100 × (n − days_since_low) / n`.
14. **Aroon Oscillator**: `Aroon_Up − Aroon_Down`.
15. **Ultimate Oscillator**: combinaison pondérée de BP (Buying Pressure) sur 3 fenêtres.
16. **Detrended Price Oscillator (DPO)**: `Close − SMA_{n/2+1}(Close shifted by n/2+1)`.
17. **Absolute Price Oscillator**: différence entre deux MAs (analogue MACD sans signal).

### Volatilité

1. **ATR (Average True Range)**: `TR = max(H−L, |H−C_prev|, |L−C_prev|)` ; `ATR = SMA(TR, n)`.
2. **Bollinger Bands**: `BB_upper = SMA + k×STD` ; `BB_lower = SMA − k×STD` (k=2 généralement).
3. **Bollinger Bandwidth**: `(BB_upper − BB_lower) / SMA`.
4. **Keltner Channels**: `KC_upper = EMA + m×ATR` ; `KC_lower = EMA − m×ATR` (m=2).
5. **Donchian Channel**: `Upper = max(High, n)` ; `Lower = min(Low, n)` ; `Middle = (Upper+Lower)/2`.
6. **Acceleration Bands**: variant des Bollinger avec biais de tendance.
7. **Standard Deviation Volatility**: rolling STD sur Close.
8. **Realised Volatility**: `sqrt(Σ(log_ret²) × 252)` (annualisée).
9. **Relative Volatility Index (RVI)**: RSI appliqué à la volatilité (STD des gains/pertes).
10. **SuperTrend**: bandes basées ATR avec état (hausse/baisse) pour stop-loss dynamique.
    - `BASIC_UPPER = (H+L)/2 + f×ATR` ; `BASIC_LOWER = (H+L)/2 − f×ATR` ; logique de flip selon Close vs bande précédente.

### Volume & Accumulation

1. **OBV (On-Balance Volume)**: `OBV_t = OBV_{t−1} + sign(Close_t − Close_{t−1}) × Volume_t`.
2. **Accumulation/Distribution Line (ADL)**: `MF_Multiplier = (2×Close − Low − High)/(High − Low)` ; `ADL_t = ADL_{t−1} + MF_Multiplier × Volume`.
3. **Chaikin Money Flow (CMF)**: `CMF = Σ(MF_Volume, n) / Σ(Volume, n)` sur n périodes.
4. **PVI (Positive Volume Index)**: ajuste seulement les jours où Volume > Volume_prev.
5. **PVT (Price Volume Trend)**: `PVT_t = PVT_{t−1} + Volume × (Close_t − Close_{t−1})/Close_{t−1}`.
6. **Force Index**: `FI = Volume × (Close − Close_prev)` (puis EMA pour lisser).
7. **Ease of Movement (EVM)**: `EVM = (H+L)/2 − (H_prev+L_prev)/2) / (Volume / (H−L))`.
8. **Volume Price Confirmation Indicator**: ratio de volume pondéré par direction prix.
9. **Breadth Indicator**: agrège avances/déclinaisons (ForceIndex, Chaikin).

### Channels & Support/Resistance

1. **Price Channels**: bandes autour High/Low max sur n périodes.
2. **Central Pivot Range (CPR)**: `Pivot = (H+L+C)/3` ; `BC = (H+L)/2` ; `TC = Pivot − BC + Pivot`.
3. **Pivot Point**: niveaux S1/S2/S3, R1/R2/R3 (formules décrites Partie 2).
4. **Speed & Resistance Lines**: lignes de tendance géométriques (Gann-like).
5. **GANN Lines/Angles**: projections géométriques (angles 1×1, 1×2, etc.).

### Ratios & Statistiques

1. **ROI (Return on Investment)**: `ROI = (Valeur_finale − Valeur_initiale) / Valeur_initiale`.
2. **Beta Indicator**: covariance(titre, marché) / variance(marché) (rolling).
3. **Correlation Coefficient**: `corr(Close_A, Close_B)` rolling.
4. **Covariance**: `cov(Close_A, Close_B)` rolling.
5. **Variance Indicator**: rolling variance des returns.
6. **Z-Score Indicator**: `(Close − SMA) / STD` (nombre d'écarts-types).
7. **Geometric Return Indicator**: produit cumulatif `(1 + ret_i)` − 1.
8. **Candle Absolute Returns**: `|Close − Open|` et ratios associés.
9. **High Minus Low**: simple différence `H − L` par période.
10. **Price Relative**: `Close_A / Close_B` pour paires ou vs indice.
11. **New Highs / New Lows**: compteurs de symboles atteignant 52w high/low (market breadth).
12. **McClellan Oscillator**: EMA(19) − EMA(39) appliqué à (Advances − Declines) sur marché.

### Régression & Smoothing

1. **Linear Regression**: fit linéaire sur fenêtre n, extrapolation ou résidus.
2. **Linear Regression Slope**: pente de la régression (angle de tendance).
3. **Moving Linear Regression**: régression glissante pour ligne de tendance.
4. **Golden/Death Cross**: détection croisements SMA50/SMA200 (buy/sell signal).

### Hybrides & Multi-Indicateurs

1. **RSI_BollingerBands**: Bollinger Bands appliqués sur la courbe RSI (seuils dynamiques).
2. **ADX (Average Directional Index)**: mesure de force de tendance (DI+, DI−, ADX); formules:
   - `+DM = max(H − H_prev, 0)` si `H − H_prev > L_prev − L` sinon 0.
   - `−DM = max(L_prev − L, 0)` si `L_prev − L > H − H_prev` sinon 0.
   - `DI+ = 100 × EMA(+DM, n) / ATR` ; `DI− = 100 × EMA(−DM, n) / ATR`.
   - `DX = 100 × |DI+ − DI−| / (DI+ + DI−)` ; `ADX = EMA(DX, n)`.

---

## Entrées/Sorties (contrats)

- **Entrées**:
  - `ticker` (str): symbole (AAPL, TSLA, etc.).
  - `start`, `end` (datetime.date): fenêtre de données.
  - Paramètres d'indicateur (int): `n` (fenêtre), `k` (facteur multiplicatif), `fast`/`slow`/`signal` (pour MACD/Stoch).
  - Dépendance externe: `ta_functions.py` (TA-Lib wrappé) pour calcul rapide d'indicateurs standards.

- **Sorties**:
  - DataFrame pandas avec colonnes ajoutées (ex: `RSI`, `MACD`, `Upper_BB`, `Lower_BB`, etc.).
  - Graphiques matplotlib (line + candlestick) avec sous-plots:
    - Subplot 1: prix (Close ou candlestick) + bandes/MAs éventuelles.
    - Subplot 2: indicateur (oscillateur, volume, etc.).
  - Aucun CSV export par défaut (impression/affichage uniquement).

- **Erreurs possibles**:
  - Ticker invalide → yfinance retourne DataFrame vide.
  - Fenêtre n trop grande vs historique dispo → NaN dans indicateurs.
  - Dépendances manquantes (TA-Lib/mplfinance) → ImportError.

---

## Formules clés consolidées

### Moyennes Mobiles

- **SMA(n)**: $\text{SMA}_t = \frac{1}{n} \sum_{i=0}^{n-1} C_{t-i}$
- **EMA(n)**: $\text{EMA}_t = \alpha \times C_t + (1-\alpha) \times \text{EMA}_{t-1}$, $\alpha = \frac{2}{n+1}$
- **WMA(n)**: $\text{WMA}_t = \frac{\sum_{i=1}^{n} w_i \times C_{t-i+1}}{\sum_{i=1}^{n} w_i}$, $w_i = i$
- **VWAP(n)**: $\text{VWAP}_t = \frac{\sum_{i=0}^{n-1} P_i \times V_i}{\sum_{i=0}^{n-1} V_i}$

### Oscillateurs

- **RSI(n)**:
  - $\text{Gain}_t = \max(C_t - C_{t-1}, 0)$, $\text{Loss}_t = |\min(C_t - C_{t-1}, 0)|$
  - $\text{AVG\_Gain} = \text{SMA}(\text{Gain}, n)$, $\text{AVG\_Loss} = \text{SMA}(\text{Loss}, n)$
  - $\text{RS} = \frac{\text{AVG\_Gain}}{\text{AVG\_Loss}}$, $\text{RSI} = 100 - \frac{100}{1 + \text{RS}}$

- **Stochastic %K (Fast)**: $\%K = 100 \times \frac{C - \text{LL}_n}{\text{HH}_n - \text{LL}_n}$
- **Stochastic %D**: $\%D = \text{SMA}(\%K, s)$

- **MACD**:
  - $\text{MACD} = \text{EMA}_{12} - \text{EMA}_{26}$
  - $\text{Signal} = \text{EMA}_9(\text{MACD})$
  - $\text{Histogram} = \text{MACD} - \text{Signal}$

- **CCI(n)**: $\text{CCI} = \frac{\text{TP} - \text{SMA}_{\text{TP}}}{0.015 \times \text{STD}_{\text{TP}}}$, $\text{TP} = \frac{H+L+C}{3}$

- **TSI**:
  - $\text{PC}_t = C_t - C_{t-1}$
  - $\text{EMA\_FS} = \text{EMA}(\text{PC}, 25)$, $\text{EMA\_SS} = \text{EMA}(\text{EMA\_FS}, 13)$
  - $\text{Absolute\_FS} = \text{EMA}(|\text{PC}|, 25)$, $\text{Absolute\_SS} = \text{EMA}(\text{Absolute\_FS}, 13)$
  - $\text{TSI} = 100 \times \frac{\text{EMA\_SS}}{\text{Absolute\_SS}}$

- **Aroon**:
  - $\text{Aroon\_Up} = 100 \times \frac{n - \text{days\_since\_high}}{n}$
  - $\text{Aroon\_Down} = 100 \times \frac{n - \text{days\_since\_low}}{n}$

### Volatilité

- **ATR(n)**:
  - $\text{TR}_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$
  - $\text{ATR}_t = \text{SMA}(\text{TR}, n)$

- **Bollinger Bands**:
  - $\text{BB\_upper} = \text{SMA}_n + k \times \text{STD}_n$
  - $\text{BB\_lower} = \text{SMA}_n - k \times \text{STD}_n$

- **Keltner Channels**:
  - $\text{KC\_upper} = \text{EMA}_n + m \times \text{ATR}_n$
  - $\text{KC\_lower} = \text{EMA}_n - m \times \text{ATR}_n$

- **SuperTrend**:
  - $\text{BASIC\_UPPER} = \frac{H+L}{2} + f \times \text{ATR}$
  - $\text{BASIC\_LOWER} = \frac{H+L}{2} - f \times \text{ATR}$
  - Logique de flip: si $C \leq \text{FINAL\_UPPER}_{t-1}$, alors $\text{SUPERTREND}_t = \text{FINAL\_UPPER}_t$ ; sinon $\text{SUPERTREND}_t = \text{FINAL\_LOWER}_t$.

### Volume

- **OBV**: $\text{OBV}_t = \text{OBV}_{t-1} + \text{sign}(C_t - C_{t-1}) \times V_t$

- **ADL**:
  - $\text{MF\_Multiplier} = \frac{2C - L - H}{H - L}$
  - $\text{ADL}_t = \text{ADL}_{t-1} + \text{MF\_Multiplier} \times V_t$

- **CMF(n)**: $\text{CMF} = \frac{\sum_{i=0}^{n-1} \text{MF\_Volume}_i}{\sum_{i=0}^{n-1} V_i}$

- **Force Index**: $\text{FI}_t = (C_t - C_{t-1}) \times V_t$, puis $\text{EMA}(\text{FI}, n)$ pour lissage.

### Autres

- **Z-Score**: $z = \frac{C - \text{SMA}_n}{\text{STD}_n}$

- **Beta**: $\beta = \frac{\text{Cov}(R_{\text{stock}}, R_{\text{market}})}{\text{Var}(R_{\text{market}})}$ (rolling)

- **ROC**: $\text{ROC} = 100 \times \frac{C_t - C_{t-n}}{C_{t-n}}$

---

## Exemples d'usage (non-exécutés)

- **RSI standalone**:
  - Paramètres: ticker="CRON", période=14, fenêtre 2 ans.
  - Calcul manuel: `change = df["Adj Close"].diff(1)` → séparation Gain/Loss → rolling mean → RS → RSI.
  - Alternative: `ta.RSI(df["Adj Close"], timeperiod=14)`.
  - Sortie: line chart (prix + RSI) avec seuils 70/30.

- **MACD**:
  - Paramètres: fast=12, slow=26, signal=9.
  - Calcul: `ta.MACD(df["Adj Close"], fastperiod=12, slowperiod=26, signalperiod=9)` → tuple (macd, signal, hist).
  - Sortie: subplot prix + subplot MACD/signal/hist (bar colorée).

- **Bollinger Bands**:
  - Paramètres: n=20, k=2.
  - Calcul: `MA = df["Adj Close"].rolling(20).mean()` ; `STD = df["Adj Close"].rolling(20).std()` ; bandes = MA ± 2×STD.
  - Sortie: line chart (Close + upper/lower bands).

- **Stochastic RSI**:
  - Paramètres: RSI(14), fenêtre 14 pour Stoch.
  - Calcul: `LL_RSI = df["RSI"].rolling(14).min()` ; `HH_RSI = df["RSI"].rolling(14).max()` ; `Stoch_RSI = (RSI − LL) / (HH − LL)`.
  - Sortie: subplot prix + Stoch_RSI avec seuils 0.8/0.2.

- **SuperTrend**:
  - Paramètres: n=7 (ATR), f=3 (facteur).
  - Calcul: TR → ATR → BASIC_UPPER/LOWER → logique de flip → SUPERTREND.
  - Sortie: line chart (Close + SUPERTREND) pour visualiser stop/trend.

- **VWAP**:
  - Fenêtre: 14 périodes.
  - Calcul: `VWAP = Σ(Close × Volume) / Σ(Volume)` rolling.
  - Sortie: candlestick + VWAP overlay.

---

## Visualisation

Tous les scripts proposent au moins deux types de graphes:

1. **Line Chart**: prix (Close) + indicateur(s) superposé ou en subplot séparé.
2. **Candlestick Chart** (via `mplfinance.original_flavor.candlestick_ohlc`):
   - Subplot 1: candlesticks OHLC + volume en twinx (barres vertes/rouges).
   - Subplot 2 (optionnel): indicateur (oscillateur, etc.).
   - Axes formattés avec `mdates.DateFormatter("%d-%m-%Y")`.

Patron de code candlestick observé:
```python
dfc = df.copy()
dfc["VolumePositive"] = dfc["Open"] < dfc["Adj Close"]
dfc = dfc.reset_index()
dfc["Date"] = mdates.date2num(dfc["Date"].tolist())
candlestick_ohlc(ax1, dfc.values, width=0.5, colorup="g", colordown="r")
ax1.xaxis_date()
ax1v = ax1.twinx()
colors = dfc.VolumePositive.map({True: "g", False: "r"})
ax1v.bar(dfc.Date, dfc["Volume"], color=colors, alpha=0.4)
```

---

## Hypothèses, limites et dépendances

- **TA-Lib**: plusieurs scripts dépendent de `ta_functions.py` qui wrap TA-Lib; si TA-Lib n'est pas installé, les appels `ta.RSI()`, `ta.MACD()`, etc. échouent (ImportError). Alternative: calcul manuel (code présent dans certains scripts).
- **Données historiques**: yfinance limite la granularité/historique selon le ticker; certains indicateurs nécessitent >200 périodes (ex: EMA200 + ATR + SuperTrend).
- **NaN handling**: `.dropna()` est utilisé pour éliminer périodes initiales sans assez de données; certains scripts ne le font pas → premiers points NaN dans indicateurs.
- **Performance**: calculs itératifs (SuperTrend, rolling window) peuvent être lents sur larges datasets; privilégier `.rolling()` vectorisé pandas quand possible.
- **Paramètres**: valeurs par défaut (ex: RSI=14, MACD 12/26/9) sont standards, mais ajustables selon stratégie.

---

## Croisements avec d'autres parties

- **Partie 2 (stock_data/)**: les fichiers `main_indicators_streamlit.py` et `main_indicators_one_graph.py` réutilisent les formules ici pour affichage interactif (Streamlit UI).
- **Partie 4 (stock_analysis/ + portfolio_strategies/)**: les backtests (SMA crossover, RSI trendline, optimized BB) s'appuient sur ces indicateurs pour générer signaux buy/sell.
- **Partie 5 (machine_learning/)**: features issues d'indicateurs (RSI, MACD, ATR, etc.) sont consommées par modèles LSTM/Prophet/sklearn pour prédiction/classification.
- **ta_functions.py (racine Finance)**: bibliothèque centrale wrappant TA-Lib (40+ indicateurs) avec signatures unifiées; audité dans Finance Partie 1.

---

## Synthèse

Le dossier `technical_indicators/` est une **bibliothèque exhaustive de ~80+ scripts** couvrant toutes les familles d'indicateurs techniques standards (moyennes mobiles, oscillateurs, volatilité, volume, channels, stats). Chaque script:

- Implémente formule(s) mathématique(s) explicite(s) avec paramètres documentés.
- Offre visualisation double (line + candlestick).
- Peut réutiliser `ta_functions` (TA-Lib) ou calculer manuellement.
- Sert de référence pour backtesting, screening, ML features, et dashboards interactifs (Streamlit).

Les formules consolidées ci-dessus constituent un registre complet des définitions mathématiques pour reproduction ou intégration dans FinBotX.
