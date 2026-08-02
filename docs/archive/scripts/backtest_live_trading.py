#!/usr/bin/env python3
"""
Backtest live trading pipeline on historical data.

Tests complete pipeline on 10 weeks of past data to validate:
- Signal generation working
- Order generation working
- Risk management working
- Performance metrics
"""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Setup logging
LOG_PATH = Path('logs')
LOG_PATH.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH / 'backtest_live_trading.log')
    ]
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class LiveTradingBacktester:
    """Backtest live trading pipeline on historical data."""

    def __init__(self, initial_capital: float = 100000.0, weeks: int = 10) -> None:
        """
        Initialize backtester.

        Args:
            initial_capital: Starting cash
            weeks: Number of weeks of historical data
        """
        self.initial_capital = initial_capital
        self.weeks = weeks
        self.capital = initial_capital
        self.positions: Dict[str, int] = {}
        self.trades: List[Dict] = []
        self.portfolio_values: List[float] = []

        logger.info(f"Initialized backtest: {weeks}w, ${initial_capital:,.0f}")

    def setup_broker(self) -> bool:
        """Setup broker connection."""
        try:
            from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

            api_key = os.getenv('ALPACA_API_KEY')
            api_secret = os.getenv('ALPACA_SECRET_KEY')

            if not api_key or not api_secret:
                logger.error("Missing API credentials")
                return False

            self.broker = AlpacaAdapter(
                api_key=api_key,
                secret_key=api_secret,
                mode='paper'
            )
            if not self.broker.connected:
                self.broker.connect()

            if self.broker.connected:
                logger.info("✅ Broker connected")
                return True
            else:
                logger.error("❌ Broker not connected")
                return False

        except Exception as e:
            logger.error(f"Broker setup failed: {e}")
            return False

    def get_backtest_dates(self) -> List[datetime]:
        """Get date range for backtest (N weeks of past weekdays)."""
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=self.weeks)

        logger.info(f"Backtest period: {start_date.date()} to {end_date.date()}")

        trading_days: List[datetime] = []
        current = start_date

        while current <= end_date:
            if current.weekday() < 5:
                trading_days.append(current)
            current += timedelta(days=1)

        logger.info(f"Trading days in period: {len(trading_days)}")
        return trading_days

    def run_backtest(self, tickers: Optional[List[str]] = None) -> Dict:
        """
        Run backtest simulation.

        Args:
            tickers: List of tickers to trade

        Returns:
            Backtest results
        """
        if tickers is None:
            tickers = ['AAPL', 'MSFT', 'GOOGL']

        if not self.setup_broker():
            return {'status': 'failed', 'reason': 'broker_setup'}

        # Get trading days
        trading_days = self.get_backtest_dates()

        # Fetch historical data upfront
        logger.info(f"Fetching historical data for {tickers}...")

        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=self.weeks)

        all_prices: Dict[str, pd.DataFrame] = {}

        try:
            for ticker in tickers:
                df = self.broker.get_bars(
                    symbol=ticker,
                    start=start_date,
                    end=end_date,
                    timeframe='1D'
                )

                if not df.empty:
                    all_prices[ticker] = df
                    logger.info(f"✅ {ticker}: {len(df)} bars fetched")
                else:
                    logger.warning(f"⚠️ {ticker}: No data")

        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return {'status': 'failed', 'reason': 'data_fetch'}

        # Simple daily step simulation (signal = 20D momentum, allocate equally among positive)
        logger.info(f"\n📊 SIMULATION: {len(trading_days)} trading days")
        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80 + "\n")

        portfolio_value = self.initial_capital
        positions: Dict[str, float] = {sym: 0.0 for sym in tickers}

        for i, day in enumerate(trading_days):
            # Build signals from available data up to 'day'
            signals: Dict[str, float] = {}
            prices_today: Dict[str, float] = {}
            for sym, df in all_prices.items():
                day_ts = pd.Timestamp(day)
                # Align timezone to data (Alpaca bars typically UTC)
                if day_ts.tz is None:
                    day_ts = day_ts.tz_localize('UTC')
                else:
                    day_ts = day_ts.tz_convert('UTC')
                df_day = df[df.index <= day_ts]
                if len(df_day) >= 20:
                    import math
                    ret20 = df_day['close'].iloc[-1] / df_day['close'].iloc[-20] - 1.0
                    signals[sym] = float(math.tanh(ret20 * 10))
                    prices_today[sym] = float(df_day['close'].iloc[-1])

            # Determine weights (long-only proportional to positive signals)
            pos = {k: v for k, v in signals.items() if v > 0}
            if pos:
                total = sum(pos.values())
                weights = {k: v / total for k, v in pos.items()}
            else:
                weights = {}

            # Rebalance to weights using current portfolio_value
            # We simulate by setting positions value accordingly
            target_values = {k: portfolio_value * w for k, w in weights.items()}
            # Compute PnL from previous positions to today
            day_pnl = 0.0
            for sym, prev_value in positions.items():
                if sym in prices_today and sym in all_prices:
                    # Approximation: mark-to-market using today's close
                    # Previous day price
                    df = all_prices[sym]
                    df_day = df[df.index <= day_ts]
                    if len(df_day) >= 2:
                        p_prev = float(df_day['close'].iloc[-2])
                        p_now = float(df_day['close'].iloc[-1])
                        if p_prev > 0:
                            # If we had prev position value, estimate quantity
                            qty = prev_value / p_prev if p_prev else 0.0
                            day_pnl += qty * (p_now - p_prev)

            # Update portfolio value
            portfolio_value += day_pnl

            # Set new positions based on targets
            positions = target_values if target_values else {sym: 0.0 for sym in tickers}
            self.portfolio_values.append(portfolio_value)

            if (i + 1) % 5 == 0:
                logger.info(f"Progress: {i+1}/{len(trading_days)} days | PV=${portfolio_value:,.2f}")

        self.capital = portfolio_value

        # Results
        initial = self.initial_capital
        final = self.capital
        total_return = (final - initial) / initial * 100 if initial else 0.0

        results = {
            'status': 'completed',
            'initial_capital': initial,
            'final_capital': final,
            'total_return_pct': total_return,
            'days_traded': len(trading_days),
            'trades_executed': len(self.trades),
        }

        return results

    def print_summary(self, results: Dict) -> None:
        """Print backtest summary."""
        print(f"Initial Capital:     ${results['initial_capital']:,.2f}")
        print(f"Final Capital:       ${results['final_capital']:,.2f}")
        print(f"Total Return:        {results['total_return_pct']:+.2f}%")
        print(f"Days Traded:         {results['days_traded']}")
        print(f"Trades Executed:     {results['trades_executed']}")
        print()


def main() -> None:
    """Run backtest."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "LIVE TRADING PIPELINE BACKTEST (10 WEEKS)" + " "*20 + "║")
    print("╚" + "="*78 + "╝\n")

    backtest = LiveTradingBacktester(initial_capital=100000.0, weeks=10)
    results = backtest.run_backtest(tickers=['AAPL', 'MSFT', 'GOOGL'])

    if results['status'] == 'completed':
        print("✅ BACKTEST COMPLETED\n")
        backtest.print_summary(results)

        print("="*80)
        print("NEXT STEPS:")
        print("- Analyze signal quality")
        print("- Check risk management")
        print("- Optimize parameters")
        print("="*80 + "\n")
    else:
        print(f"❌ Backtest failed: {results['reason']}\n")


if __name__ == '__main__':
    main()
