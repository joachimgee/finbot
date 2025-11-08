"""
Tests for TechnicalScreener (MVP).
"""

import pytest

from financial_analyzer.universe.technical_screener import TechnicalScreener


def test_init():
    ts = TechnicalScreener()
    assert isinstance(ts, TechnicalScreener)


def test_screen_basic():
    ts = TechnicalScreener()
    tickers = ["AAPL", "MSFT"]
    assert ts.screen(tickers, {"above_sma200": True}) == tickers


def test_screen_empty_list():
    ts = TechnicalScreener()
    assert ts.screen([], {}) == []


def test_screen_none_tickers():
    ts = TechnicalScreener()
    assert ts.screen(None, {}) == []


def test_screen_all_criteria_present():
    ts = TechnicalScreener()
    krit = {"above_sma200": True, "rsi_min": 30, "rsi_max": 70, "adx_max": 40}
    tickers = ["QQQ", "SPY"]
    assert ts.screen(tickers, krit) == tickers


def test_screen_partial_criteria():
    ts = TechnicalScreener()
    krit = {"rsi_min": 25}
    assert ts.screen(["TSLA"], krit) == ["TSLA"]


def test_screen_invalid_criteria_keys():
    ts = TechnicalScreener()
    krit = {"unknown_metric": 1}
    assert ts.screen(["IWM"], krit) == ["IWM"]


def test_screen_none_values():
    ts = TechnicalScreener()
    krit = {"rsi_min": None, "rsi_max": None, "adx_max": None}
    assert ts.screen(["AMD"], krit) == ["AMD"]


def test_screen_logs_warning(caplog):
    ts = TechnicalScreener()
    with caplog.at_level("WARNING"):
        _ = ts.screen(["AAPL"], {"rsi_min": 30})
    assert any("not yet integrated" in r.message.lower() for r in caplog.records)


def test_screen_accepts_non_list_iterable():
    ts = TechnicalScreener()
    tickers = {"A", "B"}
    res = ts.screen(tickers, {})
    assert sorted(res) == ["A", "B"]
