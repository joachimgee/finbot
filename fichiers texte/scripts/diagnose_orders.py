"""
Comprehensive order execution diagnosis script.

Helps debug why orders are not being generated or executed.
"""
from __future__ import annotations
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Setup logging
LOG_PATH = Path('logs')
LOG_PATH.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH / 'diagnose_orders.log')
    ]
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SEPARATOR = "=" * 80


def check_env_vars():
    """Check all required environment variables."""
    print("\n" + SEPARATOR)
    print("1️⃣  ENVIRONMENT VARIABLES CHECK")
    print(SEPARATOR)

    required_vars = ['ALPACA_API_KEY', 'ALPACA_SECRET_KEY']
    optional_vars = ['NEWS_API_KEY', 'FINNHUB_API_KEY']

    issues = []

    # Check required
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            print(f"❌ {var}: NOT SET")
            issues.append(f"Missing {var}")
        else:
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"✅ {var}: {masked}")

    # Check optional
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: SET")
        else:
            print(f"⚠️  {var}: NOT SET (optional)")

    return issues


def check_broker_connection():
    """Check broker connection status."""
    print("\n" + SEPARATOR)
    print("2️⃣  BROKER CONNECTION CHECK")
    print(SEPARATOR)

    try:
        from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_SECRET_KEY')

        if not api_key or not api_secret:
            print("❌ Missing credentials, skipping connection test")
            return False

        adapter = AlpacaAdapter(
            api_key=api_key,
            secret_key=api_secret,
            mode='paper'
        )

        if not adapter.connected:
            adapter.connect()

        if adapter.connected:
            print(f"✅ Connected to Alpaca (paper mode)")

            try:
                account = adapter.get_account()
                print(f"   Portfolio Value: ${account['portfolio_value']:,.2f}")
                print(f"   Cash: ${account['cash']:,.2f}")
                print(f"   Buying Power: ${account['buying_power']:,.2f}")
                return True
            except Exception as e:
                print(f"⚠️  Connected but failed to get account: {e}")
                return False
        else:
            print("❌ Not connected to Alpaca")
            return False

    except Exception as e:
        print(f"❌ Connection error: {e}")
        logger.exception("Broker connection failed")
        return False


def check_market_hours():
    """Check if market is open."""
    print("\n" + SEPARATOR)
    print("3️⃣  MARKET HOURS CHECK")
    print(SEPARATOR)

    try:
        from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_SECRET_KEY')

        if not api_key or not api_secret:
            print("❌ Missing credentials")
            return

        adapter = AlpacaAdapter(
            api_key=api_key,
            secret_key=api_secret,
            mode='paper'
        )
        if not adapter.connected:
            adapter.connect()

        is_open = adapter.is_market_open()

        now = datetime.now()
        day_name = now.strftime("%A")
        time_str = now.strftime("%H:%M:%S ET")

        print(f"Current: {day_name} {time_str}")

        if is_open:
            print(f"✅ Market is OPEN")
        else:
            print(f"❌ Market is CLOSED")
            print(f"   Market hours: 09:30-16:00 ET, Monday-Friday")
            print(f"   To test anyway, use: --force flag")

    except Exception as e:
        print(f"⚠️  Failed to check market hours: {e}")


def analyze_data_fetching():
    """Check data fetching step-by-step."""
    print("\n" + SEPARATOR)
    print("5️⃣  DATA FETCHING ANALYSIS")
    print(SEPARATOR)

    try:
        from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_SECRET_KEY')

        if not api_key or not api_secret:
            print("❌ Missing credentials")
            return

        adapter = AlpacaAdapter(
            api_key=api_key,
            secret_key=api_secret,
            mode='paper'
        )
        if not adapter.connected:
            adapter.connect()

        tickers = ['AAPL', 'MSFT', 'GOOGL']
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)

        print(f"Fetching 60-day history for {tickers}...")

        for ticker in tickers:
            try:
                df = adapter.get_bars(
                    symbol=ticker,
                    start=start_date,
                    end=end_date,
                    timeframe='1D'
                )

                if not df.empty:
                    latest_close = df['close'].iloc[-1]
                    print(f"✅ {ticker}: {len(df)} bars, latest: ${latest_close:.2f}")
                else:
                    print(f"❌ {ticker}: No data returned")

            except Exception as e:
                print(f"❌ {ticker}: Error - {e}")

    except Exception as e:
        print(f"❌ Data fetching error: {e}")
        logger.exception("Data fetching failed")


