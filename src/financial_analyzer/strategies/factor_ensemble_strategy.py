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
from typing import Optional, Dict, List
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

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
        ic_lookback: Number of periods for IC calculation (default 20)
        long_threshold: Composite score threshold for long entry (default 1.0)
        short_threshold: Composite score threshold for short entry (default -1.0)
        min_factor_agreement: Minimum % factors agreeing on direction (default 0.6)
        max_volatility: Maximum volatility threshold for entry (default 0.03)
        volatility_window: Rolling window for volatility calculation (default 20)
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
    ic_lookback: int = 20
    long_threshold: float = 1.0
    short_threshold: float = -1.0
    min_factor_agreement: float = 0.6
    max_volatility: float = 0.03
    volatility_window: int = 20
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
            # Extract mean IC per factor (use mean of last ic_lookback values)
            ic_values = {}
            for ic_col in ic_cols:
                factor_name = ic_col.replace('_ic', '')
                if factor_name in factor_cols:
                    # Take mean of last ic_lookback values (or all if less)
                    recent_ic = self.data.df[ic_col].iloc[-self.ic_lookback:].mean()
                    ic_values[factor_name] = recent_ic
            
            # Sort factors by absolute IC value
            sorted_factors = sorted(ic_values.items(), key=lambda x: abs(x[1]), reverse=True)
            selected_factors = [f for f, ic in sorted_factors[:self.top_k_factors] if abs(ic) >= self.ic_threshold]
            
            # Store IC values for weighting
            self.ic_values = {f: ic for f, ic in sorted_factors if f in selected_factors}
        else:
            # No IC available: use first top_k_factors
            logger.warning("No IC columns found, using first top_k_factors")
            selected_factors = factor_cols[:self.top_k_factors]
            self.ic_values = {f: 0.1 for f in selected_factors}  # Equal weights
        
        if not selected_factors:
            raise ValueError(
                f"No factors meet IC threshold {self.ic_threshold}. "
                f"Available factors: {factor_cols[:5]}... with ICs: {list(ic_values.values())[:5] if ic_cols else 'N/A'}"
            )
        
        self.selected_factors = selected_factors
        logger.info(f"Selected {len(self.selected_factors)} factors: {self.selected_factors[:5]}...")
        
        # Create Z-score normalized indicators
        self.factor_zscores = {}
        for factor in self.selected_factors:
            # Z-score normalization via self.I()
            self.factor_zscores[factor] = self.I(
                self._zscore_normalize,
                self.data.df[factor].values,
                name=f"zscore_{factor}"
            )
        
        # Compute composite score (IC-weighted if available)
        if ic_cols:
            # IC-weighted composite
            self.composite_score = self.I(
                self._compute_composite_ic_weighted,
                name="composite_score"
            )
        else:
            # Equal-weighted composite
            self.composite_score = self.I(
                self._compute_composite_equal_weighted,
                name="composite_score"
            )
        
        # Volatility indicator (20-day rolling)
        self.volatility = self.I(
            self._compute_volatility,
            self.data.Close,
            name="volatility"
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
            
            # Exit condition 2: Stop loss / Take profit
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
    
    def _zscore_normalize(self, series: np.ndarray) -> np.ndarray:
        """
        Compute Z-score normalization.
        
        Args:
            series: Input factor values
        
        Returns:
            Z-score normalized values (mean=0, std=1)
        
        Audit:
            AUDIT_ML4T_BOOK.md p.51 (factor normalization)
        """
        mean = np.mean(series)
        std = np.std(series)
        if std < 1e-9:
            return np.zeros_like(series)
        return (series - mean) / std
    
    def _compute_composite_ic_weighted(self) -> np.ndarray:
        """
        Compute IC-weighted composite score.
        
        Returns:
            IC-weighted average of Z-score factors
        
        Audit:
            AUDIT_ML4T_BOOK.md p.50 (IC-weighted composites)
        """
        weights = np.array([abs(self.ic_values.get(f, 0.05)) for f in self.selected_factors])
        weights = weights / weights.sum()  # Normalize to sum=1
        
        # Get current length from first factor
        n = len(self.factor_zscores[self.selected_factors[0]])
        composite = np.zeros(n)
        
        for i, factor in enumerate(self.selected_factors):
            composite += weights[i] * self.factor_zscores[factor]
        
        return composite
    
    def _compute_composite_equal_weighted(self) -> np.ndarray:
        """
        Compute equal-weighted composite score.
        
        Returns:
            Arithmetic mean of Z-score factors
        
        Audit:
            AUDIT_ML4T_BOOK.md p.50 (equal-weighted baseline)
        """
        n = len(self.factor_zscores[self.selected_factors[0]])
        composite = np.zeros(n)
        
        for factor in self.selected_factors:
            composite += self.factor_zscores[factor]
        
        return composite / len(self.selected_factors)
    
    def _compute_volatility(self, close: pd.Series) -> np.ndarray:
        """
        Compute rolling volatility.
        
        Args:
            close: Close price series
        
        Returns:
            Rolling standard deviation of returns (window = volatility_window)
        
        Audit:
            AUDIT_ML4T_BOOK.md p.55 (volatility filters)
        """
        # Convert to numpy if needed
        if isinstance(close, pd.Series):
            close_values = close.values
        else:
            close_values = np.asarray(close)
        
        # Compute returns manually
        returns = np.diff(close_values) / close_values[:-1]
        returns = np.concatenate([[0], returns])  # Prepend 0 for alignment
        
        # Compute rolling volatility
        window = self.volatility_window
        volatility = np.zeros(len(returns))
        for i in range(window, len(returns)):
            volatility[i] = np.std(returns[i-window:i])
        
        return volatility
    
    def _calculate_factor_agreement(self) -> float:
        """
        Calculate % of factors agreeing on signal direction.
        
        Returns:
            Fraction [0, 1] of factors with same sign as composite
        
        Audit:
            AUDIT_FINANCE_PARTIE_5_ML.md p.15 (factor agreement)
        
        Example:
            >>> # If composite=1.5 (positive), count factors with positive Z-score
            >>> agreement = 8/10 = 0.8  # 80% factors agree
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
