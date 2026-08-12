# Plan d’intégration des forks dans FinBot

Date: 2025-11-12
Auteur: FinBot Team
Statut: Proposition (aucun code modifié)

---

## Objectif

Intégrer les forks ajoutés dans `docs/Forks complet/` à l’architecture FinBot en tant que backends natifs, sans couches simplificatrices, avec une configuration stricte, des contrats formalisés, des tests d’intégration exhaustifs et une gouvernance de dépendances professionnelle. Ce document détaille le mapping par module, les points d’insertion exacts, les invariants d’API/données, des exemples d’usage, et les risques/licences.

Forks disponibles:
- FinanceDatabase (universe) — `FinanceDatabase-main`
- FinanceToolkit (150+ ratios, data, risk, options) — `FinanceToolkit-main`
- backtesting.py (engine) — `backtesting.py-master`
- PyPortfolioOpt (MV, BL, HRP helpers) — `PyPortfolioOpt-master`
- Riskfolio-Lib (24+ risk measures, HRP/HERC/NCO/BL) — `Riskfolio-Lib-master`
- financial-machine-learning (curation + patterns) — `financial-machine-learning-master`
- machine-learning-for-trading (MLOps/data/feature notebooks) — `machine-learning-for-trading-main`

---

## Inventaire FinBot actuel (audit rapide)

Références de modules et points d’extension existants dans le repo:

- Data Layer
    - `src/financial_analyzer/data/universe.py`: UniverseSelector (wrapper FinanceDatabase pour equities/ETFs/funds/crypto/indices) + `get_metadata` + stats; décoré avec `@cache_result`.
    - `src/financial_analyzer/universe/market_selector.py`: MarketSelector (filtrage taille/liquidité, parsing market cap, méthode `select_by_fundamental_criteria` intégrée à FinanceDatabase avec fallback curé).
    - `src/financial_analyzer/data/market_data.py`: MarketDataFetcher (FinanceToolkit + fallback yfinance, intraday Alpha Vantage, statements & ratios, normalisation OHLCV, throttling/caching via Toolkit différé).

- Portfolio & Risk
    - `src/financial_analyzer/portfolio/optimizer.py`: Optimiseur Mean-Variance avec régularisation covariance (shrinkage + jitter), frontière efficiente, Sharpe/Min-Var/Equal/Risk Parity, contraintes via `PortfolioConstraints`.
    - `src/financial_analyzer/portfolio/constraints.py`: Limites min/max, long-only, HHI, contraintes sectorielles (mapping secteur → tickers), custom callables.
    - `src/financial_analyzer/portfolio/metrics.py`: Return/Vol/Sharpe, VaR/CVaR, HHI, Diversification Ratio.
    - `src/financial_analyzer/portfolio_optimization/riskfolio_optimizer.py`: Intégration Riskfolio-Lib (Classic, CVaR/CDaR/EVaR, HRP/HERC/NCO) avec estimation covariance (Ledoit-Wolf/OAS) et risk decomposition.
    - `src/financial_analyzer/integration/signal_portfolio_bridge.py`: Bridge signaux → poids (NCO prioritaire, MV fallback, contraintes min/max, long-only), calcul covariances à partir d’OHLCV multi-formats.

- Backtesting
    - `src/financial_analyzer/backtesting/backtest_runner.py`: Moteur interne multi-actifs (FinBotBacktester), optimisation hyperparams, WFA, rapport; évite réseau en tests.
    - `src/financial_analyzer/backtesting/finbot_strategy.py`: FinBotBacktester + RiskConfig (stop-loss/take-profit/periodic rebalance), intégration Pipeline, SignalFusion, EnsembleAllocator.

- Pipeline/ML/Sentiment (survol)
    - `src/financial_analyzer/pipeline/` et `src/financial_analyzer/ml/`, `ml_features/`, `sentiment/`: points d’intégration pour Feature store, IC, modèles.

- Utilitaires
    - `src/financial_analyzer/utils/helpers.py`: `get_logger`, `@cache_result(ttl|expiry_hours)`, validate helpers, calculs simples, timing.
    - `src/financial_analyzer/config.py`: constantes, API keys, chemins cache.

Conséquence: la plupart des intégrations FinanceDatabase/FinanceToolkit/Riskfolio sont déjà partiellement en place. Le plan ci-dessous précise les extensions, les contrats et la convergence vers une API interne stable (y compris un backend optionnel PyPortfolioOpt et un adaptateur backtesting.py facultatif).

---

