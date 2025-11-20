"""
Tests for AlpacaAdapter.

Tests both successful operations and error handling.
Uses pytest fixtures and mocking to avoid real API calls.
"""

from __future__ import annotations
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.broker_adapter import (
    BrokerAPIError,
    InsufficientFundsError,
    OrderNotFoundError
)


class MockAlpacaAPIError(Exception):
    """
    Mock for Alpaca APIError to avoid importing alpaca_trade_api in tests.
    """
    def __init__(self, message):
        self.message = message
        super().__init__(message)
    
    def __str__(self):
        return str(self.message)


@pytest.fixture
def mock_alpaca_api():
    """
    Mock Alpaca API.
    
    Patches alpaca_trade_api.REST to avoid real API calls.
    """
    with patch('financial_analyzer.trading.alpaca_adapter.tradeapi.REST') as mock:
        # Mock get_account for successful connection
        mock_instance = mock.return_value
        mock_account = Mock()
        mock_account.status = 'ACTIVE'
        mock_account.equity = '100000.00'
        mock_instance.get_account.return_value = mock_account
        
        yield mock


@pytest.fixture
def adapter(mock_alpaca_api):
    """
    Create AlpacaAdapter with mocked API.
    
    Returns connected adapter ready for testing.
    """
    adapter = AlpacaAdapter(
        api_key='test_key',
        secret_key='test_secret',
        mode='paper'
    )
    adapter.connect()
    return adapter


