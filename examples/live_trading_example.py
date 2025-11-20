"""
Phase 6.3 Live Trading Pipeline Example.

Demonstrates:
- Initialize LiveTradingPipeline with Alpaca Paper Trading
- Configure risk limits
- Run manual execution
- Display results
- Show status and metrics
"""

import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from financial_analyzer.trading import (
    AlpacaAdapter,
    LiveTradingPipeline,
    TradingSchedule
)


def print_section(title: str):
    """Print section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def main():
    """Run live trading pipeline example."""
    
    print_section("Phase 6.3: Live Trading Pipeline Example")
    
    # Check for API keys
    api_key = os.getenv('ALPACA_API_KEY')
    api_secret = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not api_secret:
        print("⚠️  WARNING: Alpaca API credentials not found in environment")
        print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY to run with real broker")
        print("\nThis example demonstrates the expected workflow.\n")
        
        print("Expected Workflow:")
        print("1. Connect to Alpaca Paper Trading")
        print("2. Initialize LiveTradingPipeline")
        print("3. Configure risk limits and schedule")
        print("4. Run pipeline execution:")
        print("   - Fetch market data (60 days historical)")
        print("   - Generate signals (ML models / indicators)")
        print("   - Optimize portfolio (target weights)")
        print("   - Generate orders (buy/sell)")
        print("   - Validate with RiskGuard")
        print("   - Execute orders via broker")
        print("   - Update AccountMonitor")
        print("5. Display results and metrics")
        
        return
    
    # Step 1: Connect to broker
    print_section("Step 1: Connect to Alpaca Paper Trading")
    print("Initializing Alpaca adapter...")
    
    try:
        broker = AlpacaAdapter(
            api_key=api_key,
            secret_key=api_secret,
            mode='paper'
        )
        
        if not broker.connected:
            print("✗ Failed to connect to broker")
            return
        
        print(f"✓ Connected to Alpaca (paper trading)")
        print(f"✓ Account ID: {broker.account_id}")
        
        # Get account info
        account = broker.get_account()
        print(f"✓ Portfolio Value: ${float(account['portfolio_value']):,.2f}")
        print(f"✓ Cash: ${float(account['cash']):,.2f}")
        print(f"✓ Buying Power: ${float(account['buying_power']):,.2f}")
        
    except Exception as e:
        print(f"✗ Error connecting to broker: {e}")
        return
    
    # Step 2: Initialize pipeline
    print_section("Step 2: Initialize Live Trading Pipeline")
    
    # Define tickers
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
    print(f"Tickers: {', '.join(tickers)}")
    
    # Custom risk config (more conservative)
    risk_config = {
        'max_position_size': 20000.0,      # $20k max per position
        'max_position_pct': 0.15,          # 15% max concentration
        'max_total_positions': 10,         # Max 10 positions
        'max_drawdown': -0.10,             # 10% drawdown limit
        'max_daily_loss': 1000.0,          # $1k daily loss limit
        'max_leverage': 1.5,               # 1.5x leverage max
        'enable_circuit_breaker': True
    }
    
    print("\nRisk Configuration:")
    print(f"  Max Position Size: ${risk_config['max_position_size']:,.0f}")
    print(f"  Max Concentration: {risk_config['max_position_pct']:.0%}")
    print(f"  Max Positions: {risk_config['max_total_positions']}")
    print(f"  Drawdown Limit: {risk_config['max_drawdown']:.0%}")
    print(f"  Daily Loss Limit: ${risk_config['max_daily_loss']:,.0f}")
    print(f"  Max Leverage: {risk_config['max_leverage']:.1f}x")
    
    # Schedule config
    schedule = TradingSchedule(
        execution_time="09:35",
        frequency='daily',
        enabled=True
    )
    
    print(f"\nSchedule: {schedule.frequency} at {schedule.execution_time} ET")
    
    # Initialize pipeline
    try:
        pipeline = LiveTradingPipeline(
            broker_adapter=broker,
            tickers=tickers,
            initial_capital=float(account['portfolio_value']),
            strategy='factor_ensemble',
            risk_config=risk_config,
            schedule_config=schedule,
            enable_logging=True
        )
        
        print("\n✓ Pipeline initialized successfully")
        
    except Exception as e:
        print(f"✗ Error initializing pipeline: {e}")
        return
    
    # Step 3: Display current status
    print_section("Step 3: Current Portfolio & Risk Status")
    
    status = pipeline.get_status()
    
    print("Portfolio:")
    portfolio = status['portfolio']
    print(f"  Value: ${portfolio['portfolio_value']:,.2f}")
    print(f"  Cash: ${portfolio['cash']:,.2f}")
    print(f"  Daily P&L: ${portfolio['daily_pnl']:+,.2f}")
    print(f"  Positions: {portfolio['num_positions']}")
    
    print("\nRisk Status:")
    risk = status['risk']
    print(f"  Position Count: {risk['position_count']['current']}/{risk['position_count']['max']}")
    print(f"  Leverage: {risk['leverage']['current']:.2f}x / {risk['leverage']['max']:.1f}x")
    print(f"  Drawdown: {risk['drawdown']['current']:+.2%} (limit: {risk['drawdown']['max']:+.2%})")
    print(f"  Circuit Breaker: {'ACTIVE ⚠️' if status['circuit_breaker_active'] else 'OK ✓'}")
    
    # Step 4: Check market status
    print_section("Step 4: Check Market Status")
    
    if broker.is_market_open():
        print("✓ Market is OPEN")
    else:
        print("⚠️  Market is CLOSED")
        print("\nNote: Pipeline will skip execution when market is closed.")
        print("Use force=True to test pipeline logic even when market is closed.")
    
    # Step 5: Run pipeline (manual execution)
    print_section("Step 5: Execute Pipeline (Manual)")
    
    print("Executing pipeline with force=True...")
    print("(This forces execution regardless of market hours and schedule)\n")
    
    try:
        result = pipeline.run(force=True)
        
        print(f"Status: {result['status'].upper()}")
        
        if result['status'] == 'success':
            print(f"✓ Execution successful!\n")
            print(f"Orders Generated: {result.get('orders_generated', 0)}")
            print(f"Orders Executed: {result.get('orders_executed', 0)}")
            print(f"Orders Rejected: {result.get('orders_rejected', 0)}")
            
            # Show execution details
            if 'execution_results' in result:
                print("\nExecution Details:")
                for i, exec_result in enumerate(result['execution_results'], 1):
                    order = exec_result['order']
                    print(f"\n  Order {i}:")
                    print(f"    Symbol: {order['symbol']}")
                    print(f"    Side: {order['side'].upper()}")
                    print(f"    Qty: {order['qty']}")
                    print(f"    Price: ${order['price']:.2f}")
                    print(f"    Status: {exec_result['status'].upper()}")
                    
                    if exec_result['status'] == 'rejected':
                        print(f"    Reason: {exec_result.get('reason', 'Unknown')}")
        
        elif result['status'] == 'skipped':
            print(f"⚠️  Execution skipped: {result['reason']}")
        
        elif result['status'] == 'failed':
            print(f"✗ Execution failed: {result['reason']}")
        
        print(f"\nPortfolio Value: ${result['portfolio_value']:,.2f}")
        print(f"Daily P&L: ${result['daily_pnl']:+,.2f}")
        print(f"Positions: {result['num_positions']}")
        
    except Exception as e:
        print(f"✗ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 6: Show final status
    print_section("Step 6: Final Status")
    
    final_status = pipeline.get_status()
    
    print(f"Last Execution: {final_status['last_execution']}")
    print(f"Total Executions: {final_status['num_executions']}")
    
    print("\nFinal Portfolio:")
    portfolio = final_status['portfolio']
    print(f"  Value: ${portfolio['portfolio_value']:,.2f}")
    print(f"  Daily P&L: ${portfolio['daily_pnl']:+,.2f}")
    print(f"  Positions: {portfolio['num_positions']}")
    
    if portfolio['positions']:
        print("\n  Current Positions:")
        for pos in portfolio['positions']:
            print(f"    {pos['symbol']}: {pos['qty']} shares @ ${pos['current_price']:.2f} "
                  f"(P&L: ${pos['unrealized_pl']:+,.2f})")
    
    # Summary
    print_section("Summary")
    print("Phase 6.3 Live Trading Pipeline Demo Complete!")
    print("\n✅ Successfully demonstrated:")
    print("  • BrokerAdapter connection (Alpaca Paper)")
    print("  • LiveTradingPipeline initialization")
    print("  • Risk configuration")
    print("  • Pipeline execution flow")
    print("  • Order generation and validation")
    print("  • Risk guard integration")
    print("  • Portfolio tracking")
    
    print("\n📝 Next Steps:")
    print("  • Integrate real ML models for signal generation")
    print("  • Add Riskfolio-Lib for portfolio optimization")
    print("  • Set up scheduled execution (cron job)")
    print("  • Monitor with logging and metrics")
    print("  • Paper trade for 30 days validation")


if __name__ == '__main__':
    main()