def check_pipeline_execution():
    """Test actual pipeline execution."""
    print("\n" + SEPARATOR)
    print("4️⃣  PIPELINE EXECUTION CHECK")
    print(SEPARATOR)

    try:
        from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
        from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline

        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_SECRET_KEY')

        if not api_key or not api_secret:
            print("❌ Missing credentials")
            return None

        print("Creating pipeline...")
        adapter = AlpacaAdapter(
            api_key=api_key,
            secret_key=api_secret,
            mode='paper'
        )
        if not adapter.connected:
            adapter.connect()

        pipeline = LiveTradingPipeline(
            broker_adapter=adapter,
            tickers=['AAPL', 'MSFT', 'GOOGL'],
            initial_capital=100000.0
        )

        print("Running pipeline (force mode)...")
        result = pipeline.run(force=True)

        # Early check for skipped status
        if result.get('status') == 'skipped':
            print(f"\n⚠️  Pipeline skipped: {result.get('reason')}")
            print("   No orders attempted")
            return result

        print(f"\n📊 EXECUTION RESULT:")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Orders Generated: {result.get('orders_generated', 0)}")
        print(f"   Orders Executed: {result.get('orders_executed', 0)}")
        print(f"   Orders Rejected: {result.get('orders_rejected', 0)}")
        print(f"   Portfolio Value: ${result.get('portfolio_value', 0):,.2f}")

        if result.get('reason'):
            print(f"   Reason: {result['reason']}")

        if result['orders_generated'] == 0:
            print("\n❌ PROBLEM: No orders generated!")
            print("   → Check: Signals might be too weak")
            print("   → Solution: Lower momentum threshold or check data")

        if result['orders_generated'] > 0 and result['orders_executed'] == 0:
            print("\n❌ PROBLEM: Orders rejected by risk guard!")
            print("   → Check: Risk limits might be too strict")
            print("   → Solution: Use conservative.yaml config")

        if result['orders_executed'] > 0:
            print("\n✅ SUCCESS: Orders executed!")
            print("   Check Alpaca dashboard for details")

        return result

    except Exception as e:
        print(f"❌ Pipeline execution error: {e}")
        logger.exception("Pipeline execution failed")
        return None


def summarize(pipeline_result, env_issues, broker_ok):
    print("\n" + SEPARATOR)
    print("📋 DIAGNOSTIC SUMMARY")
    print(SEPARATOR)

    if env_issues:
        print("\n❌ ENV ISSUES:")
        for issue in env_issues:
            print(f"   - {issue}")
        print("\n   FIX: Set variables in .env file")
    else:
        print("\n✅ Environment OK")

    if not broker_ok:
        print("\n❌ Broker connection failed")
        print("   FIX: Check API credentials in .env")
    else:
        print("\n✅ Broker OK")

    if pipeline_result and pipeline_result.get('orders_generated', 0) == 0:
        print("\n⚠️  NO ORDERS GENERATED")
        print("   POTENTIAL CAUSES:")
        print("   1. Signals too weak (momentum calculation)")
        print("   2. Not enough data (< 60 days)")
        print("   3. Market closed (use --force)")
        print("\n   FIX: Check logs, adjust strategy")

    if pipeline_result and pipeline_result.get('orders_rejected', 0) > pipeline_result.get('orders_executed', 0):
        print("\n⚠️  ORDERS BEING REJECTED BY RISK GUARD")
        print("   Use: python scripts/run_live_trading.py \\")
        print("        --config config/live_trading_conservative.yaml")

    print("\n" + SEPARATOR)
    print("✅ DIAGNOSTIC COMPLETE")
    print(SEPARATOR + "\n")


def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "ORDER EXECUTION DIAGNOSTICS" + " "*31 + "║")
    print("╚" + "="*78 + "╝")

    env_issues = check_env_vars()
    broker_ok = check_broker_connection()
    check_market_hours()
    analyze_data_fetching()
    pipeline_result = check_pipeline_execution()
    summarize(pipeline_result, env_issues, broker_ok)


if __name__ == '__main__':
    main()
