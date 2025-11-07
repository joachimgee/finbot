# 🎯 PHASE 5.4 - MODULE 3 : PERFORMANCE ATTRIBUTION

## MISSION CRITIQUE

Tu dois implémenter un **module d'attribution de performance** qui décompose les retours totaux d'un backtest en contributions factorielles (Brinson attribution model adapté).

**Objectif** : Comprendre **POURQUOI** la stratégie performe → % gains dus au sentiment vs technicals vs allocation vs timing

---

## 📚 CONTEXTE - AUDITS OBLIGATOIRES

**Lis CES audits EN ENTIER avant de coder** :

1. **ML4T** : `docs/AUDITS/AUDIT_ML4T_BOOK.md` pp. 35-48
   - Brinson attribution model
   - Factor contribution analysis
   - Performance decomposition

2. **RISKFOLIO** : `docs/AUDITS/AUDIT_RISKFOLIO_LIB.md` pp. 22-25
   - Risk contribution per asset
   - Factor exposures

3. **BACKTESTING.PY** : `docs/AUDITS/AUDIT_BACKTESTING_PY.md` pp. 20-25
   - Trades DataFrame structure
   - Metrics extraction

---

## 🏗️ RAPPELS CONVENTIONS FinBot

### **1. IMPORTS ORDRE STRICT**

```python
# 1. Stdlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np
from scipy import stats

# 3. Finance libs (aucune dépendance backtesting.py ici)
# 4. ML (si nécessaire)

# 5. Projet local
from financial_analyzer.utils.helpers import get_logger
```

### **2. DATACLASSES POUR RÉSULTATS**

```python
@dataclass
class AttributionResult:
    """Résultat attribution."""
    sentiment_pct: float
    technical_pct: float
    allocation_pct: float
    timing_pct: float
    total_pnl: float
    residual_pct: float = 0.0
```

---

## 📦 LIVRABLES MODULE 3

**Fichiers à créer** :

```
src/financial_analyzer/
├── integration/
│   ├── __init__.py (update)
│   └── performance_attribution.py           # (1) Module principal

tests/test_integration/
├── __init__.py (update)
└── test_performance_attribution.py          # 25 tests
```

---

## 🎯 FICHIER : `integration/performance_attribution.py`

**Rôle** : Décomposer PnL en contributions factorielles

**Durée** : 1-2h | **LOC** : 350 | **Tests** : 25

### **Spécifications détaillées**

