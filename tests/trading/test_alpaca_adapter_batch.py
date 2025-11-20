import os
import sys
import types
import pandas as pd
import numpy as np
import datetime as dt
import pytest

# Inject a minimal fake alpaca_trade_api into sys.modules so we can import the adapter
class _FakeOrder:
    def __init__(self, oid="oid", symbol="AAPL", qty=1, side="buy", typ="market", status="new"):
        self.id = oid
        self.symbol = symbol
        self.qty = qty
        self.side = side
        self.type = typ
        self.status = status
        self.filled_qty = 0
        self.filled_avg_price = None
        self.submitted_at = dt.datetime.now()
        self.filled_at = None

class _FakeAccount:
    def __init__(self):
        self.cash = 100000
        self.equity = 100000
        self.buying_power = 100000
        self.portfolio_value = 100000
        self.initial_margin = 0
        self.maintenance_margin = 0
        self.daytrade_count = 0
        self.status = "ACTIVE"

class _FakeClock:
    def __init__(self, is_open=True):
        self.is_open = is_open

class _FakeREST:
    def __init__(self, *_, **__):
        pass

    def get_account(self):
        return _FakeAccount()

    def get_clock(self):
        return _FakeClock(True)

    def list_orders(self, status="all", limit=100):
        return []

    def get_bars(self, symbols, timeframe, start, end, feed=None):
        # Support both str and list for symbols; return object with .df
        idx = pd.date_range(end=dt.datetime.now(), periods=5, freq="D")
        def df_for(sym):
            return pd.DataFrame({
                'o': np.linspace(100, 104, 5),
                'h': np.linspace(101, 105, 5),
                'l': np.linspace(99, 103, 5),
                'c': np.linspace(100.5, 104.5, 5),
                'v': np.arange(5) + 1,
            }, index=idx)
        class _Obj:
            pass
        obj = _Obj()
        if isinstance(symbols, (list, tuple)):
            # MultiIndex: first level symbol
            frames = []
            arrays = []
            for sym in symbols:
                f = df_for(sym)
                f.index = pd.MultiIndex.from_product([[sym], f.index])
                frames.append(f)
            df = pd.concat(frames)
            obj.df = df
        else:
            obj.df = df_for(symbols)
        return obj

    def submit_order(self, symbol, qty, side, type, limit_price=None, time_in_force='day'):
        return _FakeOrder(symbol=symbol, qty=qty, side=side, typ=type, status="accepted")

    def cancel_order(self, order_id):
        # Return order-like with canceled status
        o = _FakeOrder(oid=order_id)
        o.status = 'canceled'
        return o

# Build fake module
fake_mod = types.ModuleType("alpaca_trade_api")
fake_mod.REST = _FakeREST
fake_mod.rest = types.SimpleNamespace(APIError=Exception)

sys.modules.setdefault("alpaca_trade_api", fake_mod)

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter


def test_from_env_constructor(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "KEY")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "SECRET")
    a = AlpacaAdapter.from_env()
    assert a.base_url.startswith("https://paper-api")


def test_connect_and_batched_bars(monkeypatch):
    a = AlpacaAdapter(api_key="k", secret_key="s")
    a.connect()
    end = dt.datetime.now()
    start = end - dt.timedelta(days=10)
    out = a.get_bars_multi(["AAPL","MSFT","NVDA"], start, end, timeframe='1D', chunk_size=2)
    assert set(out.keys()) == {"AAPL","MSFT","NVDA"}
    for sym, df in out.items():
        assert {'open','high','low','close','volume'}.issubset(df.columns)
        assert len(df) == 5


def test_single_get_bars_works(monkeypatch):
    a = AlpacaAdapter(api_key="k", secret_key="s")
    a.connect()
    end = dt.datetime.now()
    start = end - dt.timedelta(days=10)
    df = a.get_bars("AAPL", start, end, timeframe='1D')
    assert {'open','high','low','close','volume'}.issubset(df.columns)


def test_cancel_order_maps_status(monkeypatch):
    a = AlpacaAdapter(api_key="k", secret_key="s")
    a.connect()
    res = a.cancel_order("abc")
    assert res['status'] == 'canceled'
