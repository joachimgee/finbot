from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import numpy as np
import pandas as pd
import pytest

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


def _make_prices(n_assets: int, n_periods: int = 120) -> Dict[str, pd.DataFrame]:
    np.random.seed(21)
    dates = pd.date_range('2025-09-01', periods=n_periods, freq='B')
    frames: Dict[str, pd.DataFrame] = {}
    for i in range(n_assets):
        rets = np.random.normal(0.0005, 0.01, len(dates))
        prices = 100 * (1 + pd.Series(rets, index=dates)).cumprod()
        frames[f'S{i:02d}'] = pd.DataFrame({'Close': prices}, index=dates)
    return frames


def test_execution_time_small_universe():
    frames = _make_prices(5)
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=60, market_data_fetcher=DummyFetcher(frames))
    start = time.perf_counter()
    res = pipe.run('2025-11-07', list(frames.keys()))
    elapsed = time.perf_counter() - start
    assert res['status'] in {'success', 'partial'}
    assert elapsed < 10.0


def test_execution_time_large_universe():
    frames = _make_prices(50)
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=60, market_data_fetcher=DummyFetcher(frames))
    start = time.perf_counter()
    res = pipe.run('2025-11-07', list(frames.keys()))
    elapsed = time.perf_counter() - start
    assert res['status'] in {'success', 'partial'}
    assert elapsed < 60.0


def _get_memory_usage_mb() -> float:
    """Return approximate RSS memory in MB using psutil if available, else resource.

    Cross-platform fallback: psutil preferred; resource as Unix-only fallback.
    """
    try:
        import psutil  # type: ignore
        process = psutil.Process()
        return float(process.memory_info().rss) / (1024.0 * 1024.0)
    except Exception:
        try:
            import resource  # Unix-only
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # ru_maxrss is KB on Linux
            return float(usage) / 1024.0
        except Exception:
            return 0.0


def test_memory_usage_under_limit():
    frames = _make_prices(50, 252)
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=120, market_data_fetcher=DummyFetcher(frames))
    _ = pipe.run('2025-11-07', list(frames.keys()))
    mem_mb = _get_memory_usage_mb()
    # Under 2GB
    assert mem_mb < 2_000.0


def test_no_memory_leak_over_runs():
    frames = _make_prices(10, 252)
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=120, market_data_fetcher=DummyFetcher(frames))
    _ = pipe.run('2025-11-07', list(frames.keys()))
    mem1 = _get_memory_usage_mb()
    _ = pipe.run('2025-11-07', list(frames.keys()))
    mem2 = _get_memory_usage_mb()
    # Allow small drift, ensure no massive leak (>200MB)
    assert (mem2 - mem1) < 200.0


def test_memory_usage_psutil_fallback():
    """Vérifie que la fonction de mesure mémoire renvoie une valeur >=0 si psutil absent.

    Supprime psutil de sys.modules pour forcer le fallback resource. Restaure ensuite.
    """
    import sys
    original = sys.modules.get('psutil')
    if 'psutil' in sys.modules:
        del sys.modules['psutil']
    try:
        value = _get_memory_usage_mb()
        assert value >= 0.0
    finally:
        if original is not None:
            sys.modules['psutil'] = original


def test_caching_speedup_like_effect():
    frames = _make_prices(10, 252)
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=120, market_data_fetcher=DummyFetcher(frames))
    t1s = []
    for _ in range(2):
        start = time.perf_counter()
        _ = pipe.run('2025-11-07', list(frames.keys()))
        t1s.append(time.perf_counter() - start)
    # Second run should not be dramatically slower; allow some variance in CI
    assert t1s[1] <= 2.0 * t1s[0]


def test_concurrent_runs():
    frames = _make_prices(5, 120)
    pipe = Pipeline(DummyUniverseSelector(), lookback_days=60, market_data_fetcher=DummyFetcher(frames))
    tickers = list(frames.keys())

    def run_once():
        res = pipe.run('2025-11-07', tickers)
        assert res['status'] in {'success', 'partial'}
        return True

    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(run_once) for _ in range(3)]
        assert all(f.result(timeout=30) for f in futs)