class TestConnection:
    """Tests for connection methods."""
    
    def test_init_default_paper_url(self):
        """Test initialization with default paper URL."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        assert adapter.base_url == 'https://paper-api.alpaca.markets'
        assert adapter.mode == 'paper'
        assert adapter.connected is False
    
    def test_init_default_live_url(self):
        """Test initialization with default live URL."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='live')
        assert adapter.base_url == 'https://api.alpaca.markets'
        assert adapter.mode == 'live'
    
    def test_init_custom_url(self):
        """Test initialization with custom URL."""
        custom_url = 'https://custom.alpaca.markets'
        adapter = AlpacaAdapter(
            api_key='key',
            secret_key='secret',
            mode='paper',
            base_url=custom_url
        )
        assert adapter.base_url == custom_url
    
    def test_connect_success(self, mock_alpaca_api):
        """Test successful connection."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        adapter.connect()
        
        assert adapter.connected is True
        assert adapter.api is not None
        mock_alpaca_api.assert_called_once()
    
    def test_connect_failure(self, mock_alpaca_api):
        """Test connection failure."""
        mock_alpaca_api.side_effect = Exception("Connection failed")
        
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Failed to connect"):
            adapter.connect()
        
        assert adapter.connected is False
    
    def test_disconnect(self, adapter):
        """Test disconnection."""
        adapter.disconnect()
        
        assert adapter.connected is False
        assert adapter.api is None


class TestOrders:
    """Tests for order methods."""
    
    def test_submit_market_order_success(self, adapter, mock_alpaca_api):
        """Test successful market order submission."""
        mock_order = Mock()
        mock_order.id = 'order_123'
        mock_order.symbol = 'AAPL'
        mock_order.qty = '10'
        mock_order.filled_qty = '0'
        mock_order.side = 'buy'
        mock_order.type = 'market'
        mock_order.status = 'new'
        mock_order.filled_avg_price = None
        mock_order.submitted_at = datetime.now()
        mock_order.filled_at = None
        
        adapter.api.submit_order.return_value = mock_order
        
        result = adapter.submit_order('AAPL', qty=10, side='buy', order_type='market')
        
        assert result['order_id'] == 'order_123'
        assert result['symbol'] == 'AAPL'
        assert result['qty'] == 10
        assert result['side'] == 'buy'
        assert result['order_type'] == 'market'
        assert result['status'] == 'new'
        assert result['filled_qty'] == 0
        assert result['avg_fill_price'] is None
    
    def test_submit_limit_order_success(self, adapter, mock_alpaca_api):
        """Test successful limit order submission."""
        mock_order = Mock()
        mock_order.id = 'order_456'
        mock_order.symbol = 'TSLA'
        mock_order.qty = '5'
        mock_order.filled_qty = '0'
        mock_order.side = 'sell'
        mock_order.type = 'limit'
        mock_order.status = 'new'
        mock_order.filled_avg_price = None
        mock_order.submitted_at = datetime.now()
        mock_order.filled_at = None
        
        adapter.api.submit_order.return_value = mock_order
        
        result = adapter.submit_order(
            'TSLA',
            qty=5,
            side='sell',
            order_type='limit',
            limit_price=250.00
        )
        
        assert result['order_id'] == 'order_456'
        assert result['symbol'] == 'TSLA'
        assert result['order_type'] == 'limit'
    
    def test_submit_order_not_connected(self):
        """Test order submission when not connected."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.submit_order('AAPL', qty=10, side='buy')
    
    def test_submit_limit_order_missing_price(self, adapter):
        """Test limit order without limit price."""
        with pytest.raises(ValueError, match="limit_price is required"):
            adapter.submit_order('AAPL', qty=10, side='buy', order_type='limit')
    
    def test_submit_order_insufficient_funds(self, adapter, mock_alpaca_api):
        """Test order submission with insufficient funds."""
        adapter.api.submit_order.side_effect = MockAlpacaAPIError('Insufficient buying power')
        
        with pytest.raises(InsufficientFundsError):
            adapter.submit_order('AAPL', qty=1000, side='buy')
    
    def test_submit_order_api_error(self, adapter, mock_alpaca_api):
        """Test order submission with generic API error."""
        adapter.api.submit_order.side_effect = MockAlpacaAPIError('Market closed')
        
        with pytest.raises(BrokerAPIError, match="Alpaca API error"):
            adapter.submit_order('AAPL', qty=10, side='buy')
    
    def test_cancel_order_success(self, adapter, mock_alpaca_api):
        """Test successful order cancellation."""
        mock_order = Mock()
        mock_order.id = 'order_123'
        mock_order.status = 'canceled'
        
        adapter.api.cancel_order.return_value = mock_order
        
        result = adapter.cancel_order('order_123')
        
        assert result['order_id'] == 'order_123'
        assert result['status'] == 'canceled'
        adapter.api.cancel_order.assert_called_once_with('order_123')
    
    def test_cancel_order_not_found(self, adapter, mock_alpaca_api):
        """Test cancel order not found."""
        adapter.api.cancel_order.side_effect = MockAlpacaAPIError('404 Not Found')
        
        with pytest.raises(OrderNotFoundError):
            adapter.cancel_order('nonexistent_order')
    
    def test_cancel_order_not_connected(self):
        """Test cancel order when not connected."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.cancel_order('order_123')
    
    def test_get_orders_all(self, adapter, mock_alpaca_api):
        """Test get all orders."""
        mock_order1 = Mock()
        mock_order1.id = 'order_1'
        mock_order1.symbol = 'AAPL'
        mock_order1.qty = '10'
        mock_order1.filled_qty = '10'
        mock_order1.side = 'buy'
        mock_order1.type = 'market'
        mock_order1.status = 'filled'
        mock_order1.filled_avg_price = '150.00'
        mock_order1.submitted_at = datetime.now()
        mock_order1.filled_at = datetime.now()
        
        mock_order2 = Mock()
        mock_order2.id = 'order_2'
        mock_order2.symbol = 'TSLA'
        mock_order2.qty = '5'
        mock_order2.filled_qty = '0'
        mock_order2.side = 'sell'
        mock_order2.type = 'limit'
        mock_order2.status = 'new'
        mock_order2.filled_avg_price = None
        mock_order2.submitted_at = datetime.now()
        mock_order2.filled_at = None
        
        adapter.api.list_orders.return_value = [mock_order1, mock_order2]
        
        result = adapter.get_orders(status='all', limit=100)
        
        assert len(result) == 2
        assert result[0]['order_id'] == 'order_1'
        assert result[0]['status'] == 'filled'
        assert result[1]['order_id'] == 'order_2'
        assert result[1]['status'] == 'new'
        
        adapter.api.list_orders.assert_called_once_with(status='all', limit=100)
    
    def test_get_orders_open_only(self, adapter, mock_alpaca_api):
        """Test get open orders only."""
        mock_order = Mock()
        mock_order.id = 'order_open'
        mock_order.symbol = 'AAPL'
        mock_order.qty = '10'
        mock_order.filled_qty = '0'
        mock_order.side = 'buy'
        mock_order.type = 'limit'
        mock_order.status = 'new'
        mock_order.filled_avg_price = None
        mock_order.submitted_at = datetime.now()
        mock_order.filled_at = None
        
        adapter.api.list_orders.return_value = [mock_order]
        
        result = adapter.get_orders(status='open')
        
        assert len(result) == 1
        assert result[0]['status'] == 'new'
        adapter.api.list_orders.assert_called_once_with(status='open', limit=100)


class TestAccount:
    """Tests for account methods."""
    
    def test_get_account(self, adapter, mock_alpaca_api):
        """Test get account information."""
        mock_account = Mock()
        mock_account.cash = '100000.00'
        mock_account.equity = '120000.00'
        mock_account.buying_power = '200000.00'
        mock_account.portfolio_value = '120000.00'
        mock_account.initial_margin = '0.00'
        mock_account.maintenance_margin = '0.00'
        mock_account.daytrade_count = '0'
        
        adapter.api.get_account.return_value = mock_account
        
        result = adapter.get_account()
        
        assert result['cash'] == 100000.00
        assert result['equity'] == 120000.00
        assert result['buying_power'] == 200000.00
        assert result['portfolio_value'] == 120000.00
        assert result['initial_margin'] == 0.00
        assert result['maintenance_margin'] == 0.00
        assert result['daytrade_count'] == 0
    
    def test_get_account_not_connected(self):
        """Test get account when not connected."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.get_account()


