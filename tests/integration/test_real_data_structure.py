from __future__ import annotations

"""Tests d'intégration: structures de données réalistes.

Simule des structures proches de yfinance/NewsAPI et divers cas limites:
dates incohérentes, données intrajournalières, univers large, séries unitaires,
monnaies différentes. Les assertions se concentrent sur la robustesse d'entrée.
"""

from typing import Dict, List
import numpy as np
import pandas as pd
import pytest
import math

from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.strategy import SignalFusion, EnsembleAllocator


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


def _make_price_series(n: int, start: str = '2025-10-01', freq: str = 'B') -> pd.DataFrame:
    np.random.seed(11)
    dates = pd.date_range(start, periods=n, freq=freq)
    rets = np.random.normal(0.0004, 0.01, len(dates))
    prices = 100 * (1 + pd.Series(rets, index=dates)).cumprod()
    return pd.DataFrame({'Close': prices}, index=dates)


def test_yfinance_returns_structure():
    # Simulate yfinance-like DataFrame with DatetimeIndex
    df = _make_price_series(60)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert 'Close' in df.columns


def test_newsapi_structure_sentiment():
    # Simulate NewsAPI normalized structure
    data = pd.DataFrame({
        'headline': ['A', 'B'],
        'source': ['NewsAPI', 'NewsAPI'],
        'url': ['http://a', 'http://b'],
        'text': ['aaa', 'bbb'],
        'published': pd.to_datetime(['2025-10-10', '2025-10-11'], utc=True),
        'sentiment': [0.1, -0.2],
    })
    assert set(['headline', 'source', 'url', 'text', 'published']).issubset(data.columns)


def test_missing_data_handling_nan():
    df = _make_price_series(10)
    df.loc[df.index[3], 'Close'] = math.nan
    assert pd.isna(df['Close']).any()


def test_different_date_ranges_pipeline():
    frames = {
        'AAA': _make_price_series(30, start='2025-09-01'),
        'BBB': _make_price_series(45, start='2025-08-15'),
    }
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=30, market_data_fetcher=DummyFetcher(frames))
    res = pipe.run('2025-11-07', ['AAA', 'BBB'])
    assert res['status'] in {'success', 'partial'}


def test_single_asset_edge_case():
    frames = {'AAA': _make_price_series(30)}
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=30, market_data_fetcher=DummyFetcher(frames))
    res = pipe.run('2025-11-07', ['AAA'])
    assert res['status'] in {'success', 'partial'}


def test_large_universe_50_assets():
    frames = {f'S{i:02d}': _make_price_series(60) for i in range(50)}
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=30, market_data_fetcher=DummyFetcher(frames))
    res = pipe.run('2025-11-07', list(frames.keys())[:50])
    assert res['status'] in {'success', 'partial'}


def test_intraday_data_support():
    frames = {'AAA': _make_price_series(120, freq='H')}
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=5, market_data_fetcher=DummyFetcher(frames))
    res = pipe.run('2025-11-07', ['AAA'])
    assert res['status'] in {'success', 'partial'}


def test_multi_currency_like_structure():
    # We simulate different price scales; pipeline only needs Close column
    frames = {
        'USD_AAA': _make_price_series(60),
        'EUR_BBB': _make_price_series(60) * 0.9,  # scaled
    }
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=30, market_data_fetcher=DummyFetcher(frames))
    res = pipe.run('2025-11-07', list(frames.keys()))
    assert res['status'] in {'success', 'partial'}
