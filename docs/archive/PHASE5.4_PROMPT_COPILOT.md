# 🎯 PHASE 5.4 - ML SENTIMENT BACKTESTING INTEGRATION

## MISSION CRITIQUE

Tu dois implémenter le **chaînon manquant** du projet FinBot : connecter les 114 facteurs ML/Sentiment (Phase 5.1-5.3) au backtesting engine et portfolio optimizer.

**Objectif** : Pipeline complet E2E **Features → Signals → Portfolio → Backtest → Attribution**

---

## 📚 CONTEXTE - AUDITS OBLIGATOIRES À LIRE

**Avant de coder, lis CES audits EN ENTIER** (ordre critique) :

1. **INDEX COMPLET** : `docs/AUDITS/INDEX_COMPLET_AUDITS.md` (vue d'ensemble)
2. **SUMMARY** : `docs/AUDITS/SUMMARY_AUDIT_FINBOTX.md` (résumé exécutif)
3. **BACKTESTING** : `docs/AUDITS/AUDIT_BACKTESTING_PY.md` (framework vectorisé, 30 métriques)
4. **RISKFOLIO** : `docs/AUDITS/AUDIT_RISKFOLIO_LIB.md` (NCO, 24 mesures de risque)
5. **PYPORTFOLIO** : `docs/AUDITS/AUDIT_PYPORTFOLIOOPT.md` (efficient frontier, HRP)
6. **ML4T** : `docs/AUDITS/AUDIT_ML4T_BOOK.md` (attribution, factor models, walk-forward)
7. **FINANCE PART 4** : `docs/AUDITS/AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md` (stratégies quantitatives)
8. **FINANCE PART 5** : `docs/AUDITS/AUDIT_FINANCE_PARTIE_5_ML.md` (modèles ML, stacking)

**Pourquoi ces audits ?**
- backtesting.py : utiliser `.optimize()`, `.run()`, les 30 métriques auto, pas reimplementer
- Riskfolio : NCO algo, 24 risk measures, Kelly Criterion
- ML4T : Brinson attribution, factor models, cross-validation temporelle
- Finance fork : Pattern stratégies quantitatives + monoblock ML

---

## 🏗️ RAPPELS CONVENTIONS FinBot

Respecte **strictement** `.github/copilot-instructions.md` :

### **1. IMPORTS ORDRE STRICT**

```python
# 1. Stdlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 3. Finance libs (DIRECT, pas rimplementation)
from backtesting import Backtest, Strategy  # backtesting.py
import riskfolio as rp                        # Riskfolio-Lib
from pypfopt import EfficientFrontier        # PyPortfolioOpt

# 4. ML
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# 5. Projet local
from financialanalyzer.config import CONFIG, TRADINGCONFIG
from financialanalyzer.utils.helpers import get_logger
```

### **2. NAMING CONVENTIONS**

- **Classes** : `PascalCase` → `SentimentMomentumStrategy`, `SignalPortfolioBridge`
- **Functions** : `snake_case` → `convert_signals_to_weights`, `attribute_returns`
- **Constants** : `UPPER_SNAKE_CASE` → `MAX_WEIGHT`, `CONFIDENCE_THRESHOLD`
- **Private** : `_leading_underscore` → `_validate_signals`, `_apply_constraints`

### **3. TYPE HINTS OBLIGATOIRES**

```python
def convert_signals_to_weights(
    self,
    signals: Dict[str, float],
    prices: pd.DataFrame,
    lookback_days: int = 252
) -> Dict[str, float]:
    """
    Convertit signaux ML/sentiment en poids portfolio optimaux.
    
    Args:
        signals: Dict ticker → signal strength (-2 to +2)
        prices: OHLCV DataFrame, colonnes capitalisées
        lookback_days: Période historique pour covariance
    
    Returns:
        Dict ticker → poids optimal (0-1), sum=1
    
    Raises:
        ValueError: Si signals invalides ou prices non OHLCV
        TypeError: Si params mauvais type
    
    Example:
        >>> signals = {'AAPL': 1.5, 'MSFT': -0.8}
        >>> weights = bridge.convert_signals_to_weights(signals, prices)
        >>> assert abs(sum(weights.values()) - 1.0) < 0.01
    """
```

### **4. DOCSTRINGS GOOGLE STYLE COMPLET**

- Description brève + détaillée
- Args avec types ET description
- Returns avec type ET description
- Raises pour **CHAQUE** exception possible
- Example concret exécutable

### **5. LOGGING SYSTÉMATIQUE**

```python
logger = get_logger(__name__)

logger.debug(f"Détail technique: {var_name}")          # Dev debugging
logger.info(f"Signal généré pour {ticker}: {signal}")  # Normal flow
logger.warning(f"Signal anormal détecté: {ticker}")    # Attention
logger.error(f"Impossible d'optimiser: {error}")       # Erreur critique
```

### **6. GESTION ERREURS = TRY/EXCEPT/LOG + FALLBACK**

```python
try:
    weights = optimizer.optimize_nco(...)
except ValueError as e:
    logger.warning(f"NCO failed, fallback to mean-variance: {e}")
    weights = optimizer.optimize_mean_variance(...)
except Exception as e:
    logger.error(f"Portfolio optimization completely failed: {e}")
    raise
```

### **7. VALIDATION INPUTS**

```python
# TOUJOURS valider avant utiliser
if not isinstance(prices, pd.DataFrame):
    raise TypeError(f"prices must be DataFrame, got {type(prices)}")

if not all(col in prices.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume']):
    raise ValueError(f"prices missing OHLCV columns")

if prices.empty:
    raise ValueError("prices DataFrame is empty")

if pd.isna(prices).any().any():
    logger.warning("NaN values in prices, forward-filling...")
    prices = prices.fillna(method='ffill')
```

---

## 📦 LIVRABLES PHASE 5.4

**Arborescence fichiers à créer :**

```
src/financial_analyzer/
├── integration/
│   ├── __init__.py
│   ├── signal_portfolio_bridge.py        # (1) Jour 1
│   ├── ml_trading_pipeline.py            # (2) Jour 3-4
│   └── performance_attribution.py        # (3) Jour 2-3
├── strategies/
│   ├── __init__.py
│   ├── sentiment_momentum_strategy.py    # (4) Jour 2
│   └── factor_ensemble_strategy.py       # (5) Jour 2

tests/test_integration/
├── test_signal_portfolio_bridge.py       # 30 tests
├── test_sentiment_momentum_strategy.py   # 20 tests
├── test_factor_ensemble_strategy.py      # 15 tests
├── test_performance_attribution.py       # 25 tests
└── test_ml_trading_pipeline.py           # 40 tests E2E
```

---

## 🎯 MODULE 1 : `integration/signal_portfolio_bridge.py`

**Rôle** : Convertir signaux ML/sentiment en allocations portfolio optimales

**Durée** : Jour 1 | **LOC** : 400 | **Tests** : 30

### Signature principale

```python
class SignalPortfolioBridge:
    """
    Convertit signaux ML/Sentiment en allocations portfolio robustes.
    
    Pipeline:
    1. Réceptionne signaux (-2 à +2) de NewsSignalGenerator
    2. Filtre actifs par confidence + seuil sentiment
    3. Calcule expected returns (IC pondéré × signal strength)
    4. Optimise portfolio (Riskfolio NCO) avec contraintes
    5. Retourne poids optimaux (sum=1)
    
    Audit references:
    - AUDIT_RISKFOLIO_LIB.md pp. 12-18 (NCO algo)
    - AUDIT_PYPORTFOLIOOPT.md pp. 8-15 (efficient frontier)
    """
    
    def __init__(
        self,
        portfolio_optimizer,  # Phase 4
        sentiment_engine,     # Phase 5.3
        feature_selector,     # Phase 5.2
        max_weight: float = 0.20,
        min_weight: float = 0.01
    ):
        pass
    
    def convert_signals_to_weights(
        self,
        signals: Dict[str, float],
        prices: pd.DataFrame,
        lookback_days: int = 252,
        risk_measure: str = 'CVaR'
    ) -> Dict[str, float]:
        """
        Convertit signaux en poids portfolio via Riskfolio NCO.
        
        Args:
            signals: Dict[ticker, signal_strength (-2 to +2)]
            prices: OHLCV DataFrame capitalisées + DatetimeIndex UTC
            lookback_days: Fenêtre historique (252 = 1 an)
            risk_measure: 'MV'|'CVaR'|'CDaR'|'EVaR' (Riskfolio)
        
        Returns:
            Dict[ticker, weight] optimisé, sum=1.0
        
        Raises:
            ValueError: Si signals invalides
            TypeError: Si prices pas DataFrame OHLCV
        
        Process:
        1. Filter long_candidates (signal >= 1.0)
        2. Calculate expected_returns = IC_historical × signal_strength
        3. Call optimizer.optimize_nco(expected_returns, risk_measure)
        4. Apply constraints (max/min weight, sector limits)
        5. Normalize weights (sum=1)
        
        Audit:
        - AUDIT_RISKFOLIO_LIB.md p.14 (NCO step-by-step)
        - AUDIT_PYPORTFOLIOOPT.md p.10 (efficient frontier constraints)
        
        Example:
            >>> signals = {'AAPL': 1.5, 'MSFT': -0.8, 'GOOGL': 0.5}
            >>> weights = bridge.convert_signals_to_weights(signals, prices)
            >>> assert 0.95 < sum(weights.values()) <= 1.05
            >>> assert all(w >= 0.01 for w in weights.values() if w > 0)
        """
        pass
```

### Checklist implementation

- [ ] Validation inputs stricts (types, NaN, OHLCV)
- [ ] Logging debug/info/warning à chaque étape
- [ ] Utiliser **directement** Riskfolio NCO (JAMAIS réimplémenter)
- [ ] Handle cas edge : signaux tous 0, tous négatifs, NaN
- [ ] Type hints 100% (params + returns)
- [ ] Docstring Google complet avec Example exécutable
- [ ] Try/except/log avec fallback (NCO → Mean-Variance)
- [ ] Batch process si >100 actifs

### Tests à implémenter (30)

```python
# tests/test_integration/test_signal_portfolio_bridge.py

@pytest.mark.unit
class TestSignalPortfolioBridge:
    
    @pytest.fixture
    def bridge_mock(self):
        """Mock bridge avec FinanceDatabase mocké."""
        # Mock portfolio_optimizer, sentiment_engine, feature_selector
        pass
    
    # Signaux valides (10 tests)
    def test_convert_valid_signals_long_only(self, bridge_mock): pass
    def test_convert_mixed_signals_long_short(self, bridge_mock): pass
    def test_convert_signals_normalization_sums_to_one(self, bridge_mock): pass
    def test_convert_signals_respects_max_weight_constraint(self, bridge_mock): pass
    def test_convert_signals_respects_min_weight_constraint(self, bridge_mock): pass
    
    # Signaux invalides (8 tests)
    def test_convert_invalid_signal_values_not_in_range(self, bridge_mock): pass
    def test_convert_signals_all_zeros(self, bridge_mock): pass
    def test_convert_signals_with_nan(self, bridge_mock): pass
    def test_convert_signals_empty_dict(self, bridge_mock): pass
    
    # Edge cases (12 tests)
    def test_convert_signals_single_asset(self, bridge_mock): pass
    def test_convert_signals_high_volatility_prices(self, bridge_mock): pass
    def test_convert_signals_perfect_correlation(self, bridge_mock): pass
    def test_convert_signals_missing_prices(self, bridge_mock): pass
    # ... 8 tests de plus
    
    # Integration (mock backtesting)
    @pytest.mark.integration
    def test_convert_and_backtest_workflow(self, bridge_mock): pass
```

---

## 🎯 MODULE 2 : `strategies/sentiment_momentum_strategy.py`

**Rôle** : Stratégie backtesting.py combinant sentiment + momentum + technicals

**Durée** : Jour 2 | **LOC** : 350 | **Tests** : 20

### Signature

```python
from backtesting import Strategy

class SentimentMomentumStrategy(Strategy):
    """
    Stratégie long-biased combinant :
    - Sentiment score (Phase 5.3)
    - Momentum technique (RSI, EMAs)
    - Volume spike detection
    - Position sizing dynamique
    
    Long si :
    - sentiment_ma_5d > threshold (ex: 0.3)
    - sentiment_surprise_20d > 1.5 std
    - RSI < 70 (pas overbought)
    - Volume > 1.2 × MA20 volume
    
    Short si inverse (optionnel).
    
    Audit:
    - AUDIT_BACKTESTING_PY.md pp.5-12 (Strategy base class)
    - AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md pp.8-15 (stratégies quantitatives)
    """
    
    # Paramètres optimisables (via Backtest.optimize)
    sentiment_threshold = 0.3
    rsi_period = 14
    rsi_upper = 70
    volume_multiplier = 1.2
    max_position_size = 0.10  # 10% equity
    
    def init(self):
        """
        Initialiser indicateurs techniques.
        Appelé UNE FOIS avant backtesting.
        
        IMPORTANT : utiliser self.I() pour vectorisation backtesting.py
        """
        pass
    
    def next(self):
        """
        Logic trading pour chaque bar.
        Appelé CHAQUE jour/period.
        Accès : self.data[-1] = dernier bar
        """
        pass
```

### Checklist

- [ ] Hériter de `Strategy` (backtesting.py)
- [ ] `init()` initialiser tous les indicateurs via `self.I()`
- [ ] `next()` implémenter logic entry/exit
- [ ] Position sizing dynamique (signal strength × max size)
- [ ] Type hints sur paramètres
- [ ] Docstrings Google complètes
- [ ] Gestion edge cases : position existante, stop loss, timeout

### Tests (20)

```python
# tests/test_integration/test_sentiment_momentum_strategy.py

@pytest.mark.unit
def test_strategy_entry_conditions_long():
    """Vérifier entrée long respecte conditions."""
    pass

@pytest.mark.unit
def test_strategy_exit_conditions():
    """Vérifier sortie logic."""
    pass

@pytest.mark.integration
def test_strategy_backtest_end_to_end():
    """Backtest complet sur données mock."""
    pass
```

---

## 🎯 MODULE 3 : `strategies/factor_ensemble_strategy.py`

**Rôle** : Utiliser top 10 facteurs par IC pour signaux composites

**Durée** : Jour 2 | **LOC** : 300 | **Tests** : 15

---

## 🎯 MODULE 4 : `integration/performance_attribution.py`

**Rôle** : Décomposer PnL en contributions (Brinson model)

**Durée** : Jour 3 | **LOC** : 350 | **Tests** : 25

### Signature

```python
class PerformanceAttributor:
    """
    Attribution de performance multi-facteur (Brinson).
    
    Décompose retours totaux :
    1. Contribution sentiment signals (23 facteurs Phase 5.3)
    2. Contribution technical signals (91 facteurs Phase 5.2)
    3. Contribution portfolio optimization (allocation)
    4. Contribution timing (entry/exit)
    5. Résiduel inexpliqué
    
    Output : Dict[factor_type, contribution_pct]
    
    Audit:
    - AUDIT_ML4T_BOOK.md pp.35-48 (Brinson attribution, factor models)
    - AUDIT_RISKFOLIO_LIB.md pp.22-25 (risk contribution)
    """
    
    def attribute_returns(
        self,
        trades: pd.DataFrame,           # From Backtest
        sentiment_signals: pd.DataFrame, # Phase 5.3 output
        technical_factors: pd.DataFrame  # Phase 5.2 output
    ) -> Dict[str, float]:
        """
        Attribue PnL aux sources.
        
        Returns:
            {
                'sentiment_pct': 35.2,        # % PnL du sentiment
                'technical_pct': 42.8,        # % PnL des technicals
                'optimization_pct': 15.0,     # % PnL de l'allocation
                'timing_pct': 7.0,            # % PnL du timing
                'total_pnl': 15234.50         # PnL absolu
            }
        
        Audit: AUDIT_ML4T_BOOK.md p.36 (Brinson step-by-step)
        """
        pass
```

---

## 🎯 MODULE 5 : `integration/ml_trading_pipeline.py`

**Rôle** : Pipeline E2E complet

**Durée** : Jour 4 | **LOC** : 450 | **Tests** : 40 (E2E)

### Signature

```python
class MLTradingPipeline:
    """
    Pipeline E2E complet :
    Data → Features → Sentiment → Signals → Portfolio → Backtest → Attribution → Report
    
    12-step workflow production-ready.
    """
    
    def run(self) -> MLPipelineResult:
        """
        Execute pipeline complet.
        
        Steps:
        1. Fetch data (OHLCV + News)
        2. Engineer features (91 technical) [Phase 5.2]
        3. Calculate sentiment (23 factors) [Phase 5.3]
        4. Generate signals [NewsSignalGenerator]
        5. Convert signals → weights [SignalPortfolioBridge]
        6. Backtest strategy [backtesting.py]
        7. Optimize parameters [Grid/Bayesian]
        8. Attribute performance [Brinson]
        9. Calculate metrics [Sharpe, Sortino, CAR, etc.]
        10. Generate plots [Bokeh/Seaborn]
        11. Export results [JSON + CSV]
        12. Log summary
        
        Returns:
            MLPipelineResult:
                - backtest_stats
                - optimized_params
                - attribution
                - trades
                - equity_curve
                - plots
        
        Audit:
        - Référence intégration de TOUS les modules Phase 5.1-5.3
        - AUDIT_BACKTESTING_PY.md pp.20-30 (optimization, reporting)
        - AUDIT_RISKFOLIO_LIB.md pp.5-25 (portfolio constraints)
        """
        pass
```

---

## 📋 EXIGENCES QUALITÉ STRICTES

### **1. ZÉRO CODE RIMPLEMENTÉ**

- ❌ `def my_nco()` → Utiliser `riskfolio.Portfolio.optimization(model='NCO')`
- ❌ Custom backtest loop → Utiliser `backtesting.Backtest`
- ❌ Manual factor calculations → Utiliser features Phase 5.2 directement

**BON** : Wrapper minimal autour des libs, pas réinvention.

### **2. LOGGING EXHAUSTIF**

Chaque fonction critical doit logger :
- Entry : `logger.debug(f"Starting {func_name}...")`
- Progress : `logger.info(f"Processing {item}...")`
- Warnings : `logger.warning(f"Edge case detected...")`
- Errors : `logger.error(f"Failed: {exception}", exc_info=True)`

### **3. BATCH PROCESSING OBLIGATOIRE**

Si >50 signaux/actifs, utiliser batch processing (joblib, ThreadPool).

### **4. TESTS MOCKS STRICTS**

- **Zéro appels API externes** dans les tests
- Mock tous les imports externes (backtesting, riskfolio, sklearn)
- TimeSeriesSplit pour tout ML (jamais random split)
- Coverage ≥ 90%

### **5. TYPE HINTS 100%**

```python
# ❌ JAMAIS :
def convert(signals, prices, lookback):
    pass

# ✅ TOUJOURS :
def convert(
    self,
    signals: Dict[str, float],
    prices: pd.DataFrame,
    lookback: int = 252
) -> Dict[str, float]:
    pass
```

### **6. DOCSTRINGS GOOGLE COMPLETES**

```python
def method(self, param1: Type1, param2: Type2) -> ReturnType:
    """
    One-liner description.
    
    Longer description if needed.
    
    Args:
        param1: Description with type.
        param2: Description with type.
    
    Returns:
        Description with type.
    
    Raises:
        ExceptionType: When this happens.
    
    Audit:
        Reference to fork audit file and page.
    
    Example:
        >>> result = method(1, 2)
        >>> assert result > 0
    """
    pass
```

### **7. VALIDATION SYSTÉMATIQUE**

```python
# TOUJOURS valider AVANT traitement

if not isinstance(signals, dict):
    raise TypeError(f"signals must be dict, got {type(signals)}")

if not signals:
    raise ValueError("signals dict is empty")

if not all(isinstance(v, (int, float)) for v in signals.values()):
    raise ValueError("All signal values must be numeric")

if not all(-2 <= v <= 2 for v in signals.values()):
    raise ValueError(f"All signals must be in [-2, 2], got {signals}")
```

---

## 🧪 TESTS TEMPLATE

### Structure pytest

```python
# tests/test_integration/test_signal_portfolio_bridge.py

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from financialanalyzer.integration import SignalPortfolioBridge

@pytest.fixture
def mock_optimizer():
    """Mock PortfolioOptimizer."""
    return MagicMock()

@pytest.fixture
def mock_sentiment():
    """Mock SentimentFactorEngine."""
    return MagicMock()

@pytest.fixture
def bridge(mock_optimizer, mock_sentiment):
    """Bridge avec mocks."""
    return SignalPortfolioBridge(
        optimizer=mock_optimizer,
        sentiment_engine=mock_sentiment
    )

@pytest.mark.unit
def test_convert_signals_valid(bridge):
    """Test signals valides."""
    signals = {'AAPL': 1.5, 'MSFT': -0.8}
    prices = pd.DataFrame(...)  # Mock OHLCV
    
    weights = bridge.convert_signals_to_weights(signals, prices)
    
    assert isinstance(weights, dict)
    assert 0.99 < sum(weights.values()) <= 1.01

@pytest.mark.unit
def test_convert_signals_invalid_type(bridge):
    """Test type error."""
    with pytest.raises(TypeError):
        bridge.convert_signals_to_weights([1, 2, 3], None)

@pytest.mark.integration
@patch('backtesting.Backtest')
def test_full_pipeline(mock_backtest):
    """Test E2E avec backtesting mock."""
    pass
```

---

## 📊 METRIQUES DE SUCCES

| Métrique | Cible | Notes |
|----------|-------|-------|
| LOC | 1800 | 5 modules |
| Tests | 130 | 30+20+15+25+40 |
| Coverage | ≥ 90% | Mocks obligatoires |
| Type hints | 100% | Pas d'Any |
| Docstrings | 100% | Google style |
| Logs | Exhaustifs | Debug→Error |
| Tests speed | < 30s | Mocks, pas API réelles |
| Quality score | 9.8/10 | Audit refs complets |

---

## 📅 TIMELINE PHASE 5.4

| Jour | Modules | LOC | Tests | Livrables |
|------|---------|-----|-------|-----------|
| 1 | signal_portfolio_bridge.py | 400 | 30 | Code + tests mocks |
| 2 | 2 stratégies | 650 | 35 | Backtesting complet |
| 3 | performance_attribution.py | 350 | 25 | Attribution Brinson |
| 4 | ml_trading_pipeline.py | 450 | 40 | Pipeline E2E + reports |
| **TOTAL** | **5 modules** | **1800** | **130** | **Prêt Phase 5.5** |

---

## 🚀 ACTION IMMEDIATE POUR TOI

**Avant de lancer ce prompt à Copilot :**

1. ✅ Copie ce fichier `PHASE5.4_PROMPT_COPILOT.md` dans ton projet
2. ✅ Assure-toi que les audits sont dans `docs/AUDITS/` (15 fichiers)
3. ✅ `.github/copilot-instructions.md` est à jour (v2.0)
4. ✅ `requirements.txt` contient backtesting, riskfolio, pypfopt
5. ✅ Structure test/integration existe

**Copilot va générer :**
- PHASE5.4_DETAILED_PLAN.md (100+ lignes)
- Signatures complètes pour tous les modules
- Checklist d'implémentation détaillée
- Mapping audit → fonction

**Puis phase 2 :**

Copilot code les 5 modules jour par jour avec tests.

---

## ✅ CHECKLIST PRE-LANCEMENT

- [ ] Audits dans `docs/AUDITS/` (15 fichiers)
- [ ] Instructions v2.0 dans `.github/`
- [ ] `requirements.txt` à jour
- [ ] Structure répertoires créée
- [ ] Ce prompt copié dans le projet
- [ ] Prêt à envoyer à Copilot

**PROCHAINE ACTION** : Confirme les ✅ et je te dis comment envoyer à Copilot !