class TestPositions:
    """Tests for position methods."""
    
    def test_get_positions_multiple(self, adapter, mock_alpaca_api):
        """Test get multiple positions."""
        mock_position1 = Mock()
        mock_position1.symbol = 'AAPL'
        mock_position1.qty = '10'
        mock_position1.avg_entry_price = '150.50'
        mock_position1.current_price = '155.00'
        mock_position1.market_value = '1550.00'
        mock_position1.unrealized_pl = '45.00'
        mock_position1.unrealized_plpc = '0.0299'
        
        mock_position2 = Mock()
        mock_position2.symbol = 'TSLA'
        mock_position2.qty = '5'
        mock_position2.avg_entry_price = '250.00'
        mock_position2.current_price = '240.00'
        mock_position2.market_value = '1200.00'
        mock_position2.unrealized_pl = '-50.00'
        mock_position2.unrealized_plpc = '-0.04'
        
        adapter.api.list_positions.return_value = [mock_position1, mock_position2]
        
        result = adapter.get_positions()
        
        assert len(result) == 2
        assert result[0]['symbol'] == 'AAPL'
        assert result[0]['qty'] == 10
        assert result[0]['unrealized_pl'] == 45.00
        assert result[1]['symbol'] == 'TSLA'
        assert result[1]['qty'] == 5
        assert result[1]['unrealized_pl'] == -50.00
    
    def test_get_positions_empty(self, adapter, mock_alpaca_api):
        """Test get positions when no positions."""
        adapter.api.list_positions.return_value = []
        
        result = adapter.get_positions()
        
        assert len(result) == 0
    
    def test_get_positions_not_connected(self):
        """Test get positions when not connected."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.get_positions()


class TestMarketData:
    """Tests for market data methods."""
    
    def test_get_bars(self, adapter, mock_alpaca_api):
        """Test get historical bars."""
        # Create mock DataFrame
        dates = pd.date_range(start='2024-01-01', periods=5, freq='D')
        mock_df = pd.DataFrame({
            'o': [150.0, 151.0, 152.0, 153.0, 154.0],
            'h': [151.0, 152.0, 153.0, 154.0, 155.0],
            'l': [149.0, 150.0, 151.0, 152.0, 153.0],
            'c': [150.5, 151.5, 152.5, 153.5, 154.5],
            'v': [1000000, 1100000, 1200000, 1300000, 1400000]
        }, index=dates)
        
        mock_bars = Mock()
        mock_bars.df = mock_df
        
        adapter.api.get_bars.return_value = mock_bars
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 5)
        result = adapter.get_bars('AAPL', start, end, timeframe='1D')
        
        assert len(result) == 5
        assert list(result.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert result['open'].iloc[0] == 150.0
        assert result['close'].iloc[-1] == 154.5
    
    def test_get_bars_not_connected(self):
        """Test get bars when not connected."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.get_bars(
                'AAPL',
                datetime.now() - timedelta(days=30),
                datetime.now(),
                timeframe='1D'
            )
    
    def test_is_market_open_true(self, adapter, mock_alpaca_api):
        """Test market open check (open)."""
        mock_clock = Mock()
        mock_clock.is_open = True
        
        adapter.api.get_clock.return_value = mock_clock
        
        assert adapter.is_market_open() is True
    
    def test_is_market_open_false(self, adapter, mock_alpaca_api):
        """Test market open check (closed)."""
        mock_clock = Mock()
        mock_clock.is_open = False
        
        adapter.api.get_clock.return_value = mock_clock
        
        assert adapter.is_market_open() is False
    
    def test_is_market_open_not_connected(self):
        """Test market open check when not connected."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.is_market_open()


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_operation_not_connected_raises_error(self):
        """Test that all operations raise error when not connected."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.submit_order('AAPL', qty=10, side='buy')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.cancel_order('order_123')
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.get_account()
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.get_positions()
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.get_orders()
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.get_bars('AAPL', datetime.now(), datetime.now())
        
        with pytest.raises(BrokerAPIError, match="Not connected"):
            adapter.is_market_open()