## Vue d’ensemble de l’architecture FinBot cible

- Data: FinanceDatabase (sélection, métadonnées), Yahoo/FMP via FinanceToolkit (fallbacks), cache parquet
- Features: FinanceToolkit (ratios/techniques), TA-Lib (si dispo)
- Backtesting: backtesting.py (vectorisé), signaux FinBot → Strategy adapter
- Portfolio: PyPortfolioOpt (EF/BL/constraints simples), Riskfolio-Lib (mesures avancées, HRP/HERC/NCO)
- Risk: Riskfolio-Lib + métriques FinBot (VaR, CVaR, Drawdown, Ulcer, RLVaR)
- ML: Patterns et datasets des deux forks ML; modèles FinBot (LSTM, RF, FinBERT)
- Live Trading: Orchestrateur FastAPI + rebalancer; universe via FinanceDatabase; exécution broker séparée

---

## Principes d’intégration (niveau production)

- Backends natifs: adoption directe des bibliothèques comme moteurs principaux des modules concernés (Data/Portfolio/Backtesting) — pas de couches d’abstraction inutiles.
- Contrats formalisés: schémas de données Pandas (index/colonnes/freq) et signatures Python documentés et versionnés; invariants vérifiés par tests.
- Robustesse opérationnelle: timeouts, retries avec backoff, politiques fail-closed, journalisation structurée, métriques de latence/erreur.
- Configuration stricte: clés/paramètres via `.env` et `financial_analyzer/config.py`; sources de vérité uniques; feature flags de bascule.
- Caching reproductible: artefacts parquet/feather adressés par hash des paramètres; invalidation contrôlée et TTL.
- Tests et conformité: intégration/e2e offline (mocks, enregistrements figés), golden datasets, matrices de compatibilité multi-versions.

---

## Data Layer

### 1) Universe: FinanceDatabase

Contrat (entrée/sortie):
- Entrées: sectors: List[str] | None, country: str | None, n_assets: int
- Sortie: List[str] (tickers), len<=n_assets
- Erreurs: réseau, résultats vides → fallback liste curée

Exemple d’usage (natif, modules existants):
```python
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.universe.market_selector import MarketSelector

u = UniverseSelector()  # utilise FinanceDatabase nativement
tickers = u.select_equities(sector='Technology', country='United States')
ms = MarketSelector(universe_selector=u)
top = ms.get_universe(sector='Technology', country='US', n_assets=20, min_marketcap_usd=0, min_volume_usd=0)
```

Notes d’intégration:
- Mapper secteurs user-friendly → GICS FinanceDatabase (ex: Technology → Information Technology)
- Ajouter cache parquet sur la DataFrame combinée
- Injecter via `financial_analyzer.universe.market_selector.MarketSelector`

Interop avec existant:
- `UniverseSelector.select_equities()` est la façade native FinBot vers FinanceDatabase (validation + cache). Conserver cette autorité et référencer depuis `MarketSelector` (sans ajouter de couche supplémentaire).
- `MarketSelector.select_by_fundamental_criteria()` s’appuie déjà sur `Equities().search` avec fallback; ajouter un paramètre `sector_mapping_policy: strict|loose` si utile, sans dupliquer la logique de sélection.

### 2) Marché & états financiers: FinanceToolkit

Contrat:
- Entrées: tickers: List[str], start_date, end_date, api_key (optionnel)
- Sorties: DataFrames multi-index (historical, statements, ratios)

Exemple (historique + ratios):
```python
from financetoolkit import Toolkit

tk = Toolkit(["AAPL","MSFT"], api_key=os.getenv("FMP_API_KEY"), start_date="2020-01-01")
hist = tk.get_historical_data()               # prix, retours, volatilité, dividendes
ratios = tk.ratios.collect_profitability_ratios()  # 50+ ratios
```

Notes:
- Utiliser `enforce_source` si on veut bloquer le fallback Yahoo
- Normaliser les colonnes/indices pour FinBot (niveau ticker/date)
- Respecter la limite FMP (250 req/jour pour Free); prévoir throttle/cache

Interop avec existant:
- `MarketDataFetcher.get_historical_data()` implémente Toolkit prioritaire + fallback yfinance, avec double signature (dates ou period). Étendre via:
    - Paramètre explicite `source: Literal["toolkit","yfinance","auto"]`.
    - Caching disque (parquet) adressé par hash (tickers, window, interval, source).
    - Alignement direct avec FinanceDatabase (mapping tickers, pas de conversion interne additionnelle).

