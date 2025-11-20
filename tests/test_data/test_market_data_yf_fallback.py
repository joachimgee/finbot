import os
from typing import Dict
import pandas as pd
import numpy as np
import types
import pytest

from financial_analyzer.data.market_data import MarketDataFetcher


def _fake_history_df(n: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "Open": np.linspace(100, 101, n),
            "High": np.linspace(101, 102, n),
            "Low": np.linspace(99, 100, n),
            "Close": np.linspace(100, 101, n),
            "Volume": np.arange(n) + 1000,
        },
        index=idx,
    )
    return df


def test_yfinance_batch_empty_fallback(monkeypatch):
    # Force yf.download to return empty DataFrame (simulate API empty response)
    import yfinance as yf

    def fake_download(*args, **kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(yf, "download", fake_download)

    # Provide per-symbol history via Ticker().history
    class FakeTicker:
        def __init__(self, sym: str) -> None:
            self.sym = sym

        def history(self, *args, **kwargs) -> pd.DataFrame:
            return _fake_history_df(10)

    monkeypatch.setattr(yf, "Ticker", lambda sym: FakeTicker(sym))

    fetcher = MarketDataFetcher(api_key=None)
    data = fetcher.get_historical_data(["AAPL", "MSFT"], period="1mo")

    assert isinstance(data, dict)
    assert set(data.keys()) == {"AAPL", "MSFT"}
    for sym, df in data.items():
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        # Columns normalized
        assert {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns)


def test_yfinance_single_symbol_history_path(monkeypatch):
    # For single symbol, Ticker().history should be used
    import yfinance as yf

    class FakeTicker:
        def __init__(self, sym: str) -> None:
            self.sym = sym

        def history(self, *args, **kwargs) -> pd.DataFrame:
            return _fake_history_df(7)

    monkeypatch.setattr(yf, "Ticker", lambda sym: FakeTicker(sym))

    fetcher = MarketDataFetcher(api_key=None)
    df = fetcher.get_historical_data("AAPL", period="6mo")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns)
