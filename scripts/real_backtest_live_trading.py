from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class Trade:
    date: pd.Timestamp
    ticker: str
    qty: int
    price: float
    side: str
    signal: float


class RealLiveTradingBacktester:
    """
    Minimal backtester used by test_real_backtest_live_trading.py tests.

    It avoids any network dependency and focuses on deterministic operations
    for signals, order generation, execution, and metrics.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        weeks: int = 6,
        tickers: Optional[List[str]] = None,
        momentum_window: int = 10,
    ) -> None:
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.weeks = int(weeks)
        self.tickers = list(tickers) if tickers is not None else ["AAPL"]
        self.momentum_window = int(momentum_window)

        self.positions: Dict[str, int] = {}
        self.historical_prices: Dict[str, pd.DataFrame] = {}
        self.trades: List[Trade] = []
        self.daily_values: List[Dict] = []

    # --------- Setup / Data (tests monkeypatch these) ---------
    def setup_broker(self) -> bool:
        return True

    def fetch_historical_data(self) -> bool:
        # Tests usually monkeypatch this. If not, generate simple synthetic data.
        if self.historical_prices:
            return True
        dates = pd.bdate_range(end=pd.Timestamp(datetime.now(), tz="UTC"), periods=30)
        for t in self.tickers:
            base = 100 + np.cumsum(np.random.randn(len(dates)))
            close = pd.Series(base, index=dates).clip(lower=1)
            open_ = close * (1 + np.random.randn(len(dates)) * 0.001)
            high = np.maximum(open_, close) * (1 + np.abs(np.random.randn(len(dates)) * 0.002))
            low = np.minimum(open_, close) * (1 - np.abs(np.random.randn(len(dates)) * 0.002))
            volume = (1e6 + np.random.randn(len(dates)) * 1e5).clip(min=1e3).astype(int)
            self.historical_prices[t] = pd.DataFrame(
                {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
            )
        return True

    # --------- Signals / Orders ---------
    def calculate_momentum_signal(self, ticker: str, date: pd.Timestamp) -> float:
        df = self.historical_prices.get(ticker)
        if df is None or date not in df.index:
            return 0.0
        idx = df.index.get_loc(date)
        if idx < self.momentum_window:
            return 0.0
        window = df.iloc[idx - self.momentum_window:idx]["close"]
        sma = float(window.mean())
        price = float(df.loc[date, "close"])  # last available close at date
        # Simple normalized signal in [-1, 1]
        if sma == 0:
            return 0.0
        rel = (price - sma) / abs(sma)
        rel = max(min(rel, 0.5), -0.5)  # clamp to avoid extreme values in tests
        return float(rel * 2.0)  # map [-0.5,0.5] -> [-1,1]

    def generate_orders(self, signals: Dict[str, float], prices: Dict[str, float]) -> List[Dict]:
        orders: List[Dict] = []
        for t, s in signals.items():
            price = float(prices.get(t, 0.0))
            if price <= 0:
                continue
            if s > 0.5:  # strong buy
                # Use 10% of cash per buy signal
                budget = 0.10 * self.cash
                qty = int(budget // price)
                if qty > 0 and qty * price <= self.cash:
                    orders.append({
                        "ticker": t, "qty": qty, "price": price, "side": "buy", "signal": s
                    })
            elif s < -0.5:  # strong sell
                pos = int(self.positions.get(t, 0))
                if pos > 0:
                    qty = max(1, pos // 2)  # sell half position at least 1
                    orders.append({
                        "ticker": t, "qty": qty, "price": price, "side": "sell", "signal": s
                    })
        return orders

    def execute_order(self, order: Dict, date: pd.Timestamp) -> None:
        ticker = order["ticker"]
        qty = int(order["qty"])
        price = float(order["price"])
        side = order["side"]
        amt = qty * price
        if side == "buy":
            if amt <= self.cash and qty > 0:
                self.cash -= amt
                self.positions[ticker] = int(self.positions.get(ticker, 0)) + qty
        elif side == "sell":
            pos = int(self.positions.get(ticker, 0))
            if qty > 0 and pos >= qty:
                self.positions[ticker] = pos - qty
                self.cash += amt
        self.trades.append(Trade(date=date, ticker=ticker, qty=qty, price=price, side=side, signal=float(order.get("signal", 0.0))))

    # --------- Portfolio / Metrics ---------
    def calculate_portfolio_value(self, prices: Dict[str, float]) -> float:
        value = self.cash
        for t, pos in self.positions.items():
            px = float(prices.get(t, 0.0))
            value += pos * px
        return float(value)

    def calculate_metrics(self) -> Dict[str, float]:
        if not self.daily_values:
            return {"total_return_pct": 0.0, "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0}
        values = np.array([float(x["value"]) for x in self.daily_values], dtype=float)
        rets = np.diff(values) / values[:-1]
        total_return = (values[-1] / values[0]) - 1.0
        sharpe = 0.0
        if rets.size > 1 and np.std(rets) > 0:
            sharpe = float(np.sqrt(252) * np.mean(rets) / (np.std(rets) + 1e-12))
        # Max drawdown
        cummax = np.maximum.accumulate(values)
        dd = (values / (cummax + 1e-12)) - 1.0
        max_dd = float(np.min(dd))
        return {"total_return_pct": float(total_return), "sharpe_ratio": float(sharpe), "max_drawdown_pct": float(max_dd)}

    # --------- Execution Loop ---------
    def get_trading_dates(self) -> List[pd.Timestamp]:
        # If we have prices for at least one ticker, use its index
        for df in self.historical_prices.values():
            return list(df.index)
        # Fallback to recent business days
        end = pd.Timestamp(datetime.now(), tz="UTC")
        dates = pd.bdate_range(end=end, periods=self.weeks * 5)
        return list(dates)

    def execute_trading_day(self, date: pd.Timestamp) -> None:
        # Build prices dict from historical if available
        prices: Dict[str, float] = {}
        for t in self.tickers:
            df = self.historical_prices.get(t)
            if df is not None and date in df.index:
                prices[t] = float(df.loc[date, "close"])
        # Compute signals
        signals: Dict[str, float] = {t: self.calculate_momentum_signal(t, date) for t in self.tickers}
        # Generate and execute orders
        orders = self.generate_orders(signals, prices)
        for o in orders:
            self.execute_order(o, date)
        # Track daily value
        pv = self.calculate_portfolio_value(prices)
        self.daily_values.append({"date": date, "value": pv, "cash": self.cash, "positions": dict(self.positions)})

    def run_backtest(self) -> Dict:
        if not self.setup_broker():
            return {"status": "failed", "reason": "broker"}
        if not self.fetch_historical_data():
            return {"status": "failed", "reason": "data"}
        for d in self.get_trading_dates():
            self.execute_trading_day(d)
        return {"status": "completed", "metrics": self.calculate_metrics(), "trades": self.trades, "daily_values": self.daily_values}
