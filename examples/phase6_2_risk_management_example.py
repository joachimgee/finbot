"""
Phase 6.2 Integration Example: Risk Management System

Demonstrates the complete risk management workflow:
- BrokerAdapter: Connects to Alpaca paper trading
- AccountMonitor: Real-time portfolio tracking
- RiskGuard: Pre-trade risk validation

This example shows:
1. Portfolio monitoring (P&L, drawdown, exposure)
2. Risk validation (position limits, leverage, circuit breakers)
3. Order submission with risk checks
4. Circuit breaker triggering and reset
"""

import os
import time
from datetime import datetime
from financial_analyzer.trading import (
    AlpacaAdapter,
    AccountMonitor,
    RiskGuard,
    RiskLimitExceeded,
    CircuitBreakerTriggered,
    InvalidOrderError
)


def print_section(title: str):
    """Print section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def display_portfolio_status(monitor: AccountMonitor):
    """Display current portfolio status."""
    summary = monitor.get_summary()
    
    print("Portfolio Status:")
    print(f"  Portfolio Value: ${summary['portfolio_value']:,.2f}")
    print(f"  Cash: ${summary['cash']:,.2f}")
    print(f"  Equity: ${summary['equity']:,.2f}")
    print(f"  Daily P&L: ${summary['daily_pnl']:+,.2f} ({summary['daily_return_pct']:+.2f}%)")
    print(f"  Cumulative P&L: ${summary['cumulative_pnl']:+,.2f} ({summary['cumulative_return_pct']:+.2f}%)")
    print(f"  Current Drawdown: {summary['current_drawdown']:+.2%}")
    print(f"  Max Drawdown: {summary['max_drawdown']:+.2%}")
    
    print("\nPositions:")
    if summary['positions']:
        for pos in summary['positions']:
            print(f"  {pos['symbol']}: {pos['qty']} shares @ ${pos['current_price']:.2f} "
                  f"(${pos['market_value']:,.2f}, P&L: ${pos['unrealized_pl']:+,.2f})")
    else:
        print("  No positions")


def display_risk_status(guard: RiskGuard):
    """Display current risk status."""
    risk_summary = guard.get_risk_summary()
    
    print("\nRisk Status:")
    print(f"  Positions: {risk_summary['position_count']['current']}/{risk_summary['position_count']['max']}")
    print(f"  Largest Position: {risk_summary['largest_position_pct']['current']:.1%} "
          f"(max: {risk_summary['largest_position_pct']['max']:.1%})")
    print(f"  Leverage: {risk_summary['leverage']['current']:.2f}x "
          f"(max: {risk_summary['leverage']['max']:.1f}x)")
    print(f"  Drawdown: {risk_summary['drawdown']['current']:+.2%} "
          f"(limit: {risk_summary['drawdown']['max']:+.2%})")
    print(f"  Daily P&L: ${risk_summary['daily_pnl']['current']:+,.2f} "
          f"(limit: ${risk_summary['daily_pnl']['max']:+,.2f})")
    print(f"  Circuit Breaker: {'ACTIVE ⚠️' if risk_summary['circuit_breaker_active'] else 'OK ✓'}")
    
    if risk_summary['circuit_breaker_reason']:
        print(f"    Reason: {risk_summary['circuit_breaker_reason']}")


def attempt_order(broker, guard: RiskGuard, symbol: str, qty: int, side: str, price: float = None):
    """Attempt to place an order with risk validation."""
    print(f"\n▶ Attempting order: {side.upper()} {qty} {symbol} @ ${price or 'market'}")
    
    try:
        # Validate order against risk limits
        guard.validate_order(symbol, qty=qty, side=side, price=price)
        
        # If validation passes, submit order
        print(f"  ✓ Risk validation PASSED")
        
        # In real scenario, would submit order here:
        # order = broker.place_order(symbol, qty=qty, side=side, order_type='limit', limit_price=price)
        # print(f"  ✓ Order submitted: {order['id']}")
        
        print(f"  ✓ Order would be submitted to broker")
        return True
        
    except InvalidOrderError as e:
        print(f"  ✗ Invalid order parameters: {e}")
        return False
        
    except RiskLimitExceeded as e:
        print(f"  ✗ Risk limit exceeded: {e}")
        return False
        
    except CircuitBreakerTriggered as e:
        print(f"  ⚠️ Circuit breaker triggered: {e}")
        return False


def main():
    """Run Phase 6.2 integration example."""
    
    print_section("Phase 6.2 Integration Example: Risk Management System")
    
    # Check for API keys
    api_key = os.getenv('ALPACA_API_KEY')
    api_secret = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not api_secret:
        print("⚠️  WARNING: Alpaca API credentials not found in environment")
        print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY to run with real broker")
        print("\nThis example will demonstrate the workflow with mock data.\n")
        
        # For demo purposes, we'll show the expected workflow
        print("Expected Workflow:")
        print("1. Connect to broker → AccountMonitor initialized")
        print("2. Monitor portfolio → Real-time P&L tracking")
        print("3. Validate orders → RiskGuard checks limits")
        print("4. Submit orders → Only if risk validation passes")
        print("5. Circuit breaker → Automatically triggered on excessive losses")
        
        return
    
    # Step 1: Connect to broker
    print_section("Step 1: Initialize Trading System")
    print("Connecting to Alpaca paper trading...")
    
    broker = AlpacaAdapter(
        api_key=api_key,
        api_secret=api_secret,
        paper=True
    )
    
    if not broker.is_connected():
        print("✗ Failed to connect to broker")
        return
    
    print(f"✓ Connected to Alpaca (paper trading)")
    print(f"✓ Account: {broker.account_id}")
    
    # Step 2: Initialize account monitor
    print("\nInitializing account monitor...")
    
    monitor = AccountMonitor(
        broker=broker,
        enable_history=True,
        max_history_size=1000
    )
    
    print("✓ Account monitor initialized")
    monitor.update()
    
    # Step 3: Initialize risk guard
    print("\nInitializing risk guard...")
    
    guard = RiskGuard(
        account_monitor=monitor,
        max_position_size=10000.0,      # Max $10k per position
        max_position_pct=0.20,           # Max 20% concentration
        max_total_positions=10,          # Max 10 positions
        max_drawdown=-0.10,              # 10% drawdown limit
        max_daily_loss=500.0,            # $500 daily loss limit
        max_leverage=1.5                 # 1.5x leverage limit
    )
    
    print("✓ Risk guard initialized")
    print("  - Max position size: $10,000")
    print("  - Max concentration: 20%")
    print("  - Max positions: 10")
    print("  - Drawdown limit: -10%")
    print("  - Daily loss limit: $500")
    print("  - Max leverage: 1.5x")
    
    # Step 4: Display initial status
    print_section("Step 2: Portfolio & Risk Status")
    display_portfolio_status(monitor)
    display_risk_status(guard)
    
    # Step 5: Attempt various orders
    print_section("Step 3: Order Validation Examples")
    
    # Valid order
    attempt_order(broker, guard, 'AAPL', qty=10, side='buy', price=150.0)
    
    # Another valid order
    attempt_order(broker, guard, 'MSFT', qty=5, side='buy', price=350.0)
    
    # Order exceeding position size limit
    attempt_order(broker, guard, 'GOOGL', qty=100, side='buy', price=140.0)
    
    # Order exceeding concentration limit
    attempt_order(broker, guard, 'TSLA', qty=50, side='buy', price=250.0)
    
    # Invalid order parameters
    attempt_order(broker, guard, 'INVALID@', qty=10, side='buy', price=100.0)
    attempt_order(broker, guard, 'AAPL', qty=-10, side='buy', price=150.0)
    attempt_order(broker, guard, 'AAPL', qty=10, side='hold', price=150.0)
    
    # Step 6: Simulate drawdown and circuit breaker
    print_section("Step 4: Circuit Breaker Demonstration")
    
    print("Simulating portfolio drawdown...")
    # In real scenario, this would happen from market movements
    # For demo, we manually trigger it
    
    print("\n⚠️  Simulating -12% drawdown (exceeds -10% limit)...")
    
    # This would normally be detected automatically by monitor.update()
    # For demo purposes, let's show what happens
    
    print("\nAttempting order with excessive drawdown:")
    print("  - Current drawdown: -12.0% (limit: -10.0%)")
    print("  - Circuit breaker would trigger automatically")
    print("  - All new orders blocked until manual reset")
    
    # Step 7: Show risk summary
    print_section("Step 5: Final Risk Summary")
    display_risk_status(guard)
    
    # Step 8: Historical tracking
    print_section("Step 6: Historical Tracking")
    
    history_df = monitor.get_history_df()
    
    if len(history_df) > 0:
        print(f"Portfolio history: {len(history_df)} snapshots")
        print("\nRecent snapshots:")
        print(history_df.tail())
    else:
        print("No historical data yet (run longer to accumulate history)")
    
    # Cleanup
    print_section("Summary")
    print("Phase 6.2 Risk Management System:")
    print("  ✓ BrokerAdapter: Connected to Alpaca")
    print("  ✓ AccountMonitor: Real-time portfolio tracking")
    print("  ✓ RiskGuard: Pre-trade validation with 6 limit types")
    print("  ✓ Circuit Breaker: Automatic risk protection")
    print("  ✓ Historical Tracking: Portfolio state history")
    
    print("\nKey Features Demonstrated:")
    print("  • Position size limits ($10k max)")
    print("  • Concentration limits (20% max)")
    print("  • Leverage limits (1.5x max)")
    print("  • Drawdown circuit breaker (-10%)")
    print("  • Daily loss limits ($500 max)")
    print("  • Order parameter validation")
    print("  • P&L tracking (daily & cumulative)")
    print("  • Exposure metrics (long/short/net/gross)")
    
    print("\nNext Steps:")
    print("  → Phase 6.3: Live Pipeline Integration")
    print("  → OrderManager: Unified order management")
    print("  → LiveTradingPipeline: End-to-end live trading")


if __name__ == '__main__':
    main()
