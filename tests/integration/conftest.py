"""Shared fixtures and helpers for integration tests.

Provides reusable synthetic data generators and lightweight test doubles
(DummyUniverseSelector, DummyFetcher) to avoid duplication across test files.
All fixtures are deterministic via fixed NumPy seeds.
"""
from __future__ import annotations

from typing import Dict, List
import numpy as np
import pandas as pd
import pytest

from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.data.market_data import MarketDataFetcher

# ---------------------------------------------------------------------------
# Test Doubles
# ---------------------------------------------------------------------------

class DummyUniverseSelector(UniverseSelector):
    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def get_metadata(self, tickers: List[str], asset_type: str = 'equities') -> pd.DataFrame:  # pragma: no cover - trivial
        return pd.DataFrame({'symbol': tickers})


class DummyFetcher(MarketDataFetcher):
    def __init__(self, frames: Dict[str, pd.DataFrame]) -> None:  # pragma: no cover - trivial
        self.frames = frames

    def get_historical_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self.frames.get(ticker, pd.DataFrame({'Close': []}))

# ---------------------------------------------------------------------------
# Helper generation functions
# ---------------------------------------------------------------------------

def make_price_frame(n_periods: int = 120, start: str = '2025-09-01', freq: str = 'B', seed: int = 123) -> pd.DataFrame:
    """Generate synthetic price frame with lognormal-like drift.

    Args:
        n_periods: Number of periods.
        start: Start date string.
        freq: Pandas frequency code (Business day by default).
        seed: NumPy seed for determinism.
    Returns:
        DataFrame with 'Close' column.
    """
    np.random.seed(seed)
    dates = pd.date_range(start, periods=n_periods, freq=freq)
    rets = np.random.normal(0.0005, 0.01, len(dates))
    prices = 100 * (1 + pd.Series(rets, index=dates)).cumprod()
    return pd.DataFrame({'Close': prices}, index=dates)


def make_price_frames(n_assets: int, **kwargs) -> Dict[str, pd.DataFrame]:
    """Generate multiple synthetic price frames.

    Args:
        n_assets: Number of assets.
        **kwargs: Forwarded to make_price_frame.
    Returns:
        Dict[ticker, DataFrame]
    """
    frames: Dict[str, pd.DataFrame] = {}
    for i in range(n_assets):
        frames[f'S{i:02d}'] = make_price_frame(seed=kwargs.get('seed', 123) + i, **{k: v for k, v in kwargs.items() if k != 'seed'})
    return frames

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_selector() -> DummyUniverseSelector:
    return DummyUniverseSelector()


@pytest.fixture
def small_price_frames() -> Dict[str, pd.DataFrame]:
    return make_price_frames(5)


@pytest.fixture
def medium_price_frames() -> Dict[str, pd.DataFrame]:
    return make_price_frames(10)


@pytest.fixture
def large_price_frames() -> Dict[str, pd.DataFrame]:
    return make_price_frames(50)


@pytest.fixture
def dummy_fetcher(small_price_frames) -> DummyFetcher:
    return DummyFetcher(small_price_frames)


@pytest.fixture
def universe_small(small_price_frames) -> List[str]:
    return list(small_price_frames.keys())


@pytest.fixture
def universe_large(large_price_frames) -> List[str]:
    return list(large_price_frames.keys())