Contrat détaillé MarketDataFetcher (existant):
- `get_historical_data(tickers: str|List[str], start_date|end_date|period, interval) -> DataFrame|Dict[str,DataFrame]`
- `get_financial_statements(ticker) -> {income,balance,cash,ratios}` (Toolkit)
- `get_intraday_data(ticker, interval) -> {ticker: DataFrame}` (Alpha Vantage)
- `get_latest_price(tickers) -> pd.Series`
- `validate_ohlcv(df)` lève ValueError si non conforme

---

## Feature Engineering

Sources:
- FinanceToolkit.technicals (Ichimoku, etc.)
- FinanceToolkit.ratios (valuation, profitability, leverage…)
- TA-Lib (optionnel) pour compléter

Contrat features:
- Entrée: price_df: DataFrame (columns: ["Open","High","Low","Close","Volume"]) par ticker
- Sortie: features_df: DataFrame alignée (index date, colonnes MultiIndex [ticker, feature])

Exemple de pipeline (pseudo):
```python
def build_features(price_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
    feats = []
    for tkr, df in price_dict.items():
        feat = pd.DataFrame(index=df.index)
        feat["ret_1d"] = df.Close.pct_change()
        feat["ret_5d"] = df.Close.pct_change(5)
        feat["rsi_14"] = compute_rsi(df.Close, 14)
        feat.columns = pd.MultiIndex.from_product([[tkr], feat.columns])
        feats.append(feat)
    return pd.concat(feats, axis=1).dropna()
```

---

## Backtesting

Lib: `backtesting.py`

Approche:
- Conserver le moteur interne multi‑actifs comme référence de production.
- Utiliser backtesting.py uniquement pour comparatifs unitaires/recherche hors production (sans adaptateur dédié en prod).

Contrat:
- Entrée: DataFrame par instrument (OHLCV), signaux (buy/sell/size)
- Sortie: stats (dict) + figures

Exemple (stratégie SMA cross):
```python
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

class SmaCross(Strategy):
    n1 = 10; n2 = 20
    def init(self):
        p = self.data.Close
        self.ma1 = self.I(lambda x,n: x.rolling(n).mean(), p, self.n1)
        self.ma2 = self.I(lambda x,n: x.rolling(n).mean(), p, self.n2)
    def next(self):
        if crossover(self.ma1, self.ma2):
            self.buy()
        elif crossover(self.ma2, self.ma1):
            self.sell()

bt = Backtest(price_df, SmaCross, commission=.001, exclusive_orders=True)
stats = bt.run()
```

Notes:
- Benchmarks & métriques → utiliser notre reporting interne; pas de couche d’adaptation supplémentaire en production.

Interop avec existant:
- Le moteur interne (`FinBotBacktester`) couvre multi-actifs et la logique de rebalance/gestion du risque, ce que backtesting.py ne fait pas nativement (plutôt mono-instrument). Nous proposons un adaptateur FACULTATIF `backtestingpy_adapter.py` pour comparer des stratégies simples (SMA, RSI) à des fins pédagogiques/perfs unitaires.
- Endroit proposé: `src/financial_analyzer/backtesting/backtestingpy_adapter.py` avec une API:
    - `run_single(prices: pd.DataFrame, strategy_cls, **kwargs) -> dict`
    - `compare_strategies(prices, strategies: dict[name, (cls, params)]) -> pd.DataFrame`

---

## Portfolio Optimization

### 1) PyPortfolioOpt (classique/rapide)

Cas d’usage:
- Mean-Variance, Max Sharpe, Min Vol
- BL (opinions simples), contraintes poids

Exemple:
```python
from pypfopt import EfficientFrontier, risk_models, expected_returns

mu = expected_returns.mean_historical_return(prices)
S = risk_models.sample_cov(prices)
ef = EfficientFrontier(mu, S)
weights = ef.max_sharpe(); weights = ef.clean_weights()
perf = ef.portfolio_performance(verbose=False)
```

Intégration:
- Intégration native PyPortfolioOpt comme backend optionnel appelé directement dans la voie d’optimisation, sélectionné par feature flag/paramètres, sans réécriture.
- Utilisation de nos estimations de covariance (Ledoit–Wolf + jitter) si cohérent, sinon risk_models natifs.

Interop avec existant:
- `portfolio/optimizer.py` couvre MV/Sharpe/Min-Var/Risk Parity. Ajouter une voie PyPortfolioOpt native via paramètre (`method="pyportfolioopt"`) et appels directs EfficientFrontier/BL.

