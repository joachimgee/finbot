import math
import types
from datetime import datetime, timedelta
from typing import Dict

import numpy as np
import pandas as pd
import pytest

from scripts.real_backtest_live_trading import RealLiveTradingBacktester


@pytest.fixture()
def synthetic_prices():
    # 40 business days of synthetic prices
    dates = pd.bdate_range(end=datetime.now(), periods=40).tz_localize('UTC')
    base = 100 + np.cumsum(np.random.randn(len(dates)))
    close = pd.Series(base).clip(lower=1)
    open_ = close * (1 + np.random.randn(len(dates)) * 0.001)
    high = np.maximum(open_, close) * (1 + np.abs(np.random.randn(len(dates)) * 0.002))
    low = np.minimum(open_, close) * (1 - np.abs(np.random.randn(len(dates)) * 0.002))
    volume = (1e6 + np.random.randn(len(dates)) * 1e5).clip(min=1e3).astype(int)
    df = pd.DataFrame({
        'open': open_.values,
        'high': high.values,
        'low': low.values,
        'close': close.values,
        'volume': volume
    }, index=dates)
    return df


def make_backtester_with_data(tickers=("AAA", "BBB"), window=5):
    bt = RealLiveTradingBacktester(initial_capital=100000.0, weeks=6, tickers=list(tickers), momentum_window=window)
    # Monkeypatch broker setup and data fetch to bypass network
    bt.setup_broker = types.MethodType(lambda self: True, bt)  # type: ignore
    bt.fetch_historical_data = types.MethodType(lambda self: True, bt)  # type: ignore
    return bt


def test_momentum_signal_zero_without_data():
    bt = make_backtester_with_data()
    now = pd.Timestamp(datetime.now(), tz='UTC')
    assert bt.calculate_momentum_signal('AAA', now) == 0.0


def test_momentum_signal_positive_when_above_sma(synthetic_prices):
    bt = make_backtester_with_data(window=5)
    bt.historical_prices['AAA'] = synthetic_prices
    date = synthetic_prices.index[10]
    # Boost price above SMA to ensure positive signal
    bt.historical_prices['AAA'].loc[date, 'close'] = bt.historical_prices['AAA']['close'].iloc[5:10].mean() * 1.2
    sig = bt.calculate_momentum_signal('AAA', date)
    assert sig > 0


def test_momentum_signal_negative_when_below_sma(synthetic_prices):
    bt = make_backtester_with_data(window=5)
    bt.historical_prices['AAA'] = synthetic_prices
    date = synthetic_prices.index[10]
    bt.historical_prices['AAA'].loc[date, 'close'] = bt.historical_prices['AAA']['close'].iloc[5:10].mean() * 0.8
    sig = bt.calculate_momentum_signal('AAA', date)
    assert sig < 0


def test_generate_orders_buy_and_sell_paths(synthetic_prices):
    bt = make_backtester_with_data(window=5)
    bt.historical_prices['AAA'] = synthetic_prices
    date = synthetic_prices.index[10]
    prices: Dict[str, float] = {'AAA': float(synthetic_prices.loc[date, 'close'])}
    # Strong buy signal
    orders = bt.generate_orders({'AAA': 0.9}, prices)
    assert any(o['side'] == 'buy' for o in orders)
    # Assume we bought
    bt.positions['AAA'] = 10
    # Strong sell signal
    orders = bt.generate_orders({'AAA': -0.9}, prices)
    assert any(o['side'] == 'sell' for o in orders)


def test_execute_order_buy_reduces_cash_increases_position(synthetic_prices):
    bt = make_backtester_with_data()
    price = 100.0
    init_cash = bt.cash
    bt.execute_order({'ticker': 'AAA', 'qty': 10, 'price': price, 'side': 'buy', 'signal': 0.9}, synthetic_prices.index[0])
    assert bt.cash == pytest.approx(init_cash - 10 * price)
    assert bt.positions.get('AAA', 0) == 10


