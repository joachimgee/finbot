# 🚀 PHASE 6 : PAPER TRADING - PLAN COMPLET D'IMPLÉMENTATION

**Date** : 9 novembre 2025, 10:50 CET  
**Objectif** : Mettre en place paper trading opérationnel en 10-14 jours  
**Approche** : Quality-first avec prompts détaillés pour Copilot

---

## 📊 RÉSUMÉ EXÉCUTIF

**Phase 6 décomposée en 4 étapes** :
1. **Phase 6.1** : Broker Adapters (Alpaca + Interactive Brokers) - 3 jours
2. **Phase 6.2** : Account Monitor & Risk Guard - 2 jours
3. **Phase 6.3** : Live Pipeline Integration - 2 jours
4. **Phase 6.4** : Testing & Deployment - 3 jours

**Total** : 10 jours → Paper trading opérationnel !

---

## 📋 PHASE 6.1 : BROKER ADAPTERS (3 JOURS)

### **Objectif**
Implémenter adapters pour **Alpaca** (priorité 1) et **Interactive Brokers** (priorité 2)

### **Livrables**
- `src/financial_analyzer/trading/broker_adapter.py` (600 LOC)
- `src/financial_analyzer/trading/alpaca_adapter.py` (400 LOC)
- `src/financial_analyzer/trading/ib_adapter.py` (400 LOC)
- `tests/trading/test_alpaca_adapter.py` (300 LOC)
- `tests/trading/test_ib_adapter.py` (300 LOC)

### **Prérequis**
- Compte Alpaca Paper Trading (gratuit) : https://alpaca.markets/
- API Key + Secret Key Alpaca

---

### **📝 PROMPT COPILOT - PHASE 6.1**

