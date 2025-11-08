"""Tests pour OrderExecutor (8 tests)."""
import pytest
import pandas as pd

from financial_analyzer.pipeline.order_executor import OrderExecutor


def test_init_default():
    exec = OrderExecutor()
    assert exec.cash == 100_000.0
    assert exec.get_positions().empty


def test_init_invalid():
    with pytest.raises(ValueError):
        OrderExecutor(initial_capital=0)


def test_execute_buy_increases_position_and_decreases_cash():
    exec = OrderExecutor(initial_capital=10_000)
    order = {'ticker':'AAPL','action':'BUY','target_weight':0.1,'delta_weight':0.1,'notional':5_000}
    res = exec.execute(order, current_price=100.0)
    assert res['status']=='success'
    pos = exec.get_positions()
    assert pos.loc[pos['ticker']=='AAPL','quantity'].iloc[0] == pytest.approx(50.0)
    assert exec.cash == pytest.approx(5_000.0)


def test_execute_sell_reduces_position_and_increases_cash():
    exec = OrderExecutor(initial_capital=10_000)
    # Buy first
    exec.execute({'ticker':'AAPL','action':'BUY','target_weight':0.1,'delta_weight':0.1,'notional':5_000}, 100.0)
    # Sell half
    res = exec.execute({'ticker':'AAPL','action':'SELL','target_weight':0.05,'delta_weight':-0.05,'notional':-2_500}, 100.0)
    assert res['status']=='success'
    pos = exec.get_positions()
    assert pos.loc[pos['ticker']=='AAPL','quantity'].iloc[0] == pytest.approx(25.0)
    assert exec.cash == pytest.approx(7_500.0)


def test_execute_hold_no_change():
    exec = OrderExecutor()
    res = exec.execute({'ticker':'AAPL','action':'HOLD','target_weight':0.0,'delta_weight':0.0,'notional':0.0}, 150.0)
    assert res['status']=='success'
    assert exec.get_positions().empty


def test_trade_tracking_has_records():
    exec = OrderExecutor()
    exec.execute({'ticker':'AAPL','action':'BUY','target_weight':0.1,'delta_weight':0.1,'notional':10_000}, 100.0)
    trades = exec.track_trades()
    assert not trades.empty
    assert trades.iloc[0]['action'] == 'BUY'


def test_portfolio_valuation():
    exec = OrderExecutor()
    exec.execute({'ticker':'AAPL','action':'BUY','target_weight':0.1,'delta_weight':0.1,'notional':10_000}, 100.0)
    value = exec.get_portfolio_value({'AAPL': 110.0})
    assert value['total_value'] > 100_000.0


def test_invalid_order_missing_keys():
    exec = OrderExecutor()
    res = exec.execute({'ticker':'AAPL','action':'BUY','notional':10_000}, 100.0)
    assert res['status'] == 'error'


def test_invalid_order_action():
    exec = OrderExecutor()
    res = exec.execute({'ticker':'AAPL','action':'INVALID','target_weight':0.1,'delta_weight':0.1,'notional':10_000}, 100.0)
    assert res['status'] == 'error'
