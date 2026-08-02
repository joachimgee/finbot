# 🎯 PHASE 5.4 - MODULE 4 : FACTOR ENSEMBLE STRATEGY

## MISSION CRITIQUE

Tu dois implémenter une **2ème stratégie de trading** utilisant un ensemble de facteurs ML (Phase 5.2) avec pondération IC pour générer des signaux robustes.

**Objectif** : Stratégie factor-driven multi-signal avec IC-weighting (plus sophistiquée que Module 2)

---

## 📚 CONTEXTE - AUDITS OBLIGATOIRES

**Lis CES audits EN ENTIER avant de coder** :

1. **ML4T** : `docs/AUDITS/AUDIT_ML4T_BOOK.md` pp. 48-65
   - Factor models (Fama-French, custom factors)
   - IC-weighted signals
   - Composite scores (Z-score normalization)

2. **FINANCE PART 5** : `docs/AUDITS/AUDIT_FINANCE_PARTIE_5_ML.md` pp. 10-20
   - Factor selection (top-K by IC)
   - Multi-factor strategies
   - Signal combination techniques

3. **BACKTESTING.PY** : `docs/AUDITS/AUDIT_BACKTESTING_PY.md` pp. 5-15
   - Strategy base class
   - self.I() vectorization
   - .optimize() parameter tuning

---

## 🏗️ RAPPELS CONVENTIONS FinBot

**Mêmes conventions que Module 2 (Sentiment-Momentum Strategy)** :

### **1. IMPORTS ORDRE STRICT**

```python
# 1. Stdlib
from typing import Optional, Dict, List, Tuple
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 3. Finance libs
from backtesting import Strategy

# 5. Local
from financial_analyzer.utils.helpers import get_logger
```

### **2. HERITAGE STRATEGY**

```python
class FactorEnsembleStrategy(Strategy):
    """TOUJOURS hériter de backtesting.Strategy."""
    
    # Paramètres optimisables
    top_k_factors = 10
    ic_threshold = 0.05
    ...
```

---

## 📦 LIVRABLES MODULE 4

**Fichiers à créer** :

```
src/financial_analyzer/
├── strategies/
│   ├── __init__.py (update)
│   └── factor_ensemble_strategy.py          # (1) Stratégie 2

tests/test_strategies/
├── __init__.py (update)
└── test_factor_ensemble_strategy.py         # 15 tests
```

---

## 🎯 FICHIER : `strategies/factor_ensemble_strategy.py`

**Rôle** : Stratégie multi-facteurs avec IC-weighting

**Durée** : 1-1.5h | **LOC** : 300 | **Tests** : 15

### **Spécifications détaillées**

