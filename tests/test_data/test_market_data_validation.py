import pandas as pd
import numpy as np
import pytest

from financial_analyzer.data.market_data import MarketDataFetcher


def test_supported_periods_non_empty():
    fetcher = MarketDataFetcher(api_key=None)
    periods = fetcher.supported_periods
    assert isinstance(periods, list)
    assert len(periods) > 0


def test_validate_ohlcv_raises_on_missing_volume():
    fetcher = MarketDataFetcher(api_key=None)
    idx = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    df = pd.DataFrame({
        "Open": np.linspace(100, 101, 5),
        "High": np.linspace(100, 102, 5),
        "Low": np.linspace(99, 100, 5),
        "Close": np.linspace(100, 101, 5),
        # Missing Volume
    }, index=idx)
    with pytest.raises(ValueError):
        fetcher.validate_ohlcv(df)