### 2) Riskfolio-Lib (avancé)

Cas d’usage:
- 24+ risk measures (CVaR, CDaR, Ulcer, RLVaR…)
- HRP/HERC/NCO, Risk Parity
- Contraintes Turnover/TE/Facteurs

Exemple (Min CVaR):
```python
import riskfolio as rp

Y = returns_df  # T x N
port = rp.Portfolio(returns=Y)
port.assets_stats(method_mu='hist', method_cov='ledoit_wolf')
model = 'Classic'; rm = 'CVaR'; obj = 'MinRisk'
w = port.optimization(model=model, rm=rm, obj=obj, hist=True)
```

Intégration:
- Appels Riskfolio-Lib directs depuis les modules d’optimisation; retour `pd.Series` poids; contributions au risque calculées avec covariance de référence.

Interop avec existant:
- `portfolio_optimization/riskfolio_optimizer.py` est déjà en place (Classic, NCO, HRP, covariance shrinkage). Étendre avec:
    - Contraintes (poids min/max, long-only) paramétrées depuis `PortfolioConstraints`.
    - Exposition des diagnostics (codependence method, linkage, dendrogram data) et risk contributions.

---

## Risk & Metrics

- Utiliser Riskfolio-Lib pour calculer: VaR, CVaR, CDaR, Ulcer, MDD, RLDaR, EVaR
- Consolider avec nos métriques (Sharpe, Sortino, Calmar, Beta, TE)
- Normaliser fréquences (daily→annualisé) et périodes (window mobile)

Exemple (Sortino custom):
```python
def sortino(weights: pd.Series, returns: pd.DataFrame, rf: float = 0.02) -> float:
    p = (returns @ weights).dropna()
    ex = p - rf/252
    d = ex[ex<0]
    if len(d)==0: return float('nan')
    dd = d.std()* (252**0.5)
    return (p.mean()*252 - rf)/dd if dd>0 else float('nan')
```

---

## Machine Learning

Apports des forks:
- financial-machine-learning: curation d’outils (mlfinlab, factor research, OLPS, risk parity, RL)
- machine-learning-for-trading: workflow ML4T, data pipelining, factor → portfolio

Intégration progressive:
- Feature store: registry des features (source, fréquence, window, leakage guards)
- Validation factor: Information Coefficient (IC), turnover, decay
- Modèles: LSTM/GRU (retours), RF/XGBoost (classement), FinBERT (sentiment)

Exemple (IC sur signaux):
```python
from scipy.stats import spearmanr

def information_coefficient(signal: pd.Series, fwd_returns: pd.Series) -> float:
    s = signal.align(fwd_returns, join='inner')[0]
    r = fwd_returns.reindex_like(s)
    ic, _ = spearmanr(s.values, r.values)
    return float(ic)
```

---

## Live Trading

- Universe via FinanceDatabase (fallback curé)
- Data via Toolkit (Yahoo/FMP) ou provider maison
- Signal → BacktestingRunner pour simulation intraday/offline
- Rebalancer via PyPortfolioOpt / Riskfolio-Lib selon profil risque
- Gestion erreurs: timeouts, données manquantes, retry

---

## Gouvernance des dépendances

- Pinner versions dans `requirements.txt` (compat Python >=3.10)
- Optionnels: `extra[portfolio]`, `extra[risk]`, `extra[ml]`
- Heavy libs (cvxpy/mosek/gurobi) en option; fallback sur solveur open-source

Exemple (requirements extrait):
```txt
financedatabase>=2.1.0
financetoolkit>=1.5.0
PyPortfolioOpt>=1.5.6
riskfolio-lib>=6.0.0
backtesting>=0.3.3
scikit-learn>=1.4
xgboost>=2.0 ; extra == "ml"
cvxpy>=1.4 ; extra == "portfolio"
```

## Détails par fork (intégration spécifique et exemples)

### 1) FinanceDatabase (docs/Forks complet/FinanceDatabase-main)

- Rôle: sélection d’univers cross‑asset (Equities/ETFs/Funds/Indices/Crypto), métadonnées riches, filtres sectoriels/pays.
- État FinBot: UniverseSelector déjà branché (select_*), MarketSelector déjà intègre `select_by_fundamental_criteria()` avec fallback curé.
- Extensions proposées:
    - Mapping secteur configurable strict/loose et normalisation GICS (ex: Technology → Information Technology).
    - Cache parquet (TTL configurable) pour résultats `select`/`search` + métadonnées.
    - Stats d’univers (comptes par asset type) exposées à la Dashboard.
