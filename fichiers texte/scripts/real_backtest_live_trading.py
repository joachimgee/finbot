#!/usr/bin/env python3
"""
Real backtesting of live trading pipeline on historical data.

REAL simulation:
- Download TRUE historical data from Alpaca (10 weeks)
- Generate signals for each day (momentum-based)
- Execute REAL buy/sell orders (not just allocation)
- Track portfolio performance daily
- Calculate proper metrics (Sharpe, drawdown, win rate)

NOT simulation: fake data, theoretical allocations, 0 orders
"""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Setup logging
import pathlib
LOG_PATH = pathlib.Path('logs')
LOG_PATH.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH / 'real_backtest.log')
    ]
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class RealLiveTradingBacktester:
    """Real backtesting with order execution simulation."""

    def __init__(
        self,
        initial_capital: float = 100000.0,
        weeks: int = 10,
        tickers: Optional[List[str]] = None,
        momentum_window: int = 20,
    ) -> None:
        self.initial_capital = initial_capital
        self.weeks = weeks
        self.tickers = tickers or ['AAPL', 'MSFT', 'GOOGL']
        self.momentum_window = momentum_window

        # Portfolio state
        self.cash: float = initial_capital
        self.positions: Dict[str, int] = {}
        self.historical_prices: Dict[str, pd.DataFrame] = {}

        # Trading history
        self.trades: List[Dict] = []
        self.daily_values: List[Dict] = []

        logger.info(
            f"RealBacktester: ${initial_capital:,.0f}, {weeks}w, tickers={self.tickers}"
        )

    def setup_broker(self) -> bool:
        """Connect to Alpaca."""
        try:
            from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

            api_key = os.getenv('ALPACA_API_KEY')
            secret_key = os.getenv('ALPACA_SECRET_KEY')
            if not api_key or not secret_key:
                logger.error("❌ Missing API credentials")
                return False

            self.broker = AlpacaAdapter(
                api_key=api_key,
                secret_key=secret_key,
                mode='paper'
            )
            if not self.broker.connected:
                self.broker.connect()

            if self.broker.connected:
                logger.info("✅ Broker connected")
                return True
            logger.error("❌ Broker not connected")
            return False
        except Exception as e:
            logger.error(f"❌ Broker setup failed: {e}")
            return False

    def fetch_historical_data(self) -> bool:
        """Download REAL historical data from Alpaca."""
        logger.info(f"Fetching historical data for {self.tickers}...")

        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=self.weeks)

        for ticker in self.tickers:
            try:
                df = self.broker.get_bars(
                    symbol=ticker,
                    start=start_date,
                    end=end_date,
                    timeframe='1D'
                )
                if df.empty:
                    logger.warning(f"⚠️ {ticker}: No data returned")
                    continue

                # Ensure datetime index is tz-aware (UTC)
                if df.index.tz is None:
                    df.index = df.index.tz_localize('UTC')
                else:
                    df.index = df.index.tz_convert('UTC')

                self.historical_prices[ticker] = df
                logger.info(f"✅ {ticker}: {len(df)} bars fetched | range ${df['close'].min():.2f}-${df['close'].max():.2f}")
            except Exception as e:
                logger.error(f"❌ {ticker}: Failed to fetch - {e}")
                continue

        if not self.historical_prices:
            logger.error("❌ No data fetched for any ticker")
            return False
        return True

    def get_trading_dates(self) -> List[pd.Timestamp]:
        """Get all trading dates from data (UTC tz-aware Timestamps)."""
        all_dates: List[pd.Timestamp] = []
        for df in self.historical_prices.values():
            all_dates.extend(list(df.index))
        # Unique and sorted
        unique_sorted = sorted(set(all_dates))
        return unique_sorted

    def _get_index_pos_for_date(self, df: pd.DataFrame, date: pd.Timestamp) -> int:
        """Get index position for date using pad method (<= date)."""
        idx = df.index.get_indexer([date], method='pad')
        return int(idx[0]) if idx.size and idx[0] != -1 else -1

    def calculate_momentum_signal(self, ticker: str, date: pd.Timestamp) -> float:
        """Calculate momentum signal for ticker on specific date (-1..+1)."""
        df = self.historical_prices.get(ticker)
        if df is None:
            return 0.0
        pos = self._get_index_pos_for_date(df, date)
        if pos < self.momentum_window:
            return 0.0
        closes = df['close'].to_numpy()
        current_price = float(closes[pos])
        sma = float(np.mean(closes[pos - self.momentum_window:pos]))
        if sma <= 0:
            return 0.0
        momentum = (current_price - sma) / sma
        return float(np.tanh(momentum * 10.0))

    def execute_trading_day(self, date: pd.Timestamp) -> None:
        """Execute trading logic for one day."""
        # Build current prices map using latest <= date
        current_prices: Dict[str, float] = {}
        for ticker, df in self.historical_prices.items():
            pos = self._get_index_pos_for_date(df, date)
            if pos != -1:
                current_prices[ticker] = float(df['close'].iloc[pos])

        if not current_prices:
            return

        # Calculate signals
        signals: Dict[str, float] = {}
        for ticker in self.tickers:
            signals[ticker] = self.calculate_momentum_signal(ticker, date)

        # Generate orders
        orders = self.generate_orders(signals, current_prices)

        # Execute orders
        for order in orders:
            self.execute_order(order, date)

        # Record daily value
        pv = self.calculate_portfolio_value(current_prices)
        self.daily_values.append({
            'date': date,
            'value': pv,
            'cash': self.cash,
            'positions': self.positions.copy()
        })

    def generate_orders(self, signals: Dict[str, float], prices: Dict[str, float]) -> List[Dict]:
        """Generate buy/sell orders from signals."""
        orders: List[Dict] = []

        # Compute portfolio value
        pv = self.cash + sum(self.positions.get(sym, 0) * prices.get(sym, 0.0) for sym in self.positions)
        max_position_value = pv * 0.20  # 20% cap per ticker

        for ticker, signal in signals.items():
            price = prices.get(ticker)
            if price is None or price <= 0:
                continue

            current_qty = int(self.positions.get(ticker, 0))
            target_value = max(0.0, max_position_value * max(0.0, signal))  # only positive for buys
            target_qty = int(target_value // price)

            if signal > 0.3:
                qty_to_buy = target_qty - current_qty
                if qty_to_buy > 0 and self.cash >= qty_to_buy * price:
                    orders.append({'ticker': ticker, 'qty': qty_to_buy, 'price': price, 'side': 'buy', 'signal': signal})

            elif signal < -0.3 and current_qty > 0:
                qty_to_sell = max(1, int(current_qty * 0.5))
                orders.append({'ticker': ticker, 'qty': qty_to_sell, 'price': price, 'side': 'sell', 'signal': signal})

        return orders

    def execute_order(self, order: Dict, date: pd.Timestamp) -> None:
        """Execute single order and update portfolio."""
        ticker = order['ticker']
        qty = int(order['qty'])
        price = float(order['price'])
        side = order['side']

        if qty <= 0 or price <= 0:
            return

        if side == 'buy':
            cost = qty * price
            if self.cash >= cost:
                self.cash -= cost
                self.positions[ticker] = int(self.positions.get(ticker, 0)) + qty
                self.trades.append({'date': date, 'ticker': ticker, 'qty': qty, 'price': price, 'side': 'buy', 'commission': cost * 0.001})
                logger.debug(f"{date.date()}: BUY {qty} {ticker} @ ${price:.2f}")
        elif side == 'sell':
            current_qty = int(self.positions.get(ticker, 0))
            if current_qty >= qty:
                revenue = qty * price
                self.cash += revenue
                self.positions[ticker] = current_qty - qty
                self.trades.append({'date': date, 'ticker': ticker, 'qty': qty, 'price': price, 'side': 'sell', 'commission': revenue * 0.001})
                logger.debug(f"{date.date()}: SELL {qty} {ticker} @ ${price:.2f}")

    def calculate_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value on given date."""
        pv = self.cash
        for ticker, qty in self.positions.items():
            pv += qty * prices.get(ticker, 0.0)
        return pv

    def run_backtest(self) -> Dict:
        """Run complete backtest."""
        if not self.setup_broker():
            return {'status': 'failed', 'reason': 'broker'}
        if not self.fetch_historical_data():
            return {'status': 'failed', 'reason': 'data'}

        dates = self.get_trading_dates()
        logger.info(f"Trading {len(dates)} days\n")

        for day in dates:
            self.execute_trading_day(day)

        metrics = self.calculate_metrics()
        return {'status': 'completed', 'metrics': metrics, 'trades': self.trades, 'daily_values': self.daily_values}

    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics."""
        if not self.daily_values:
            return {}
        values = np.array([d['value'] for d in self.daily_values], dtype=float)
        initial = float(self.initial_capital)
        final = float(values[-1])
        total_return = (final - initial) / initial * 100.0 if initial else 0.0
        # Daily returns
        if len(values) >= 2:
            returns = np.diff(values) / values[:-1]
        else:
            returns = np.array([], dtype=float)
        mean_return = float(np.mean(returns)) if returns.size else 0.0
        std_return = float(np.std(returns)) if returns.size else 0.0
        sharpe = (mean_return * 252) / (std_return * np.sqrt(252)) if std_return > 0 else 0.0
        cummax = np.maximum.accumulate(values)
        drawdown = (values - cummax) / cummax
        max_drawdown = float(np.min(drawdown) * 100.0) if drawdown.size else 0.0
        wins = int(np.sum(returns > 0)) if returns.size else 0
        win_rate = (wins / returns.size) * 100.0 if returns.size else 0.0
        buy_trades = sum(1 for t in self.trades if t['side'] == 'buy')
        sell_trades = sum(1 for t in self.trades if t['side'] == 'sell')
        return {
            'initial_capital': initial,
            'final_capital': final,
            'total_return_pct': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'win_rate_pct': win_rate,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'total_trades': len(self.trades),
            'trading_days': len(self.daily_values),
        }

    def print_summary(self, result: Dict) -> None:
        if result.get('status') != 'completed':
            print(f"❌ Backtest failed: {result.get('reason')}")
            return
        m = result['metrics']
        trades = result['trades']
        print("\n" + "="*80)
        print("REAL BACKTEST RESULTS - 10 WEEKS HISTORICAL DATA")
        print("="*80)
        print(f"\n📊 PORTFOLIO PERFORMANCE:")
        print(f"  Initial Capital:      ${m['initial_capital']:>15,.2f}")
        print(f"  Final Capital:        ${m['final_capital']:>15,.2f}")
        print(f"  Total Return:         {m['total_return_pct']:>15.2f}%")
        print(f"\n📈 RISK METRICS:")
        print(f"  Sharpe Ratio:         {m['sharpe_ratio']:>15.2f}")
        print(f"  Max Drawdown:         {m['max_drawdown_pct']:>15.2f}%")
        print(f"  Win Rate:             {m['win_rate_pct']:>15.2f}%")
        print(f"\n💱 TRADING ACTIVITY:")
        print(f"  Buy Trades:           {m['buy_trades']:>15}")
        print(f"  Sell Trades:          {m['sell_trades']:>15}")
        print(f"  Total Trades:         {m['total_trades']:>15}")
        print(f"  Trading Days:         {m['trading_days']:>15}")
        print(f"\n📝 FIRST 10 TRADES:")
        for i, trade in enumerate(trades[:10]):
            print(f"  {i+1}. {trade['date'].date()} | {trade['side'].upper():4s} {trade['qty']:3d} {trade['ticker']} @ ${trade['price']:.2f}")
        if len(trades) > 10:
            print(f"  ... and {len(trades)-10} more trades")
        print("\n" + "="*80 + "\n")


def main() -> None:
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*18 + "REAL LIVE TRADING BACKTEST (10 WEEKS)" + " "*24 + "║")
    print("║" + " "*15 + "Using TRUE Historical Data + Order Simulation" + " "*17 + "║")
    print("╚" + "="*78 + "╝\n")

    backtest = RealLiveTradingBacktester(
        initial_capital=100000.0,
        weeks=10,
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        momentum_window=20,
    )
    result = backtest.run_backtest()
    backtest.print_summary(result)
    if result.get('status') == 'completed':
        print("✅ BACKTEST COMPLETED - REAL ORDERS SIMULATED\n")


if __name__ == '__main__':
    main()
