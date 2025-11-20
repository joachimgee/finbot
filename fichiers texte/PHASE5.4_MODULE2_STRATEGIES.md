# 🎯 PHASE 5.4 - MODULE 2 : ML/SENTIMENT STRATEGIES

## MISSION CRITIQUE

Tu dois implémenter **2 stratégies de trading** utilisant les 114 facteurs ML/Sentiment (Phase 5.2-5.3) pour le backtesting engine (backtesting.py).

**Objectif** : Stratégies production-ready exploitant Features + Sentiment → Signaux → Positions

---

## 📚 CONTEXTE - AUDITS OBLIGATOIRES

**Lis CES audits EN ENTIER avant de coder** :

1. **BACKTESTING.PY** : `docs/AUDITS/AUDIT_BACKTESTING_PY.md` pp. 5-30
   - Classe `Strategy` (init, next, position sizing)
   - Méthode `self.I()` pour indicateurs vectorisés
   - `.optimize()` pour tuning paramètres
   - 30 métriques automatiques
   
2. **FINANCE PART 4** : `docs/AUDITS/AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md` pp. 8-20
   - Stratégies quantitatives (momentum, mean-reversion)
   - Pattern signal combination
   - Position sizing dynamique

3. **ML4T** : `docs/AUDITS/AUDIT_ML4T_BOOK.md` pp. 15-35
   - Factor-based strategies
   - IC-weighted signals
   - Walk-forward validation

---

## 🏗️ RAPPELS CONVENTIONS FinBot

### **1. IMPORTS ORDRE STRICT**

```python
# 1. Stdlib
from typing import Optional, Dict, Any
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 3. Finance libs - backtesting.py DIRECT
from backtesting import Strategy
import talib  # Technical indicators

# 4. ML (si nécessaire)
# 5. Projet local
from financial_analyzer.utils.helpers import get_logger
```

### **2. HERITAGE STRATEGY (backtesting.py)**

```python
class MyStrategy(Strategy):
    """
    TOUJOURS hériter de backtesting.Strategy (pas reimplementation).
    
    Méthodes obligatoires:
    - init() : Initialiser indicateurs (appelé 1 fois)
    - next() : Logic trading (appelé chaque bar)
    """
    
    # Paramètres optimisables (backtesting.py les voit)
    param1 = 10
    param2 = 0.5
    
    def init(self):
        """Initialiser indicateurs AVEC self.I()."""
        # ✅ BON : vectorisé, backtesting.py optimise
        self.sma = self.I(talib.SMA, self.data.Close, self.param1)
        
        # ❌ MAUVAIS : non-vectorisé, lent
        # self.sma = talib.SMA(self.data.Close, self.param1)
    
    def next(self):
        """Logic trading pour chaque bar."""
        # Accès dernier bar : self.data.Close[-1]
        # Accès position actuelle : self.position
        # Entry : self.buy(size=0.1)
        # Exit : self.position.close()
```

### **3. TYPE HINTS + DOCSTRINGS**

Même standards que Module 1 (Google style, Examples exécutables).

---

## 📦 LIVRABLES MODULE 2

**Fichiers à créer** :

```
src/financial_analyzer/
├── strategies/
│   ├── __init__.py
│   ├── sentiment_momentum_strategy.py    # (1) Stratégie 1
│   └── factor_ensemble_strategy.py       # (2) Stratégie 2

tests/test_strategies/
├── __init__.py
├── test_sentiment_momentum_strategy.py   # 20 tests
└── test_factor_ensemble_strategy.py      # 15 tests
```

---

## 🎯 FICHIER 1 : `strategies/sentiment_momentum_strategy.py`

**Rôle** : Stratégie combinant sentiment (Phase 5.3) + momentum technique

**Durée** : 1-2h | **LOC** : 350 | **Tests** : 20

### **Spécifications détaillées**

