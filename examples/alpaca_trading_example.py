"""
Example: Using AlpacaAdapter for paper trading.

This example demonstrates how to use AlpacaAdapter to:
1. Connect to Alpaca paper trading
2. Check account information
3. Submit orders
4. Check positions
5. Get market data

Prerequisites:
    - Alpaca paper trading account (free): https://alpaca.markets/
    - Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env file
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.utils.helpers import get_logger

# Load environment variables
load_dotenv()

# Setup logger
logger = get_logger(__name__)


def main():
    """
    Main example function demonstrating AlpacaAdapter usage.
    """
    # Get API credentials from environment
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    mode = os.getenv('BROKER_MODE', 'paper')
    
    if not api_key or not secret_key:
        logger.error(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env file.\n"
            "Get your keys from: https://alpaca.markets/"
        )
        return
    
    logger.info("=" * 80)
    logger.info("ALPACA PAPER TRADING EXAMPLE")
    logger.info("=" * 80)
    
    # Initialize adapter
    adapter = AlpacaAdapter(
        api_key=api_key,
        secret_key=secret_key,
        mode=mode
    )
    
    try:
        # 1. Connect to Alpaca
        logger.info("\n1. Connecting to Alpaca...")
        adapter.connect()
        logger.info("✓ Connected successfully!")
        
        # 2. Check if market is open
        logger.info("\n2. Checking market status...")
        is_open = adapter.is_market_open()
        logger.info(f"Market is {'OPEN' if is_open else 'CLOSED'}")
        
        # 3. Get account information
        logger.info("\n3. Fetching account information...")
        account = adapter.get_account()
        logger.info(f"Cash: ${account['cash']:,.2f}")
        logger.info(f"Equity: ${account['equity']:,.2f}")
        logger.info(f"Buying Power: ${account['buying_power']:,.2f}")
        logger.info(f"Portfolio Value: ${account['portfolio_value']:,.2f}")
        logger.info(f"Day Trade Count: {account['daytrade_count']}")
        
        # 4. Get current positions
        logger.info("\n4. Fetching current positions...")
        positions = adapter.get_positions()
        if positions:
            logger.info(f"Current positions ({len(positions)}):")
            for pos in positions:
                logger.info(
                    f"  {pos['symbol']}: {pos['qty']} shares @ ${pos['current_price']:.2f} "
                    f"(P&L: ${pos['unrealized_pl']:.2f}, {pos['unrealized_plpc']*100:.2f}%)"
                )
        else:
            logger.info("No current positions")
        
        # 5. Get open orders
        logger.info("\n5. Fetching open orders...")
        open_orders = adapter.get_orders(status='open')
        if open_orders:
            logger.info(f"Open orders ({len(open_orders)}):")
            for order in open_orders:
                logger.info(
                    f"  {order['symbol']}: {order['side']} {order['qty']} @ {order['order_type']} "
                    f"(status: {order['status']})"
                )
        else:
            logger.info("No open orders")
        
        # 6. Get historical bars
        logger.info("\n6. Fetching historical data for AAPL...")
        end = datetime.now()
        start = end - timedelta(days=5)
        bars = adapter.get_bars('AAPL', start, end, timeframe='1D')
        logger.info(f"Fetched {len(bars)} bars:")
        logger.info(f"\n{bars.tail()}")
        
        # 7. Submit a test order (COMMENTED OUT - uncomment to test)
        # WARNING: This will submit a real order in paper trading mode!
        """
        if is_open:
            logger.info("\n7. Submitting test market order...")
            order = adapter.submit_order(
                symbol='AAPL',
                qty=1,
                side='buy',
                order_type='market'
            )
            logger.info(f"✓ Order submitted: {order['order_id']}")
            logger.info(f"  Symbol: {order['symbol']}")
            logger.info(f"  Qty: {order['qty']}")
            logger.info(f"  Side: {order['side']}")
            logger.info(f"  Status: {order['status']}")
            
            # Cancel the order (if still open)
            if order['status'] in ['new', 'pending_new', 'accepted']:
                logger.info(f"\n8. Canceling order {order['order_id']}...")
                result = adapter.cancel_order(order['order_id'])
                logger.info(f"✓ Order canceled: {result['status']}")
        else:
            logger.info("\n7. Market is closed, skipping order submission test")
        """
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    
    finally:
        # Disconnect
        logger.info("\nDisconnecting...")
        adapter.disconnect()
        logger.info("✓ Disconnected")
    
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE COMPLETED")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
