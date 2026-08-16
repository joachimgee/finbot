"""Tests du fetcher Yahoo (parsing de la réponse chart, sans réseau)."""
from __future__ import annotations

import time

import pandas as pd

from financial_analyzer.data import yahoo_history


class _FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p


def _chart_payload(ts, adjclose):
    return {"chart": {"result": [{
        "timestamp": ts,
        "indicators": {"adjclose": [{"adjclose": adjclose}],
                       "quote": [{"close": adjclose}]},
    }]}}


def test_fetch_daily_close_parses_adjclose(monkeypatch):
    days = [int(time.mktime(time.strptime(f"2020-01-{d:02d}", "%Y-%m-%d"))) for d in (2, 3, 6)]
    payload = _chart_payload(days, [100.0, 101.0, 102.0])

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResp(payload)

    monkeypatch.setattr(yahoo_history.requests, "get", fake_get)
    df = yahoo_history.fetch_daily_close(["AAPL"], "2020-01-01", "2020-02-01", pause=0.0)
    assert list(df.columns) == ["AAPL"]
    assert len(df) == 3
    assert df["AAPL"].iloc[-1] == 102.0


def test_fetch_skips_unavailable_symbol(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResp({"chart": {"result": [None]}}, status=200)

    monkeypatch.setattr(yahoo_history.requests, "get", fake_get)
    df = yahoo_history.fetch_daily_close(["ZZZZ"], "2020-01-01", "2020-02-01", pause=0.0)
    assert df.empty


def test_load_or_fetch_uses_cache(tmp_path, monkeypatch):
    cache = tmp_path / "panel.csv"
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    pd.DataFrame({"AAPL": [1.0, 2.0, 3.0]}, index=idx).to_csv(cache)

    def boom(*a, **k):  # ne doit PAS être appelé si le cache existe
        raise AssertionError("fetch appelé malgré le cache")

    monkeypatch.setattr(yahoo_history, "fetch_daily_close", boom)
    df = yahoo_history.load_or_fetch_yahoo(["AAPL"], "2020-01-01", "2020-02-01", str(cache))
    assert list(df.columns) == ["AAPL"] and len(df) == 3
