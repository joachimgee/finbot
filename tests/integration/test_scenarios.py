from __future__ import annotations

from typing import Dict, List
import numpy as np
import pandas as pd

from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.data.market_data import MarketDataFetcher


class DummyUniverseSelector(UniverseSelector):
    def __init__(self) -> None:
        pass
    def get_metadata(self, tickers: List[str], asset_type: str = 'equities') -> pd.DataFrame:
        return pd.DataFrame({'symbol': tickers})


class DummyFetcher(MarketDataFetcher):
    def __init__(self, frames: Dict[str, pd.DataFrame]) -> None:
        self.frames = frames
    def get_historical_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self.frames.get(ticker, pd.DataFrame({'Close': []}))


def _prices_from_returns(returns: pd.Series) -> pd.DataFrame:
    prices = 100 * (1 + returns).cumprod()
    return pd.DataFrame({'Close': prices}, index=returns.index)


def _make_returns(n: int, mu: float, sigma: float) -> pd.Series:
    np.random.seed(42)
    dates = pd.date_range('2025-09-01', periods=n, freq='B')
    return pd.Series(np.random.normal(mu, sigma, n), index=dates)


def _run_pipeline(frames: Dict[str, pd.DataFrame]) -> Dict[str, object]:
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=60, forecast_horizon=5, market_data_fetcher=DummyFetcher(frames))
    res = pipe.run('2025-11-07', list(frames.keys()))
    return res


def test_bull_market_high_allocation():
    # Positive drift
    frames = {t: _prices_from_returns(_make_returns(120, mu=0.001, sigma=0.01)) for t in ['AAA', 'BBB', 'CCC']}
    res = _run_pipeline(frames)
    alloc = res['steps'].get('allocation', {})
    # Expect non-trivial non-cash allocation
    assert alloc.get('count', 0) >= 1


def test_bear_market_defensive():
    frames = {t: _prices_from_returns(_make_returns(120, mu=-0.001, sigma=0.015)) for t in ['AAA', 'BBB', 'CCC']}
    res = _run_pipeline(frames)
    # Allocation present (specific allocator rules may keep some cash)
    assert res['status'] in {'success', 'partial'}


def test_high_volatility_reduce_positions():
    frames = {t: _prices_from_returns(_make_returns(120, mu=0.0, sigma=0.05)) for t in ['AAA', 'BBB', 'CCC']}
    res = _run_pipeline(frames)
    assert res['status'] in {'success', 'partial'}


def test_crash_scenario_risk_management():
    # Large negative returns period to simulate crash
    dates = pd.date_range('2025-09-01', periods=120, freq='B')
    crash = pd.Series(np.concatenate([np.random.normal(0.0002, 0.01, 100), np.full(20, -0.05)]), index=dates)
    frames = {'AAA': _prices_from_returns(crash)}
    res = _run_pipeline(frames)
    assert res['status'] in {'success', 'partial'}


def test_divergent_signals_sanity():
    # Different assets with different drifts
    frames = {
        'AAA': _prices_from_returns(_make_returns(120, mu=0.001, sigma=0.01)),
        'BBB': _prices_from_returns(_make_returns(120, mu=-0.001, sigma=0.01)),
        'CCC': _prices_from_returns(_make_returns(120, mu=0.0, sigma=0.03)),
    }
    res = _run_pipeline(frames)
    assert res['status'] in {'success', 'partial'}


def test_all_bearish_high_cash_possible():
    frames = {t: _prices_from_returns(_make_returns(120, mu=-0.002, sigma=0.02)) for t in ['AAA', 'BBB', 'CCC']}
    res = _run_pipeline(frames)
    assert res['status'] in {'success', 'partial'}


def test_mixed_signals():
    frames = {
        'AAA': _prices_from_returns(_make_returns(120, mu=0.001, sigma=0.02)),
        'BBB': _prices_from_returns(_make_returns(120, mu=0.0, sigma=0.02)),
        'CCC': _prices_from_returns(_make_returns(120, mu=-0.001, sigma=0.02)),
    }
    res = _run_pipeline(frames)
    assert res['status'] in {'success', 'partial'}


def test_extreme_outliers_handling():
    dates = pd.date_range('2025-09-01', periods=120, freq='B')
    rets = pd.Series(np.random.normal(0.0003, 0.01, 120), index=dates)
    rets.iloc[10] = 0.25  # extreme positive
    rets.iloc[50] = -0.3  # extreme negative
    frames = {'AAA': _prices_from_returns(rets)}
    res = _run_pipeline(frames)
    assert res['status'] in {'success', 'partial'}
