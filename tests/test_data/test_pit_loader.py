"""P3: PITDataLoader real-data path (Alpaca) with safe synthetic fallback."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from financial_analyzer.data.pit_loader import PITDataLoader, RealDataUnavailableError

_OHLCV = ["open", "high", "low", "close", "volume"]


# ------------------------------- synthetic -------------------------------

def test_synthetic_default_is_deterministic():
    a = PITDataLoader().load_prices(["AAPL"], "2020-01-01", "2020-03-01")
    b = PITDataLoader().load_prices(["AAPL"], "2020-01-01", "2020-03-01")
    assert list(a["AAPL"].columns) == _OHLCV
    pd.testing.assert_frame_equal(a["AAPL"], b["AAPL"])


def test_unknown_source_raises():
    with pytest.raises(ValueError):
        PITDataLoader(source="bogus").load_prices(["AAPL"], "2020-01-01", "2020-02-01")


# ------------------------------- alpaca path -------------------------------

def _fake_ohlcv(symbols, *_a, **_k):
    idx = pd.date_range("2020-01-01", periods=30, freq="B")
    return {
        s: pd.DataFrame(
            {c: range(len(idx)) for c in _OHLCV}, index=idx
        )
        for s in symbols
    }


def test_alpaca_source_returns_real_data():
    with patch(
        "financial_analyzer.data.alpaca_history.fetch_daily_ohlcv",
        side_effect=lambda syms, *a, **k: _fake_ohlcv(syms),
    ):
        data = PITDataLoader(source="alpaca").load_prices(["AAPL", "MSFT"], "2020-01-01", "2020-02-14")
    assert set(data) == {"AAPL", "MSFT"}
    assert list(data["AAPL"].columns) == _OHLCV


def test_alpaca_falls_back_to_synthetic_on_failure(caplog):
    with patch(
        "financial_analyzer.data.alpaca_history.fetch_daily_ohlcv",
        side_effect=RuntimeError("no creds"),
    ):
        data = PITDataLoader(source="alpaca").load_prices(["AAPL"], "2020-01-01", "2020-02-01")
    # Still returns usable synthetic data...
    assert list(data["AAPL"].columns) == _OHLCV
    # ...but the fallback is loud.
    assert any("SYNTH" in r.message.upper() for r in caplog.records)


def test_alpaca_empty_result_triggers_fallback():
    with patch(
        "financial_analyzer.data.alpaca_history.fetch_daily_ohlcv",
        return_value={},
    ):
        data = PITDataLoader(source="alpaca").load_prices(["AAPL"], "2020-01-01", "2020-02-01")
    assert "AAPL" in data  # synthetic fallback populated it


def test_fallback_forbidden_raises():
    with patch(
        "financial_analyzer.data.alpaca_history.fetch_daily_ohlcv",
        side_effect=RuntimeError("no creds"),
    ), pytest.raises(RealDataUnavailableError):
        PITDataLoader(source="alpaca", allow_synthetic_fallback=False).load_prices(
            ["AAPL"], "2020-01-01", "2020-02-01"
        )


# --------------------------- fetch_daily_ohlcv parsing ---------------------------

def test_fetch_daily_ohlcv_parses_payload(monkeypatch):
    from financial_analyzer.data import alpaca_history

    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "bars": {
                    "AAPL": [
                        {"t": "2020-01-02T05:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100},
                        {"t": "2020-01-03T05:00:00Z", "o": 1.5, "h": 3, "l": 1, "c": 2.0, "v": 200},
                    ]
                },
                "next_page_token": None,
            }

    monkeypatch.setattr(alpaca_history.requests, "get", lambda *a, **k: _Resp())
    out = alpaca_history.fetch_daily_ohlcv(["AAPL"], "2020-01-01", "2020-01-31")
    assert list(out["AAPL"].columns) == _OHLCV
    assert out["AAPL"]["close"].tolist() == [1.5, 2.0]
    assert len(out["AAPL"]) == 2
