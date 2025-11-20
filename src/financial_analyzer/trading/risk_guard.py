"""
Risk Guard - Pre-trade risk validation and circuit breakers.

Features:
- Position size limits (per position, total)
- Concentration limits (max weight per position)
- Drawdown circuit breakers
- Daily loss limits
- Order validation (qty, symbol, side)
- Exposure limits (gross, net, leverage)

Integrates with AccountMonitor and BrokerAdapter.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Literal
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

from .broker_adapter import BrokerAdapter
from .account_monitor import AccountMonitor


class RiskLimitExceeded(Exception):
    """Raised when risk limit is exceeded."""
    pass


class CircuitBreakerTriggered(Exception):
    """Raised when circuit breaker is triggered."""
    pass


class InvalidOrderError(Exception):
    """Raised when order validation fails."""
    pass


class RiskGuard:
    """
    Pre-trade risk validation and circuit breakers.
    
    Validates all orders before submission to prevent excessive risk taking.
    Implements position limits, concentration limits, drawdown circuit breakers,
    and daily loss limits.
    
    Attributes:
        account_monitor: AccountMonitor instance for portfolio state
        broker: BrokerAdapter instance (optional, from account_monitor if not provided)
        max_position_size: Maximum position size (USD)
        max_position_pct: Maximum position weight (0-1)
        max_total_positions: Maximum number of positions
        max_drawdown: Maximum allowed drawdown (negative, e.g., -0.10 = 10%)
        max_daily_loss: Maximum daily loss (USD, positive)
        max_leverage: Maximum leverage ratio
        circuit_breaker_active: Whether circuit breaker is currently active
    
    Example:
        >>> monitor = AccountMonitor(adapter, initial_capital=100000)
        >>> guard = RiskGuard(
        ...     account_monitor=monitor,
        ...     max_position_size=20000,
        ...     max_position_pct=0.20,
        ...     max_drawdown=-0.10
        ... )
        >>> guard.validate_order('AAPL', qty=100, side='buy', price=150.0)
        >>> # Raises RiskLimitExceeded if limits exceeded
    """
    
    def __init__(
        self,
        account_monitor: AccountMonitor,
        broker_adapter: Optional[BrokerAdapter] = None,
        max_position_size: float = 50000.0,
        max_position_pct: float = 0.25,
        max_total_positions: int = 20,
        max_drawdown: float = -0.15,
        max_daily_loss: float = 5000.0,
        max_leverage: float = 2.0,
        enable_circuit_breaker: bool = True
    ) -> None:
        """
        Initialize risk guard.
        
        Args:
            account_monitor: AccountMonitor instance
            broker_adapter: BrokerAdapter instance (optional, uses monitor.broker if None)
            max_position_size: Max position size in USD (default: 50,000)
            max_position_pct: Max position weight 0-1 (default: 0.25 = 25%)
            max_total_positions: Max number of positions (default: 20)
            max_drawdown: Max drawdown, negative (default: -0.15 = 15%)
            max_daily_loss: Max daily loss in USD (default: 5,000)
            max_leverage: Max leverage ratio (default: 2.0x)
            enable_circuit_breaker: Enable circuit breaker (default: True)
        
        Example:
            >>> guard = RiskGuard(
            ...     account_monitor=monitor,
            ...     max_position_size=20000,
            ...     max_drawdown=-0.10,
            ...     max_daily_loss=2000
            ... )
        """
        self.account_monitor = account_monitor
        self.broker = broker_adapter or account_monitor.broker
        
        # Risk limits
        self.max_position_size = max_position_size
        self.max_position_pct = max_position_pct
        self.max_total_positions = max_total_positions
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        self.max_leverage = max_leverage
        
        # Circuit breaker
        self.enable_circuit_breaker = enable_circuit_breaker
        self.circuit_breaker_active = False
        self.circuit_breaker_triggered_at: Optional[datetime] = None
        self.circuit_breaker_reason: Optional[str] = None
        
        logger.info(
            f"RiskGuard initialized: "
            f"max_position=${max_position_size:,.0f}, "
            f"max_dd={max_drawdown:.1%}, "
            f"max_daily_loss=${max_daily_loss:,.0f}"
        )
    
    def validate_order(
        self,
        symbol: str,
        qty: int,
        side: Literal['buy', 'sell'],
        price: Optional[float] = None
    ) -> None:
        """
        Validate order before submission.
        
        Checks:
        - Circuit breaker status
        - Order parameters (symbol, qty, side)
        - Position size limits
        - Concentration limits
        - Total position limits
        - Leverage limits
        - Drawdown limits
        - Daily loss limits
        
        Args:
            symbol: Ticker symbol
            qty: Order quantity (positive integer)
            side: 'buy' or 'sell'
            price: Expected fill price (optional, for size calculation)
        
        Raises:
            CircuitBreakerTriggered: If circuit breaker is active
            InvalidOrderError: If order parameters invalid
            RiskLimitExceeded: If any risk limit would be exceeded
        
        Example:
            >>> guard.validate_order('AAPL', qty=100, side='buy', price=150.0)
            >>> # If successful, order is safe to submit
        """
        # Check circuit breaker
        if self.circuit_breaker_active:
            raise CircuitBreakerTriggered(
                f"Circuit breaker active since {self.circuit_breaker_triggered_at}: "
                f"{self.circuit_breaker_reason}"
            )
        
        # Validate parameters
        self._validate_order_parameters(symbol, qty, side, price)
        
        # Update account state
        self.account_monitor.update()
        
        # Check risk limits
        self._check_position_size_limit(symbol, qty, side, price)
        self._check_concentration_limit(symbol, qty, side, price)
        self._check_total_positions_limit(symbol, side)
        self._check_leverage_limit(symbol, qty, side, price)
        self._check_drawdown_limit()
        self._check_daily_loss_limit()
        
        logger.debug(f"Order validated: {symbol} {side} {qty} @ ${price}")
    
    def _validate_order_parameters(
        self,
        symbol: str,
        qty: int,
        side: str,
        price: Optional[float]
    ) -> None:
        """Validate order parameters."""
        if not symbol or not isinstance(symbol, str):
            raise InvalidOrderError(f"Invalid symbol: {symbol}")
        
        if not symbol.replace('.', '').replace('-', '').isalnum():
            raise InvalidOrderError(f"Invalid symbol format: {symbol}")
        
        if qty <= 0:
            raise InvalidOrderError(f"Invalid qty: {qty}. Must be positive integer.")
        
        if side not in ['buy', 'sell']:
            raise InvalidOrderError(f"Invalid side: {side}. Must be 'buy' or 'sell'.")
        
        if price is not None and price <= 0:
            raise InvalidOrderError(f"Invalid price: {price}. Must be positive.")
    
    def _check_position_size_limit(
        self,
        symbol: str,
        qty: int,
        side: str,
        price: Optional[float]
    ) -> None:
        """Check if order would exceed position size limit."""
        # Get current position
        current_qty = 0
        for pos in self.account_monitor.positions:
            if pos['symbol'] == symbol:
                current_qty = pos['qty']
                break
        
        # Calculate new position
        if side == 'buy':
            new_qty = current_qty + qty
        else:  # sell
            new_qty = current_qty - qty
        
        # Estimate price if not provided
        if price is None:
            price = self._estimate_current_price(symbol)
        
        # Calculate new position size
        new_position_size = abs(new_qty * price)
        
        if new_position_size > self.max_position_size:
            raise RiskLimitExceeded(
                f"Position size limit exceeded: "
                f"${new_position_size:,.0f} > ${self.max_position_size:,.0f} "
                f"({symbol})"
            )
    
    def _check_concentration_limit(
        self,
        symbol: str,
        qty: int,
        side: str,
        price: Optional[float]
    ) -> None:
        """Check if order would exceed concentration limit."""
        # Get current position
        current_qty = 0
        for pos in self.account_monitor.positions:
            if pos['symbol'] == symbol:
                current_qty = pos['qty']
                break
        
        # Calculate new position
        if side == 'buy':
            new_qty = current_qty + qty
        else:
            new_qty = current_qty - qty
        
        # Estimate price
        if price is None:
            price = self._estimate_current_price(symbol)
        
        # Calculate new position weight
        new_position_value = abs(new_qty * price)
        portfolio_value = self.account_monitor.portfolio_value
        
        if portfolio_value > 0:
            new_weight = new_position_value / portfolio_value
            
            if new_weight > self.max_position_pct:
                raise RiskLimitExceeded(
                    f"Concentration limit exceeded: "
                    f"{new_weight:.1%} > {self.max_position_pct:.1%} "
                    f"({symbol})"
                )
    
    def _check_total_positions_limit(self, symbol: str, side: str) -> None:
        """Check if order would exceed total positions limit."""
        # Count current positions
        current_positions = len(self.account_monitor.positions)
        
        # Check if this is a new position (buying when no current position)
        has_position = any(pos['symbol'] == symbol for pos in self.account_monitor.positions)
        
        if not has_position and side == 'buy':
            if current_positions >= self.max_total_positions:
                raise RiskLimitExceeded(
                    f"Total positions limit exceeded: "
                    f"{current_positions} >= {self.max_total_positions}"
                )
    
    def _check_leverage_limit(
        self,
        symbol: str,
        qty: int,
        side: str,
        price: Optional[float]
    ) -> None:
        """Check if order would exceed leverage limit."""
        # Estimate price
        if price is None:
            price = self._estimate_current_price(symbol)
        
        # Calculate order value
        order_value = qty * price
        
        # Get current exposure
        exposure = self.account_monitor.get_exposure_metrics()
        current_gross = exposure['gross_exposure']
        
        # Calculate new gross exposure
        if side == 'buy':
            new_gross = current_gross + order_value
        else:
            # Selling reduces exposure (unless going short)
            current_qty = 0
            for pos in self.account_monitor.positions:
                if pos['symbol'] == symbol:
                    current_qty = pos['qty']
                    break
            
            if current_qty >= qty:
                new_gross = current_gross - order_value
            else:
                # Going short
                new_gross = current_gross + order_value
        
        # Calculate new leverage
        portfolio_value = self.account_monitor.portfolio_value
        if portfolio_value > 0:
            new_leverage = new_gross / portfolio_value
            
            if new_leverage > self.max_leverage:
                raise RiskLimitExceeded(
                    f"Leverage limit exceeded: "
                    f"{new_leverage:.2f}x > {self.max_leverage:.2f}x"
                )
    
    def _check_drawdown_limit(self) -> None:
        """Check if current drawdown exceeds limit."""
        current_dd = self.account_monitor.current_drawdown
        
        if current_dd < self.max_drawdown:
            self._trigger_circuit_breaker(
                f"Drawdown limit exceeded: {current_dd:.2%} < {self.max_drawdown:.2%}"
            )
    
    def _check_daily_loss_limit(self) -> None:
        """Check if daily loss exceeds limit."""
        daily_pnl = self.account_monitor.daily_pnl
        
        if daily_pnl < -self.max_daily_loss:
            self._trigger_circuit_breaker(
                f"Daily loss limit exceeded: ${daily_pnl:,.0f} < -${self.max_daily_loss:,.0f}"
            )
    
    def _trigger_circuit_breaker(self, reason: str) -> None:
        """Trigger circuit breaker."""
        if not self.enable_circuit_breaker:
            logger.warning(f"Circuit breaker disabled, but limit exceeded: {reason}")
            return
        
        self.circuit_breaker_active = True
        self.circuit_breaker_triggered_at = datetime.now()
        self.circuit_breaker_reason = reason
        
        logger.critical(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
        
        raise CircuitBreakerTriggered(reason)
    
    def reset_circuit_breaker(self) -> None:
        """
        Reset circuit breaker manually.
        
        Use with caution. Should only be reset after reviewing the situation
        and confirming it's safe to resume trading.
        
        Example:
            >>> guard.reset_circuit_breaker()
            >>> # Trading can resume
        """
        self.circuit_breaker_active = False
        self.circuit_breaker_triggered_at = None
        self.circuit_breaker_reason = None
        
        logger.warning("Circuit breaker manually reset")
    
    def _estimate_current_price(self, symbol: str) -> float:
        """Estimate current price for a symbol."""
        # Try to get from current positions
        for pos in self.account_monitor.positions:
            if pos['symbol'] == symbol:
                return pos['current_price']
        
        # Default fallback (should ideally fetch from broker)
        logger.warning(f"No price found for {symbol}, using placeholder 100.0")
        return 100.0
    
    def get_risk_summary(self) -> Dict:
        """
        Get risk summary (current state vs limits).
        
        Returns:
            Dict with current metrics and limits:
            - position_count: Current / Max
            - largest_position_pct: Current / Max
            - leverage: Current / Max
            - drawdown: Current / Max
            - daily_pnl: Current / Daily loss limit
            - circuit_breaker_active: Boolean
        
        Example:
            >>> summary = guard.get_risk_summary()
            >>> print(f"Leverage: {summary['leverage']['current']:.2f}x / {summary['leverage']['max']:.2f}x")
        """
        self.account_monitor.update()
        
        concentration = self.account_monitor.get_position_concentration()
        largest_position_pct = max(concentration.values()) if concentration else 0.0
        
        exposure = self.account_monitor.get_exposure_metrics()
        
        return {
            'position_count': {
                'current': len(self.account_monitor.positions),
                'max': self.max_total_positions
            },
            'largest_position_pct': {
                'current': largest_position_pct,
                'max': self.max_position_pct
            },
            'leverage': {
                'current': exposure['leverage'],
                'max': self.max_leverage
            },
            'drawdown': {
                'current': self.account_monitor.current_drawdown,
                'max': self.max_drawdown
            },
            'daily_pnl': {
                'current': self.account_monitor.daily_pnl,
                'daily_loss_limit': -self.max_daily_loss
            },
            'circuit_breaker_active': self.circuit_breaker_active,
            'circuit_breaker_reason': self.circuit_breaker_reason
        }
    
    def get_risk_score(self) -> float:
        """
        Get overall risk score (0-100).
        
        Calculates a single risk metric combining all risk factors.
        Lower score = safer, higher score = riskier.
        
        Score interpretation:
        - 0-30: Low risk (safe)
        - 30-60: Medium risk (normal)
        - 60-80: High risk (caution)
        - 80-100: Very high risk (danger)
        - 100: Circuit breaker triggered
        
        Returns:
            Risk score from 0 (no positions) to 100 (at all limits)
        
        Example:
            >>> score = guard.get_risk_score()
            >>> if score > 80:
            ...     print("WARNING: High risk level!")
            >>> elif score > 60:
            ...     print("CAUTION: Elevated risk")
        """
        # Circuit breaker = max risk
        if self.circuit_breaker_active:
            return 100.0
        
        summary = self.get_risk_summary()
        
        # No positions = no risk
        if summary['position_count']['current'] == 0:
            return 0.0
        
        # Calculate sub-scores (0-1 for each factor)
        position_score = min(1.0, summary['position_count']['current'] / summary['position_count']['max'])
        concentration_score = min(1.0, summary['largest_position_pct']['current'] / summary['largest_position_pct']['max'])
        leverage_score = min(1.0, summary['leverage']['current'] / summary['leverage']['max'])
        
        # Drawdown score (more negative = worse)
        dd_pct = abs(summary['drawdown']['current'] / summary['drawdown']['max'])
        drawdown_score = min(1.0, dd_pct)
        
        # Daily loss score
        if summary['daily_pnl']['current'] < 0:
            loss_pct = abs(summary['daily_pnl']['current'] / summary['daily_pnl']['daily_loss_limit'])
            loss_score = min(1.0, loss_pct)
        else:
            loss_score = 0.0
        
        # Weighted average (customize weights as needed)
        # Higher weights on concentration and drawdown (most critical)
        overall = (
            position_score * 0.15 +
            concentration_score * 0.25 +
            leverage_score * 0.20 +
            drawdown_score * 0.25 +
            loss_score * 0.15
        )
        
        return overall * 100.0
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"RiskGuard(max_position=${self.max_position_size:,.0f}, "
            f"max_dd={self.max_drawdown:.1%}, "
            f"cb_active={self.circuit_breaker_active})"
        )
