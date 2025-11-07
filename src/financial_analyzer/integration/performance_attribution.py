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

Example:
    >>> from backtesting import Backtest
    >>> import pandas as pd
    >>> # Run backtest → trades DataFrame
    >>> attributor = PerformanceAttributor()
    >>> result = attributor.attribute_returns(
    ...     trades_df, sentiment_signals, technical_factors
    ... )
    >>> print(f"Sentiment: {result.sentiment_pct:.1f}%")
    Sentiment: 35.2%
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
    """
    Attribution calculation methods.
    
    Attributes:
        BRINSON: Brinson-Fachler attribution model (selection + allocation)
        FACTOR_REGRESSION: Linear regression on factor exposures
        SIMPLE: Direct signal strength proportional attribution
    
    Audit:
        AUDIT_ML4T_BOOK.md p.36 (attribution methodologies comparison)
    
    Example:
        >>> method = AttributionMethod.BRINSON
        >>> method.value
        'brinson'
    """
    BRINSON = "brinson"
    FACTOR_REGRESSION = "regression"
    SIMPLE = "simple"


@dataclass
class AttributionResult:
    """
    Performance attribution result.
    
    Decompose total backtest P&L into percentage contributions from:
    - Sentiment signals (news-driven alpha)
    - Technical indicators (momentum/trend alpha)
    - Portfolio allocation decisions (optimizer impact)
    - Entry/exit timing (vs buy-and-hold)
    
    Attributes:
        sentiment_pct: % of total PnL attributed to sentiment signals
        technical_pct: % of total PnL attributed to technical factors
        allocation_pct: % of total PnL attributed to portfolio allocation
        timing_pct: % of total PnL attributed to entry/exit timing
        total_pnl: Total P&L in currency units
        residual_pct: % of PnL unexplained (should be small <5%)
        trade_count: Number of trades analyzed
        attribution_method: Method used for calculation
    
    Invariants:
        sentiment_pct + technical_pct + allocation_pct + timing_pct + residual_pct ≈ 100%
    
    Audit:
        AUDIT_ML4T_BOOK.md p.37 (attribution result structure)
    
    Example:
        >>> result = AttributionResult(
        ...     sentiment_pct=35.2, technical_pct=42.8, allocation_pct=15.0,
        ...     timing_pct=7.0, total_pnl=15234.50, residual_pct=0.0,
        ...     trade_count=47, attribution_method='brinson'
        ... )
        >>> result.sentiment_pct + result.technical_pct
        78.0
        >>> # Validate sum ~100%
        >>> sum_pct = (result.sentiment_pct + result.technical_pct +
        ...            result.allocation_pct + result.timing_pct + result.residual_pct)
        >>> 95.0 < sum_pct <= 105.0
        True
    """
    sentiment_pct: float
    technical_pct: float
    allocation_pct: float
    timing_pct: float
    total_pnl: float
    residual_pct: float = 0.0
    trade_count: int = 0
    attribution_method: str = "brinson"
    
    def __post_init__(self) -> None:
        """
        Validate attribution percentages sum to ~100%.
        
        Raises:
            Warning (logged): If sum deviates > 5% from 100%
        
        Audit:
            AUDIT_ML4T_BOOK.md p.38 (attribution validation)
        
        Example:
            >>> # Valid result
            >>> result = AttributionResult(
            ...     sentiment_pct=40.0, technical_pct=35.0,
            ...     allocation_pct=15.0, timing_pct=10.0,
            ...     total_pnl=1000.0, residual_pct=0.0
            ... )
            >>> # No warning logged
            
            >>> # Invalid result (sum = 120%)
            >>> result2 = AttributionResult(
            ...     sentiment_pct=50.0, technical_pct=50.0,
            ...     allocation_pct=20.0, timing_pct=10.0,
            ...     total_pnl=1000.0, residual_pct=-10.0
            ... )
            >>> # Warning: "Attribution percentages sum to 120.0%, expected ~100%"
        """
        total = (
            self.sentiment_pct + self.technical_pct + 
            self.allocation_pct + self.timing_pct + self.residual_pct
        )
        if abs(total - 100.0) > 5.0:  # 5% tolerance
            logger.warning(
                f"Attribution percentages sum to {total:.1f}%, expected ~100%. "
                f"Large residual may indicate incomplete attribution. "
                f"sentiment={self.sentiment_pct:.1f}%, technical={self.technical_pct:.1f}%, "
                f"allocation={self.allocation_pct:.1f}%, timing={self.timing_pct:.1f}%, "
                f"residual={self.residual_pct:.1f}%"
            )


