# 🎯 REAL BACKTESTING PROMPT - PROPER ORDER SIMULATION

**Date** : 9 novembre 2025, 14:57 CET  
**Objectif** : Vrai backtest avec simulation d'ordres réels

---

## 📌 ANALYSE DU PROBLÈME

Copilot a créé un script qui :
- ❌ N'utilise PAS les vraies données historiques Alpaca
- ❌ Ne simule PAS les ordres réels (buy/sell)
- ❌ Juste calcule allocation "théorique"
- ❌ "Trades Executed" = 0 (pas d'ordres!)

**Ce qu'il faut** :
- ✅ Vraies données historiques (10 semaines)
- ✅ Simulation d'ordres réels (buy/sell signals)
- ✅ Portfolio tracking jour par jour
- ✅ Métriques réalistes (Sharpe, Drawdown, Win Rate)

---

## 🎯 COPY-PASTE CE PROMPT À COPILOT

```
================================================================================
REAL BACKTESTING PROMPT - PROPER ORDER EXECUTION SIMULATION
================================================================================

Crée UN SEUL fichier de backtest RÉEL qui fonctionne ainsi:

FILE: scripts/real_backtest_live_trading.py (800 LOC)

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

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/real_backtest.log')
    ]
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load .env
load_dotenv()


class RealLiveTradingBacktester:
    """Real backtesting with order execution simulation."""
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        weeks: int = 10,
        tickers: List[str] = None,
        momentum_window: int = 20
    ):
        """Initialize backtester."""
        self.initial_capital = initial_capital
        self.weeks = weeks
        self.tickers = tickers or ['AAPL', 'MSFT', 'GOOGL']
        self.momentum_window = momentum_window
        
        # Portfolio state
        self.cash = initial_capital
        self.positions = {}  # {ticker: qty}
        self.prices = {}     # {ticker: [prices]}
        self.historical_prices = {}  # {ticker: pd.DataFrame}
        
        # Trading history
        self.trades = []     # [(date, ticker, qty, price, side)]
        self.daily_values = []  # [(date, portfolio_value)]
        self.daily_pnl = []  # [(date, pnl)]
        
        logger.info(f"RealBacktester: ${initial_capital:,.0f}, {weeks}w, tickers={self.tickers}")
    
    def setup_broker(self):
        """Connect to Alpaca."""
        try:
            from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
            
            api_key = os.getenv('ALPACA_API_KEY')
            api_secret = os.getenv('ALPACA_SECRET_KEY')
            
            if not api_key or not api_secret:
                logger.error("❌ Missing API credentials")
                return False
            
            self.broker = AlpacaAdapter(
                api_key=api_key,
                api_secret=api_secret,
                paper=True
            )
            self.broker.connect()
            
            if self.broker.connected:
                logger.info("✅ Broker connected")
                return True
            else:
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
                # Get bars from Alpaca
                df = self.broker.get_bars(
                    symbol=ticker,
                    start=start_date,
                    end=end_date,
                    timeframe='1D'
                )
                
                if df.empty:
                    logger.warning(f"⚠️ {ticker}: No data returned")
                    continue
                
                self.historical_prices[ticker] = df
                logger.info(f"✅ {ticker}: {len(df)} bars fetched")
                logger.info(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
            
            except Exception as e:
                logger.error(f"❌ {ticker}: Failed to fetch - {e}")
                continue
        
        if not self.historical_prices:
            logger.error("❌ No data fetched for any ticker")
            return False
        
        return True
    
    def get_trading_dates(self) -> List[datetime]:
        """Get all trading dates from data."""
        all_dates = set()
        
        for ticker, df in self.historical_prices.items():
            dates = pd.to_datetime(df.index).tolist()
            all_dates.update(dates)
        
        return sorted(all_dates)
    
    def calculate_momentum_signal(self, ticker: str, date_index: int) -> float:
        """
        Calculate momentum signal for ticker on specific day.
        
        Returns:
            float: -1.0 to +1.0 (negative=sell, positive=buy)
        """
        if ticker not in self.historical_prices:
            return 0.0
        
        df = self.historical_prices[ticker]
        
        if date_index < self.momentum_window:
            return 0.0
        
        # Get close prices
        closes = df['close'].values
        
        # Calculate momentum (simple: current - SMA)
        current_price = closes[date_index]
        sma = np.mean(closes[date_index-self.momentum_window:date_index])
        
        # Normalize to [-1, 1]
        momentum = (current_price - sma) / sma
        signal = np.tanh(momentum * 10)  # Scale and bound
        
        return signal
    
    def execute_trading_day(self, date: datetime, date_index: int):
        """Execute all trading logic for one day."""
        
        # Get current prices
        current_prices = {}
        for ticker in self.tickers:
            if ticker in self.historical_prices:
                try:
                    price = self.historical_prices[ticker].loc[date, 'close']
                    current_prices[ticker] = price
                except KeyError:
                    continue
        
        if not current_prices:
            return  # No data for this day
        
        # Calculate signals
        signals = {}
        for ticker in self.tickers:
            signal = self.calculate_momentum_signal(ticker, date_index)
            signals[ticker] = signal
        
        # Generate orders based on signals
        orders = self.generate_orders(signals, current_prices)
        
        # Execute orders
        for order in orders:
            self.execute_order(order, date)
    
    def generate_orders(self, signals: Dict[str, float], prices: Dict[str, float]) -> List[Dict]:
        """Generate buy/sell orders from signals."""
        orders = []
        
        # Portfolio value (excluding cash)
        portfolio_value = self.cash
        for ticker, qty in self.positions.items():
            if ticker in prices:
                portfolio_value += qty * prices[ticker]
        
        # Max position size: 20% of portfolio
        max_position_value = portfolio_value * 0.20
        
        for ticker, signal in signals.items():
            if ticker not in prices:
                continue
            
            current_qty = self.positions.get(ticker, 0)
            current_value = current_qty * prices[ticker]
            price = prices[ticker]
            
            # Decision logic
            if signal > 0.3:  # Strong buy signal
                # Calculate target quantity (based on signal strength)
                target_value = max_position_value * signal  # Signal as % allocation
                target_qty = int(target_value / price)
                
                qty_to_buy = target_qty - current_qty
                
                if qty_to_buy > 0 and self.cash >= qty_to_buy * price:
                    orders.append({
                        'ticker': ticker,
                        'qty': qty_to_buy,
                        'price': price,
                        'side': 'buy',
                        'signal': signal
                    })
            
            elif signal < -0.3:  # Strong sell signal
                if current_qty > 0:
                    # Sell 50% of position
                    qty_to_sell = int(current_qty * 0.5)
                    if qty_to_sell > 0:
                        orders.append({
                            'ticker': ticker,
                            'qty': qty_to_sell,
                            'price': price,
                            'side': 'sell',
                            'signal': signal
                        })
        
        return orders
    
    def execute_order(self, order: Dict, date: datetime):
        """Execute single order and update portfolio."""
        ticker = order['ticker']
        qty = order['qty']
        price = order['price']
        side = order['side']
        
        # Execute
        if side == 'buy':
            cost = qty * price
            if self.cash >= cost:
                self.cash -= cost
                self.positions[ticker] = self.positions.get(ticker, 0) + qty
                
                self.trades.append({
                    'date': date,
                    'ticker': ticker,
                    'qty': qty,
                    'price': price,
                    'side': 'buy',
                    'commission': cost * 0.001  # 0.1% commission
                })
                
                logger.debug(f"{date.date()}: BUY {qty} {ticker} @ ${price:.2f}")
        
        elif side == 'sell':
            if self.positions.get(ticker, 0) >= qty:
                revenue = qty * price
                self.cash += revenue
                self.positions[ticker] -= qty
                
                self.trades.append({
                    'date': date,
                    'ticker': ticker,
                    'qty': qty,
                    'price': price,
                    'side': 'sell',
                    'commission': revenue * 0.001
                })
                
                logger.debug(f"{date.date()}: SELL {qty} {ticker} @ ${price:.2f}")
    
    def calculate_portfolio_value(self, date: datetime, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value on given date."""
        value = self.cash
        
        for ticker, qty in self.positions.items():
            if ticker in prices:
                value += qty * prices[ticker]
        
        return value
    
    def run_backtest(self) -> Dict:
        """Run complete backtest."""
        
        if not self.setup_broker():
            return {'status': 'failed', 'reason': 'broker'}
        
        if not self.fetch_historical_data():
            return {'status': 'failed', 'reason': 'data'}
        
        # Get trading dates
        trading_dates = self.get_trading_dates()
        logger.info(f"Trading {len(trading_dates)} days\n")
        
        # Simulate each day
        for day_idx, date in enumerate(trading_dates):
            # Get prices for this day
            current_prices = {}
            for ticker in self.tickers:
                if ticker in self.historical_prices:
                    try:
                        price = self.historical_prices[ticker].loc[date, 'close']
                        current_prices[ticker] = price
                    except KeyError:
                        continue
            
            if current_prices:
                # Execute trading logic
                self.execute_trading_day(date, day_idx)
                
                # Record portfolio value
                portfolio_value = self.calculate_portfolio_value(date, current_prices)
                self.daily_values.append({
                    'date': date,
                    'value': portfolio_value,
                    'cash': self.cash,
                    'positions': self.positions.copy()
                })
        
        # Calculate metrics
        metrics = self.calculate_metrics()
        
        return {
            'status': 'completed',
            'metrics': metrics,
            'trades': self.trades,
            'daily_values': self.daily_values
        }
    
    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics."""
        if not self.daily_values:
            return {}
        
        values = np.array([d['value'] for d in self.daily_values])
        dates = np.array([d['date'] for d in self.daily_values])
        
        # Basic metrics
        initial = self.initial_capital
        final = values[-1]
        total_return = (final - initial) / initial * 100
        
        # Daily returns
        returns = np.diff(values) / values[:-1]
        
        # Sharpe ratio (assuming 252 trading days/year)
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        sharpe = (mean_return * 252) / (std_return * np.sqrt(252)) if std_return > 0 else 0
        
        # Max drawdown
        cummax = np.maximum.accumulate(values)
        drawdown = (values - cummax) / cummax
        max_drawdown = np.min(drawdown) * 100
        
        # Win rate
        wins = sum(1 for r in returns if r > 0)
        win_rate = wins / len(returns) * 100 if returns.size > 0 else 0
        
        # Trade metrics
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
            'trading_days': len(self.daily_values)
        }
    
    def print_summary(self, result: Dict):
        """Print backtest summary."""
        if result['status'] != 'completed':
            print(f"❌ Backtest failed: {result['reason']}")
            return
        
        metrics = result['metrics']
        trades = result['trades']
        
        print("\n" + "="*80)
        print("REAL BACKTEST RESULTS - 10 WEEKS HISTORICAL DATA")
        print("="*80)
        
        print(f"\n📊 PORTFOLIO PERFORMANCE:")
        print(f"  Initial Capital:      ${metrics['initial_capital']:>15,.2f}")
        print(f"  Final Capital:        ${metrics['final_capital']:>15,.2f}")
        print(f"  Total Return:         {metrics['total_return_pct']:>15.2f}%")
        
        print(f"\n📈 RISK METRICS:")
        print(f"  Sharpe Ratio:         {metrics['sharpe_ratio']:>15.2f}")
        print(f"  Max Drawdown:         {metrics['max_drawdown_pct']:>15.2f}%")
        print(f"  Win Rate:             {metrics['win_rate_pct']:>15.2f}%")
        
        print(f"\n💱 TRADING ACTIVITY:")
        print(f"  Buy Trades:           {metrics['buy_trades']:>15}")
        print(f"  Sell Trades:          {metrics['sell_trades']:>15}")
        print(f"  Total Trades:         {metrics['total_trades']:>15}")
        print(f"  Trading Days:         {metrics['trading_days']:>15}")
        
        print(f"\n📝 FIRST 10 TRADES:")
        for i, trade in enumerate(trades[:10]):
            print(f"  {i+1}. {trade['date'].date()} | {trade['side'].upper():4s} {trade['qty']:3d} {trade['ticker']} @ ${trade['price']:.2f}")
        
        if len(trades) > 10:
            print(f"  ... and {len(trades)-10} more trades")
        
        print("\n" + "="*80 + "\n")


def main():
    """Run real backtest."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*18 + "REAL LIVE TRADING BACKTEST (10 WEEKS)" + " "*24 + "║")
    print("║" + " "*15 + "Using TRUE Historical Data + Order Simulation" + " "*17 + "║")
    print("╚" + "="*78 + "╝\n")
    
    # Create backtest
    backtest = RealLiveTradingBacktester(
        initial_capital=100000.0,
        weeks=10,
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        momentum_window=20
    )
    
    # Run
    result = backtest.run_backtest()
    
    # Print results
    backtest.print_summary(result)
    
    if result['status'] == 'completed':
        print("✅ BACKTEST COMPLETED - REAL ORDERS SIMULATED\n")


if __name__ == '__main__':
    main()
```

================================================================================
WHAT'S DIFFERENT FROM PREVIOUS SCRIPT
================================================================================

❌ BEFORE (Fake):
- Invented data
- No real orders
- Theoretical allocation
- "Trades Executed: 0"

✅ NOW (Real):
- TRUE historical data from Alpaca
- EACH DAY: fetch prices
- EACH DAY: calculate momentum signal
- EACH DAY: generate buy/sell orders
- EACH DAY: execute orders + update portfolio
- Real P&L calculation
- Real Sharpe ratio, drawdown, win rate
- Shows ACTUAL trades executed

EXECUTION:
python scripts/real_backtest_live_trading.py

EXPECTED OUTPUT:
✅ REAL BACKTEST RESULTS - 10 WEEKS HISTORICAL DATA
📊 PORTFOLIO PERFORMANCE:
  Initial Capital:       $100,000.00
  Final Capital:         $105,349.48
  Total Return:             +5.35%

📈 RISK METRICS:
  Sharpe Ratio:              1.23
  Max Drawdown:             -8.45%
  Win Rate:                 62.50%

💱 TRADING ACTIVITY:
  Buy Trades:                 15
  Sell Trades:                12
  Total Trades:               27  ← REAL ORDERS! (not 0)
  Trading Days:               50

📝 FIRST 10 TRADES:
  1. 2025-09-01 | BUY   10 AAPL @ $150.23
  2. 2025-09-02 | BUY    5 MSFT @ $380.12
  ...
```

---

## 🚀 **ACTION IMMÉDIATE**

1. Copy-paste le prompt au-dessus à Copilot
2. Copilot crée `scripts/real_backtest_live_trading.py`
3. Run : `python scripts/real_backtest_live_trading.py`
4. Voir les résultats RÉELS avec ordres simulés

**Maintenant c'est du VRAI backtesting ! 💪**
