"""Order Execution and Portfolio Tracking.

Provides a lightweight in-memory execution engine for generated orders
from the unified Pipeline. This component is intentionally simplified
and mock-oriented so tests can validate functionality without real broker
integrations.

Features
--------
- Order validation (structure, action, weights)
- Position tracking (quantity, avg cost, market value)
- Trade logging (timestamped records)
- Portfolio valuation (cash + positions)

Example
-------
>>> from financial_analyzer.pipeline.order_executor import OrderExecutor
>>> exec = OrderExecutor(initial_capital=100_000)
>>> result = exec.execute({'ticker': 'AAPL', 'action': 'BUY', 'target_weight': 0.10, 'delta_weight': 0.10, 'notional': 10_000}, current_price=150.0)
>>> result['status']
'success'
>>> positions = exec.get_positions()
>>> portfolio = exec.get_portfolio_value({'AAPL': 152.0})

Design Notes
------------
- Quantities derived from notional / current_price
- Average cost recalculated using weighted method
- SELL operations reduce quantity; if resulting quantity ~0 remove position
- Cash adjusted by trade notional (+ for SELL, - for BUY)
- HOLD operations produce a record but no changes

"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import pandas as pd
from datetime import datetime

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

VALID_ACTIONS = {"BUY", "SELL", "HOLD"}


@dataclass
class Position:
    """Represents a single asset position."""
    ticker: str
    quantity: float = 0.0
    avg_cost: float = 0.0

    def market_value(self, price: float) -> float:
        return self.quantity * price


@dataclass
class TradeRecord:
    """Represents an executed trade."""
    timestamp: datetime
    ticker: str
    action: str
    quantity: float
    price: float
    notional: float
    target_weight: float
    delta_weight: float


class OrderExecutor:
    """In-memory order execution engine.

    Parameters
    ----------
    initial_capital : float, default 100000
        Starting cash balance.

    Attributes
    ----------
    cash : float
        Current cash balance.
    positions : Dict[str, Position]
        Active positions keyed by ticker.
    trades : List[TradeRecord]
        History of executed trades.

    Raises
    ------
    ValueError
        If initial_capital <= 0.
    """
    def __init__(self, initial_capital: float = 100_000.0) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be > 0")
        self.cash: float = float(initial_capital)
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        logger.info(f"OrderExecutor initialized with cash=${self.cash:,.2f}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute(self, order: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """Validate and execute a single order.

        Parameters
        ----------
        order : dict
            Order dict with required keys: ticker, action, target_weight,
            delta_weight, notional.
        current_price : float
            Current asset price used for quantity calculation.

        Returns
        -------
        dict
            Execution result with status and details.
        """
        try:
            self._validate_order(order, current_price)
            ticker = order['ticker']
            action = order['action']
            notional = float(order['notional'])
            target_weight = float(order.get('target_weight', 0.0))
            delta_weight = float(order.get('delta_weight', 0.0))

            quantity = 0.0
            if action in {"BUY", "SELL"}:
                if current_price <= 0:
                    raise ValueError("current_price must be > 0 for trade execution")
                quantity = abs(notional) / current_price if current_price > 0 else 0.0

            # Execute
            if action == "BUY" and notional > 0:
                self._apply_buy(ticker, quantity, current_price, notional)
            elif action == "SELL" and notional < 0:
                self._apply_sell(ticker, quantity, current_price, notional)
            else:
                # HOLD or zero-impact
                logger.debug(f"No position change for {ticker} action={action}")

            # Record trade
            record = TradeRecord(
                timestamp=datetime.utcnow(),
                ticker=ticker,
                action=action,
                quantity=quantity if action != "HOLD" else 0.0,
                price=current_price,
                notional=notional,
                target_weight=target_weight,
                delta_weight=delta_weight,
            )
            self.trades.append(record)

            return {
                'status': 'success',
                'ticker': ticker,
                'action': action,
                'quantity': quantity,
                'price': current_price,
                'cash_after': self.cash,
            }
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            return {'status': 'error', 'error': str(e), 'order': order}

    def get_positions(self) -> pd.DataFrame:
        """Return current positions as DataFrame."""
        if not self.positions:
            return pd.DataFrame(columns=['ticker', 'quantity', 'avg_cost'])
        rows = [
            {'ticker': p.ticker, 'quantity': p.quantity, 'avg_cost': p.avg_cost}
            for p in self.positions.values()
        ]
        return pd.DataFrame(rows)

    def get_portfolio_value(self, price_map: Dict[str, float]) -> Dict[str, float]:
        """Compute portfolio valuation given current prices.

        Parameters
        ----------
        price_map : dict
            Mapping ticker -> current price
        Returns
        -------
        dict
            {'cash': ..., 'positions_value': ..., 'total_value': ...}
        """
        positions_val = 0.0
        for ticker, pos in self.positions.items():
            price = price_map.get(ticker)
            if price is not None and price > 0:
                positions_val += pos.market_value(price)
        total = self.cash + positions_val
        return {
            'cash': self.cash,
            'positions_value': positions_val,
            'total_value': total,
        }

    def track_trades(self) -> pd.DataFrame:
        """Return trade history."""
        if not self.trades:
            return pd.DataFrame(columns=['timestamp', 'ticker', 'action', 'quantity', 'price', 'notional'])
        return pd.DataFrame([
            {
                'timestamp': t.timestamp,
                'ticker': t.ticker,
                'action': t.action,
                'quantity': t.quantity,
                'price': t.price,
                'notional': t.notional,
                'target_weight': t.target_weight,
                'delta_weight': t.delta_weight,
            }
            for t in self.trades
        ])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _validate_order(self, order: Dict[str, Any], current_price: float) -> None:
        required = ['ticker', 'action', 'target_weight', 'delta_weight', 'notional']
        missing = [k for k in required if k not in order]
        if missing:
            raise ValueError(f"Missing order keys: {missing}")

        action = order['action']
        if action not in VALID_ACTIONS:
            raise ValueError(f"Invalid action: {action}")

        if not isinstance(order['ticker'], str) or not order['ticker']:
            raise ValueError("ticker must be non-empty string")

        if action in {"BUY", "SELL"}:
            if current_price <= 0:
                raise ValueError("current_price must be > 0 for trade")
            notional = float(order['notional'])
            if action == "BUY" and notional <= 0:
                raise ValueError("BUY order must have positive notional")
            if action == "SELL" and notional >= 0:
                raise ValueError("SELL order must have negative notional")

    def _apply_buy(self, ticker: str, quantity: float, price: float, notional: float) -> None:
        cost = quantity * price
        if cost > self.cash + 1e-6:
            raise ValueError("Insufficient cash for BUY order")
        pos = self.positions.get(ticker)
        if pos:
            total_cost = pos.avg_cost * pos.quantity + cost
            new_qty = pos.quantity + quantity
            pos.avg_cost = total_cost / new_qty if new_qty > 0 else 0.0
            pos.quantity = new_qty
        else:
            self.positions[ticker] = Position(ticker=ticker, quantity=quantity, avg_cost=price)
        self.cash -= cost
        logger.info(f"BUY executed {ticker}: qty={quantity:.4f} price={price:.2f} cash={self.cash:.2f}")

    def _apply_sell(self, ticker: str, quantity: float, price: float, notional: float) -> None:
        pos = self.positions.get(ticker)
        if not pos or pos.quantity <= 0:
            raise ValueError("Cannot SELL non-existing position")
        if quantity > pos.quantity + 1e-6:
            quantity = pos.quantity  # Sell remaining
        proceeds = quantity * price
        pos.quantity -= quantity
        if pos.quantity <= 1e-6:
            del self.positions[ticker]
        self.cash += proceeds
        logger.info(f"SELL executed {ticker}: qty={quantity:.4f} price={price:.2f} cash={self.cash:.2f}")

__all__ = ["OrderExecutor", "Position", "TradeRecord"]