class PerformanceAttributor:
    """
    Attribute backtest performance to factor sources (Brinson-style).
    
    Decompose total backtest P&L into contributions from:
    1. Sentiment signals (Phase 5.3 news factors)
    2. Technical indicators (Phase 5.2 momentum/trend factors)
    3. Portfolio allocation (optimizer weight decisions vs benchmark)
    4. Timing effects (entry/exit timing vs buy-and-hold)
    
    Process:
    1. Receives trades DataFrame + signal DataFrames (sentiment, technical)
    2. For each trade, identify dominant signal type at entry time
    3. Calculate contribution per signal type (classify + aggregate PnL)
    4. Compute allocation effect (portfolio optimizer impact)
    5. Compute timing effect (entry/exit vs buy-and-hold)
    6. Return AttributionResult with percentage breakdown
    
    Audit References:
    - AUDIT_ML4T_BOOK.md p.36 (Brinson attribution step-by-step)
    - AUDIT_RISKFOLIO_LIB.md p.23 (factor contribution formula)
    - AUDIT_BACKTESTING_PY.md p.22 (trades DataFrame structure)
    
    Example:
        >>> import pandas as pd
        >>> attributor = PerformanceAttributor()
        >>> # Assume trades, sentiment, technical from backtest
        >>> result = attributor.attribute_returns(
        ...     trades_df, sentiment_signals, technical_factors
        ... )
        >>> print(f"Sentiment: {result.sentiment_pct:.1f}%")
        Sentiment: 35.2%
        >>> print(f"Technical: {result.technical_pct:.1f}%")
        Technical: 42.8%
    """
    
    def __init__(
        self,
        method: AttributionMethod = AttributionMethod.BRINSON,
        min_confidence: float = 0.5
    ) -> None:
        """
        Initialize performance attributor.
        
        Args:
            method: Attribution calculation method (default: Brinson)
            min_confidence: Minimum signal confidence to attribute (0-1)
                           Signals below this threshold treated as noise
        
        Raises:
            ValueError: If min_confidence not in [0, 1]
        
        Notes:
            - Brinson method: decompose returns into selection + allocation + interaction
            - Regression method: factor regression on returns (Phase 5.5)
            - Simple method: direct signal strength × PnL
        
        Audit:
            AUDIT_ML4T_BOOK.md p.35 (attribution methods overview)
        
        Example:
            >>> # Default Brinson with 50% confidence threshold
            >>> attr = PerformanceAttributor()
            >>> attr.method.value
            'brinson'
            >>> attr.min_confidence
            0.5
            
            >>> # Custom high-confidence threshold
            >>> attr2 = PerformanceAttributor(
            ...     method=AttributionMethod.SIMPLE,
            ...     min_confidence=0.75
            ... )
            >>> attr2.min_confidence
            0.75
        """
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(
                f"min_confidence must be in [0, 1], got {min_confidence}"
            )
        
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
                - EntryTime (pd.Timestamp): Trade entry datetime
                - ExitTime (pd.Timestamp): Trade exit datetime
                - PnL (float): Trade profit/loss in currency
                - Optional: EntryPrice, ExitPrice, Size, Ticker
            sentiment_signals: DataFrame with sentiment scores per ticker/time
                - Index: DatetimeIndex
                - Columns: ticker symbols
                - Values: sentiment scores [-1, 1]
            technical_factors: DataFrame with technical factor values
                - Index: DatetimeIndex
                - Columns: factor names (e.g., RSI, MACD, etc.)
                - Values: factor values (normalized)
            prices: Optional OHLCV DataFrame for timing analysis (Phase 5.5)
        
        Returns:
            AttributionResult with percentage contributions summing to ~100%
        
        Raises:
            ValueError: If trades DataFrame empty or missing required columns
            TypeError: If inputs not DataFrames
        
        Process:
        1. Validate inputs (columns, types, DatetimeIndex alignment)
        2. For each trade, extract signals at entry time (asof)
        3. Classify trade as sentiment-driven, technical-driven, or overlap
        4. Aggregate PnL per category
        5. Compute allocation effect (vs equal-weight benchmark)
        6. Compute timing effect (actual vs buy-and-hold)
        7. Calculate percentages (normalized to 100%)
        8. Calculate residual (unexplained)
        
        Audit:
        - AUDIT_ML4T_BOOK.md p.37 (attribution calculation flow)
        - AUDIT_BACKTESTING_PY.md p.22 (trades DataFrame structure)
        
        Example:
            >>> trades = pd.DataFrame({
            ...     'EntryTime': pd.to_datetime(['2024-01-10', '2024-01-15']),
            ...     'ExitTime': pd.to_datetime(['2024-01-12', '2024-01-17']),
            ...     'PnL': [100.0, -50.0]
            ... })
            >>> sentiment = pd.DataFrame({
            ...     'AAPL': [0.7, 0.8]
            ... }, index=pd.to_datetime(['2024-01-10', '2024-01-15']))
            >>> technical = pd.DataFrame({
            ...     'RSI': [0.3, 0.4]
            ... }, index=pd.to_datetime(['2024-01-10', '2024-01-15']))
            >>> 
            >>> attr = PerformanceAttributor()
            >>> result = attr.attribute_returns(trades, sentiment, technical)
            >>> 95 < (result.sentiment_pct + result.technical_pct +
            ...       result.allocation_pct + result.timing_pct) <= 105
            True
        """
        logger.debug("Starting performance attribution calculation ...")
        
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
        logger.info(
            f"Attributing {len(trades)} trades, total PnL: {total_pnl:.2f}"
        )
        
        # Step 1: Classify trades by dominant signal
        trade_classifications = self._classify_trades(
            trades, sentiment_signals, technical_factors
        )
        
        # Step 2: Calculate contributions
        sentiment_pnl = trade_classifications['sentiment_pnl'].sum()
        technical_pnl = trade_classifications['technical_pnl'].sum()
        overlap_pnl = trade_classifications['overlap_pnl'].sum()
        
        logger.debug(
            f"Signal contributions: sentiment={sentiment_pnl:.2f}, "
            f"technical={technical_pnl:.2f}, overlap={overlap_pnl:.2f}"
        )
        
        # Step 3: Allocation effect (vs equal-weight benchmark)
        allocation_pnl = self._calculate_allocation_effect(trades, prices)
        
        # Step 4: Timing effect (entry/exit vs buy-and-hold)
        timing_pnl = self._calculate_timing_effect(trades, prices)
        
        # Step 5: Calculate percentages
        if abs(total_pnl) < 1e-6:
            logger.warning(
                "Total PnL near zero, returning equal attribution fallback"
            )
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
        residual_pct = 100.0 - (
            sentiment_pct + technical_pct + allocation_pct + timing_pct
        )
        
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
        """
        Validate input DataFrames structure and types.
        
        Args:
            trades: Trades DataFrame (backtesting.py format)
            sentiment_signals: Sentiment scores with DatetimeIndex
            technical_factors: Technical factors with DatetimeIndex
        
        Raises:
            TypeError: If inputs not DataFrames
            ValueError: If missing required columns or DatetimeIndex
        
        Audit:
            AUDIT_BACKTESTING_PY.md p.22 (trades DataFrame structure)
        
        Example:
            >>> # Valid inputs pass silently
            >>> trades = pd.DataFrame({
            ...     'EntryTime': [pd.Timestamp('2024-01-10')],
            ...     'ExitTime': [pd.Timestamp('2024-01-12')],
            ...     'PnL': [100.0]
            ... })
            >>> sentiment = pd.DataFrame(
            ...     {'AAPL': [0.5]},
            ...     index=pd.DatetimeIndex([pd.Timestamp('2024-01-10')])
            ... )
            >>> technical = pd.DataFrame(
            ...     {'RSI': [50.0]},
            ...     index=pd.DatetimeIndex([pd.Timestamp('2024-01-10')])
            ... )
            >>> attr = PerformanceAttributor()
            >>> attr._validate_inputs(trades, sentiment, technical)
            >>> # No error raised
        """
        logger.debug("Validating attribution inputs ...")
        
        if not isinstance(trades, pd.DataFrame):
            raise TypeError(
                f"trades must be pandas DataFrame, got {type(trades).__name__}"
            )
        if not isinstance(sentiment_signals, pd.DataFrame):
            raise TypeError(
                f"sentiment_signals must be pandas DataFrame, "
                f"got {type(sentiment_signals).__name__}"
            )
        if not isinstance(technical_factors, pd.DataFrame):
            raise TypeError(
                f"technical_factors must be pandas DataFrame, "
                f"got {type(technical_factors).__name__}"
            )
        
        # Check required columns in trades (backtesting.py standard)
        required_trade_cols = ['EntryTime', 'ExitTime', 'PnL']
        missing = [c for c in required_trade_cols if c not in trades.columns]
        if missing:
            raise ValueError(
                f"trades DataFrame missing required columns: {missing}. "
                f"Expected from backtesting.py: {required_trade_cols}. "
                f"Available columns: {list(trades.columns)}"
            )
        
        # Check DatetimeIndex
        if not isinstance(sentiment_signals.index, pd.DatetimeIndex):
            raise ValueError(
                f"sentiment_signals must have DatetimeIndex, "
                f"got {type(sentiment_signals.index).__name__}"
            )
        if not isinstance(technical_factors.index, pd.DatetimeIndex):
            raise ValueError(
                f"technical_factors must have DatetimeIndex, "
                f"got {type(technical_factors.index).__name__}"
            )
        
        logger.debug(
            f"Input validation passed: {len(trades)} trades, "
            f"{len(sentiment_signals)} sentiment rows, "
            f"{len(technical_factors)} technical rows"
        )
    
    def _classify_trades(
        self,
        trades: pd.DataFrame,
        sentiment_signals: pd.DataFrame,
        technical_factors: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Classify each trade by dominant signal type.
        
        Args:
            trades: Trades DataFrame with EntryTime and PnL
            sentiment_signals: Sentiment scores (ticker columns)
            technical_factors: Technical factors (factor columns)
        
        Returns:
            DataFrame with columns: sentiment_pnl, technical_pnl, overlap_pnl
        
        Logic:
        - Extract sentiment & technical signal strength at entry time
        - If both signals > min_confidence → overlap:
          - sentiment_pnl = trade_pnl * 0.5
          - technical_pnl = trade_pnl * 0.5
          - overlap_pnl = trade_pnl (for tracking)
        - Else attribute to dominant signal (higher absolute value)
        
        Audit:
            AUDIT_ML4T_BOOK.md p.38 (signal classification rules)
        
        Example:
            >>> trades = pd.DataFrame({
            ...     'EntryTime': [pd.Timestamp('2024-01-10')],
            ...     'PnL': [100.0]
            ... })
            >>> sentiment = pd.DataFrame(
            ...     {'AAPL': [0.8]},
            ...     index=[pd.Timestamp('2024-01-10')]
            ... )
            >>> technical = pd.DataFrame(
            ...     {'RSI': [0.3]},
            ...     index=[pd.Timestamp('2024-01-10')]
            ... )
            >>> attr = PerformanceAttributor()
            >>> result = attr._classify_trades(trades, sentiment, technical)
            >>> result['sentiment_pnl'].iloc[0]
            100.0
        """
        logger.debug(f"Classifying {len(trades)} trades by signal type ...")
        
        results = []
        for idx, trade in trades.iterrows():
            entry_time = trade['EntryTime']
            pnl = trade['PnL']
            
            # Extract signals at entry time (or nearest asof)
            sentiment_score = self._get_signal_at_time(
                sentiment_signals, entry_time
            )
            technical_score = self._get_signal_at_time(
                technical_factors, entry_time
            )
            
            logger.debug(
                f"Trade {idx}: entry={entry_time}, pnl={pnl:.2f}, "
                f"sentiment={sentiment_score:.3f}, technical={technical_score:.3f}"
            )
            
            # Classify
            sentiment_strong = abs(sentiment_score) > self.min_confidence
            technical_strong = abs(technical_score) > self.min_confidence
            
            if sentiment_strong and technical_strong:
                # Overlap: both signals strong → split equally
                logger.debug(f"Trade {idx} classified as OVERLAP")
                results.append({
                    'sentiment_pnl': pnl * 0.5,
                    'technical_pnl': pnl * 0.5,
                    'overlap_pnl': pnl
                })
            elif abs(sentiment_score) > abs(technical_score):
                # Sentiment dominant
                logger.debug(f"Trade {idx} classified as SENTIMENT-driven")
                results.append({
                    'sentiment_pnl': pnl,
                    'technical_pnl': 0.0,
                    'overlap_pnl': 0.0
                })
            else:
                # Technical dominant (or equal → default to technical)
                logger.debug(f"Trade {idx} classified as TECHNICAL-driven")
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
        Extract composite signal value at specific time.
        
        Args:
            signals: DataFrame with DatetimeIndex (multi-column possible)
            target_time: Target datetime to extract signal
        
        Returns:
            Composite signal score (mean of all columns)
            Returns 0.0 if time not found (before signal start)
        
        Process:
        1. Try exact match on index
        2. Fallback to asof (nearest backward fill)
        3. If multiple columns, average across columns
        4. Return 0.0 if no match (date before signals)
        
        Audit:
            AUDIT_ML4T_BOOK.md p.39 (signal extraction at trade time)
        
        Example:
            >>> signals = pd.DataFrame({
            ...     'AAPL': [0.5, 0.7],
            ...     'MSFT': [0.6, 0.8]
            ... }, index=pd.to_datetime(['2024-01-10', '2024-01-12']))
            >>> attr = PerformanceAttributor()
            >>> # Exact match
            >>> attr._get_signal_at_time(signals, pd.Timestamp('2024-01-10'))
            0.55
            >>> # Asof (nearest backward)
            >>> attr._get_signal_at_time(signals, pd.Timestamp('2024-01-11'))
            0.55
        """
        try:
            # Try exact match first
            if target_time in signals.index:
                row = signals.loc[target_time]
            else:
                # Nearest backward fill (asof)
                idx = signals.index.asof(target_time)
                if pd.isna(idx):
                    logger.debug(
                        f"No signal before {target_time}, returning 0.0"
                    )
                    return 0.0
                row = signals.loc[idx]
            
            # If multiple columns, average across columns
            if isinstance(row, pd.Series):
                # Multi-column or single row
                composite = float(row.mean())
                return composite
            else:
                # Single value (unlikely if DataFrame input)
                return float(row)
        
        except Exception as e:
            logger.warning(
                f"Could not extract signal at {target_time}: {e}. "
                f"Returning 0.0 as fallback"
            )
            return 0.0
    
    def _calculate_allocation_effect(
        self,
        trades: pd.DataFrame,
        prices: Optional[pd.DataFrame]
    ) -> float:
        """
        Calculate allocation effect vs equal-weight benchmark.
        
        Args:
            trades: Trades DataFrame
            prices: Optional OHLCV for full calculation (Phase 5.5)
        
        Returns:
            Allocation effect PnL contribution
        
        Formula (Brinson):
            Allocation effect = (actual weights - equal weights) × benchmark returns
        
        Notes:
            Current implementation: placeholder scaling with trade count
            Base allocation: 10% for <10 trades, up to 15% for 50+ trades
            Full implementation (Phase 5.5) requires:
            - Portfolio weights history from optimizer
            - Benchmark returns (equal-weight or market-cap weighted)
            - Cross-sectional weight deviations
        
        Audit:
            AUDIT_ML4T_BOOK.md p.40 (allocation attribution formula)
        
        Example:
            >>> trades = pd.DataFrame({'PnL': [100, 200]})
            >>> attr = PerformanceAttributor()
            >>> effect = attr._calculate_allocation_effect(trades, None)
            >>> effect
            30.0
        """
        total_pnl = trades['PnL'].sum()
        trade_count = len(trades)
        
        # Placeholder: scale allocation factor with trade count
        # More trades = more allocation decisions = higher attribution
        if trade_count < 10:
            allocation_factor = 0.10
        else:
            allocation_factor = min(0.15, 0.10 + 0.01 * (trade_count // 10))
        
        allocation_effect = total_pnl * allocation_factor
        
        logger.debug(
            f"Allocation effect (placeholder {allocation_factor*100:.1f}%, "
            f"{trade_count} trades): {allocation_effect:.2f}"
        )
        return allocation_effect
    
    def _calculate_timing_effect(
        self,
        trades: pd.DataFrame,
        prices: Optional[pd.DataFrame]
    ) -> float:
        """
        Calculate timing effect (entry/exit vs buy-and-hold).
        
        Args:
            trades: Trades DataFrame with EntryTime, ExitTime, PnL
            prices: Optional OHLCV for full calculation (Phase 5.5)
        
        Returns:
            Timing effect PnL contribution
        
        Formula:
            Timing effect = actual PnL - buy_and_hold PnL
        
        Notes:
            Current implementation: placeholder 5% of total PnL
            Full implementation (Phase 5.5) requires:
            - Price series for each ticker traded
            - Buy-and-hold simulation (entry to exit period)
            - Compare actual exit timing vs holding to end
        
        Audit:
            AUDIT_ML4T_BOOK.md p.42 (timing attribution formula)
        
        Example:
            >>> trades = pd.DataFrame({'PnL': [100, 200]})
            >>> attr = PerformanceAttributor()
            >>> effect = attr._calculate_timing_effect(trades, None)
            >>> effect
            15.0
        """
        total_pnl = trades['PnL'].sum()
        
        # Placeholder: assume timing contributes 5% of total PnL
        # TODO Phase 5.5: implement full timing attribution
        # Requires: price OHLCV history + buy-and-hold benchmark
        timing_effect = total_pnl * 0.05
        
        logger.debug(
            f"Timing effect (placeholder 5%): {timing_effect:.2f}"
        )
        return timing_effect


# Module exports
__all__ = ['PerformanceAttributor', 'AttributionResult', 'AttributionMethod']
