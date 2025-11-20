"""
Interactive Brokers adapter (OPTIONAL - Phase 6.1b).

Uses ib_insync library for IB Gateway/TWS connection.
Implements BrokerAdapter interface.

Documentation: https://ib-insync.readthedocs.io/

Note: This is a stub implementation. IBAdapter can be implemented later if needed.
      For now, use AlpacaAdapter for paper/live trading.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Literal
from datetime import datetime
import pandas as pd
from financial_analyzer.trading.broker_adapter import BrokerAdapter
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class IBAdapter(BrokerAdapter):
    """
    Interactive Brokers adapter (STUB - implement later).
    
    This is a placeholder implementation. Use AlpacaAdapter for now.
    
    To implement:
        1. Install ib_insync: pip install ib_insync
        2. Implement all abstract methods from BrokerAdapter
        3. Connect to IB Gateway or TWS
        4. Test with paper trading account
    
    Example:
        >>> adapter = IBAdapter(api_key='key', secret_key='secret')
        Traceback (most recent call last):
            ...
        NotImplementedError: IBAdapter not yet implemented. Use AlpacaAdapter.
    
    Raises:
        NotImplementedError: Always raised (not yet implemented)
    """
    
    def __init__(
        self,
        api_key: str = '',
        secret_key: str = '',
        mode: Literal['paper', 'live'] = 'paper',
        base_url: Optional[str] = None,
        host: str = '127.0.0.1',
        port: int = 7497,
        client_id: int = 1
    ) -> None:
        """
        Initialize IB adapter (STUB).
        
        Args:
            api_key: Not used (IB doesn't use API keys)
            secret_key: Not used (IB doesn't use API keys)
            mode: 'paper' or 'live'
            base_url: Not used
            host: IB Gateway/TWS host (default: 127.0.0.1)
            port: IB Gateway/TWS port (default: 7497 for paper, 7496 for live)
            client_id: Client ID (default: 1)
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        super().__init__(api_key, secret_key, mode, base_url)
        
        self.host = host
        self.port = port
        self.client_id = client_id
        
        logger.warning(
            "IBAdapter is not yet implemented. "
            "Use AlpacaAdapter for paper/live trading."
        )
        
        raise NotImplementedError(
            "IBAdapter not yet implemented. Use AlpacaAdapter.\n\n"
            "To implement IBAdapter:\n"
            "1. pip install ib_insync\n"
            "2. Implement all abstract methods\n"
            "3. Connect to IB Gateway/TWS\n"
            "4. Test with paper account"
        )
    
    def connect(self) -> None:
        """
        Establish connection to IB (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
    def disconnect(self) -> None:
        """
        Close connection to IB (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
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
        Submit order to IB (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel pending order (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
    def get_account(self) -> Dict:
        """
        Get account information (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
    def get_positions(self) -> List[Dict]:
        """
        Get current positions (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
    def get_orders(
        self,
        status: Literal['open', 'closed', 'all'] = 'all',
        limit: int = 100
    ) -> List[Dict]:
        """
        Get orders (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: Literal['1Min', '5Min', '15Min', '1H', '1D'] = '1D'
    ) -> pd.DataFrame:
        """
        Get historical bars (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
    
    def is_market_open(self) -> bool:
        """
        Check if market is currently open (STUB).
        
        Raises:
            NotImplementedError: Always raised (not yet implemented)
        """
        raise NotImplementedError("IBAdapter not yet implemented")
