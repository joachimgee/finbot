import numpy as np
import pandas as pd

from financial_analyzer.portfolio.rebalancer import (
    PortfolioRebalancer,
    rebalance_periodic,
    rebalance_threshold,
    rebalance_calendar,
)


def _make_returns(n_days=60, n_assets=3, seed=1):
    rng = np.random.default_rng(seed)
    data = rng.normal(loc=0.0005, scale=0.01, size=(n_days, n_assets))
    dates = pd.date_range('2023-01-01', periods=n_days, freq='B')
    return pd.DataFrame(data, index=dates, columns=[f'A{i}' for i in range(n_assets)])


def test_rebalance_periodic_monthly():
    returns = _make_returns(80, 3)
    tw = pd.Series({'A0': 0.5, 'A1': 0.3, 'A2': 0.2})
    res = rebalance_periodic(returns, tw, freq='M')
    assert isinstance(res.weights, pd.DataFrame)
    assert np.allclose(res.weights.sum(axis=1), 1.0, atol=1e-6)
    # At least one trade occurs at month-end
    assert (res.trades.abs().sum(axis=1) > 0).any()


def test_rebalance_threshold_trigger():
    returns = _make_returns(50, 3)
    tw = pd.Series({'A0': 0.4, 'A1': 0.4, 'A2': 0.2})
    pr = PortfolioRebalancer(returns)
    res = pr.rebalance_threshold(tw, threshold=0.02)
    assert isinstance(res.weights, pd.DataFrame)
    # Ensure weights stay normalized
    assert np.allclose(res.weights.sum(axis=1), 1.0, atol=1e-6)


def test_rebalance_calendar_quarters():
    returns = _make_returns(260, 4)
    tw = pd.Series({'A0': 0.25, 'A1': 0.25, 'A2': 0.25, 'A3': 0.25})
    res = rebalance_calendar(returns, tw, months=(3, 6, 9, 12))
    assert isinstance(res.weights, pd.DataFrame)
    assert res.weights.shape[0] == returns.shape[0]
    # Trades should only appear on specified months
    trade_days = res.trades.index[res.trades.abs().sum(axis=1) > 0]
    assert all(trade_days.month.isin([3, 6, 9, 12]))