- Exemple (consolidation UniverseSelector + MarketSelector):
```python
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.universe.market_selector import MarketSelector

u = UniverseSelector()
tickers = u.select_equities(sector='Technology', country='United States')
ms = MarketSelector(universe_selector=u)
top = ms.get_universe(sector='Technology', country='US', n_assets=20, min_marketcap_usd=0, min_volume_usd=0)
```

### 2) FinanceToolkit (docs/Forks complet/FinanceToolkit-main)

- Rôle: historique de prix, états financiers, ratios (150+), techniques, options, economics; fallback possible selon source.
- État FinBot: MarketDataFetcher l’utilise déjà en priorité (clé FMP), fallback yfinance; expose statements/ratios/intraday.
- Extensions proposées:
    - Paramètre `source={auto,toolkit,yfinance}` et cache parquet.
    - Normalisation uniforme des sorties de ratios (MultiIndex [ticker, ratio], daté).
    - Limiteur de débit (throttle) et retries avec backoff.
- Exemple:
```python
from financial_analyzer.data.market_data import MarketDataFetcher

md = MarketDataFetcher(api_key=os.getenv('FMP_API_KEY'))
hist = md.get_historical_data(['AAPL','MSFT'], period='1y', interval='1d')
statements = md.get_financial_statements('AAPL')
```

### 3) PyPortfolioOpt (docs/Forks complet/PyPortfolioOpt-master)

- Rôle: expected_returns, risk_models, EfficientFrontier (max_sharpe/min_vol), Black‑Litterman simple, allocation discrète.
- État FinBot: mentionné et référencé, pas de backend dédié (MV maison + Riskfolio déjà en place).
- Intégration proposée: `portfolio_optimization/pyportfolioopt_optimizer.py`.
    - API homogène: `optimize_max_sharpe(returns|prices, bounds, market_neutral=False)` etc.
    - Conversion de `PortfolioConstraints` → bounds/objectives PyPO.
    - Tests: comparer poids et perfs vs MV maison sur cas synthétiques.
- Exemple:
```python
from pypfopt import expected_returns, risk_models, EfficientFrontier

mu = expected_returns.mean_historical_return(prices)
S = risk_models.sample_cov(prices)
ef = EfficientFrontier(mu, S)
w = ef.max_sharpe(); w = ef.clean_weights()
```

### 4) Riskfolio‑Lib (docs/Forks complet/Riskfolio-Lib-master)

- Rôle: 24+ risk measures (CVaR/CDaR/EVaR/RLVaR/Ulcer…), HRP/HERC/NCO, BL factoriel; plots/reporting.
- État FinBot: module d’intégration `RiskfolioOptimizer` déjà présent (Classic CVaR/CDaR, HRP/HERC/NCO, LW/OAS), risk decomposition.
- Extensions proposées:
    - Injection de `PortfolioConstraints` (bornes min/max, long‑only) dans calls riskfolio.
    - Diagnostics: linkage/codependence, dendrogramme (pour dashboards), contributions au risque par facteur (si dispo).
    - Sélection solveur CVXPY configurable; mode dégradé si indisponible.
- Exemple (déjà couvert par module existant):
```python
from financial_analyzer.portfolio_optimization.riskfolio_optimizer import RiskfolioOptimizer
w = RiskfolioOptimizer(returns).optimize_mean_cvar()
```

### 5) backtesting.py (docs/Forks complet/backtesting.py-master)

- Rôle: moteur de backtest simple, orienté Strategy mono‑instrument, indicateurs custom via `Strategy.I()`.
- État FinBot: moteur interne multi‑actifs complet; backtesting.py non utilisé directement.
- Intégration proposée: option d’engine intégrée au `BacktestRunner` (engine="finbot"|"backtestingpy").
    - Implémenter une voie d’exécution native dans `backtest_runner.py` qui instancie Backtesting.Backtest si engine="backtestingpy".
    - Signatures et sorties unifiées (stats dict, equity curve), sans couche d’adaptation séparée.
- Exemple:
```python
from backtesting import Backtest, Strategy
class SmaCross(Strategy):
        n1=10; n2=20
        def init(self):
                c = self.data.Close
                self.ma1 = self.I(lambda x,n: x.rolling(n).mean(), c, self.n1)
                self.ma2 = self.I(lambda x,n: x.rolling(n).mean(), c, self.n2)
        def next(self):
                from backtesting.lib import crossover
                if crossover(self.ma1, self.ma2): self.buy()
                elif crossover(self.ma2, self.ma1): self.sell()
```

