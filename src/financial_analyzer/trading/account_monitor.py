"""
Account Monitor - Track portfolio state in real-time.

Features:
- Get portfolio value, cash, equity, positions
- Track P&L (daily, cumulative, per position)
- Position concentration analysis
- Drawdown tracking (current, max)
- Exposure metrics (long, short, net, gross)
- Historical tracking

Integrates with BrokerAdapter for real-time data.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import logging
from collections import deque

logger = logging.getLogger(__name__)

from .broker_adapter import BrokerAdapter


class AccountMonitor:
    """
    Monitor account state and performance in real-time.
    
    Tracks portfolio value, P&L, drawdowns, exposure metrics, and position-level
    performance. Integrates with BrokerAdapter to fetch real-time data.
    
    Attributes:
        broker: BrokerAdapter instance for fetching account data
        initial_capital: Starting capital for performance calculations
        portfolio_value: Current total portfolio value
        cash: Available cash
        equity: Total equity (cash + positions)
        positions: List of current positions
        daily_pnl: Daily profit/loss
        cumulative_pnl: Total P&L since inception
        peak_value: Highest portfolio value reached
        current_drawdown: Current drawdown from peak (negative = loss)
        max_drawdown: Maximum drawdown experienced (negative = worst loss)
        history: Historical portfolio snapshots
    
    Example:
        >>> from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
        >>> adapter = AlpacaAdapter(api_key='...', secret_key='...', mode='paper')
        >>> adapter.connect()
        >>> monitor = AccountMonitor(adapter, initial_capital=100000)
        >>> monitor.update()  # Fetch latest from broker
        >>> print(f"Portfolio: ${monitor.portfolio_value:.2f}")
        >>> print(f"Daily P&L: ${monitor.daily_pnl:.2f}")
        >>> print(f"Max DD: {monitor.max_drawdown:.2%}")
    """
    
    def __init__(
        self,
        broker_adapter: BrokerAdapter,
        initial_capital: float = 100000.0,
        track_history: bool = True,
        max_history_size: int = 5000
    ) -> None:
        """
        Initialize account monitor.
        
        Args:
            broker_adapter: Connected BrokerAdapter instance
            initial_capital: Initial capital for drawdown calculation (default: 100,000)
            track_history: Track historical portfolio values (default: True)
            max_history_size: Max history entries to keep (default: 5,000)
        
        Raises:
            ValueError: If broker_adapter not connected
        
        Example:
            >>> monitor = AccountMonitor(
            ...     broker_adapter=adapter,
            ...     initial_capital=100000,
            ...     track_history=True
            ... )
        """
        if not broker_adapter.connected:
            raise ValueError("BrokerAdapter must be connected. Call connect() first.")
        
        self.broker = broker_adapter
        self.initial_capital = initial_capital
        self.track_history = track_history
        self.max_history_size = max_history_size
        
        # Current state
        self.portfolio_value: float = initial_capital
        self.cash: float = initial_capital
        self.equity: float = initial_capital
        self.positions: List[Dict] = []
        
        # P&L tracking
        self.daily_pnl: float = 0.0
        self.cumulative_pnl: float = 0.0
        self.last_portfolio_value: float = initial_capital
        
        # Drawdown tracking
        self.peak_value: float = initial_capital
        self.current_drawdown: float = 0.0
        self.max_drawdown: float = 0.0
        
        # History (deque for memory efficiency)
        self.history: Optional[deque] = deque(maxlen=max_history_size) if track_history else None
        
        # Last update
        self.last_update: Optional[datetime] = None
        
        logger.info(
            f"AccountMonitor initialized: "
            f"initial_capital=${initial_capital:.2f}, "
            f"tracking={'enabled' if track_history else 'disabled'}"
        )
    
    def update(self) -> None:
        """
        Update account state from broker.
        
        Fetches latest account info and positions from broker.
        Updates P&L, drawdown, and history.
        
        Raises:
            BrokerAPIError: If broker connection fails
        
        Example:
            >>> monitor.update()
            >>> print(f"Updated: {monitor.last_update}")
        """
        try:
            # Fetch account info
            account = self.broker.get_account()
            self.cash = account['cash']
            self.equity = account['equity']
            self.portfolio_value = account['portfolio_value']
            
            # Fetch positions
            self.positions = self.broker.get_positions()
            
            # Calculate P&L
            if self.last_portfolio_value is not None:
                self.daily_pnl = self.portfolio_value - self.last_portfolio_value
            
            self.cumulative_pnl = self.portfolio_value - self.initial_capital
            
            # Update drawdown
            if self.portfolio_value > self.peak_value:
                self.peak_value = self.portfolio_value
                logger.debug(f"New peak: ${self.peak_value:.2f}")
            
            self.current_drawdown = (
                (self.portfolio_value - self.peak_value) / self.peak_value 
                if self.peak_value > 0 else 0.0
            )
            
            # Update max drawdown (more negative = worse)
            if self.current_drawdown < self.max_drawdown:
                self.max_drawdown = self.current_drawdown
                logger.warning(f"New max drawdown: {self.max_drawdown:.2%}")
            
            # Track history
            if self.track_history and self.history is not None:
                self.history.append({
                    'timestamp': datetime.now(),
                    'portfolio_value': self.portfolio_value,
                    'cash': self.cash,
                    'equity': self.equity,
                    'daily_pnl': self.daily_pnl,
                    'cumulative_pnl': self.cumulative_pnl,
                    'current_drawdown': self.current_drawdown,
                    'num_positions': len(self.positions)
                })
            
            # Update last values
            self.last_portfolio_value = self.portfolio_value
            self.last_update = datetime.now()
            
            logger.debug(
                f"Portfolio updated: ${self.portfolio_value:.2f} "
                f"(daily: ${self.daily_pnl:+.2f}, cumulative: ${self.cumulative_pnl:+.2f}, "
                f"dd: {self.current_drawdown:.2%})"
            )
        
        except Exception as e:
            logger.error(f"Failed to update account monitor: {e}", exc_info=True)
            raise
    
    def get_position_concentration(self) -> Dict[str, float]:
        """
        Get position concentration (weight of each position).
        
        Returns percentage of portfolio allocated to each position.
        
        Returns:
            Dict mapping symbol to weight (0-1)
        
        Example:
            >>> monitor.update()
            >>> conc = monitor.get_position_concentration()
            >>> print(conc)  # {'AAPL': 0.15, 'MSFT': 0.20, ...}
            >>> largest = max(conc.values())
            >>> print(f"Largest position: {largest:.1%}")
        """
        if self.portfolio_value <= 0:
            return {}
        
        concentration = {}
        for pos in self.positions:
            weight = abs(pos['market_value']) / self.portfolio_value
            concentration[pos['symbol']] = weight
        
        return concentration
    
    def get_exposure_metrics(self) -> Dict:
        """
        Get exposure metrics (long, short, net, gross).
        
        Calculates various exposure metrics useful for risk management:
        - Long exposure: Total market value of long positions
        - Short exposure: Total market value of short positions
        - Net exposure: Long - Short (directional bias)
        - Gross exposure: Long + Short (total market exposure)
        - Leverage: Gross exposure / portfolio value
        
        Returns:
            Dict with keys:
            - long_exposure: Long market value (USD)
            - short_exposure: Short market value (USD, positive)
            - net_exposure: Net market value (long - short, USD)
            - gross_exposure: Gross market value (long + short, USD)
            - leverage: Gross / portfolio_value (ratio)
            - long_pct: Long / portfolio (%)
            - short_pct: Short / portfolio (%)
        
        Example:
            >>> monitor.update()
            >>> exposure = monitor.get_exposure_metrics()
            >>> print(f"Long: ${exposure['long_exposure']:,.0f}")
            >>> print(f"Net: ${exposure['net_exposure']:,.0f}")
            >>> print(f"Leverage: {exposure['leverage']:.2f}x")
        """
        long_value = sum(
            pos['market_value'] 
            for pos in self.positions 
            if pos['qty'] > 0
        )
        short_value = sum(
            abs(pos['market_value']) 
            for pos in self.positions 
            if pos['qty'] < 0
        )
        
        pv = self.portfolio_value if self.portfolio_value > 0 else 1
        
        return {
            'long_exposure': long_value,
            'short_exposure': short_value,
            'net_exposure': long_value - short_value,
            'gross_exposure': long_value + short_value,
            'leverage': (long_value + short_value) / pv,
            'long_pct': long_value / pv * 100 if pv > 0 else 0,
            'short_pct': short_value / pv * 100 if pv > 0 else 0
        }
    
    def get_position_pnl(self) -> Dict[str, Dict]:
        """
        Get P&L per position.
        
        Returns detailed P&L breakdown for each position.
        
        Returns:
            Dict mapping symbol to P&L metrics:
            - unrealized_pl: Unrealized P&L in USD
            - unrealized_plpc: Unrealized P&L percent (decimal)
            - qty: Position quantity
            - avg_entry_price: Average entry price
            - current_price: Current market price
            - market_value: Current market value
        
        Example:
            >>> monitor.update()
            >>> pnl = monitor.get_position_pnl()
            >>> for symbol, metrics in pnl.items():
            ...     print(f"{symbol}: ${metrics['unrealized_pl']:+,.2f}")
        """
        position_pnl = {}
        for pos in self.positions:
            position_pnl[pos['symbol']] = {
                'unrealized_pl': pos['unrealized_pl'],
                'unrealized_plpc': pos['unrealized_plpc'],
                'qty': pos['qty'],
                'avg_entry_price': pos['avg_entry_price'],
                'current_price': pos['current_price'],
                'market_value': pos['market_value']
            }
        
        return position_pnl
    
    def get_summary(self) -> Dict:
        """
        Get account summary (all key metrics).
        
        Returns comprehensive snapshot of account state including portfolio value,
        P&L, drawdowns, positions, exposure, and concentration.
        
        Returns:
            Dict with all key metrics:
            - timestamp: Last update time
            - portfolio_value: Current portfolio value
            - cash: Available cash
            - equity: Total equity
            - initial_capital: Starting capital
            - daily_pnl: Daily P&L (USD)
            - cumulative_pnl: Total P&L (USD)
            - daily_return_pct: Daily return (%)
            - cumulative_return_pct: Total return (%)
            - current_drawdown: Current drawdown (negative %)
            - max_drawdown: Max drawdown (negative %)
            - peak_value: Peak portfolio value
            - num_positions: Number of positions
            - concentration: Position concentration dict
            - exposure: Exposure metrics dict
            - position_pnl: Per-position P&L dict
        
        Example:
            >>> monitor.update()
            >>> summary = monitor.get_summary()
            >>> print(f"Return: {summary['cumulative_return_pct']:.2f}%")
            >>> print(f"Max DD: {summary['max_drawdown']:.2%}")
        """
        return {
            'timestamp': self.last_update,
            'portfolio_value': self.portfolio_value,
            'cash': self.cash,
            'equity': self.equity,
            'initial_capital': self.initial_capital,
            'daily_pnl': self.daily_pnl,
            'cumulative_pnl': self.cumulative_pnl,
            'daily_return_pct': (
                self.daily_pnl / self.last_portfolio_value * 100 
                if self.last_portfolio_value > 0 else 0
            ),
            'cumulative_return_pct': (
                self.cumulative_pnl / self.initial_capital * 100 
                if self.initial_capital > 0 else 0
            ),
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'peak_value': self.peak_value,
            'num_positions': len(self.positions),
            'concentration': self.get_position_concentration(),
            'exposure': self.get_exposure_metrics(),
            'position_pnl': self.get_position_pnl()
        }
    
    def get_history_df(self) -> pd.DataFrame:
        """
        Get history as DataFrame.
        
        Converts historical portfolio snapshots to pandas DataFrame for analysis.
        
        Returns:
            DataFrame with columns: timestamp (index), portfolio_value, cash, 
            equity, daily_pnl, cumulative_pnl, current_drawdown, num_positions
        
        Example:
            >>> monitor.update()  # Multiple times...
            >>> df = monitor.get_history_df()
            >>> df.to_csv('portfolio_history.csv')
            >>> print(df['portfolio_value'].plot())
        """
        if not self.history:
            return pd.DataFrame()
        
        return pd.DataFrame(list(self.history)).set_index('timestamp')
    
    def get_equity_curve(self) -> pd.Series:
        """
        Get equity curve as pandas Series.
        
        Returns time series of portfolio values, useful for plotting and
        performance analysis.
        
        Returns:
            Series with timestamp index and portfolio values.
            Empty series if no history available.
        
        Example:
            >>> monitor.update()  # Multiple times to build history
            >>> equity = monitor.get_equity_curve()
            >>> equity.plot(title='Equity Curve')
            >>> plt.show()
            
            >>> # Calculate returns
            >>> returns = equity.pct_change()
            >>> sharpe = returns.mean() / returns.std() * np.sqrt(252)
        """
        if not self.history:
            return pd.Series(dtype=float, name='portfolio_value')
        
        df = self.get_history_df()
        return df['portfolio_value']
    
    def reset_stats(self) -> None:
        """
        Reset tracking stats (but keep current position).
        
        Resets daily P&L and sets last portfolio value to current value.
        Useful for starting new trading day/period.
        
        Example:
            >>> monitor.reset_stats()  # Reset daily stats at market open
        """
        self.daily_pnl = 0.0
        self.last_portfolio_value = self.portfolio_value
        logger.info("Tracking stats reset")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"AccountMonitor(portfolio=${self.portfolio_value:.2f}, "
            f"positions={len(self.positions)}, "
            f"dd={self.current_drawdown:.2%})"
        )
