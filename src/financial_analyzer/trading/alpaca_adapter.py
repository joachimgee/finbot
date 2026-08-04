"""
Alpaca broker adapter implementation.

Uses alpaca-trade-api SDK for Paper & Live trading.
Implements BrokerAdapter interface.

Documentation: https://alpaca.markets/docs/api-references/trading-api/
"""

from __future__ import annotations
from typing import Dict, List, Optional, Literal, Iterable, Tuple
from datetime import datetime, timedelta
import pandas as pd
import logging
import time
from functools import wraps
from collections import deque

try:
    import alpaca_trade_api as tradeapi
except ImportError as e:
    raise ImportError(
        "alpaca-trade-api not installed. "
        "Install with: pip install alpaca-trade-api"
    ) from e

from financial_analyzer.trading.broker_adapter import (
    BrokerAdapter,
    BrokerAPIError,
    InsufficientFundsError,
    OrderNotFoundError
)
from financial_analyzer.trading.safety import (
    assert_live_allowed,
    base_url_for_mode,
    resolve_trading_mode,
)

logger = logging.getLogger(__name__)


def retry_on_api_error(max_retries: int = 3, backoff: float = 1.0):
    """
    Decorator to retry API calls on transient errors.
    
    Args:
        max_retries: Max number of retries (default: 3)
        backoff: Backoff multiplier for exponential backoff (default: 1.0)
    
    Example:
        >>> @retry_on_api_error(max_retries=3, backoff=2.0)
        ... def fetch_data():
        ...     return api.get_data()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if error is retryable
                    error_str = str(e).lower()
                    is_retryable = any(x in error_str for x in [
                        'timeout', 'rate limit', '429', '503', 'connection', 'timed out'
                    ])
                    
                    # If not retryable or last attempt, re-raise
                    if not is_retryable or attempt == max_retries - 1:
                        raise
                    
                    # Exponential backoff
                    wait_time = backoff * (2 ** attempt)
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    time.sleep(wait_time)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class AlpacaAdapter(BrokerAdapter):
    """
    Alpaca broker adapter.
    
    Implements BrokerAdapter interface using Alpaca Trading API.
    Supports both paper and live trading modes.
    
    Attributes:
        api: Alpaca REST API client
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        mode: Trading mode ('paper' or 'live')
        base_url: Alpaca API base URL
        connected: Connection status
    
    Example:
        >>> adapter = AlpacaAdapter(
        ...     api_key='YOUR_API_KEY',
        ...     secret_key='YOUR_SECRET_KEY',
        ...     mode='paper'
        ... )
        >>> adapter.connect()
        >>> account = adapter.get_account()
        >>> print(f"Cash: ${account['cash']:.2f}")
        >>> order = adapter.submit_order('AAPL', qty=10, side='buy', order_type='market')
        >>> print(f"Order ID: {order['order_id']}")
        >>> adapter.disconnect()
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        mode: Literal['paper', 'live'] = 'paper',
        base_url: Optional[str] = None
    ) -> None:
        """
        Initialize Alpaca adapter.
        
        Args:
            api_key: Alpaca API key (get from https://alpaca.markets/)
            secret_key: Alpaca secret key
            mode: 'paper' (paper trading) or 'live' (live trading)
            base_url: Override base URL (default: https://paper-api.alpaca.markets for paper)
        
        Example:
            >>> adapter = AlpacaAdapter(
            ...     api_key='PK...',
            ...     secret_key='...',
            ...     mode='paper'
            ... )
        """
        super().__init__(api_key, secret_key, mode, base_url)
        
        # Set default base URL based on mode
        if base_url is None:
            self.base_url = (
                'https://paper-api.alpaca.markets' if mode == 'paper'
                else 'https://api.alpaca.markets'
            )
        
        self.api: Optional[tradeapi.REST] = None
        
        # Rate limiting (Alpaca limit: 200 requests/minute)
        self._rate_limit_window = 60  # seconds
        self._rate_limit_max = 200
        self._rate_limit_requests = deque(maxlen=self._rate_limit_max)
        
        logger.info(
            f"AlpacaAdapter initialized in {mode} mode "
            f"(base_url={self.base_url}, rate_limit={self._rate_limit_max}/min)"
        )
        # Lightweight in-memory cache for bars
        import os
        try:
            self._bars_cache_ttl = int(os.environ.get('ALPACA_BARS_CACHE_TTL', '300'))
        except Exception:
            self._bars_cache_ttl = 300
        self._bars_cache: Dict[Tuple, Tuple[float, object]] = {}

    @classmethod
    def from_env(
        cls,
        mode: Literal['paper', 'live'] = 'paper',
        base_url: Optional[str] = None,
        api_key_env: str = 'APCA_API_KEY_ID',
        secret_key_env: str = 'APCA_API_SECRET_KEY'
    ) -> 'AlpacaAdapter':
        """
        Create adapter from environment variables.

        Args:
            mode: 'paper' or 'live'
            base_url: Optional explicit base URL override
            api_key_env: Env var name for API key
            secret_key_env: Env var name for secret key

        Returns:
            AlpacaAdapter instance configured from environment.
        """
        import os
        # Primary (official) env names per Alpaca docs
        candidates_key = [api_key_env, 'APCA_API_KEY_ID', 'ALPACA_API_KEY', 'ALPACA_KEY']
        candidates_secret = [secret_key_env, 'APCA_API_SECRET_KEY', 'ALPACA_API_SECRET', 'ALPACA_SECRET_KEY']

        def first_env(names):
            for n in names:
                v = os.environ.get(n)
                if v:
                    return v, n
            return None, None

        api_key, key_name = first_env(candidates_key)
        secret_key, sec_name = first_env(candidates_secret)

        # Politique de sûreté : résoudre le mode (le live est rétrogradé en paper
        # s'il n'est pas explicitement activé) et DÉRIVER l'URL du mode résolu.
        # On n'accepte plus une base URL d'environnement qui pourrait diverger du
        # mode (mode=paper mais APCA_API_BASE_URL=live) — ce croisement était le
        # trou de sûreté principal.
        resolved_mode = resolve_trading_mode(mode)
        expected_url = base_url_for_mode(resolved_mode)
        if base_url is not None and base_url != expected_url:
            raise ValueError(
                f"base_url {base_url!r} incohérent avec le mode résolu "
                f"'{resolved_mode.value}' (attendu {expected_url!r})."
            )
        base_url = expected_url

        if not api_key or not secret_key:
            checked = ','.join(candidates_key) + ' / ' + ','.join(candidates_secret)
            raise ValueError(
                f"Missing Alpaca credentials in env. Checked: {checked}"
            )
        return cls(api_key=api_key, secret_key=secret_key, mode=resolved_mode.value, base_url=base_url)
    
    def _check_rate_limit(self) -> None:
        """
        Check and enforce rate limit (200 req/min for Alpaca).
        
        Sleeps if rate limit would be exceeded.
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._rate_limit_window)
        
        # Remove old requests outside window
        while self._rate_limit_requests and self._rate_limit_requests[0] < cutoff:
            self._rate_limit_requests.popleft()
        
        # Check if at limit
        if len(self._rate_limit_requests) >= self._rate_limit_max:
            sleep_time = (self._rate_limit_requests[0] - cutoff).total_seconds() + 1
            logger.warning(
                f"Rate limit reached ({len(self._rate_limit_requests)}/{self._rate_limit_max}), "
                f"sleeping {sleep_time:.1f}s"
            )
            time.sleep(sleep_time)
        
        # Record this request
        self._rate_limit_requests.append(now)
    
    def connect(self) -> None:
        """
        Establish connection to Alpaca.
        
        Creates REST API client and validates connection by fetching account info.
        
        Raises:
            BrokerAPIError: If connection fails
        
        Example:
            >>> adapter.connect()
            >>> assert adapter.connected is True
        """
        # Dernier garde-fou avant toute connexion live : refuser le live non
        # activé, même si l'adaptateur a été construit directement en mode live.
        assert_live_allowed(self.mode)
        try:
            logger.info("Connecting to Alpaca...")

            self.api = tradeapi.REST(
                key_id=self.api_key,
                secret_key=self.secret_key,
                base_url=self.base_url
            )
            
            # Test connection by fetching account
            account = self.api.get_account()
            self.connected = True
            
            logger.info(
                f"Connected to Alpaca successfully. "
                f"Account status: {account.status}, "
                f"Equity: ${float(account.equity):.2f}"
            )
            
        except Exception as e:
            self.connected = False
            logger.error(f"Failed to connect to Alpaca: {e}")
            raise BrokerAPIError(f"Failed to connect to Alpaca: {e}") from e
    
    def disconnect(self) -> None:
        """
        Close connection to Alpaca.
        
        Clears API client and sets connected flag to False.
        
        Example:
            >>> adapter.disconnect()
            >>> assert adapter.connected is False
        """
        logger.info("Disconnecting from Alpaca...")
        self.api = None
        self.connected = False
        logger.info("Disconnected from Alpaca.")
    
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
        Submit order to Alpaca.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL')
            qty: Quantity (positive integer)
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            limit_price: Limit price (required if order_type='limit')
            time_in_force: 'day', 'gtc', 'ioc', or 'fok'
        
        Returns:
            Order dict with keys: order_id, symbol, qty, side, order_type, status, 
            filled_qty, avg_fill_price, submitted_at, filled_at
        
        Raises:
            BrokerAPIError: If not connected or API call fails
            InsufficientFundsError: If insufficient buying power
            ValueError: If limit_price missing for limit order
        
        Example:
            >>> order = adapter.submit_order(
            ...     symbol='AAPL',
            ...     qty=10,
            ...     side='buy',
            ...     order_type='market'
            ... )
            >>> print(f"Order submitted: {order['order_id']}")
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")
        
        # Validate symbol
        self._validate_symbol(symbol)
        
        # Validate quantity
        if qty <= 0:
            raise ValueError(f"Quantity must be positive, got {qty}")
        
        # Validate limit order
        if order_type == 'limit' and limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        
        # Check rate limit
        self._check_rate_limit()
        
        try:
            logger.info(
                f"Submitting {order_type} {side} order: {symbol} x{qty} "
                f"{'@$' + str(limit_price) if limit_price else ''}"
            )
            
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                limit_price=limit_price,
                time_in_force=time_in_force
            )
            
            result = {
                'order_id': order.id,
                'symbol': order.symbol,
                'qty': int(order.qty),
                'side': order.side,
                'order_type': order.type,
                'status': order.status,
                'filled_qty': int(order.filled_qty),
                'avg_fill_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                'submitted_at': order.submitted_at,
                'filled_at': order.filled_at
            }
            
            logger.info(
                f"Order submitted successfully: {result['order_id']} "
                f"(status={result['status']})"
            )
            
            return result
        
        except tradeapi.rest.APIError as e:
            # Check for insufficient funds error
            if 'insufficient' in str(e).lower() or 'buying power' in str(e).lower():
                logger.error(f"Insufficient funds: {e}")
                raise InsufficientFundsError(str(e)) from e
            
            logger.error(f"Alpaca API error: {e}")
            raise BrokerAPIError(f"Alpaca API error: {e}") from e
        except Exception as e:
            # Catch other exceptions (including mock errors in tests)
            error_str = str(e).lower()
            if 'insufficient' in error_str or 'buying power' in error_str:
                logger.error(f"Insufficient funds: {e}")
                raise InsufficientFundsError(str(e)) from e
            
            logger.error(f"Alpaca API error: {e}")
            raise BrokerAPIError(f"Alpaca API error: {e}") from e
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel pending order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Dict with keys: order_id, status
        
        Raises:
            BrokerAPIError: If not connected or API call fails
            OrderNotFoundError: If order not found
        
        Example:
            >>> result = adapter.cancel_order('order_123')
            >>> assert result['status'] == 'canceled'
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")
        
        try:
            logger.info(f"Canceling order: {order_id}")
            
            order = self.api.cancel_order(order_id)
            
            result = {
                'order_id': order.id,
                'status': order.status
            }
            
            logger.info(f"Order canceled successfully: {order_id}")
            
            return result
        
        except tradeapi.rest.APIError as e:
            # Check for 404 Not Found
            if '404' in str(e) or 'not found' in str(e).lower():
                logger.error(f"Order not found: {order_id}")
                raise OrderNotFoundError(f"Order {order_id} not found") from e
            
            logger.error(f"Alpaca API error: {e}")
            raise BrokerAPIError(f"Alpaca API error: {e}") from e
        except Exception as e:
            # Catch other exceptions (including mock errors in tests)
            error_str = str(e)
            if '404' in error_str or 'not found' in error_str.lower():
                logger.error(f"Order not found: {order_id}")
                raise OrderNotFoundError(f"Order {order_id} not found") from e
            
            logger.error(f"Alpaca API error: {e}")
            raise BrokerAPIError(f"Alpaca API error: {e}") from e
    
    @retry_on_api_error(max_retries=3, backoff=1.0)
    def get_account(self) -> Dict:
        """
        Get Alpaca account information (with retry on transient errors).
        
        Returns:
            Dict with keys: cash, equity, buying_power, portfolio_value, 
            initial_margin, maintenance_margin, daytrade_count
        
        Raises:
            BrokerAPIError: If not connected or API call fails
        
        Example:
            >>> account = adapter.get_account()
            >>> print(f"Cash: ${account['cash']:.2f}")
            >>> print(f"Equity: ${account['equity']:.2f}")
            >>> print(f"Buying Power: ${account['buying_power']:.2f}")
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")
        
        self._check_rate_limit()
        
        try:
            logger.debug("Fetching account information...")
            
            account = self.api.get_account()
            
            result = {
                'cash': float(account.cash),
                'equity': float(account.equity),
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value),
                'initial_margin': float(account.initial_margin),
                'maintenance_margin': float(account.maintenance_margin),
                'daytrade_count': int(account.daytrade_count)
            }
            
            logger.debug(
                f"Account: cash=${result['cash']:.2f}, "
                f"equity=${result['equity']:.2f}, "
                f"buying_power=${result['buying_power']:.2f}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to fetch account: {e}")
            raise BrokerAPIError(f"Failed to fetch account: {e}") from e
    
    @retry_on_api_error(max_retries=3, backoff=1.0)
    def get_positions(self) -> List[Dict]:
        """
        Get current Alpaca positions (with retry on transient errors).
        
        Returns:
            List of position dicts with keys: symbol, qty, avg_entry_price, 
            current_price, market_value, unrealized_pl, unrealized_plpc
        
        Raises:
            BrokerAPIError: If not connected or API call fails
        
        Example:
            >>> positions = adapter.get_positions()
            >>> for pos in positions:
            ...     print(f"{pos['symbol']}: {pos['qty']} shares, "
            ...           f"P&L: ${pos['unrealized_pl']:.2f}")
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")
        
        self._check_rate_limit()
        
        try:
            logger.debug("Fetching positions...")
            
            positions = self.api.list_positions()
            
            result = [{
                'symbol': pos.symbol,
                'qty': int(pos.qty),
                'avg_entry_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'market_value': float(pos.market_value),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc)
            } for pos in positions]
            
            logger.debug(f"Fetched {len(result)} positions")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            raise BrokerAPIError(f"Failed to fetch positions: {e}") from e
    
    @retry_on_api_error(max_retries=3, backoff=1.0)
    def get_orders(
        self,
        status: Literal['open', 'closed', 'all'] = 'all',
        limit: int = 100
    ) -> List[Dict]:
        """
        Get Alpaca orders (with retry on transient errors).
        
        Args:
            status: Filter by status ('open', 'closed', 'all')
            limit: Max number of orders to return
        
        Returns:
            List of order dicts with keys: order_id, symbol, qty, side, order_type, 
            status, filled_qty, avg_fill_price
        
        Raises:
            BrokerAPIError: If not connected or API call fails
        
        Example:
            >>> open_orders = adapter.get_orders(status='open')
            >>> print(f"Open orders: {len(open_orders)}")
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")
        
        self._check_rate_limit()
        
        try:
            logger.debug(f"Fetching {status} orders (limit={limit})...")
            
            orders = self.api.list_orders(status=status, limit=limit)
            
            result = [{
                'order_id': order.id,
                'symbol': order.symbol,
                'qty': int(order.qty),
                'side': order.side,
                'order_type': order.type,
                'status': order.status,
                'filled_qty': int(order.filled_qty),
                'avg_fill_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                'submitted_at': order.submitted_at,
                'filled_at': order.filled_at
            } for order in orders]
            
            logger.debug(f"Fetched {len(result)} orders")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            raise BrokerAPIError(f"Failed to fetch orders: {e}") from e
    
    @retry_on_api_error(max_retries=3, backoff=1.0)
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Literal['1Min', '5Min', '15Min', '1H', '1D'] = '1D'
    ) -> pd.DataFrame:
        """
        Get Alpaca historical bars (with retry on transient errors).
        
        Args:
            symbol: Ticker symbol
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            timeframe: Bar timeframe ('1Min', '5Min', '15Min', '1H', '1D')
        
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex
        
        Raises:
            BrokerAPIError: If not connected or API call fails
        
        Example:
            >>> from datetime import datetime, timedelta
            >>> end = datetime.now()
            >>> start = end - timedelta(days=30)
            >>> bars = adapter.get_bars('AAPL', start, end, timeframe='1D')
            >>> print(bars.head())
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")
        
        self._check_rate_limit()
        
        try:
            logger.debug(
                f"Fetching bars for {symbol}: {start} to {end} ({timeframe})"
            )
            
            # Format timestamps to RFC3339 without microseconds for Alpaca
            def _fmt(dt: datetime) -> str:
                return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            # Use free 'iex' feed for paper accounts when available
            feed = 'iex' if getattr(self, 'mode', 'paper') == 'paper' else None

            # Cache check
            key = ('single', symbol, timeframe, start.replace(microsecond=0), end.replace(microsecond=0), self.mode)
            import time as _t
            now_ts = _t.time()
            if key in self._bars_cache:
                ts, val = self._bars_cache[key]
                if now_ts - ts <= self._bars_cache_ttl:
                    return val.copy() if isinstance(val, pd.DataFrame) else val

            bars = self.api.get_bars(
                symbol,
                timeframe,
                start=_fmt(start),
                end=_fmt(end),
                feed=feed if feed else None
            ).df
            
            # Rename columns to standard format (o, h, l, c, v -> open, high, low, close, volume)
            bars = bars.rename(columns={
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            })
            
            # Select only standard columns
            result = bars[['open', 'high', 'low', 'close', 'volume']]
            # Store in cache
            self._bars_cache[key] = (now_ts, result.copy())
            
            logger.debug(f"Fetched {len(result)} bars for {symbol}")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to fetch bars for {symbol}: {e}")
            raise BrokerAPIError(f"Failed to fetch bars for {symbol}: {e}") from e

    @retry_on_api_error(max_retries=3, backoff=1.0)
    def get_bars_multi(
        self,
        symbols: Iterable[str],
        start: datetime,
        end: datetime,
        timeframe: Literal['1Min', '5Min', '15Min', '1H', '1D'] = '1D',
        chunk_size: int = 50
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical bars for multiple symbols with batching and rate limiting.

        Args:
            symbols: Iterable of ticker symbols
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            timeframe: Bar timeframe
            chunk_size: Symbols per batch request (tune per rate limits)

        Returns:
            Dict mapping symbol -> DataFrame with columns open, high, low, close, volume
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")

        self._check_rate_limit()

        # Helper formatter
        def _fmt(dt: datetime) -> str:
            return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        feed = 'iex' if getattr(self, 'mode', 'paper') == 'paper' else None

        symbols = list(symbols)
        result: Dict[str, pd.DataFrame] = {}

        try:
            for i in range(0, len(symbols), chunk_size):
                batch = symbols[i:i + chunk_size]
                if not batch:
                    continue
                # Cache check for batch
                key = ('multi', tuple(sorted(batch)), timeframe, start.replace(microsecond=0), end.replace(microsecond=0), self.mode)
                import time as _t
                now_ts = _t.time()
                cached = self._bars_cache.get(key)
                if cached and (now_ts - cached[0] <= self._bars_cache_ttl):
                    cached_result = cached[1]
                    if isinstance(cached_result, dict):
                        result.update({k: v.copy() for k, v in cached_result.items()})
                        continue

                # alpaca-trade-api supports list of symbols; returns MultiIndex df
                bars = self.api.get_bars(
                    batch,
                    timeframe,
                    start=_fmt(start),
                    end=_fmt(end),
                    feed=feed if feed else None
                ).df

                # When multiple symbols, DataFrame often has symbol in a column or index level
                if 'symbol' in bars.columns:
                    bars_grouped = bars.groupby('symbol')
                    for sym, g in bars_grouped:
                        df = g.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                        df = df[['open', 'high', 'low', 'close', 'volume']]
                        result[str(sym)] = df
                else:
                    # MultiIndex [('AAPL', ts), ...] with o,h,l,c,v columns
                    if isinstance(bars.index, pd.MultiIndex):
                        # level 0: symbol, level 1: timestamp
                        for sym in sorted(set(bars.index.get_level_values(0))):
                            g = bars.xs(sym, level=0)
                            df = g.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                            df = df[['open', 'high', 'low', 'close', 'volume']]
                            result[str(sym)] = df
                    else:
                        # Single symbol path but called via multi
                        df = bars.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                        df = df[['open', 'high', 'low', 'close', 'volume']]
                        # No symbol column; assign first batch member
                        result[str(batch[0])] = df

                    # Cache batch
                    self._bars_cache[key] = (now_ts, {k: v.copy() for k, v in result.items()})

            return result

        except Exception as e:
            logger.error(f"Failed to fetch multi-symbol bars: {e}")
            raise BrokerAPIError(f"Failed to fetch multi-symbol bars: {e}") from e
    
    @retry_on_api_error(max_retries=3, backoff=1.0)
    def is_market_open(self) -> bool:
        """
        Check if US market is currently open (with retry on transient errors).
        
        Returns:
            True if market open, False otherwise
        
        Raises:
            BrokerAPIError: If not connected or API call fails
        
        Example:
            >>> if adapter.is_market_open():
            ...     print("Market is open!")
            ... else:
            ...     print("Market is closed.")
        """
        if not self.connected or self.api is None:
            raise BrokerAPIError("Not connected to broker. Call connect() first.")
        
        self._check_rate_limit()
        
        try:
            clock = self.api.get_clock()
            is_open = clock.is_open
            
            logger.debug(f"Market is {'open' if is_open else 'closed'}")
            
            return is_open
        
        except Exception as e:
            logger.error(f"Failed to check market status: {e}")
            raise BrokerAPIError(f"Failed to check market status: {e}") from e