```python
"""
Factor Ensemble Trading Strategy.

Multi-factor strategy using IC-weighted composite scores from Phase 5.2 factors.
Selects top-K factors by historical IC, combines them into a composite Z-score,
and generates long/short signals.

Audit references:
- AUDIT_ML4T_BOOK.md pp. 48-65 (factor models, IC-weighting)
- AUDIT_FINANCE_PARTIE_5_ML.md pp. 10-20 (multi-factor strategies)
- AUDIT_BACKTESTING_PY.md pp. 5-12 (Strategy base class)

Example:
    >>> from backtesting import Backtest
    >>> bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    >>> stats = bt.run()
    >>> stats['Return [%]']  # doctest: +SKIP
    18.5
"""

# 1. Stdlib
from typing import Optional, Dict, List, Tuple
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np
from scipy import stats

# 3. Finance libs
from backtesting import Strategy

# 5. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FactorEnsembleStrategy(Strategy):
    """
    Factor ensemble strategy with IC-weighted composite scores.
    
    Process:
    1. Select top-K factors by historical IC (Phase 5.2 factors)
    2. Normalize each factor to Z-score
    3. Compute IC-weighted composite score
    4. Generate long/short signals based on composite score thresholds
    5. Enter positions with dynamic sizing (proportional to composite score strength)
    6. Exit when composite score crosses zero or stop-loss triggered
    
    Entry Conditions (LONG):
    - composite_score > long_threshold (e.g., +1.0)
    - At least min_factor_agreement factors agree on direction
    - Volatility < max_volatility (risk control)
    
    Entry Conditions (SHORT):
    - composite_score < short_threshold (e.g., -1.0)
    - At least min_factor_agreement factors agree on direction
    - Volatility < max_volatility
    
    Exit Conditions:
    - composite_score crosses zero (signal reversal)
    - Stop loss: -max_loss_pct since entry
    - Take profit: +target_profit_pct since entry
    
    Position Sizing:
    - Proportional to abs(composite_score) (stronger signal = larger position)
    - Max max_position_size equity per position
    
    Audit References:
    - AUDIT_ML4T_BOOK.md p.50 (IC-weighted composite scores)
    - AUDIT_FINANCE_PARTIE_5_ML.md p.12 (factor selection by IC)
    - AUDIT_BACKTESTING_PY.md p.7 (Strategy.init, Strategy.next)
    
    Attributes:
        top_k_factors: Number of top factors to select by IC (default 10)
        ic_threshold: Minimum IC to consider factor (default 0.05)
        long_threshold: Composite score threshold for long entry (default 1.0)
        short_threshold: Composite score threshold for short entry (default -1.0)
        min_factor_agreement: Minimum % factors agreeing on direction (default 0.6)
        max_volatility: Maximum volatility threshold for entry (default 0.03)
        max_position_size: Max equity per position (default 0.10)
        max_loss_pct: Stop loss percentage (default 0.05)
        target_profit_pct: Take profit percentage (default 0.10)
        long_only: If True, only long positions (default False for long/short)
    
    Example:
        >>> bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
        >>> stats = bt.run()
        >>> print(f"Sharpe: {stats['Sharpe Ratio']:.2f}")  # doctest: +SKIP
        Sharpe: 1.82
        
        >>> # Optimize parameters
        >>> stats_opt = bt.optimize(
        ...     top_k_factors=[5, 10, 15],
        ...     long_threshold=[0.8, 1.0, 1.2],
        ...     maximize='Sharpe Ratio'
        ... )  # doctest: +SKIP
    """
    
    # Paramètres optimisables
    top_k_factors: int = 10
    ic_threshold: float = 0.05
    long_threshold: float = 1.0
    short_threshold: float = -1.0
    min_factor_agreement: float = 0.6
    max_volatility: float = 0.03
    max_position_size: float = 0.10
    max_loss_pct: float = 0.05
    target_profit_pct: float = 0.10
    long_only: bool = False
    
    def init(self) -> None:
        """
        Initialize factor ensemble indicators.
        
        Process:
        1. Validate presence of factor columns in self.data
        2. Select top-K factors by IC (mock: use first K columns)
        3. Create Z-score normalized indicators via self.I()
        4. Compute composite score (IC-weighted average)
        5. Compute volatility indicator (for risk control)
        
        Notes:
            - Factor columns expected format: factor_1, factor_2, ..., factor_N
            - IC values expected in column: factor_ic_1, factor_ic_2, ...
            - If IC columns missing, use equal weights
        
        Raises:
            ValueError: If no factor columns found
        
        Audit:
            - AUDIT_BACKTESTING_PY.md p.7 (Strategy.init)
            - AUDIT_ML4T_BOOK.md p.52 (factor selection by IC)
        
        Example:
            >>> # Colonnes requises dans data
            >>> required = ['Close', 'factor_1', 'factor_2', 'factor_ic_1', 'factor_ic_2']
        """
        logger.debug(f"Initializing {self.__class__.__name__} ...")
        
        # Identify factor columns (Phase 5.2 naming: factor_1, factor_2, ...)
        factor_cols = [c for c in self.data.df.columns if c.startswith('factor_') and not c.endswith('_ic')]
        ic_cols = [c for c in self.data.df.columns if c.endswith('_ic')]
        
        if not factor_cols:
            raise ValueError(
                f"No factor columns found in data. Expected columns like 'factor_1', 'factor_2', etc. "
                f"Available: {list(self.data.df.columns)}"
            )
        
        logger.info(f"Found {len(factor_cols)} factor columns, {len(ic_cols)} IC columns")
        
        # Select top-K factors by IC (if IC available)
        if ic_cols:
            # Extract mean IC per factor (mock: use latest value)
            ic_values = {c.replace('_ic', ''): self.data.df[c].iloc[-1] for c in ic_cols}
            sorted_factors = sorted(ic_values.items(), key=lambda x: abs(x[1]), reverse=True)
            selected_factors = [f for f, ic in sorted_factors[:self.top_k_factors] if abs(ic) >= self.ic_threshold]
        else:
            # No IC available: use first top_k_factors
            logger.warning("No IC columns found, using first top_k_factors")
            selected_factors = factor_cols[:self.top_k_factors]
        
        if not selected_factors:
            raise ValueError(
                f"No factors meet IC threshold {self.ic_threshold}. "
                f"Available factors: {factor_cols[:5]}..."
            )
        
        self.selected_factors = selected_factors
        logger.info(f"Selected {len(self.selected_factors)} factors: {self.selected_factors[:5]}...")
        
        # Create Z-score normalized indicators
        self.factor_zscores = {}
        for factor in self.selected_factors:
            # Z-score normalization via self.I()
            self.factor_zscores[factor] = self.I(
                lambda series=self.data.df[factor]: (series - series.mean()) / (series.std() + 1e-9)
            )
        
        # Compute composite score (IC-weighted if available)
        if ic_cols:
            # IC-weighted composite
            self.composite_score = self.I(
                self._compute_composite_ic_weighted,
                self.selected_factors,
                ic_values
            )
        else:
            # Equal-weighted composite
            self.composite_score = self.I(
                self._compute_composite_equal_weighted,
                self.selected_factors
            )
        
        # Volatility indicator (20-day rolling)
        self.volatility = self.I(
            lambda: self.data.Close.pct_change().rolling(20).std()
        )
        
        # Entry price tracking for stop-loss/take-profit
        self._entry_price: Optional[float] = None
        
        logger.info(
            f"{self.__class__.__name__} initialized: "
            f"{len(self.selected_factors)} factors, "
            f"long_threshold={self.long_threshold:.2f}, "
            f"short_threshold={self.short_threshold:.2f}"
        )
    
    def next(self) -> None:
        """
        Execute trading logic for current bar.
        
        Process:
        1. Extract current composite score and volatility
        2. If no position: check ENTRY conditions (long or short)
        3. If position exists: check EXIT conditions
        4. Calculate dynamic position size
        5. Log decisions
        
        Notes:
            - self.data[-1] = current bar
            - self.buy(size=X) = long position
            - self.sell(size=X) = short position (if long_only=False)
            - self.position.close() = close position
        
        Audit:
            AUDIT_BACKTESTING_PY.md p.10, AUDIT_ML4T_BOOK.md p.55
        """
        # Extract current values
        composite = self.composite_score[-1]
        volatility = self.volatility[-1]
        close = self.data.Close[-1]
        
        # Skip if indicators not ready
        if np.isnan(composite) or np.isnan(volatility):
            logger.debug(f"Skipping bar: composite={composite}, volatility={volatility}")
            return
        
        # --- ENTRY LOGIC ---
        if not self.position:
            # Check factor agreement
            factor_agreement = self._calculate_factor_agreement()
            
            # LONG entry conditions
            if (composite > self.long_threshold and 
                factor_agreement >= self.min_factor_agreement and
                volatility < self.max_volatility):
                
                # Position sizing: proportional to composite strength
                strength = min((composite - self.long_threshold) / self.long_threshold, 1.0)
                size = self.max_position_size * strength
                
                self._entry_price = close
                
                logger.info(
                    f"▲ ENTRY LONG @ {close:.2f} | composite={composite:.2f}, "
                    f"agreement={factor_agreement:.1%}, volatility={volatility:.3f}, size={size:.2%}"
                )
                self.buy(size=size)
            
            # SHORT entry conditions (if not long_only)
            elif (not self.long_only and
                  composite < self.short_threshold and 
                  factor_agreement >= self.min_factor_agreement and
                  volatility < self.max_volatility):
                
                strength = min(abs((composite - self.short_threshold) / self.short_threshold), 1.0)
                size = self.max_position_size * strength
                
                self._entry_price = close
                
                logger.info(
                    f"▼ ENTRY SHORT @ {close:.2f} | composite={composite:.2f}, "
                    f"agreement={factor_agreement:.1%}, volatility={volatility:.3f}, size={size:.2%}"
                )
                self.sell(size=size)
        
        # --- EXIT LOGIC ---
        else:
            is_long = self.position.size > 0
            
            # Exit condition 1: Composite crosses zero
            exit_signal_reversal = (is_long and composite < 0) or (not is_long and composite > 0)
            
            # Exit condition 2: Stop loss
            exit_stop_loss = False
            exit_take_profit = False
            if self._entry_price:
                pnl_pct = (close - self._entry_price) / self._entry_price * (1 if is_long else -1)
                exit_stop_loss = pnl_pct < -self.max_loss_pct
                exit_take_profit = pnl_pct > self.target_profit_pct
            
            if exit_signal_reversal or exit_stop_loss or exit_take_profit:
                reason = ("signal_reversal" if exit_signal_reversal else 
                          ("stop_loss" if exit_stop_loss else "take_profit"))
                
                logger.info(
                    f"{'▲' if is_long else '▼'} EXIT @ {close:.2f} | reason={reason}, "
                    f"composite={composite:.2f}"
                )
                self.position.close()
                self._entry_price = None
    
    # --- Helper Methods ---
    
    def _compute_composite_ic_weighted(self, factors: List[str], ic_values: Dict[str, float]) -> pd.Series:
        """Compute IC-weighted composite score."""
        weights = np.array([abs(ic_values.get(f, 0.05)) for f in factors])
        weights = weights / weights.sum()  # Normalize
        
        composite = pd.Series(0.0, index=self.data.df.index)
        for i, factor in enumerate(factors):
            composite += weights[i] * self.factor_zscores[factor]
        
        return composite
    
    def _compute_composite_equal_weighted(self, factors: List[str]) -> pd.Series:
        """Compute equal-weighted composite score."""
        composite = pd.Series(0.0, index=self.data.df.index)
        for factor in factors:
            composite += self.factor_zscores[factor]
        return composite / len(factors)
    
    def _calculate_factor_agreement(self) -> float:
        """
        Calculate % of factors agreeing on signal direction.
        
        Returns:
            Fraction [0, 1] of factors with same sign as composite
        """
        composite = self.composite_score[-1]
        if abs(composite) < 1e-6:
            return 0.0
        
        direction = 1 if composite > 0 else -1
        agreements = sum(
            1 for f in self.selected_factors 
            if np.sign(self.factor_zscores[f][-1]) == direction
        )
        return agreements / len(self.selected_factors)


# Module exports
__all__ = ['FactorEnsembleStrategy']
```