```python
"""
Sentiment-Momentum Trading Strategy.

Combine news sentiment analysis (Phase 5.3) with technical momentum indicators
to generate robust long-biased trading signals.

Audit references:
- AUDIT_BACKTESTING_PY.md pp. 5-12 (Strategy base class, vectorization)
- AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md pp. 10-15 (momentum strategies)
"""

# 1. Stdlib
from typing import Optional, Dict, Any
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 3. Finance libs
from backtesting import Strategy
import talib

# 5. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class SentimentMomentumStrategy(Strategy):
    """
    Long-biased strategy combining sentiment scores + technical momentum.
    
    Entry Conditions (LONG):
    1. sentiment_ma_5d > threshold (persistent positive sentiment)
    2. sentiment_surprise_20d > surprise_threshold (positive shock)
    3. RSI < rsi_upper (not overbought)
    4. Volume > volume_ma * volume_multiplier (volume confirmation)
    
    Exit Conditions:
    1. sentiment_ma_5d < 0 (sentiment turned negative)
    2. RSI > rsi_exit (overbought)
    3. Stop loss : -5% depuis entry (optionnel)
    
    Position Sizing:
    - Proportionnel à sentiment strength (0-1 scaling)
    - Max 10% equity per position (default)
    
    Audit:
    - AUDIT_BACKTESTING_PY.md p.7 (Strategy.init, Strategy.next)
    - AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md p.12 (momentum patterns)
    
    Example:
        >>> from backtesting import Backtest
        >>> bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
        >>> stats = bt.run()
        >>> stats['Return [%]']  # doctest: +SKIP
        15.2
    """
    
    # Paramètres optimisables (backtesting.py Backtest.optimize les voit)
    sentiment_threshold: float = 0.3      # Min sentiment score pour entry
    surprise_threshold: float = 1.5       # Min sentiment surprise (std)
    rsi_period: int = 14                  # RSI lookback period
    rsi_upper: int = 70                   # RSI overbought threshold
    rsi_exit: int = 80                    # RSI exit threshold
    volume_multiplier: float = 1.2        # Volume spike multiplier
    max_position_size: float = 0.10       # Max 10% equity
    stop_loss_pct: float = 0.05           # 5% stop loss (0 = disabled)
    
    def init(self) -> None:
        """
        Initialiser indicateurs techniques.
        
        IMPORTANT : Utiliser self.I() pour TOUTES les calculations
        (backtesting.py optimise automatiquement).
        
        Notes:
            - self.data contient OHLCV + features custom (sentiment_ma_5d, etc.)
            - self.I() vectorise les calculs pour performance
            - Ne jamais calculer en boucle dans init()
        
        Raises:
            ValueError: Si colonnes sentiment manquantes dans self.data
        """
        logger.debug(f"Initializing {self.__class__.__name__} ...")
        
        # Validation : vérifier colonnes sentiment présentes
        required_cols = ['sentiment_ma_5d', 'sentiment_surprise_20d']
        missing = [c for c in required_cols if c not in self.data.df.columns]
        if missing:
            raise ValueError(
                f"Missing sentiment columns: {missing}. "
                f"Ensure Phase 5.3 sentiment factors are computed before backtesting."
            )
        
        # Indicateurs sentiment (déjà calculés par Phase 5.3)
        # self.I() crée un wrapper vectorisé autour des séries
        self.sentiment_ma = self.I(lambda: self.data.sentiment_ma_5d)
        self.sentiment_surprise = self.I(lambda: self.data.sentiment_surprise_20d)
        
        # Indicateurs techniques
        self.rsi = self.I(talib.RSI, self.data.Close, self.rsi_period)
        self.volume_ma = self.I(talib.SMA, self.data.Volume, 20)
        
        logger.info(
            f"Strategy initialized: sentiment_threshold={self.sentiment_threshold:.2f}, "
            f"rsi_period={self.rsi_period}"
        )
    
    def next(self) -> None:
        """
        Logic trading pour chaque bar (appelé chaque jour/period).
        
        Process:
        1. Vérifier conditions ENTRY si pas de position
        2. Vérifier conditions EXIT si position existante
        3. Calculer position size dynamique
        4. Logger décisions importantes
        
        Notes:
            - self.data[-1] = dernier bar (current)
            - self.data[-2] = bar précédent
            - self.position = position actuelle (None si aucune)
            - self.buy(size=X) = ouvrir position long
            - self.position.close() = fermer position
        """
        # Variables locales pour lisibilité
        sentiment = self.sentiment_ma[-1]
        surprise = self.sentiment_surprise[-1]
        rsi_current = self.rsi[-1]
        volume_current = self.data.Volume[-1]
        volume_avg = self.volume_ma[-1]
        
        # --- ENTRY LOGIC (si pas de position) ---
        if not self.position:
            # Conditions cumulatives
            cond_sentiment = sentiment > self.sentiment_threshold
            cond_surprise = surprise > self.surprise_threshold
            cond_rsi = rsi_current < self.rsi_upper
            cond_volume = volume_current > (volume_avg * self.volume_multiplier)
            
            if cond_sentiment and cond_surprise and cond_rsi and cond_volume:
                # Position sizing : proportionnel à sentiment strength
                # Sentiment max = 1.0 (normalisé), min = threshold
                sentiment_strength = min((sentiment - self.sentiment_threshold) / (1.0 - self.sentiment_threshold), 1.0)
                size = self.max_position_size * sentiment_strength
                
                logger.info(
                    f"ENTRY LONG @ {self.data.Close[-1]:.2f} | "
                    f"sentiment={sentiment:.2f}, surprise={surprise:.2f}, "
                    f"rsi={rsi_current:.1f}, size={size:.2%}"
                )
                
                self.buy(size=size)
        
        # --- EXIT LOGIC (si position existante) ---
        else:
            # Exit conditions
            exit_sentiment = sentiment < 0  # Sentiment turned negative
            exit_rsi = rsi_current > self.rsi_exit  # Overbought extreme
            
            # Stop loss (optionnel)
            exit_stop_loss = False
            if self.stop_loss_pct > 0:
                entry_price = self.position.pl / self.position.size if self.position.size != 0 else 0
                current_loss = (self.data.Close[-1] - entry_price) / entry_price if entry_price > 0 else 0
                exit_stop_loss = current_loss < -self.stop_loss_pct
            
            if exit_sentiment or exit_rsi or exit_stop_loss:
                reason = "sentiment_neg" if exit_sentiment else ("rsi_exit" if exit_rsi else "stop_loss")
                logger.info(
                    f"EXIT @ {self.data.Close[-1]:.2f} | reason={reason}, "
                    f"sentiment={sentiment:.2f}, rsi={rsi_current:.1f}"
                )
                self.position.close()
```