class TestValidations:
    """Tests for input validations."""
    
    def test_submit_order_negative_qty(self, adapter):
        """Test order submission with negative quantity."""
        with pytest.raises(ValueError, match="must be positive"):
            adapter.submit_order('AAPL', qty=-10, side='buy')
    
    def test_submit_order_zero_qty(self, adapter):
        """Test order submission with zero quantity."""
        with pytest.raises(ValueError, match="must be positive"):
            adapter.submit_order('AAPL', qty=0, side='buy')
    
    def test_submit_order_invalid_symbol_lowercase(self, adapter):
        """Test order submission with lowercase symbol."""
        with pytest.raises(ValueError, match="must be uppercase"):
            adapter.submit_order('aapl', qty=10, side='buy')
    
    def test_submit_order_invalid_symbol_special_chars(self, adapter):
        """Test order submission with special characters in symbol."""
        with pytest.raises(ValueError, match="only letters"):
            adapter.submit_order('AA-PL', qty=10, side='buy')
    
    def test_submit_order_invalid_symbol_too_long(self, adapter):
        """Test order submission with too long symbol."""
        with pytest.raises(ValueError, match="too long"):
            adapter.submit_order('TOOLONG', qty=10, side='buy')
    
    def test_submit_order_valid_symbol_with_dot(self, adapter, mock_alpaca_api):
        """Test order submission with valid symbol containing dot (e.g., BRK.A)."""
        mock_order = Mock()
        mock_order.id = 'order_123'
        mock_order.symbol = 'BRK.A'
        mock_order.qty = '10'
        mock_order.filled_qty = '0'
        mock_order.side = 'buy'
        mock_order.type = 'market'
        mock_order.status = 'new'
        mock_order.filled_avg_price = None
        mock_order.submitted_at = datetime.now()
        mock_order.filled_at = None
        
        adapter.api.submit_order.return_value = mock_order
        
        result = adapter.submit_order('BRK.A', qty=10, side='buy')
        assert result['symbol'] == 'BRK.A'


class TestContextManager:
    """Tests for context manager functionality."""
    
    def test_context_manager_auto_connects(self, mock_alpaca_api):
        """Test context manager auto-connects on entry."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        assert adapter.connected is False
        
        with adapter as a:
            assert a.connected is True
            assert a is adapter
        
        assert adapter.connected is False
    
    def test_context_manager_disconnects_on_exception(self, mock_alpaca_api):
        """Test context manager disconnects even on exception."""
        adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
        
        try:
            with adapter:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        assert adapter.connected is False


class TestRateLimiting:
    """Tests for rate limiting."""
    
    def test_rate_limit_allows_under_limit(self, adapter):
        """Test rate limit allows requests under limit."""
        # Should not raise or sleep for requests under limit
        for _ in range(10):
            adapter._check_rate_limit()
    
    def test_rate_limit_sleeps_when_exceeded(self, adapter):
        """Test rate limit sleeps when limit exceeded."""
        # Fill rate limit queue
        from datetime import datetime
        from collections import deque
        now = datetime.now()
        adapter._rate_limit_requests = deque(
            [now] * adapter._rate_limit_max,
            maxlen=adapter._rate_limit_max
        )
        
        # Next request should sleep
        import time
        start = time.time()
        adapter._check_rate_limit()
        elapsed = time.time() - start
        
        # Should have slept at least 0.5 seconds
        assert elapsed > 0.5
