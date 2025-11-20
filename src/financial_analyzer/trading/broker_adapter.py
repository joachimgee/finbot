"""
Abstract base class for broker adapters.

Interface uniforme pour tous les brokers (Alpaca, Interactive Brokers, etc.)
Permet de switcher de broker sans changer le code upstream.

Methods:
    - connect() : Établir connexion
    - disconnect() : Fermer connexion
    - submit_order(order) : Soumettre ordre (market, limit)
    - cancel_order(order_id) : Annuler ordre
    - get_account() : Info compte (cash, equity, buying_power)
    - get_positions() : Positions actuelles
    - get_orders(status) : Ordres (open, filled, canceled)
    - get_bars(symbol, start, end, timeframe) : Prix historiques
    - is_market_open() : Marché ouvert ?
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Literal
from datetime import datetime
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BrokerAdapter(ABC):
    """
    Abstract broker adapter interface.
    
    Provides uniform interface for all brokers (Alpaca, Interactive Brokers, etc.).
    Allows switching between brokers without changing upstream code.
    
    Attributes:
        api_key: API key for broker authentication
        secret_key: Secret key for broker authentication
        mode: Trading mode ('paper' or 'live')
        base_url: Base URL for broker API
        connected: Connection status flag
    
    Example:
        >>> class MyBroker(BrokerAdapter):
        ...     def connect(self):
        ...         self.connected = True
        ...     # Implement other abstract methods...
        >>> broker = MyBroker(api_key='key', secret_key='secret')
        >>> broker.connect()
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        mode: Literal['paper', 'live'] = 'paper',
        base_url: Optional[str] = None
    ) -> None:
        """
        Initialize broker adapter.
        
        Args:
            api_key: API key for broker authentication
            secret_key: Secret key for broker authentication
            mode: Trading mode ('paper' for paper trading, 'live' for live trading)
            base_url: Base URL for broker API (optional, defaults per broker)
        
        Example:
            >>> adapter = MyBrokerAdapter(
            ...     api_key='my_api_key',
            ...     secret_key='my_secret',
            ...     mode='paper'
            ... )
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.mode = mode
        self.base_url = base_url
        self.connected = False
        
        logger.info(
            f"Initialized {self.__class__.__name__} in {mode} mode"
        )
    
    @staticmethod
    def _validate_symbol(symbol: str) -> None:
        """
        Validate ticker symbol format.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'MSFT')
        
        Raises:
            ValueError: If symbol format invalid
        
        Example:
            >>> BrokerAdapter._validate_symbol('AAPL')  # OK
            >>> BrokerAdapter._validate_symbol('aapl')  # ValueError: must be uppercase
        """
        if not symbol or not isinstance(symbol, str):
            raise ValueError(f"Symbol must be non-empty string, got {type(symbol).__name__}")
        
        if not symbol.isupper():
            raise ValueError(f"Symbol must be uppercase, got '{symbol}'")
        
        if not symbol.replace('.', '').isalpha():  # Allow dots for special tickers (e.g., BRK.A)
            raise ValueError(f"Symbol must contain only letters (and optional dots), got '{symbol}'")
        
        if len(symbol) > 6:  # Some tickers have 5-6 chars (e.g., GOOGL, AMZN)
            raise ValueError(f"Symbol too long (max 6 chars), got '{symbol}' ({len(symbol)} chars)")
    
    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to broker.
        
        Sets self.connected to True upon successful connection.
        
        Raises:
            BrokerAPIError: If connection fails
        
        Example:
            >>> adapter = MyBrokerAdapter(api_key='key', secret_key='secret')
            >>> adapter.connect()
            >>> assert adapter.connected is True
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """
        Close connection to broker.
        
        Sets self.connected to False upon successful disconnection.
        
        Example:
            >>> adapter.disconnect()
            >>> assert adapter.connected is False
        """
        pass
    
    def __enter__(self):
        """
        Context manager entry.
        
        Example:
            >>> with AlpacaAdapter(api_key='...', secret_key='...') as adapter:
            ...     account = adapter.get_account()
            # Auto-disconnected!
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}(mode='{self.mode}', connected={self.connected})"
    
    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: Literal['buy', 'sell'],
        order_type: Literal['market', 'limit'] = 'market',
        limit_price: Optional[float] = None,
        time_in_force: Literal['day', 'gtc', 'ioc', 'fok'] = 'day'
    ) -> Dict:
        """
        Submit order to broker.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'MSFT')
            qty: Quantity (positive integer)
            side: Order side ('buy' or 'sell')
            order_type: Order type ('market' or 'limit')
            limit_price: Limit price (required if order_type='limit')
            time_in_force: Time in force ('day', 'gtc', 'ioc', 'fok')
                - 'day': Good for day
                - 'gtc': Good till canceled
                - 'ioc': Immediate or cancel
                - 'fok': Fill or kill
        
        Returns:
            Order dict with keys:
                - order_id: Unique order identifier
                - symbol: Ticker symbol
                - qty: Order quantity
                - side: Order side ('buy' or 'sell')
                - order_type: Order type ('market' or 'limit')
                - status: Order status ('new', 'filled', 'canceled', etc.)
                - filled_qty: Filled quantity
                - avg_fill_price: Average fill price (None if not filled)
                - submitted_at: Submission timestamp
                - filled_at: Fill timestamp (None if not filled)
        
        Raises:
            BrokerAPIError: If API call fails
            InsufficientFundsError: If insufficient capital
            ValueError: If invalid parameters (e.g., limit_price missing for limit order)
        
        Example:
            >>> order = adapter.submit_order(
            ...     symbol='AAPL',
            ...     qty=10,
            ...     side='buy',
            ...     order_type='market'
            ... )
            >>> print(f"Order ID: {order['order_id']}")
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel pending order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Canceled order dict with keys:
                - order_id: Unique order identifier
                - status: Order status (should be 'canceled')
        
        Raises:
            BrokerAPIError: If API call fails
            OrderNotFoundError: If order_id doesn't exist
        
        Example:
            >>> result = adapter.cancel_order('order_123')
            >>> assert result['status'] == 'canceled'
        """
        pass
    
    @abstractmethod
    def get_account(self) -> Dict:
        """
        Get account information.
        
        Returns:
            Dict with keys:
                - cash: Available cash (USD)
                - equity: Total equity (cash + positions market value)
                - buying_power: Buying power (cash * margin multiplier)
                - portfolio_value: Total portfolio value
                - initial_margin: Initial margin requirement
                - maintenance_margin: Maintenance margin requirement
                - daytrade_count: Number of day trades (for PDT rule)
        
        Raises:
            BrokerAPIError: If API call fails
        
        Example:
            >>> account = adapter.get_account()
            >>> print(f"Cash: ${account['cash']:.2f}")
            >>> print(f"Equity: ${account['equity']:.2f}")
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """
        Get current positions.
        
        Returns:
            List of position dicts with keys:
                - symbol: Ticker symbol
                - qty: Quantity (positive = long, negative = short)
                - avg_entry_price: Average entry price
                - current_price: Current market price
                - market_value: Current market value (qty * current_price)
                - unrealized_pl: Unrealized profit/loss (USD)
                - unrealized_plpc: Unrealized profit/loss percent (decimal)
        
        Raises:
            BrokerAPIError: If API call fails
        
        Example:
            >>> positions = adapter.get_positions()
            >>> for pos in positions:
            ...     print(f"{pos['symbol']}: {pos['qty']} shares @ ${pos['current_price']:.2f}")
        """
        pass
    
    @abstractmethod
    def get_orders(
        self,
        status: Literal['open', 'closed', 'all'] = 'all',
        limit: int = 100
    ) -> List[Dict]:
        """
        Get orders.
        
        Args:
            status: Filter by status ('open', 'closed', 'all')
            limit: Max number of orders to return
        
        Returns:
            List of order dicts with keys:
                - order_id: Unique order identifier
                - symbol: Ticker symbol
                - qty: Order quantity
                - side: Order side ('buy' or 'sell')
                - order_type: Order type ('market' or 'limit')
                - status: Order status ('new', 'filled', 'canceled', etc.)
                - filled_qty: Filled quantity
                - avg_fill_price: Average fill price (None if not filled)
                - submitted_at: Submission timestamp
                - filled_at: Fill timestamp (None if not filled)
        
        Raises:
            BrokerAPIError: If API call fails
        
        Example:
            >>> open_orders = adapter.get_orders(status='open')
            >>> print(f"Open orders: {len(open_orders)}")
        """
        pass
    
    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Literal['1Min', '5Min', '15Min', '1H', '1D'] = '1D'
    ) -> pd.DataFrame:
        """
        Get historical bars.
        
        Args:
            symbol: Ticker symbol
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            timeframe: Bar timeframe ('1Min', '5Min', '15Min', '1H', '1D')
        
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex
        
        Raises:
            BrokerAPIError: If API call fails
        
        Example:
            >>> from datetime import datetime, timedelta
            >>> end = datetime.now()
            >>> start = end - timedelta(days=30)
            >>> bars = adapter.get_bars('AAPL', start, end, timeframe='1D')
            >>> print(bars.head())
        """
        pass
    
    @abstractmethod
    def is_market_open(self) -> bool:
        """
        Check if market is currently open.
        
        Returns:
            True if market open, False otherwise
        
        Raises:
            BrokerAPIError: If API call fails
        
        Example:
            >>> if adapter.is_market_open():
            ...     print("Market is open!")
            ... else:
            ...     print("Market is closed.")
        """
        pass


class BrokerAPIError(Exception):
    """
    Broker API error.
    
    Raised when broker API call fails (connection error, API error, etc.).
    
    Example:
        >>> raise BrokerAPIError("Failed to connect to broker")
    """
    pass


class InsufficientFundsError(Exception):
    """
    Insufficient funds error.
    
    Raised when order cannot be submitted due to insufficient buying power.
    
    Example:
        >>> raise InsufficientFundsError("Insufficient buying power: required $10000, available $5000")
    """
    pass


class OrderNotFoundError(Exception):
    """
    Order not found error.

    Raised when an operation references a non-existent order ID.

    Example:
        >>> raise OrderNotFoundError("Order 123 not found")
    """
    pass


class OrderNotFoundError(Exception):
    """
    Order not found error.
    
    Raised when trying to cancel or query an order that doesn't exist.
    
    Example:
        >>> raise OrderNotFoundError("Order order_123 not found")
    """
    pass