### **Checklist implémentation**

- [ ] Hérite de `Strategy` (backtesting.py)
- [ ] Tous les paramètres en attributs de classe (pas dans `__init__`)
- [ ] `init()` utilise **SEULEMENT** `self.I()` pour indicateurs
- [ ] `next()` accès données via `self.data[-1]`
- [ ] Validation colonnes sentiment dans `init()`
- [ ] Position sizing dynamique (sentiment strength)
- [ ] Logging info/debug aux bons endroits
- [ ] Type hints sur paramètres et méthodes
- [ ] Docstrings Google complètes avec Example
- [ ] Stop loss optionnel (param `stop_loss_pct=0` pour désactiver)

---

## 🧪 TESTS FICHIER : `test_sentiment_momentum_strategy.py`

**20 tests requis** :

```python
"""
Tests for SentimentMomentumStrategy.

Coverage:
- Initialization (5 tests)
- Entry conditions (6 tests)
- Exit conditions (4 tests)
- Position sizing (3 tests)
- Integration backtest (2 tests)
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from financial_analyzer.strategies.sentiment_momentum_strategy import SentimentMomentumStrategy
# backtesting.Backtest pour tests integration
from backtesting import Backtest


def _make_backtest_data(days: int = 252) -> pd.DataFrame:
    """
    Génère données mock pour backtesting avec sentiment factors.
    
    Returns:
        DataFrame avec colonnes : Open, High, Low, Close, Volume,
                                  sentiment_ma_5d, sentiment_surprise_20d
    """
    idx = pd.date_range('2024-01-01', periods=days, freq='D')
    
    # Prix OHLC (random walk)
    close = 100 + np.cumsum(np.random.randn(days) * 0.5)
    
    # Sentiment factors (mock)
    sentiment_ma = np.random.uniform(-0.5, 0.8, days)  # Mostly positive
    sentiment_surprise = np.random.normal(0, 1.0, days)  # Centered 0
    
    df = pd.DataFrame({
        'Open': close * 0.998,
        'High': close * 1.005,
        'Low': close * 0.995,
        'Close': close,
        'Volume': np.random.randint(900_000, 1_200_000, days),
        'sentiment_ma_5d': sentiment_ma,
        'sentiment_surprise_20d': sentiment_surprise
    }, index=idx)
    
    return df


# -------------------- Initialization Tests --------------------

def test_strategy_init_with_valid_data():
    """Strategy s'initialise correctement avec données valides."""
    data = _make_backtest_data(100)
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.002)
    
    # Run pour déclencher init()
    stats = bt.run()
    
    # Vérifier que backtest a tourné
    assert stats is not None
    assert 'Return [%]' in stats


def test_strategy_init_missing_sentiment_columns():
    """Strategy lève ValueError si colonnes sentiment manquantes."""
    data = _make_backtest_data(100)
    data = data.drop(columns=['sentiment_ma_5d'])  # Remove required column
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    
    with pytest.raises(ValueError, match="Missing sentiment columns"):
        bt.run()


def test_strategy_parameters_default_values():
    """Vérifier valeurs par défaut des paramètres."""
    assert SentimentMomentumStrategy.sentiment_threshold == 0.3
    assert SentimentMomentumStrategy.rsi_period == 14
    assert SentimentMomentumStrategy.max_position_size == 0.10


def test_strategy_init_with_custom_parameters():
    """Strategy accepte paramètres custom."""
    data = _make_backtest_data(100)
    
    class CustomStrategy(SentimentMomentumStrategy):
        sentiment_threshold = 0.5
        rsi_period = 21
    
    bt = Backtest(data, CustomStrategy, cash=100_000)
    stats = bt.run()
    
    assert stats is not None


def test_strategy_indicators_initialized():
    """Indicateurs techniques initialisés correctement."""
    data = _make_backtest_data(100)
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    
    # Accès à la stratégie après run
    stats = bt.run()
    
    # Vérifier que RSI a été calculé (30+ valeurs non-NaN)
    # Note : backtesting.py ne donne pas accès direct à strategy._results
    # On vérifie indirectement via stats (si backtest a tourné, indicateurs OK)
    assert stats['# Trades'] >= 0


# -------------------- Entry Conditions Tests --------------------

def test_entry_long_all_conditions_met():
    """Entry LONG quand toutes conditions respectées."""
    data = _make_backtest_data(200)
    
    # Forcer conditions favorables sur une période
    data.loc[data.index[50:60], 'sentiment_ma_5d'] = 0.6  # > 0.3
    data.loc[data.index[50:60], 'sentiment_surprise_20d'] = 2.0  # > 1.5
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.001)
    stats = bt.run()
    
    # Au moins 1 trade doit avoir été généré
    assert stats['# Trades'] >= 1


def test_no_entry_if_sentiment_too_low():
    """Pas d'entry si sentiment < threshold."""
    data = _make_backtest_data(100)
    
    # Forcer sentiment négatif partout
    data['sentiment_ma_5d'] = -0.5
    data['sentiment_surprise_20d'] = 2.0  # Surprise OK mais sentiment trop bas
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Aucun trade attendu
    assert stats['# Trades'] == 0


def test_no_entry_if_rsi_overbought():
    """Pas d'entry si RSI > rsi_upper."""
    data = _make_backtest_data(100)
    
    # Forcer sentiment OK mais créer trend haussier → RSI élevé
    data['sentiment_ma_5d'] = 0.7
    data['sentiment_surprise_20d'] = 2.0
    data['Close'] = 100 + np.cumsum(np.ones(100) * 2)  # Strong uptrend → RSI > 70
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Peu ou pas de trades (RSI constamment overbought)
    assert stats['# Trades'] <= 2


def test_entry_position_sizing_proportional_to_sentiment():
    """Position size proportionnel à sentiment strength."""
    data = _make_backtest_data(100)
    
    # Scenario 1: sentiment moyen (0.5) → size ~= 50% de max
    data.loc[data.index[30:40], 'sentiment_ma_5d'] = 0.5
    data.loc[data.index[30:40], 'sentiment_surprise_20d'] = 2.0
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Vérifier via exposition max
    # Si sentiment=0.5 et max_position_size=0.10 → ~5% equity utilisé
    # Note : test indirect car backtesting.py n'expose pas position sizes individuels
    assert stats['Exposure Time [%]'] > 0


def test_no_entry_if_volume_too_low():
    """Pas d'entry si volume < threshold."""
    data = _make_backtest_data(100)
    
    # Forcer sentiment OK mais volume très bas
    data['sentiment_ma_5d'] = 0.7
    data['sentiment_surprise_20d'] = 2.0
    data['Volume'] = 100  # Très faible → volume_ma * 1.2 toujours > current
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    assert stats['# Trades'] <= 1


def test_entry_logged_correctly():
    """Entry events sont logged (via mock)."""
    data = _make_backtest_data(100)
    data.loc[data.index[40:50], 'sentiment_ma_5d'] = 0.8
    data.loc[data.index[40:50], 'sentiment_surprise_20d'] = 2.5
    
    with patch('financial_analyzer.strategies.sentiment_momentum_strategy.logger') as mock_logger:
        bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
        stats = bt.run()
        
        # Vérifier que logger.info a été appelé (au moins 1 fois pour init)
        assert mock_logger.info.call_count >= 1


# -------------------- Exit Conditions Tests --------------------

def test_exit_when_sentiment_turns_negative():
    """Exit position si sentiment < 0."""
    data = _make_backtest_data(100)
    
    # Entry conditions @ bar 30-40
    data.loc[data.index[30:40], 'sentiment_ma_5d'] = 0.7
    data.loc[data.index[30:40], 'sentiment_surprise_20d'] = 2.0
    
    # Exit trigger @ bar 45 : sentiment négatif
    data.loc[data.index[45:], 'sentiment_ma_5d'] = -0.3
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Trade fermé rapidement
    assert stats['# Trades'] >= 1
    assert stats['Avg. Trade Duration'] < pd.Timedelta(days=20)


def test_exit_when_rsi_extreme_overbought():
    """Exit position si RSI > rsi_exit (80)."""
    data = _make_backtest_data(100)
    
    # Entry @ bar 20
    data.loc[data.index[20:30], 'sentiment_ma_5d'] = 0.6
    data.loc[data.index[20:30], 'sentiment_surprise_20d'] = 1.8
    
    # Strong rally → RSI > 80 @ bar 40
    data.loc[data.index[35:], 'Close'] = data.loc[data.index[35:], 'Close'] * 1.2
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    assert stats['# Trades'] >= 1


def test_stop_loss_triggered():
    """Stop loss déclenché si perte > stop_loss_pct."""
    data = _make_backtest_data(100)
    
    # Entry @ bar 30
    data.loc[data.index[30:35], 'sentiment_ma_5d'] = 0.7
    data.loc[data.index[30:35], 'sentiment_surprise_20d'] = 2.0
    
    # Crash @ bar 40 : -10% depuis entry
    entry_price = data.loc[data.index[30], 'Close']
    data.loc[data.index[40:], 'Close'] = entry_price * 0.90  # -10%
    
    # stop_loss_pct = 0.05 (5%) → exit attendu
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Trade fermé avec perte
    assert stats['# Trades'] >= 1
    # Note : backtesting.py peut avoir +1 trade si réentrée après stop


def test_no_exit_if_all_conditions_still_valid():
    """Position reste ouverte si toutes conditions valides."""
    data = _make_backtest_data(100)
    
    # Sentiment constamment positif, RSI OK
    data['sentiment_ma_5d'] = 0.5
    data['sentiment_surprise_20d'] = 1.8
    data['Close'] = 100 + np.linspace(0, 5, 100)  # Trend modéré → RSI OK
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Très peu de trades (position longue maintenue)
    assert stats['# Trades'] <= 3


# -------------------- Position Sizing Tests --------------------

def test_position_size_scales_with_sentiment_strength():
    """Position size augmente avec sentiment strength."""
    # Déjà testé indirectement dans test_entry_position_sizing_proportional_to_sentiment
    # Test direct impossible sans accéder aux positions internes
    pass


def test_max_position_size_respected():
    """Position size ne dépasse jamais max_position_size."""
    data = _make_backtest_data(100)
    data['sentiment_ma_5d'] = 1.0  # Sentiment max
    data['sentiment_surprise_20d'] = 3.0
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Max Exposure ne doit pas dépasser max_position_size * cash
    # Note : Exposure Time [%] est temps en position, pas size
    # Test indirect : vérifier que strategy n'a pas over-leveraged
    assert stats['Exposure Time [%]'] <= 100


def test_position_size_zero_if_sentiment_at_threshold():
    """Position size ~0 si sentiment exactement au threshold."""
    data = _make_backtest_data(100)
    data['sentiment_ma_5d'] = 0.3  # Exactement au threshold
    data['sentiment_surprise_20d'] = 2.0
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Peu ou pas de trades (size trop faible)
    assert stats['# Trades'] <= 2


# -------------------- Integration Tests --------------------

def test_backtest_complete_run():
    """Backtest complet sur 1 an de données."""
    data = _make_backtest_data(252)  # 1 trading year
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.002)
    stats = bt.run()
    
    # Vérifier métriques clés présentes
    assert 'Return [%]' in stats
    assert 'Sharpe Ratio' in stats
    assert 'Max. Drawdown [%]' in stats
    assert stats['# Trades'] >= 0


def test_backtest_with_optimization():
    """Optimization des paramètres via backtesting.py."""
    data = _make_backtest_data(300)
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.002)
    
    # Optimize 2 paramètres
    stats = bt.optimize(
        sentiment_threshold=range(20, 50, 10),  # [0.2, 0.3, 0.4]
        rsi_period=[10, 14, 21],
        maximize='Sharpe Ratio',
        constraint=lambda p: p.# Trades >= 5  # Min 5 trades
    )
    
    # Vérifier que optimization a tourné
    assert stats is not None
    assert 'Return [%]' in stats
    assert stats._strategy.sentiment_threshold in [0.2, 0.3, 0.4]
```