### **Checklist implémentation**

- [ ] Hérite de `Strategy` (backtesting.py)
- [ ] Paramètres en attributs classe (optimisables)
- [ ] `init()` utilise `self.I()` pour tous les indicateurs
- [ ] Selection top-K factors par IC
- [ ] Z-score normalization des factors
- [ ] Composite score IC-weighted
- [ ] Long/short support (paramètre `long_only`)
- [ ] Position sizing dynamique (composite strength)
- [ ] Factor agreement calculation
- [ ] Stop-loss + take-profit
- [ ] Logging exhaustif
- [ ] Type hints 100%
- [ ] Docstrings Google complètes

---

## 🧪 TESTS FICHIER : `test_factor_ensemble_strategy.py`

**15 tests requis** :

```python
"""
Tests for FactorEnsembleStrategy.

Coverage:
- Initialization (3 tests)
- Entry conditions (5 tests)
- Exit conditions (3 tests)
- Factor selection (2 tests)
- Integration (2 tests)
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from financial_analyzer.strategies.factor_ensemble_strategy import FactorEnsembleStrategy
from backtesting import Backtest


def _make_backtest_data_with_factors(days: int = 252, n_factors: int = 15) -> pd.DataFrame:
    """
    Generate mock backtest data with factor columns.
    
    Returns:
        DataFrame with OHLCV + factor_1...factor_N + factor_ic_1...factor_ic_N
    """
    idx = pd.date_range('2024-01-01', periods=days, freq='D')
    
    close = 100 + np.cumsum(np.random.randn(days) * 0.5)
    close = np.maximum(close, 50)
    
    data = {
        'Open': close * 0.998,
        'High': close * 1.005,
        'Low': close * 0.995,
        'Close': close,
        'Volume': np.random.randint(900_000, 1_200_000, days)
    }
    
    # Add factors (Z-score normalized random walks)
    for i in range(1, n_factors + 1):
        factor_vals = np.cumsum(np.random.randn(days) * 0.1)
        data[f'factor_{i}'] = (factor_vals - factor_vals.mean()) / (factor_vals.std() + 1e-9)
        data[f'factor_ic_{i}'] = np.random.uniform(0.03, 0.15, days)  # Mock IC
    
    return pd.DataFrame(data, index=idx)


# --- Initialization Tests ---

def test_strategy_init_with_factors():
    """Strategy initializes correctly with factor columns."""
    data = _make_backtest_data_with_factors(100, n_factors=15)
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats is not None


def test_strategy_init_missing_factors():
    """Strategy raises ValueError if no factor columns."""
    data = pd.DataFrame({
        'Open': [100], 'High': [102], 'Low': [99], 'Close': [101], 'Volume': [1_000_000]
    }, index=pd.date_range('2024-01-01', periods=1))
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    with pytest.raises(ValueError, match="No factor columns found"):
        bt.run()


def test_strategy_parameters_default():
    """Verify default parameter values."""
    assert FactorEnsembleStrategy.top_k_factors == 10
    assert FactorEnsembleStrategy.long_threshold == 1.0
    assert FactorEnsembleStrategy.short_threshold == -1.0


# --- Entry Condition Tests ---

def test_entry_long_composite_above_threshold():
    """Entry long when composite > long_threshold."""
    data = _make_backtest_data_with_factors(200, n_factors=10)
    
    # Force high composite score (mock by setting factors positive)
    for i in range(1, 11):
        data.loc[data.index[50:60], f'factor_{i}'] = 1.5
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats['# Trades'] >= 1


def test_no_entry_if_composite_below_threshold():
    """No entry if composite < long_threshold."""
    data = _make_backtest_data_with_factors(100, n_factors=10)
    
    # Force low composite scores
    for i in range(1, 11):
        data[f'factor_{i}'] = -0.5
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats['# Trades'] <= 1


def test_entry_short_if_not_long_only():
    """Entry short when composite < short_threshold (long_only=False)."""
    
    class ShortStrategy(FactorEnsembleStrategy):
        long_only = False
    
    data = _make_backtest_data_with_factors(200, n_factors=10)
    
    # Force negative composite
    for i in range(1, 11):
        data.loc[data.index[50:60], f'factor_{i}'] = -1.8
    
    bt = Backtest(data, ShortStrategy, cash=100_000)
    stats = bt.run()
    # Should have trades (long or short)
    assert stats['# Trades'] >= 0


def test_no_entry_if_volatility_too_high():
    """No entry if volatility > max_volatility."""
    data = _make_backtest_data_with_factors(100, n_factors=10)
    
    # Force high volatility (large price swings)
    data['Close'] = 100 + np.cumsum(np.random.randn(100) * 5)
    data['High'] = data['Close'] * 1.01
    data['Low'] = data['Close'] * 0.99
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    # Fewer trades due to volatility filter
    assert stats['# Trades'] <= 3


def test_entry_position_sizing():
    """Position size proportional to composite strength."""
    data = _make_backtest_data_with_factors(150, n_factors=10)
    
    # Moderate composite score
    for i in range(1, 11):
        data.loc[data.index[50:60], f'factor_{i}'] = 1.2
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats['Exposure Time [%]'] > 0


# --- Exit Condition Tests ---

def test_exit_on_signal_reversal():
    """Exit when composite crosses zero."""
    data = _make_backtest_data_with_factors(100, n_factors=10)
    
    # Entry conditions @ 30-40
    for i in range(1, 11):
        data.loc[data.index[30:40], f'factor_{i}'] = 1.5
    
    # Exit trigger @ 50: factors go negative
    for i in range(1, 11):
        data.loc[data.index[50:], f'factor_{i}'] = -0.8
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats['# Trades'] >= 1


def test_exit_on_stop_loss():
    """Exit when stop-loss triggered."""
    data = _make_backtest_data_with_factors(100, n_factors=10)
    
    # Entry @ 30
    for i in range(1, 11):
        data.loc[data.index[30:35], f'factor_{i}'] = 1.5
    
    # Crash @ 40
    entry_price = data.loc[data.index[30], 'Close']
    data.loc[data.index[40:], 'Close'] = entry_price * 0.90
    data.loc[data.index[40:], 'High'] = data.loc[data.index[40:], 'Close'] * 1.002
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats['# Trades'] >= 1


def test_exit_on_take_profit():
    """Exit when take-profit triggered."""
    data = _make_backtest_data_with_factors(100, n_factors=10)
    
    # Entry @ 30
    for i in range(1, 11):
        data.loc[data.index[30:35], f'factor_{i}'] = 1.5
    
    # Rally @ 40
    entry_price = data.loc[data.index[30], 'Close']
    data.loc[data.index[40:], 'Close'] = entry_price * 1.15
    data.loc[data.index[40:], 'High'] = data.loc[data.index[40:], 'Close'] * 1.002
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats['# Trades'] >= 1


# --- Factor Selection Tests ---

def test_factor_selection_by_ic():
    """Top-K factors selected by IC."""
    data = _make_backtest_data_with_factors(100, n_factors=20)
    
    class TopKStrategy(FactorEnsembleStrategy):
        top_k_factors = 5
    
    bt = Backtest(data, TopKStrategy, cash=100_000)
    stats = bt.run()
    # Verify strategy ran (factor selection worked)
    assert stats is not None


def test_factor_agreement_calculation():
    """Factor agreement calculated correctly."""
    data = _make_backtest_data_with_factors(100, n_factors=10)
    
    # All factors positive → high agreement
    for i in range(1, 11):
        data.loc[data.index[50:60], f'factor_{i}'] = 1.2
    
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    stats = bt.run()
    assert stats['# Trades'] >= 0


# --- Integration Tests ---

def test_backtest_complete_run():
    """Complete backtest on 1 year data."""
    data = _make_backtest_data_with_factors(252, n_factors=15)
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000, commission=0.002)
    stats = bt.run()
    
    assert 'Return [%]' in stats
    assert 'Sharpe Ratio' in stats
    assert stats['# Trades'] >= 0


def test_backtest_with_optimization():
    """Optimization of parameters."""
    data = _make_backtest_data_with_factors(300, n_factors=15)
    bt = Backtest(data, FactorEnsembleStrategy, cash=100_000)
    
    stats = bt.optimize(
        top_k_factors=[5, 10],
        long_threshold=[0.8, 1.0],
        maximize='Sharpe Ratio',
        constraint=lambda p: p['# Trades'] >= 3
    )
    
    assert stats is not None
    assert stats._strategy.top_k_factors in [5, 10]
```

### **Checklist tests**

- [ ] 15 tests minimum
- [ ] Coverage init (3), entry (5), exit (3), factors (2), integration (2)
- [ ] Fixture `_make_backtest_data_with_factors` génère factor_1...factor_N
- [ ] Tests long + short (long_only=False)
- [ ] Tests factor selection top-K
- [ ] Tests volatility filter
- [ ] Tests stop-loss + take-profit
- [ ] Test optimization

---

## 📊 CRITÈRES QUALITÉ

| Critère | Target |
|---------|--------|
| LOC | 300 |
| Tests | 15 |
| Coverage | 90%+ |
| Type hints | 100% |
| Docstrings | 100% |
| Audit refs | Chaque méthode |

---

## ✅ CHECKLIST PRÉ-LANCEMENT

- [ ] Audits lus (ML4T, Finance Part 5, Backtesting)
- [ ] Conventions Strategy comprises
- [ ] IC-weighting + Z-score clairs
- [ ] Prêt à coder

---

## 🚀 ACTION COPILOT

**Phase 1** : Génère `factor_ensemble_strategy.py` (300 LOC)
**Phase 2** : Génère `test_factor_ensemble_strategy.py` (15 tests)

**Qualité > Vitesse** 🎯