```python
"""
Performance Attribution Module.

Decompose backtest P&L into factor contributions using adapted Brinson model:
- Sentiment signals contribution (Phase 5.3 factors)
- Technical signals contribution (Phase 5.2 factors)
- Portfolio allocation contribution (optimizer impact)
- Timing contribution (entry/exit timing)

Audit references:
- AUDIT_ML4T_BOOK.md pp. 35-48 (Brinson attribution, factor models)
- AUDIT_RISKFOLIO_LIB.md pp. 22-25 (risk contribution per factor)
"""

# 1. Stdlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
from enum import Enum

# 2. Data/Calc
import pandas as pd
import numpy as np
from scipy import stats

# 5. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class AttributionMethod(Enum):
    """Attribution calculation methods."""
    BRINSON = "brinson"              # Brinson-Fachler model
    FACTOR_REGRESSION = "regression" # Factor regression
    SIMPLE = "simple"                # Simple contribution


@dataclass
class AttributionResult:
    """
    Performance attribution result.
    
    Attributes:
        sentiment_pct: % of total PnL attributed to sentiment signals
        technical_pct: % of total PnL attributed to technical factors
        allocation_pct: % of total PnL attributed to portfolio allocation
        timing_pct: % of total PnL attributed to entry/exit timing
        total_pnl: Total P&L in currency units
        residual_pct: % of PnL unexplained (should be small)
        trade_count: Number of trades analyzed
        attribution_method: Method used for calculation
    
    Notes:
        sentiment_pct + technical_pct + allocation_pct + timing_pct + residual_pct ≈ 100%
    
    Example:
        >>> result = AttributionResult(
        ...     sentiment_pct=35.2, technical_pct=42.8, allocation_pct=15.0,
        ...     timing_pct=7.0, total_pnl=15234.50, residual_pct=0.0,
        ...     trade_count=47, attribution_method='brinson'
        ... )
        >>> result.sentiment_pct + result.technical_pct
        78.0
    """
    sentiment_pct: float
    technical_pct: float
    allocation_pct: float
    timing_pct: float
    total_pnl: float
    residual_pct: float = 0.0
    trade_count: int = 0
    attribution_method: str = "brinson"
    
    def __post_init__(self):
        """Validate attribution percentages sum to ~100%."""
        total = (
            self.sentiment_pct + self.technical_pct + 
            self.allocation_pct + self.timing_pct + self.residual_pct
        )
        if abs(total - 100.0) > 5.0:  # 5% tolerance
            logger.warning(
                f"Attribution percentages sum to {total:.1f}%, expected ~100%. "
                f"Large residual may indicate incomplete attribution."
            )


class PerformanceAttributor:
    """
    Attribute backtest performance to factors (Brinson-style).
    
    Process:
    1. Receives trades DataFrame + signal DataFrames (sentiment, technical)
    2. For each trade, identify dominant signal type
    3. Calculate contribution per signal type
    4. Compute allocation effect (portfolio optimizer impact)
    5. Compute timing effect (entry/exit vs buy-and-hold)
    6. Return AttributionResult
    
    Audit References:
    - AUDIT_ML4T_BOOK.md p.36 (Brinson attribution step-by-step)
    - AUDIT_RISKFOLIO_LIB.md p.23 (factor contribution formula)
    
    Example:
        >>> attributor = PerformanceAttributor()
        >>> result = attributor.attribute_returns(
        ...     trades_df, sentiment_signals, technical_factors
        ... )
        >>> print(f"Sentiment: {result.sentiment_pct:.1f}%")
        Sentiment: 35.2%
    """
    
    def __init__(
        self,
        method: AttributionMethod = AttributionMethod.BRINSON,
        min_confidence: float = 0.5
    ):
        """
        Initialize attributor.
        
        Args:
            method: Attribution calculation method (default: Brinson)
            min_confidence: Minimum signal confidence to attribute (0-1)
        
        Notes:
            - Brinson method: decompose returns into selection + allocation + interaction
            - Regression method: factor regression on returns
            - Simple method: direct signal strength × PnL
        """
        self.method = method
        self.min_confidence = min_confidence
        logger.info(
            f"PerformanceAttributor initialized: method={method.value}, "
            f"min_confidence={min_confidence:.2f}"
        )
    
    def attribute_returns(
        self,
        trades: pd.DataFrame,
        sentiment_signals: pd.DataFrame,
        technical_factors: pd.DataFrame,
        prices: Optional[pd.DataFrame] = None
    ) -> AttributionResult:
        """
        Attribute P&L to factor sources.
        
        Args:
            trades: DataFrame from backtesting.py with columns:
                - EntryTime, ExitTime, EntryPrice, ExitPrice, PnL, Size, Ticker
            sentiment_signals: DataFrame with sentiment scores per ticker/time
                - Index: DatetimeIndex
                - Columns: tickers
                - Values: sentiment scores [-1, 1]
            technical_factors: DataFrame with technical factor values
                - Index: DatetimeIndex
                - Columns: factor names (e.g., RSI, MACD, etc.)
                - Values: factor values (normalized)
            prices: Optional OHLCV DataFrame for timing analysis
        
        Returns:
            AttributionResult with percentage contributions
        
        Raises:
            ValueError: If trades DataFrame empty or missing required columns
            TypeError: If inputs not DataFrames
        
        Process:
        1. Validate inputs (columns, types, alignment)
        2. For each trade, extract signals at entry time
        3. Classify trade as sentiment-driven or technical-driven
        4. Calculate contribution per category
        5. Compute allocation effect (vs equal-weight)
        6. Compute timing effect (actual vs buy-and-hold)
        7. Calculate residual (unexplained)
        
        Audit:
        - AUDIT_ML4T_BOOK.md p.37 (attribution calculation)
        - AUDIT_BACKTESTING_PY.md p.22 (trades DataFrame structure)
        
        Example:
            >>> trades = pd.DataFrame({
            ...     'EntryTime': [...], 'ExitTime': [...],
            ...     'PnL': [100, -50, 200], 'Size': [0.1, 0.1, 0.1]
            ... })
            >>> result = attributor.attribute_returns(trades, sentiment, technical)
            >>> assert 95 < sum([
            ...     result.sentiment_pct, result.technical_pct,
            ...     result.allocation_pct, result.timing_pct
            ... ]) <= 105
        """
        logger.debug("Starting performance attribution ...")
        
        # Validation
        self._validate_inputs(trades, sentiment_signals, technical_factors)
        
        if trades.empty:
            logger.warning("No trades to attribute, returning zero attribution")
            return AttributionResult(
                sentiment_pct=0.0, technical_pct=0.0,
                allocation_pct=0.0, timing_pct=0.0,
                total_pnl=0.0, trade_count=0,
                attribution_method=self.method.value
            )
        
        total_pnl = trades['PnL'].sum()
        logger.info(f"Attributing {len(trades)} trades, total PnL: {total_pnl:.2f}")
        
        # Step 1: Classify trades by dominant signal
        trade_classifications = self._classify_trades(
            trades, sentiment_signals, technical_factors
        )
        
        # Step 2: Calculate contributions
        sentiment_pnl = trade_classifications['sentiment_pnl'].sum()
        technical_pnl = trade_classifications['technical_pnl'].sum()
        overlap_pnl = trade_classifications['overlap_pnl'].sum()
        
        # Step 3: Allocation effect (vs equal-weight benchmark)
        allocation_pnl = self._calculate_allocation_effect(trades, prices)
        
        # Step 4: Timing effect (entry/exit vs buy-and-hold)
        timing_pnl = self._calculate_timing_effect(trades, prices)
        
        # Step 5: Calculate percentages
        attributed_pnl = sentiment_pnl + technical_pnl + allocation_pnl + timing_pnl
        
        if abs(total_pnl) < 1e-6:
            logger.warning("Total PnL near zero, returning equal attribution")
            return AttributionResult(
                sentiment_pct=25.0, technical_pct=25.0,
                allocation_pct=25.0, timing_pct=25.0,
                total_pnl=total_pnl, residual_pct=0.0,
                trade_count=len(trades),
                attribution_method=self.method.value
            )
        
        sentiment_pct = 100.0 * sentiment_pnl / total_pnl
        technical_pct = 100.0 * technical_pnl / total_pnl
        allocation_pct = 100.0 * allocation_pnl / total_pnl
        timing_pct = 100.0 * timing_pnl / total_pnl
        residual_pct = 100.0 - (sentiment_pct + technical_pct + allocation_pct + timing_pct)
        
        logger.info(
            f"Attribution complete: sentiment={sentiment_pct:.1f}%, "
            f"technical={technical_pct:.1f}%, allocation={allocation_pct:.1f}%, "
            f"timing={timing_pct:.1f}%, residual={residual_pct:.1f}%"
        )
        
        return AttributionResult(
            sentiment_pct=sentiment_pct,
            technical_pct=technical_pct,
            allocation_pct=allocation_pct,
            timing_pct=timing_pct,
            total_pnl=total_pnl,
            residual_pct=residual_pct,
            trade_count=len(trades),
            attribution_method=self.method.value
        )
    
    # -------------------- Internal Methods --------------------
    
    def _validate_inputs(
        self,
        trades: pd.DataFrame,
        sentiment_signals: pd.DataFrame,
        technical_factors: pd.DataFrame
    ) -> None:
        """Validate input DataFrames."""
        logger.debug("Validating attribution inputs ...")
        
        if not isinstance(trades, pd.DataFrame):
            raise TypeError(f"trades must be DataFrame, got {type(trades)}")
        if not isinstance(sentiment_signals, pd.DataFrame):
            raise TypeError(f"sentiment_signals must be DataFrame, got {type(sentiment_signals)}")
        if not isinstance(technical_factors, pd.DataFrame):
            raise TypeError(f"technical_factors must be DataFrame, got {type(technical_factors)}")
        
        # Check required columns in trades (backtesting.py standard)
        required_trade_cols = ['EntryTime', 'ExitTime', 'PnL']
        missing = [c for c in required_trade_cols if c not in trades.columns]
        if missing:
            raise ValueError(
                f"trades DataFrame missing required columns: {missing}. "
                f"Expected from backtesting.py: {required_trade_cols}"
            )
        
        # Check DatetimeIndex
        if not isinstance(sentiment_signals.index, pd.DatetimeIndex):
            raise ValueError("sentiment_signals must have DatetimeIndex")
        if not isinstance(technical_factors.index, pd.DatetimeIndex):
            raise ValueError("technical_factors must have DatetimeIndex")
        
        logger.debug("Input validation passed")
    
    def _classify_trades(
        self,
        trades: pd.DataFrame,
        sentiment_signals: pd.DataFrame,
        technical_factors: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Classify each trade as sentiment-driven, technical-driven, or overlap.
        
        Returns:
            DataFrame with columns: sentiment_pnl, technical_pnl, overlap_pnl
        
        Logic:
        - Si sentiment signal > threshold ET technical signal > threshold → overlap
        - Sinon, attribuer au signal dominant
        
        Audit: AUDIT_ML4T_BOOK.md p.38 (signal classification)
        """
        logger.debug("Classifying trades by signal type ...")
        
        results = []
        for idx, trade in trades.iterrows():
            entry_time = trade['EntryTime']
            pnl = trade['PnL']
            
            # Extract signals at entry time (or nearest)
            sentiment_score = self._get_signal_at_time(sentiment_signals, entry_time)
            technical_score = self._get_signal_at_time(technical_factors, entry_time)
            
            # Classify
            if abs(sentiment_score) > self.min_confidence and abs(technical_score) > self.min_confidence:
                # Overlap: both signals strong
                results.append({
                    'sentiment_pnl': pnl * 0.5,  # Split equally
                    'technical_pnl': pnl * 0.5,
                    'overlap_pnl': pnl
                })
            elif abs(sentiment_score) > abs(technical_score):
                # Sentiment dominant
                results.append({
                    'sentiment_pnl': pnl,
                    'technical_pnl': 0.0,
                    'overlap_pnl': 0.0
                })
            else:
                # Technical dominant
                results.append({
                    'sentiment_pnl': 0.0,
                    'technical_pnl': pnl,
                    'overlap_pnl': 0.0
                })
        
        return pd.DataFrame(results)
    
    def _get_signal_at_time(
        self,
        signals: pd.DataFrame,
        target_time: pd.Timestamp
    ) -> float:
        """
        Extract signal value at specific time (or nearest).
        
        Returns:
            Composite signal score (mean of all columns if multi-column)
        """
        try:
            # Try exact match
            if target_time in signals.index:
                row = signals.loc[target_time]
            else:
                # Nearest backward fill (asof)
                idx = signals.index.asof(target_time)
                if pd.isna(idx):
                    return 0.0
                row = signals.loc[idx]
            
            # If multiple columns, average
            if isinstance(row, pd.Series):
                return float(row.mean())
            else:
                return float(row)
        except Exception as e:
            logger.warning(f"Could not extract signal at {target_time}: {e}")
            return 0.0
    
    def _calculate_allocation_effect(
        self,
        trades: pd.DataFrame,
        prices: Optional[pd.DataFrame]
    ) -> float:
        """
        Calculate allocation effect vs equal-weight benchmark.
        
        Allocation effect = (actual weights - equal weights) × asset returns
        
        Audit: AUDIT_ML4T_BOOK.md p.40 (allocation attribution)
        """
        # Simplified: assume allocation effect = 10% of total PnL
        # Full implementation would require portfolio weights history
        total_pnl = trades['PnL'].sum()
        allocation_effect = total_pnl * 0.10  # Placeholder
        
        logger.debug(f"Allocation effect (placeholder): {allocation_effect:.2f}")
        return allocation_effect
    
    def _calculate_timing_effect(
        self,
        trades: pd.DataFrame,
        prices: Optional[pd.DataFrame]
    ) -> float:
        """
        Calculate timing effect (entry/exit vs buy-and-hold).
        
        Timing effect = actual PnL - buy-and-hold PnL
        
        Audit: AUDIT_ML4T_BOOK.md p.42 (timing attribution)
        """
        # Simplified: assume timing effect = 5% of total PnL
        # Full implementation would compare to buy-and-hold strategy
        total_pnl = trades['PnL'].sum()
        timing_effect = total_pnl * 0.05  # Placeholder
        
        logger.debug(f"Timing effect (placeholder): {timing_effect:.2f}")
        return timing_effect


# Module exports
__all__ = ['PerformanceAttributor', 'AttributionResult', 'AttributionMethod']
```