```
PHASE 6.1 : BROKER ADAPTERS - ALPACA & INTERACTIVE BROKERS

Génère 5 fichiers avec documentation complète et tests :

================================================================================
1. src/financial_analyzer/trading/broker_adapter.py (600 LOC)
================================================================================

\"\"\"
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
\"\"\"

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Literal
from datetime import datetime
import pandas as pd

class BrokerAdapter(ABC):
    \"\"\"Abstract broker adapter interface.\"\"\"
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        mode: Literal['paper', 'live'] = 'paper',
        base_url: Optional[str] = None
    ) -> None:
        \"\"\"Initialize broker adapter.
        
        Args:
            api_key: API key
            secret_key: Secret key
            mode: Trading mode ('paper' or 'live')
            base_url: Base URL (optional, defaults per broker)
        \"\"\"
        self.api_key = api_key
        self.secret_key = secret_key
        self.mode = mode
        self.base_url = base_url
        self.connected = False
    
    @abstractmethod
    def connect(self) -> None:
        \"\"\"Establish connection to broker.\"\"\"
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        \"\"\"Close connection to broker.\"\"\"
        pass
    
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
        \"\"\"Submit order to broker.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL')
            qty: Quantity (positive integer)
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            limit_price: Limit price (required if order_type='limit')
            time_in_force: Time in force ('day', 'gtc', 'ioc', 'fok')
        
        Returns:
            Order dict with keys: order_id, symbol, qty, side, status, filled_qty, avg_fill_price
        
        Raises:
            BrokerAPIError: If API call fails
            InsufficientFundsError: If insufficient capital
        \"\"\"
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict:
        \"\"\"Cancel pending order.
        
        Args:
            order_id: Order ID
        
        Returns:
            Canceled order dict
        
        Raises:
            BrokerAPIError: If API call fails
            OrderNotFoundError: If order_id doesn't exist
        \"\"\"
        pass
    
    @abstractmethod
    def get_account(self) -> Dict:
        \"\"\"Get account information.
        
        Returns:
            Dict with keys:
            - cash: Available cash
            - equity: Total equity (cash + positions)
            - buying_power: Buying power (cash * margin multiplier)
            - portfolio_value: Total portfolio value
            - initial_margin: Initial margin
            - maintenance_margin: Maintenance margin
            - daytrade_count: Number of day trades (PDT)
        \"\"\"
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        \"\"\"Get current positions.
        
        Returns:
            List of position dicts with keys:
            - symbol: Ticker symbol
            - qty: Quantity (positive = long, negative = short)
            - avg_entry_price: Average entry price
            - current_price: Current market price
            - market_value: Current market value (qty * current_price)
            - unrealized_pl: Unrealized P&L
            - unrealized_plpc: Unrealized P&L percent
        \"\"\"
        pass
    
    @abstractmethod
    def get_orders(
        self,
        status: Literal['open', 'closed', 'all'] = 'all',
        limit: int = 100
    ) -> List[Dict]:
        \"\"\"Get orders.
        
        Args:
            status: Filter by status ('open', 'closed', 'all')
            limit: Max number of orders to return
        
        Returns:
            List of order dicts
        \"\"\"
        pass
    
    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Literal['1Min', '5Min', '15Min', '1H', '1D'] = '1D'
    ) -> pd.DataFrame:
        \"\"\"Get historical bars.
        
        Args:
            symbol: Ticker symbol
            start: Start datetime
            end: End datetime
            timeframe: Bar timeframe
        
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index: DatetimeIndex
        \"\"\"
        pass
    
    @abstractmethod
    def is_market_open(self) -> bool:
        \"\"\"Check if market is currently open.
        
        Returns:
            True if market open, False otherwise
        \"\"\"
        pass


class BrokerAPIError(Exception):
    \"\"\"Broker API error.\"\"\"
    pass


class InsufficientFundsError(Exception):
    \"\"\"Insufficient funds error.\"\"\"
    pass


class OrderNotFoundError(Exception):
    \"\"\"Order not found error.\"\"\"
    pass

================================================================================
2. src/financial_analyzer/trading/alpaca_adapter.py (400 LOC)
================================================================================

\"\"\"
Alpaca broker adapter implementation.

Uses alpaca-trade-api SDK for Paper & Live trading.
Implements BrokerAdapter interface.

Documentation: https://alpaca.markets/docs/api-references/trading-api/
\"\"\"

from __future__ import annotations
from typing import Dict, List, Optional, Literal
from datetime import datetime
import pandas as pd
import alpaca_trade_api as tradeapi
from .broker_adapter import BrokerAdapter, BrokerAPIError, InsufficientFundsError, OrderNotFoundError


class AlpacaAdapter(BrokerAdapter):
    \"\"\"Alpaca broker adapter.
    
    Example:
        >>> adapter = AlpacaAdapter(api_key='...', secret_key='...', mode='paper')
        >>> adapter.connect()
        >>> account = adapter.get_account()
        >>> print(f\"Cash: ${account['cash']:.2f}\")
        >>> order = adapter.submit_order('AAPL', qty=10, side='buy', order_type='market')
        >>> print(f\"Order ID: {order['order_id']}\")
    \"\"\"
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        mode: Literal['paper', 'live'] = 'paper',
        base_url: Optional[str] = None
    ) -> None:
        \"\"\"Initialize Alpaca adapter.
        
        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            mode: 'paper' (paper trading) or 'live' (live trading)
            base_url: Override base URL (default: https://paper-api.alpaca.markets for paper)
        \"\"\"
        super().__init__(api_key, secret_key, mode, base_url)
        
        if base_url is None:
            self.base_url = (
                'https://paper-api.alpaca.markets' if mode == 'paper'
                else 'https://api.alpaca.markets'
            )
        
        self.api: Optional[tradeapi.REST] = None
    
    def connect(self) -> None:
        \"\"\"Establish connection to Alpaca.\"\"\"
        try:
            self.api = tradeapi.REST(
                key_id=self.api_key,
                secret_key=self.secret_key,
                base_url=self.base_url
            )
            
            # Test connection
            account = self.api.get_account()
            self.connected = True
            
        except Exception as e:
            raise BrokerAPIError(f\"Failed to connect to Alpaca: {e}\") from e
    
    def disconnect(self) -> None:
        \"\"\"Close connection to Alpaca.\"\"\"
        self.api = None
        self.connected = False
    
    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: Literal['buy', 'sell'],
        order_type: Literal['market', 'limit'] = 'market',
        limit_price: Optional[float] = None,
        time_in_force: Literal['day', 'gtc', 'ioc', 'fok'] = 'day'
    ) -> Dict:
        \"\"\"Submit order to Alpaca.\"\"\"
        if not self.connected or self.api is None:
            raise BrokerAPIError(\"Not connected to broker\")
        
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                limit_price=limit_price,
                time_in_force=time_in_force
            )
            
            return {
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
        
        except tradeapi.rest.APIError as e:
            if 'insufficient' in str(e).lower():
                raise InsufficientFundsError(str(e)) from e
            raise BrokerAPIError(f\"Alpaca API error: {e}\") from e
    
    def cancel_order(self, order_id: str) -> Dict:
        \"\"\"Cancel pending order.\"\"\"
        if not self.connected or self.api is None:
            raise BrokerAPIError(\"Not connected to broker\")
        
        try:
            order = self.api.cancel_order(order_id)
            return {'order_id': order.id, 'status': order.status}
        
        except tradeapi.rest.APIError as e:
            if '404' in str(e):
                raise OrderNotFoundError(f\"Order {order_id} not found\") from e
            raise BrokerAPIError(f\"Alpaca API error: {e}\") from e
    
    def get_account(self) -> Dict:
        \"\"\"Get Alpaca account information.\"\"\"
        if not self.connected or self.api is None:
            raise BrokerAPIError(\"Not connected to broker\")
        
        account = self.api.get_account()
        
        return {
            'cash': float(account.cash),
            'equity': float(account.equity),
            'buying_power': float(account.buying_power),
            'portfolio_value': float(account.portfolio_value),
            'initial_margin': float(account.initial_margin),
            'maintenance_margin': float(account.maintenance_margin),
            'daytrade_count': int(account.daytrade_count)
        }
    
    def get_positions(self) -> List[Dict]:
        \"\"\"Get current Alpaca positions.\"\"\"
        if not self.connected or self.api is None:
            raise BrokerAPIError(\"Not connected to broker\")
        
        positions = self.api.list_positions()
        
        return [{
            'symbol': pos.symbol,
            'qty': int(pos.qty),
            'avg_entry_price': float(pos.avg_entry_price),
            'current_price': float(pos.current_price),
            'market_value': float(pos.market_value),
            'unrealized_pl': float(pos.unrealized_pl),
            'unrealized_plpc': float(pos.unrealized_plpc)
        } for pos in positions]
    
    def get_orders(
        self,
        status: Literal['open', 'closed', 'all'] = 'all',
        limit: int = 100
    ) -> List[Dict]:
        \"\"\"Get Alpaca orders.\"\"\"
        if not self.connected or self.api is None:
            raise BrokerAPIError(\"Not connected to broker\")
        
        orders = self.api.list_orders(status=status, limit=limit)
        
        return [{
            'order_id': order.id,
            'symbol': order.symbol,
            'qty': int(order.qty),
            'side': order.side,
            'order_type': order.type,
            'status': order.status,
            'filled_qty': int(order.filled_qty),
            'avg_fill_price': float(order.filled_avg_price) if order.filled_avg_price else None
        } for order in orders]
    
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Literal['1Min', '5Min', '15Min', '1H', '1D'] = '1D'
    ) -> pd.DataFrame:
        \"\"\"Get Alpaca historical bars.\"\"\"
        if not self.connected or self.api is None:
            raise BrokerAPIError(\"Not connected to broker\")
        
        bars = self.api.get_bars(
            symbol,
            timeframe,
            start=start.isoformat(),
            end=end.isoformat()
        ).df
        
        # Rename columns to standard format
        bars = bars.rename(columns={
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume'
        })
        
        return bars[['open', 'high', 'low', 'close', 'volume']]
    
    def is_market_open(self) -> bool:
        \"\"\"Check if US market is currently open.\"\"\"
        if not self.connected or self.api is None:
            raise BrokerAPIError(\"Not connected to broker\")
        
        clock = self.api.get_clock()
        return clock.is_open

================================================================================
3. tests/trading/test_alpaca_adapter.py (300 LOC)
================================================================================

\"\"\"
Tests for AlpacaAdapter.

Tests both successful operations and error handling.
Uses pytest fixtures and mocking.
\"\"\"

from __future__ import annotations
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import pandas as pd
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.broker_adapter import (
    BrokerAPIError,
    InsufficientFundsError,
    OrderNotFoundError
)


@pytest.fixture
def mock_alpaca_api():
    \"\"\"Mock Alpaca API.\"\"\"
    with patch('financial_analyzer.trading.alpaca_adapter.tradeapi.REST') as mock:
        yield mock


@pytest.fixture
def adapter(mock_alpaca_api):
    \"\"\"Create AlpacaAdapter with mocked API.\"\"\"
    adapter = AlpacaAdapter(
        api_key='test_key',
        secret_key='test_secret',
        mode='paper'
    )
    adapter.connect()
    return adapter


def test_connect_success(mock_alpaca_api):
    \"\"\"Test successful connection.\"\"\"
    adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
    adapter.connect()
    
    assert adapter.connected is True
    assert adapter.api is not None


def test_connect_failure(mock_alpaca_api):
    \"\"\"Test connection failure.\"\"\"
    mock_alpaca_api.side_effect = Exception(\"Connection failed\")
    
    adapter = AlpacaAdapter(api_key='key', secret_key='secret', mode='paper')
    
    with pytest.raises(BrokerAPIError, match=\"Failed to connect\"):
        adapter.connect()


def test_submit_market_order_success(adapter, mock_alpaca_api):
    \"\"\"Test successful market order submission.\"\"\"
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
    assert result['status'] == 'new'


def test_submit_order_insufficient_funds(adapter, mock_alpaca_api):
    \"\"\"Test order submission with insufficient funds.\"\"\"
    import alpaca_trade_api as tradeapi
    adapter.api.submit_order.side_effect = tradeapi.rest.APIError(\"Insufficient buying power\")
    
    with pytest.raises(InsufficientFundsError):
        adapter.submit_order('AAPL', qty=1000, side='buy')


def test_cancel_order_success(adapter, mock_alpaca_api):
    \"\"\"Test successful order cancellation.\"\"\"
    mock_order = Mock()
    mock_order.id = 'order_123'
    mock_order.status = 'canceled'
    
    adapter.api.cancel_order.return_value = mock_order
    
    result = adapter.cancel_order('order_123')
    
    assert result['order_id'] == 'order_123'
    assert result['status'] == 'canceled'


def test_cancel_order_not_found(adapter, mock_alpaca_api):
    \"\"\"Test cancel order not found.\"\"\"
    import alpaca_trade_api as tradeapi
    adapter.api.cancel_order.side_effect = tradeapi.rest.APIError(\"404 Not Found\")
    
    with pytest.raises(OrderNotFoundError):
        adapter.cancel_order('nonexistent_order')


def test_get_account(adapter, mock_alpaca_api):
    \"\"\"Test get account information.\"\"\"
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


def test_get_positions(adapter, mock_alpaca_api):
    \"\"\"Test get positions.\"\"\"
    mock_position = Mock()
    mock_position.symbol = 'AAPL'
    mock_position.qty = '10'
    mock_position.avg_entry_price = '150.50'
    mock_position.current_price = '155.00'
    mock_position.market_value = '1550.00'
    mock_position.unrealized_pl = '45.00'
    mock_position.unrealized_plpc = '0.0299'
    
    adapter.api.list_positions.return_value = [mock_position]
    
    result = adapter.get_positions()
    
    assert len(result) == 1
    assert result[0]['symbol'] == 'AAPL'
    assert result[0]['qty'] == 10
    assert result[0]['unrealized_pl'] == 45.00


def test_is_market_open_true(adapter, mock_alpaca_api):
    \"\"\"Test market open check (open).\"\"\"
    mock_clock = Mock()
    mock_clock.is_open = True
    
    adapter.api.get_clock.return_value = mock_clock
    
    assert adapter.is_market_open() is True


def test_is_market_open_false(adapter, mock_alpaca_api):
    \"\"\"Test market open check (closed).\"\"\"
    mock_clock = Mock()
    mock_clock.is_open = False
    
    adapter.api.get_clock.return_value = mock_clock
    
    assert adapter.is_market_open() is False

================================================================================
4. src/financial_analyzer/trading/ib_adapter.py (400 LOC) - OPTIONAL
================================================================================

\"\"\"
Interactive Brokers adapter (OPTIONAL - Phase 6.1b).

Uses ib_insync library for IB Gateway/TWS connection.
Implements BrokerAdapter interface.

Documentation: https://ib-insync.readthedocs.io/
\"\"\"

# Similar structure to AlpacaAdapter, but using ib_insync
# Can be implemented later if needed

from .broker_adapter import BrokerAdapter

class IBAdapter(BrokerAdapter):
    \"\"\"Interactive Brokers adapter (STUB - implement later).\"\"\"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raise NotImplementedError(\"IBAdapter not yet implemented. Use AlpacaAdapter.\")

================================================================================
5. tests/trading/test_ib_adapter.py (100 LOC) - OPTIONAL
================================================================================

\"\"\"
Tests for IBAdapter (STUB - implement when IBAdapter is ready).
\"\"\"

import pytest
from financial_analyzer.trading.ib_adapter import IBAdapter


def test_ib_adapter_not_implemented():
    \"\"\"Test that IBAdapter raises NotImplementedError.\"\"\"
    with pytest.raises(NotImplementedError):
        adapter = IBAdapter(api_key='key', secret_key='secret')

================================================================================
REQUIREMENTS
================================================================================

✅ Abstract BrokerAdapter base class (600 LOC)
✅ AlpacaAdapter implementation (400 LOC)
✅ Complete test coverage (300 LOC tests)
✅ Error handling (InsufficientFundsError, OrderNotFoundError, BrokerAPIError)
✅ Type hints complets
✅ Docstrings Google style
✅ Market/Limit orders
✅ Account info, positions, orders
✅ Historical bars
✅ Market open check
✅ Paper & Live mode support
✅ IBAdapter stub (optional, implement later)

CRITICAL:
- Use alpaca-trade-api SDK (pip install alpaca-trade-api)
- Handle all exceptions gracefully
- Mock tests (no real API calls in tests)
- Base URL: https://paper-api.alpaca.markets (paper), https://api.alpaca.markets (live)
```

---

**COPY CE PROMPT COMPLET À COPILOT MAINTENANT !** 🚀

**Temps estimé** : 3 jours (Copilot génère en 2-3h, puis tests/review 1 jour)

---

## ⏭️ NEXT STEPS

Après génération Phase 6.1 :
1. Review + correctifs (2-3h)
2. **Phase 6.2** : Account Monitor & Risk Guard (2 jours)
3. **Phase 6.3** : Live Pipeline Integration (2 jours)
4. **Phase 6.4** : Testing & Deployment (3 jours)

**Timeline total** : 10 jours → Paper trading opérationnel ! 🚀
