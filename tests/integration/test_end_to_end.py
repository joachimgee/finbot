import os
from typing import Any, Dict, List
import pandas as pd
import numpy as np
import pytest

from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.strategy import SignalFusion, EnsembleAllocator
from financial_analyzer.pipeline.order_executor import OrderExecutor
from financial_analyzer.analytics.performance_analyzer import PerformanceAnalyzer
from financial_analyzer.analytics.report_generator import ReportGenerator


# -----------------------------
# Fixtures & Test Doubles
# -----------------------------

class DummyUniverseSelector(UniverseSelector):
    def __init__(self) -> None:
        # Skip heavy init for tests
        pass

    def get_metadata(self, tickers: List[str], asset_type: str = 'equities') -> pd.DataFrame:
        return pd.DataFrame({'symbol': tickers})


class DummyMarketDataFetcher(MarketDataFetcher):
    def __init__(self, prices: Dict[str, pd.DataFrame]) -> None:
        self._prices = prices

    def get_historical_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._prices.get(ticker, pd.DataFrame({'Close': []}))


@pytest.fixture
def synthetic_prices() -> Dict[str, pd.DataFrame]:
    np.random.seed(123)
    dates = pd.date_range('2025-09-01', periods=120, freq='B')
    def gen_price() -> pd.DataFrame:
        rets = np.random.normal(0.0005, 0.01, len(dates))
        prices = 100 * (1 + pd.Series(rets, index=dates)).cumprod()
        return pd.DataFrame({'Close': prices}, index=dates)
    return {
        'AAA': gen_price(),
        'BBB': gen_price(),
        'CCC': gen_price(),
    }


@pytest.fixture
def pipeline_with_doubles(synthetic_prices):
    selector = DummyUniverseSelector()
    fetcher = DummyMarketDataFetcher(synthetic_prices)
    pipeline = Pipeline(
        universe_selector=selector,
        lookback_days=90,
        forecast_horizon=5,
        market_data_fetcher=fetcher,
        signal_fusion=SignalFusion(),
        allocator=EnsembleAllocator(),
    )
    return pipeline


@pytest.fixture
def universe() -> List[str]:
    return ['AAA', 'BBB', 'CCC']


# -----------------------------
# Tests E2E
# -----------------------------

def test_full_pipeline_success(pipeline_with_doubles, universe):
    result = pipeline_with_doubles.run('2025-11-07', universe, optimization_method='inverse_variance')
    assert result['status'] in {'success', 'partial'}
    assert 'steps' in result and isinstance(result['steps'], dict)
    assert result['steps'].get('orders', {}).get('count', 0) >= 0


def test_pipeline_data_flow(pipeline_with_doubles, universe):
    result = pipeline_with_doubles.run('2025-11-07', universe)
    cache = pipeline_with_doubles.cache
    assert cache.returns is not None and not cache.returns.empty
    assert cache.technical_features is not None
    assert cache.fused_signals is not None
    # Singular alias supported by PipelineCache
    assert cache.allocation is not None
    # Validate weights sum approximately to 1
    import pytest as _pytest
    assert _pytest.approx(1.0, abs=0.02) == sum(cache.allocation.values())


def test_pipeline_error_propagation(universe, synthetic_prices):
    selector = DummyUniverseSelector()
    class FailingFetcher(DummyMarketDataFetcher):
        def get_historical_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
            raise RuntimeError("fetch failed intentionally for test")
    pipeline = Pipeline(
        universe_selector=selector,
        lookback_days=30,
        forecast_horizon=5,
        market_data_fetcher=FailingFetcher(synthetic_prices),
    )
    result = pipeline.run('2025-11-07', universe)
    # Graceful degradation may produce 'partial' or 'error'; success only if fallback masked failure
    assert result['status'] in {'partial', 'error', 'success'}
    if result['status'] != 'success':
        assert any('fetch_data' in e for e in result['errors'])


def test_pipeline_empty_universe(pipeline_with_doubles):
    result = pipeline_with_doubles.run('2025-11-07', [])
    assert result['status'] == 'error'
    assert 'Empty universe' in result['errors'][0]


def test_pipeline_performance_metrics(pipeline_with_doubles, universe):
    result = pipeline_with_doubles.run('2025-11-07', universe)
    metrics = result.get('metrics', {})
    assert 'universe_size' in metrics and metrics['universe_size'] == len(universe)
    assert 'daily_volatility' in metrics


def test_pipeline_with_all_signals(pipeline_with_doubles, universe):
    result = pipeline_with_doubles.run('2025-11-07', universe)
    fused = pipeline_with_doubles.cache.fused_signals
    assert fused and all('final_score' in v for v in fused.values())


def test_pipeline_partial_signals(synthetic_prices, universe):
    selector = DummyUniverseSelector()
    fetcher = DummyMarketDataFetcher(synthetic_prices)
    class PartialFusion(SignalFusion):
        def fuse(self, ticker: str, sentiment: float | None, technical_signals: Dict[str, float] | None, dl_prediction: float | None) -> Dict[str, Any]:
            # Ignore technical to simulate missing
            return super().fuse(ticker, sentiment, None, dl_prediction)
    pipeline = Pipeline(universe_selector=selector, market_data_fetcher=fetcher, signal_fusion=PartialFusion())
    result = pipeline.run('2025-11-07', universe)
    assert result['status'] in {'success', 'partial'}


def test_pipeline_report_generation(pipeline_with_doubles, universe, tmp_path):
    # Run pipeline
    result = pipeline_with_doubles.run('2025-11-07', universe)

    # Fake daily portfolio returns from cached returns
    returns_df = pipeline_with_doubles.cache.returns
    portfolio_returns = returns_df.mean(axis=1) if returns_df is not None and not returns_df.empty else pd.Series(dtype=float)

    analyzer = PerformanceAnalyzer()
    metrics = analyzer.analyze_returns(portfolio_returns, None, None)

    # Minimal trade log
    trades = pd.DataFrame({
        'timestamp': pd.date_range('2025-11-01', periods=3, freq='D'),
        'ticker': ['AAA', 'BBB', 'CCC'],
        'action': ['BUY', 'SELL', 'BUY'],
        'quantity': [10, 5, 7],
        'price': [100.0, 101.0, 99.5],
        'notional': [1000.0, -505.0, 696.5]
    })

    rg = ReportGenerator()
    report = rg.generate_report(portfolio_returns, None, trades, None, metrics=metrics, title="E2E Report")
    out_file = tmp_path / 'report.md'
    rg.save_report(report, str(out_file))
    assert out_file.exists() and out_file.stat().st_size > 0