### **Checklist tests**

- [ ] 20 tests minimum
- [ ] Coverage init (5), entry (6), exit (4), sizing (3), integration (2)
- [ ] Fixtures `_make_backtest_data()` avec sentiment factors
- [ ] Tests unitaires (sans dépendances externes)
- [ ] Tests integration avec `Backtest.run()`
- [ ] Test optimization avec `Backtest.optimize()`
- [ ] Mocks logger pour vérifier logging
- [ ] Assertions robustes (pas de flakiness)
- [ ] Docstrings sur chaque test
- [ ] Pas de tests flaky (random seed si nécessaire)

---

## 📊 CRITÈRES QUALITÉ

| Critère | Target | Validation |
|---------|--------|------------|
| LOC | 350 | Docstrings incluses |
| Tests | 20 | 5+6+4+3+2 |
| Coverage | 90%+ | pytest-cov |
| Type hints | 100% | mypy |
| Docstrings | 100% | Google style + Example |
| Audit refs | Chaque méthode | Commentaires |
| Logging | Debug+Info | get_logger |
| Performance | < 5s backtest | 252 bars |

---

## ✅ CHECKLIST PRÉ-LANCEMENT

- [ ] Audits lus (BACKTESTING_PY, FINANCE_PART_4, ML4T)
- [ ] Conventions FinBot comprises (imports, Strategy, self.I())
- [ ] Structure fichiers claire (strategies/, tests/)
- [ ] Prêt à coder

---

## 🚀 ACTION COPILOT

**Phase 1** : Génère `sentiment_momentum_strategy.py` complet (350 LOC)
- Code complet avec docstrings
- Type hints partout
- Logging exhaustif
- Validation colonnes

**Phase 2** : Génère `test_sentiment_momentum_strategy.py` (20 tests)
- Fixtures robustes
- Coverage complète
- Mocks corrects
- Assertions strictes

**Quand prêt** : Envoie les 2 fichiers pour review !

---

## 📝 NOTES IMPORTANTES

1. **NE PAS réimplémenter backtesting.py** : Toujours hériter `Strategy`
2. **Utiliser self.I()** : Obligatoire pour performance
3. **Paramètres en attributs classe** : Pas dans `__init__`
4. **Validation données** : Vérifier colonnes sentiment dans `init()`
5. **Logging production** : Info pour events, debug pour détails

**Bon courage ! Qualité > Vitesse** 🎯
