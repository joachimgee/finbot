import sys
import types
import pandas as pd
import numpy as np
import datetime as dt

# Build a fake yfinance module with download and Ticker().history
class _FakeTicker:
    def __init__(self, sym):
        self.sym = sym
    def history(self, period=None, interval="1d", start=None, end=None):
        idx = pd.date_range(end=dt.datetime.now(), periods=5, freq="D")
        return pd.DataFrame({
            'Open': np.linspace(100, 104, 5),
            'High': np.linspace(101, 105, 5),
            'Low': np.linspace(99, 103, 5),
            'Close': np.linspace(100.5, 104.5, 5),
            'Volume': np.arange(5)+1,
        }, index=idx)

def _fake_download(symbols, period=None, interval="1d", start=None, end=None, group_by='column', auto_adjust=False, progress=False):
    # Return MultiIndex columns when symbols is list-like
    if isinstance(symbols, (list, tuple, set)):
        frames = []
        idx = pd.date_range(end=dt.datetime(2025, 1, 10), periods=5, freq="D")
        for sym in symbols:
            f = pd.DataFrame({
                (sym, 'Open'): np.linspace(100, 104, 5),
                (sym, 'High'): np.linspace(101, 105, 5),
                (sym, 'Low'): np.linspace(99, 103, 5),
                (sym, 'Close'): np.linspace(100.5, 104.5, 5),
                (sym, 'Volume'): np.arange(5)+1,
            }, index=idx)
            frames.append(f)
        df = pd.concat(frames, axis=1)
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        return df
    else:
        idx = pd.date_range(end=dt.datetime(2025, 1, 10), periods=5, freq="D")
        return pd.DataFrame({
            'Open': np.linspace(100, 104, 5),
            'High': np.linspace(101, 105, 5),
            'Low': np.linspace(99, 103, 5),
            'Close': np.linspace(100.5, 104.5, 5),
            'Volume': np.arange(5)+1,
        }, index=idx)

fake_yf = types.SimpleNamespace(Ticker=_FakeTicker, download=_fake_download)

import pytest

import financial_analyzer.data.market_data as _md
from financial_analyzer.data.market_data import MarketDataFetcher


@pytest.fixture(autouse=True)
def _fake_yfinance(monkeypatch):
    """Substitue yfinance dans le module market_data, pour ce fichier seulement.

    L'ancien `sys.modules['yfinance'] = fake_yf` (au niveau module) fuyait dans
    tous les tests collectés après ce fichier, et le SimpleNamespace sans
    __spec__ cassait la collection d'autres modules.
    """
    monkeypatch.setattr(_md, 'yf', fake_yf, raising=False)


def test_yfinance_batched_download_and_cache(tmp_path, monkeypatch):
    # Ensure cache is enabled and directory writable
    import financial_analyzer.config as config
    monkeypatch.setattr(config, 'CACHE_ENABLED', True, raising=False)
    monkeypatch.setattr(config, 'CACHE_DIR', tmp_path, raising=False)

    f = MarketDataFetcher(api_key=None)
    syms = ["AAPL","MSFT","NVDA"]
    out = f.get_historical_data(syms, period='1mo', interval='1d')
    assert isinstance(out, dict)
    assert set(out.keys()) == set(syms)
    for df in out.values():
        assert {'Open','High','Low','Close','Volume'}.issubset(df.columns)
        assert len(df) == 5

    # Call again and expect cache hit (just ensure it still works)
    out2 = f.get_historical_data(syms, period='1mo', interval='1d')
    assert set(out2.keys()) == set(syms)