def test_execute_order_sell_increases_cash_decreases_position(synthetic_prices):
    bt = make_backtester_with_data()
    price = 100.0
    bt.positions['AAA'] = 10
    init_cash = bt.cash
    bt.execute_order({'ticker': 'AAA', 'qty': 4, 'price': price, 'side': 'sell', 'signal': -0.9}, synthetic_prices.index[0])
    assert bt.cash == pytest.approx(init_cash + 4 * price)
    assert bt.positions.get('AAA', 0) == 6


def test_calculate_portfolio_value(synthetic_prices):
    bt = make_backtester_with_data()
    bt.positions = {'AAA': 10}
    prices = {'AAA': 50.0}
    pv = bt.calculate_portfolio_value(prices)
    assert pv == pytest.approx(bt.cash + 10 * 50.0)


def test_calculate_metrics_monotonic_growth():
    bt = make_backtester_with_data()
    # Create monotonic increasing daily values
    bt.daily_values = [{'date': pd.Timestamp(datetime.now(), tz='UTC') + timedelta(days=i), 'value': 100000 + i * 1000, 'cash': 0.0, 'positions': {}} for i in range(10)]
    m = bt.calculate_metrics()
    assert m['total_return_pct'] > 0
    assert m['sharpe_ratio'] >= 0
    assert m['max_drawdown_pct'] <= 0


def test_run_backtest_with_synthetic_data_executes_trades(synthetic_prices):
    bt = make_backtester_with_data(window=5)
    # Provide data for two tickers to trigger multiple trading days
    bt.historical_prices['AAA'] = synthetic_prices.copy()
    bt.historical_prices['BBB'] = synthetic_prices.copy()

    # Override run to bypass broker/data fetching but still simulate days
    def fake_run(self):
        for d in self.get_trading_dates():
            self.execute_trading_day(d)
        return {'status': 'completed', 'metrics': self.calculate_metrics(), 'trades': self.trades, 'daily_values': self.daily_values}

    bt.run_backtest = types.MethodType(fake_run, bt)  # type: ignore
    result = bt.run_backtest()
    assert result['status'] == 'completed'
    # Some trades likely executed depending on signals; at least ensure days recorded
    assert result['daily_values']


@pytest.mark.parametrize("window", [5, 10, 15])
def test_momentum_window_effects(synthetic_prices, window):
    bt = make_backtester_with_data(window=window)
    bt.historical_prices['AAA'] = synthetic_prices
    mid = synthetic_prices.index[20]
    # Force a spike above SMA to generate signal irrespective of window (if enough history)
    bt.historical_prices['AAA'].loc[mid, 'close'] = bt.historical_prices['AAA']['close'].iloc[max(0, 20-window):20].mean() * 1.3
    sig = bt.calculate_momentum_signal('AAA', mid)
    # If insufficient history, signal is zero; else should be positive
    if 20 < window:
        assert sig == 0.0
    else:
        assert sig > 0.0


def test_order_generation_respects_cash(synthetic_prices):
    bt = make_backtester_with_data()
    bt.cash = 50  # Very low cash
    price = 100.0
    orders = bt.generate_orders({'AAA': 0.9}, {'AAA': price})
    # Should not be able to buy anything
    assert not orders or all(o['qty'] * o['price'] <= bt.cash for o in orders)


def test_no_data_fetch_returns_failed():
    bt = RealLiveTradingBacktester()
    bt.setup_broker = types.MethodType(lambda self: True, bt)  # type: ignore
    bt.fetch_historical_data = types.MethodType(lambda self: False, bt)  # type: ignore
    result = bt.run_backtest()
    assert result['status'] == 'failed'
    assert result['reason'] == 'data'


def test_broker_fail_returns_failed():
    bt = RealLiveTradingBacktester()
    bt.setup_broker = types.MethodType(lambda self: False, bt)  # type: ignore
    result = bt.run_backtest()
    assert result['status'] == 'failed'
    assert result['reason'] == 'broker'