### 6) financial‑machine‑learning (docs/Forks complet/financial-machine-learning-master)

- Rôle: hub documentaire et référentiel de ressources (liens/recherches) sur ML en finance (mlfinlab, OLPS, RL…).
- Intégration: inspiration méthodologique pour `FactorLab` (IC, turnover, decay), pipelines de recherche, checklists de validation; pas de dépendance directe.
- Action: ajouter un dossier `docs/AUDITS/` (déjà présent) pour consigner les choix et justifications, et pointer vers notebooks d’exemples internes.

### 7) machine‑learning‑for‑trading (docs/Forks complet/machine-learning-for-trading-main)

- Rôle: matériel éducatif (notebooks) couvrant data → factors → backtesting → DL/RL.
- Intégration: importer quelques notebooks de référence (réécrits pour nos APIs) pour on‑boarding/dev; pas de dépendance runtime.
- Action: dossier `notebooks/ml4t_*` avec adaptations à `MarketDataFetcher`/`SignalPortfolioBridge`.

### 8) Finance (docs/Forks complet/Finance-master)

- Rôle: collection de 150+ scripts (screeners, indicateurs techniques, data collection, ML intro, stratégies portefeuilles).
- Intégration: sélectionner des morceaux utiles comme compléments pédagogiques/diagnostics:
    - `technical_indicators/` → implémentations alternatives à TA‑Lib (si indispo), sous module `features/technical_extras.py`.
    - `find_stocks/` → exemples de screeners mappés à notre UniverseSelector/MarketSelector.
    - `portfolio_strategies/` → comparer résultats avec notre moteur interne via adapter simple.
- Contraintes: scripts standalone → encapsuler en fonctions pures avec I/O DataFrame; ajouter logs et tests; pas de web scraping en CI.

---

## Plan d’intégration par étapes (0 code modifié maintenant)

1. Universe (FinanceDatabase)
    - Utiliser `UniverseSelector` existant; compléter mapping secteurs (strict/loose) et cache TTL; tests d’intégration (mocks FinanceDatabase).
2. Data/Features (FinanceToolkit)
    - Étendre `MarketDataFetcher`: paramètre `source`, cache parquet, throttle/retry; normalisation stricte des sorties.
3. Portfolio
    - Ajouter une voie PyPortfolioOpt native (EF/BL) sélectionnable par paramètre; Riskfolio-Lib déjà en place (CVaR/HRP/HERC/NCO).
    - `SignalPortfolioBridge`: privilégier NCO; fallback MV/PyPortfolioOpt en paramètre.
4. Backtesting
    - Conserver le runner interne; utiliser backtesting.py pour comparatifs hors prod (sans adapter prod).
5. ML
    - `FactorLab` (IC, decay, turnover) et `ModelHub` (LSTM/RF/FinBERT) alignés sur jeux de données contrôlés.
6. Live
    - Orchestrateur: feature flags backends, surveillance métriques, alertes; plans de rollback.

Critères d’acceptation (exemples):
- Frontière efficiente (100 points, N≤50) < 500ms sur laptop; HRP < 1s pour N≤50.
- 0 réseau en CI (mocks), 90%+ lignes couvertes sur wrappers; 80%+ branches.
- Observabilité: logs structurés et compteurs Prometheus clés (latences fetch/optim, erreurs, taux fallback).
- FinanceDatabase / FinanceToolkit: suivre leurs LICENSE respectives et TOS des sources (FMP/Yahoo). Throttle + cache requis.
- PyPortfolioOpt: licence permissive (voir LICENSE du repo) → backend optionnel recommandé.
- Riskfolio‑Lib: BSD‑3‑Clause (compatible). Dépendances solveurs à isoler en extra.
- backtesting.py: licence permissive (voir LICENSE). À garder en démo/adapter facultatif.
- financial‑machine‑learning / machine‑learning‑for‑trading: ressources/notebooks; intégrer en documentation, pas en dépendance runtime.
- Finance (scripts): MIT (repo indiqué). Intégration par extraction ciblée + tests.

---

## Risques & Licences

- MIT/BSD (PyPortfolioOpt, backtesting.py): compatible
- Riskfolio-Lib (BSD-3-Clause): OK
- FinanceToolkit/FinanceDatabase: usage conforme, respect des TOS sources (FMP/Yahoo)
- mlfinlab (non inclus ici): attention licence commerciale si utilisé
- Performance: cvxpy/solveurs → coûts; prévoir modes dégradés