### **Checklist implémentation**

- [ ] Dataclass `AttributionResult` avec validation `__post_init__`
- [ ] Enum `AttributionMethod` (Brinson, Regression, Simple)
- [ ] Validation stricte inputs (types, colonnes, DatetimeIndex)
- [ ] Méthode `_classify_trades` : sentiment vs technical vs overlap
- [ ] Méthode `_get_signal_at_time` : extraction signal avec asof
- [ ] Placeholders pour allocation/timing (à améliorer Phase 5.5)
- [ ] Logging exhaustif (debug + info + warning)
- [ ] Type hints 100%
- [ ] Docstrings Google complètes
- [ ] Gestion erreurs (try/except/log)

---

## 🧪 TESTS FICHIER : `test_performance_attribution.py`

**25 tests requis** :

```python
"""
Tests for PerformanceAttributor.

Coverage:
- Initialization (3 tests)
- Input validation (5 tests)
- Trade classification (6 tests)
- Attribution calculation (7 tests)
- Edge cases (4 tests)
"""

import pytest
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

from financial_analyzer.integration.performance_attribution import (
    PerformanceAttributor, AttributionResult, AttributionMethod
)


# -------------------- Fixtures --------------------

@pytest.fixture
def mock_trades():
    """Create mock trades DataFrame (backtesting.py format)."""
    return pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15', '2024-01-20']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17', '2024-01-22']),
        'EntryPrice': [100.0, 105.0, 102.0],
        'ExitPrice': [105.0, 103.0, 110.0],
        'PnL': [500.0, -200.0, 800.0],
        'Size': [0.10, 0.10, 0.10]
    })


@pytest.fixture
def mock_sentiment_signals():
    """Create mock sentiment signals."""
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'AAPL': np.random.uniform(-0.5, 0.8, 30),
        'MSFT': np.random.uniform(-0.3, 0.7, 30)
    }, index=dates)


@pytest.fixture
def mock_technical_factors():
    """Create mock technical factors."""
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'RSI': np.random.uniform(30, 70, 30),
        'MACD': np.random.uniform(-2, 2, 30)
    }, index=dates)


@pytest.fixture
def attributor_default():
    """Default attributor."""
    return PerformanceAttributor()


# -------------------- Initialization Tests --------------------

def test_attributor_init_default():
    """Attributor initializes with default params."""
    attr = PerformanceAttributor()
    assert attr.method == AttributionMethod.BRINSON
    assert attr.min_confidence == 0.5


def test_attributor_init_custom():
    """Attributor initializes with custom params."""
    attr = PerformanceAttributor(
        method=AttributionMethod.SIMPLE,
        min_confidence=0.7
    )
    assert attr.method == AttributionMethod.SIMPLE
    assert attr.min_confidence == 0.7


def test_attribution_result_validation():
    """AttributionResult validates sum ~100%."""
    # Valid result (sum = 100%)
    result = AttributionResult(
        sentiment_pct=40.0, technical_pct=35.0,
        allocation_pct=15.0, timing_pct=10.0,
        total_pnl=1000.0, residual_pct=0.0
    )
    assert abs(result.sentiment_pct + result.technical_pct + 
               result.allocation_pct + result.timing_pct - 100.0) < 1e-6


# -------------------- Input Validation Tests --------------------

def test_validate_inputs_missing_columns(attributor_default, mock_sentiment_signals, mock_technical_factors):
    """Raise ValueError if trades missing columns."""
    bad_trades = pd.DataFrame({'EntryTime': [], 'PnL': []})  # Missing ExitTime
    
    with pytest.raises(ValueError, match="missing required columns"):
        attributor_default.attribute_returns(
            bad_trades, mock_sentiment_signals, mock_technical_factors
        )


def test_validate_inputs_wrong_types(attributor_default):
    """Raise TypeError if inputs not DataFrames."""
    with pytest.raises(TypeError, match="trades must be DataFrame"):
        attributor_default.attribute_returns(
            None, pd.DataFrame(), pd.DataFrame()
        )


def test_validate_inputs_no_datetimeindex(attributor_default, mock_trades):
    """Raise ValueError if signals not DatetimeIndex."""
    bad_signals = pd.DataFrame({'AAPL': [0.5, 0.6]})  # No DatetimeIndex
    
    with pytest.raises(ValueError, match="must have DatetimeIndex"):
        attributor_default.attribute_returns(
            mock_trades, bad_signals, pd.DataFrame(index=pd.date_range('2024-01-01', periods=2))
        )


def test_empty_trades_returns_zero_attribution(attributor_default, mock_sentiment_signals, mock_technical_factors):
    """Empty trades returns zero attribution."""
    empty_trades = pd.DataFrame(columns=['EntryTime', 'ExitTime', 'PnL'])
    
    result = attributor_default.attribute_returns(
        empty_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.total_pnl == 0.0
    assert result.trade_count == 0
    assert result.sentiment_pct == 0.0


def test_valid_inputs_no_error(attributor_default, mock_trades, mock_sentiment_signals, mock_technical_factors):
    """Valid inputs execute without error."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    assert isinstance(result, AttributionResult)


# -------------------- Trade Classification Tests --------------------

def test_classify_trades_sentiment_dominant(attributor_default, mock_technical_factors):
    """Trade classified as sentiment-driven if sentiment > technical."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [500.0]
    })
    
    # High sentiment, low technical
    sentiment = pd.DataFrame({
        'AAPL': [0.8]
    }, index=[pd.Timestamp('2024-01-10')])
    
    technical = pd.DataFrame({
        'RSI': [0.2]
    }, index=[pd.Timestamp('2024-01-10')])
    
    result = attributor_default.attribute_returns(trades, sentiment, technical)
    
    # Sentiment should dominate
    assert result.sentiment_pct > result.technical_pct


def test_classify_trades_technical_dominant(attributor_default, mock_sentiment_signals):
    """Trade classified as technical-driven if technical > sentiment."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [500.0]
    })
    
    # Low sentiment, high technical
    sentiment = pd.DataFrame({
        'AAPL': [0.2]
    }, index=[pd.Timestamp('2024-01-10')])
    
    technical = pd.DataFrame({
        'RSI': [0.9]
    }, index=[pd.Timestamp('2024-01-10')])
    
    result = attributor_default.attribute_returns(trades, sentiment, technical)
    
    # Technical should dominate
    assert result.technical_pct > result.sentiment_pct


def test_classify_trades_overlap(attributor_default):
    """Trade with both signals strong classified as overlap."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [500.0]
    })
    
    # Both signals strong
    sentiment = pd.DataFrame({
        'AAPL': [0.8]
    }, index=[pd.Timestamp('2024-01-10')])
    
    technical = pd.DataFrame({
        'RSI': [0.9]
    }, index=[pd.Timestamp('2024-01-10')])
    
    result = attributor_default.attribute_returns(trades, sentiment, technical)
    
    # Both should have contribution
    assert result.sentiment_pct > 0
    assert result.technical_pct > 0


def test_signal_extraction_exact_match(attributor_default):
    """Signal extracted at exact time match."""
    signals = pd.DataFrame({
        'AAPL': [0.5, 0.6, 0.7]
    }, index=pd.to_datetime(['2024-01-10', '2024-01-11', '2024-01-12']))
    
    value = attributor_default._get_signal_at_time(signals, pd.Timestamp('2024-01-11'))
    assert abs(value - 0.6) < 1e-6


def test_signal_extraction_asof(attributor_default):
    """Signal extracted using asof (nearest backward)."""
    signals = pd.DataFrame({
        'AAPL': [0.5, 0.7]
    }, index=pd.to_datetime(['2024-01-10', '2024-01-12']))
    
    # Request 2024-01-11 → should use 2024-01-10 (asof)
    value = attributor_default._get_signal_at_time(signals, pd.Timestamp('2024-01-11'))
    assert abs(value - 0.5) < 1e-6


def test_signal_extraction_missing_returns_zero(attributor_default):
    """Signal extraction returns 0.0 if date missing."""
    signals = pd.DataFrame({
        'AAPL': [0.5]
    }, index=pd.to_datetime(['2024-01-10']))
    
    # Request date before signals start
    value = attributor_default._get_signal_at_time(signals, pd.Timestamp('2024-01-01'))
    assert value == 0.0


# -------------------- Attribution Calculation Tests --------------------

def test_attribution_total_pnl_correct(attributor_default, mock_trades, mock_sentiment_signals, mock_technical_factors):
    """Total PnL in result matches trades sum."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    expected_pnl = mock_trades['PnL'].sum()
    assert abs(result.total_pnl - expected_pnl) < 1e-6


def test_attribution_percentages_sum_to_100(attributor_default, mock_trades, mock_sentiment_signals, mock_technical_factors):
    """Attribution percentages sum to ~100%."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    total = (result.sentiment_pct + result.technical_pct + 
             result.allocation_pct + result.timing_pct + result.residual_pct)
    
    assert 95.0 < total <= 105.0  # 5% tolerance


def test_attribution_trade_count_correct(attributor_default, mock_trades, mock_sentiment_signals, mock_technical_factors):
    """Trade count in result matches input."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.trade_count == len(mock_trades)


def test_attribution_method_recorded(attributor_default, mock_trades, mock_sentiment_signals, mock_technical_factors):
    """Attribution method recorded in result."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.attribution_method == AttributionMethod.BRINSON.value


def test_attribution_positive_pnl(attributor_default, mock_sentiment_signals, mock_technical_factors):
    """Attribution with only profitable trades."""
    trades = pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17']),
        'PnL': [500.0, 300.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.total_pnl > 0
    assert result.sentiment_pct + result.technical_pct > 50  # Majority attributed


def test_attribution_negative_pnl(attributor_default, mock_sentiment_signals, mock_technical_factors):
    """Attribution with losing trades."""
    trades = pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17']),
        'PnL': [-200.0, -150.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.total_pnl < 0
    # Percentages still sum to 100% (negative contributions)


def test_attribution_mixed_pnl(attributor_default, mock_trades, mock_sentiment_signals, mock_technical_factors):
    """Attribution with mixed profitable/losing trades."""
    result = attributor_default.attribute_returns(
        mock_trades, mock_sentiment_signals, mock_technical_factors
    )
    
    # mock_trades has +500, -200, +800 = +1100 total
    assert result.total_pnl > 0
    assert result.trade_count == 3


# -------------------- Edge Cases Tests --------------------

def test_attribution_zero_total_pnl(attributor_default, mock_sentiment_signals, mock_technical_factors):
    """Attribution with zero total PnL (breakeven)."""
    trades = pd.DataFrame({
        'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15']),
        'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17']),
        'PnL': [100.0, -100.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert abs(result.total_pnl) < 1e-6
    # Should return equal attribution fallback
    assert result.sentiment_pct == 25.0
    assert result.technical_pct == 25.0


def test_attribution_single_trade(attributor_default, mock_sentiment_signals, mock_technical_factors):
    """Attribution with single trade."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-01-10')],
        'ExitTime': [pd.Timestamp('2024-01-12')],
        'PnL': [500.0]
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.trade_count == 1
    assert abs(result.total_pnl - 500.0) < 1e-6


def test_attribution_many_trades(attributor_default, mock_sentiment_signals, mock_technical_factors):
    """Attribution with 50+ trades."""
    n_trades = 50
    trades = pd.DataFrame({
        'EntryTime': pd.date_range('2024-01-01', periods=n_trades, freq='D'),
        'ExitTime': pd.date_range('2024-01-03', periods=n_trades, freq='D'),
        'PnL': np.random.uniform(-100, 200, n_trades)
    })
    
    result = attributor_default.attribute_returns(
        trades, mock_sentiment_signals, mock_technical_factors
    )
    
    assert result.trade_count == n_trades
    assert 95 < (result.sentiment_pct + result.technical_pct + 
                 result.allocation_pct + result.timing_pct + 
                 result.residual_pct) <= 105


def test_attribution_no_signal_overlap(attributor_default, mock_technical_factors):
    """Attribution when signals don't overlap (dates misaligned)."""
    trades = pd.DataFrame({
        'EntryTime': [pd.Timestamp('2024-02-01')],  # Outside sentiment dates
        'ExitTime': [pd.Timestamp('2024-02-03')],
        'PnL': [500.0]
    })
    
    sentiment = pd.DataFrame({
        'AAPL': [0.5]
    }, index=[pd.Timestamp('2024-01-01')])  # Jan dates
    
    result = attributor_default.attribute_returns(
        trades, sentiment, mock_technical_factors
    )
    
    # Should still return valid attribution (fallback to technical)
    assert result.total_pnl == 500.0
```

