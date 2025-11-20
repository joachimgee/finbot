"""
Trading module for live and paper trading.

Provides broker adapters, order management, risk guards, and live pipeline integration.
"""

from financial_analyzer.trading.broker_adapter import (
    BrokerAdapter,
    BrokerAPIError,
    InsufficientFundsError,
    OrderNotFoundError
)
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.ib_adapter import IBAdapter
from financial_analyzer.trading.account_monitor import AccountMonitor
from financial_analyzer.trading.risk_guard import (
    RiskGuard,
    RiskLimitExceeded,
    CircuitBreakerTriggered,
    InvalidOrderError
)
from financial_analyzer.trading.live_trading_pipeline import (
    LiveTradingPipeline,
    TradingSchedule,
    create_demo_pipeline
)

__all__ = [
    'BrokerAdapter',
    'BrokerAPIError',
    'InsufficientFundsError',
    'OrderNotFoundError',
    'AlpacaAdapter',
    'IBAdapter',
    'AccountMonitor',
    'RiskGuard',
    'RiskLimitExceeded',
    'CircuitBreakerTriggered',
    'InvalidOrderError',
    'LiveTradingPipeline',
    'TradingSchedule',
    'create_demo_pipeline'
]