---

## Matrice de tests (proposition 80+ tests)

- Data
    - UniverseSelector/MarketSelector: 12 tests (params, mapping, cache TTL, fallback)
    - MarketDataFetcher: 16 tests (historical dates/period, yfinance fallback, intraday AV, statements/ratios, normalisation, validate_ohlcv)
- Portfolio
    - Optimizer MV: 12 tests (Sharpe/Min-Var, contraintes, frontière, PD covariance)
    - Riskfolio: 12 tests (CVaR/CDaR/EVaR, HRP/HERC/NCO, covariance methods, risk decomposition)
    - Constraints: 8 tests (min/max, long-only, HHI, secteurs mapping partiel)
- Backtesting
    - Runner interne: 8 tests (init/next/equity, stop-loss/TP, rebalance period)
    - Adapter backtesting.py: 4 tests (SMA cross, stats shape, erreurs)
- Integration
    - SignalPortfolioBridge: 10 tests (formats prix A/B/C, NCO→MV→fallback, contraintes, somme=1, NaN ffill)
    - Live pipeline (smoke): 4 tests (scheduling, risk guard mocks, order gen mocks)

Benchmarks rapides (pytest markers `perf`):
- Covariance estims (LW/OAS/sample) N=50, T=252: < 50ms
- MV optimize (SLSQP) N=50: < 150ms; HRP N=50: < 500ms

---

## Observabilité et journaux

- Logging via `get_logger(__name__)`, niveaux: debug (diagnostics), info (milestones), warning (fallbacks), error (échecs)
- Champs recommandés: module, fonction, asset_count, timing_ms, source, fallback_used, risk_measure
- Export Prometheus (optionnel): compteurs/latences par catégorie (fetch, optimize, backtest)

---

## Sécurité & conformité

- Gestion des secrets: `.env` + variables env; ne pas committer; docs `GUIDE_VERIFY_ORDERS_API_KEYS.md`
- TOS/Data: respect Financial Modeling Prep/Yahoo; throttle configurable; caches invalidables
- PII: aucune; logs sans données sensibles; rotation des logs en prod

---

## Matrice licences & compatibilité (préliminaire, à vérifier)

| Fork | Version cible (indicative) | Compat Python | Dépendances clés | Licence (à vérifier) | TOS / Notes |
|---|---|---|---|---|---|
| FinanceDatabase | ≥ 2.x | 3.10–3.12 | pandas, PyYAML (selon versions) | Voir LICENSE upstream | Respecter TOS des sources référencées |
| FinanceToolkit | ≥ 1.5 | 3.10–3.12 | requests, pandas | Voir LICENSE upstream | TOS FMP/Yahoo; throttling requis |
| PyPortfolioOpt | ≥ 1.5.6 | 3.10–3.12 | numpy, pandas, cvxopt (optionnel) | Voir LICENSE upstream | Backend “moteur portfolio” intégré |
| Riskfolio‑Lib | ≥ 6.x | 3.10–3.12 | numpy, pandas, cvxpy (solveurs) | BSD‑3‑Clause (confirmer) | Solveur open‑source par défaut; optionnels propriétaires |
| backtesting.py | ≥ 0.3.3 | 3.10–3.12 | numpy, pandas | Voir LICENSE upstream | Utilisation en engine intégré |
| financial‑machine‑learning | n/a | n/a | n/a | Agrégateur (divers) | Documentation/R&D, pas de dépendance runtime |
| machine‑learning‑for‑trading | n/a | n/a | n/a | Voir LICENSE upstream | Notebooks d’onboarding, pas de runtime |
| Finance (scripts) | n/a | n/a | variable | MIT (confirmer) | Extraction ciblée, pas de scraping en CI |

Notes:
- Les licences exactes doivent être vérifiées sur les fichiers LICENSE upstream au moment du pinning.
- Les politiques d’usage des données (Yahoo/FMP) doivent être respectées; prévoir limites de débit et caches.

---

## CI/CD et “Definition of Done” (DoD)

- Static checks: mypy strict, ruff/pylint sans warnings bloquants, formatting (black/isort) stable.
- Tests: 80%+ couverture globale; 90%+ sur modules d’intégration; 100% sur contrats critiques (somme poids, PD cov, validate_ohlcv).
- Benchmarks: MV N≤50 < 150 ms; HRP/HERC N≤50 < 1 s; fetching mocké < 100 ms par appel.
- Reproducibilité: seeds fixés; caches versionnés; golden datasets sous `tests/data/`.
- Observabilité: logs clés présents; métriques exportables (compteurs, latences) activables.
- Sécurité: aucune clé en clair; `.env` requis validé au démarrage; pas de PII en logs.