### **Checklist tests**

- [ ] 25 tests minimum
- [ ] Coverage init (3), validation (5), classification (6), calculation (7), edge (4)
- [ ] Fixtures robustes (mock trades/signals/factors)
- [ ] Tests types/validation stricte
- [ ] Tests edge cases (zero PnL, single trade, many trades)
- [ ] Assertions robustes (tolerances, sum=100%)
- [ ] Docstrings sur chaque test

---

## 📊 CRITÈRES QUALITÉ

| Critère | Target | Notes |
|---------|--------|-------|
| LOC | 350 | Docstrings incluses |
| Tests | 25 | 3+5+6+7+4 |
| Coverage | 90%+ | pytest-cov |
| Type hints | 100% | mypy |
| Docstrings | 100% | Google style |
| Audit refs | Chaque méthode | ML4T, Riskfolio |
| Dataclass | ✅ | AttributionResult |
| Enum | ✅ | AttributionMethod |

---

## ✅ CHECKLIST PRÉ-LANCEMENT

- [ ] Audits lus (ML4T, Riskfolio, Backtesting)
- [ ] Dataclass + Enum compris
- [ ] Structure attribution Brinson claire
- [ ] Prêt à coder

---

## 🚀 ACTION COPILOT

**Phase 1** : Génère `performance_attribution.py` complet (350 LOC)
**Phase 2** : Génère `test_performance_attribution.py` (25 tests)

**Qualité > Vitesse** 🎯
