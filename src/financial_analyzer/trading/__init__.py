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
from financial_analyzer.trading.order_gateway import OrderGateway
from financial_analyzer.trading.journal import TradingJournal
from financial_analyzer.trading.reconciliation import (
    ReconciliationReport,
    reconcile_orders,
)
from financial_analyzer.trading.run_manifest import build_run_manifest
from financial_analyzer.trading.safety import (
    LiveTradingNotEnabledError,
    TradingMode,
    assert_live_allowed,
    live_trading_enabled,
    resolve_trading_mode,
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
    'create_demo_pipeline',
    'OrderGateway',
    'TradingJournal',
    'ReconciliationReport',
    'reconcile_orders',
    'build_run_manifest',
    'TradingMode',
    'LiveTradingNotEnabledError',
    'assert_live_allowed',
    'live_trading_enabled',
    'resolve_trading_mode',
]