---

## Exemples d’orchestration (pseudo-code)

```python
# 1) Universe
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.universe.market_selector import MarketSelector
u = UniverseSelector()
tickers = u.select_equities(sector="Technology", country="United States")
tickers = MarketSelector(u).get_universe(sector="Technology", country="US", n_assets=20, min_marketcap_usd=0, min_volume_usd=0)

# 2) Data & Features
from financial_analyzer.data.market_data import MarketDataFetcher
md = MarketDataFetcher(api_key=os.getenv("FMP_API_KEY"))
prices = md.get_historical_data(tickers, period="1y", interval="1d")
# features: via modules features/ ou pipeline existante

# 3) Signals (propre à FinBot)
signals = SignalEngine().generate(features)

# 4) Backtest rapide
from financial_analyzer.backtesting.backtest_runner import run as run_bt
stats = run_bt({"AAPL": prices["AAPL"]})

# 5) Optimisation
returns = prices.pct_change().dropna()
from financial_analyzer.portfolio.optimizer import calculate_max_sharpe
w = calculate_max_sharpe(returns)
# avancé (riskfolio)
from financial_analyzer.portfolio_optimization.riskfolio_optimizer import RiskfolioOptimizer
w2 = RiskfolioOptimizer(returns).optimize_mean_cvar()

# 6) Rebalancing
orders = Rebalancer().plan(current_holdings, target_weights=w, prices=latest)

# 7) Monitoring
metrics = RiskDashboard().compute(returns, w)
```

---

## Check-list d’adoption

- [ ] Valider versions & compat (Python, NumPy, Pandas)
- [ ] Ajouter extras dans requirements
- [ ] Activer backends natifs (paramètres/feature flags)
- [ ] Implémenter cache & mocks réseau
- [ ] Ajouter 30+ tests intégration (smoke + e2e offline)
- [ ] Bench simple (optimisation < 1s pour N<=50)
- [ ] Docs sphinx/markdown (API wrappers + exemples)

---

## SLO/SLA & opérations

- SLO latence (p95):
    - Sélection univers (FinanceDatabase): < 400 ms (cache chaud), < 2s (cache froid)
    - Historique (Toolkit/yfinance, 20 tickers, 1y): < 3s (cache froid), < 300 ms (cache chaud)
    - Optimisation MV (N=50): < 150 ms; HRP (N=50): < 1 s
- Erreur max: < 0.1% des exécutions/jour (réseaux exclus) avec retries/backoff
- Observabilité: logs structurés + métriques Prometheus (latence/erreur/cache_hits)

## Déploiement & rollback

- Stratégie: flags de bascule pour chaque backend (Toolkit/yfinance, PyPO/Riskfolio)
- Canary 5% des jobs planifiés, puis ramp-up; rollback instantané via flags
- Artefacts: Docker image unique (voir `Dockerfile`), config montée via `.env`

## Qualité des données

- Contrôles Great Expectations (ou équivalent) sur OHLCV/ratios (schéma, NA, monotonicité)
- Golden datasets figés pour tests offline; horodatage et hachage des artefacts

## CI/CD & compatibilité

- Matrice: Python 3.10/3.11, NumPy/Pandas versions compatibles; CPU-only
- Jobs: lint (flake8/ruff), type-check (mypy), tests unitaires/intégration (sans réseau), benchmarks rapides


---

## Conclusion

L’intégration proposée maximise la valeur des forks tout en protégeant la stabilité de FinBot (API interne stable, gestion des erreurs, cache, tests). Les exemples fournis montrent comment brancher chaque brique sans toucher au cœur de FinBot, conformément à la demande (aucun code modifié pour l’instant). Prochaine étape: créer les wrappers et tests d’intégration correspondants dans `src/financial_analyzer/` et `tests/`.

---

## Annexes: schémas de données standard

- OHLCV DataFrame (single asset)
    - Index: DatetimeIndex (UTC)
    - Colonnes: [Open, High, Low, Close, Volume]
- OHLCV Multi-asset (production)
    - Colonnes: MultiIndex (ticker, field), fields ∈ {Open, High, Low, Close, Volume}
- Returns matrix
    - Index: date; Colonnes: tickers; dtype: float64; fréquence daily; annualisation ×252
- Weights
    - `pd.Series` index=tickers; somme=1; contraintes appliquées; long-only par défaut

