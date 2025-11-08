"""
Tests for FundamentalScreener (MVP).
"""

from unittest.mock import patch

import pytest

from financial_analyzer.universe.fundamental_screener import FundamentalScreener


def test_init():
    fs = FundamentalScreener()
    assert isinstance(fs, FundamentalScreener)


def test_screen_basic():
    fs = FundamentalScreener()
    tickers = ["AAPL", "MSFT", "GOOGL"]
    result = fs.screen(tickers, criteria={"pe_min": 5, "pe_max": 30})
    assert result == tickers


def test_screen_empty_list():
    fs = FundamentalScreener()
    assert fs.screen([], {}) == []


def test_screen_none_tickers():
    fs = FundamentalScreener()
    assert fs.screen(None, {}) == []


def test_screen_all_criteria_present():
    fs = FundamentalScreener()
    krit = {"pe_min": 5, "pe_max": 25, "roe_min": 0.15, "debt_equity_max": 1.2, "dividend_yield_min": 0.02}
    tickers = ["IBM", "ORCL"]
    result = fs.screen(tickers, krit)
    assert result == tickers


def test_screen_partial_criteria():
    fs = FundamentalScreener()
    krit = {"pe_min": 10}
    tickers = ["META", "NVDA"]
    assert fs.screen(tickers, krit) == tickers


def test_screen_invalid_criteria_keys():
    fs = FundamentalScreener()
    krit = {"unknown_metric": 123}
    tickers = ["SHOP"]
    assert fs.screen(tickers, krit) == tickers


def test_screen_none_values():
    fs = FundamentalScreener()
    krit = {"pe_min": None, "pe_max": None}
    tickers = ["ADBE", "INTC"]
    assert fs.screen(tickers, krit) == tickers


def test_screen_logs_warning(caplog):
    fs = FundamentalScreener()
    tickers = ["AAPL"]
    with caplog.at_level("WARNING"):
        _ = fs.screen(tickers, {"pe_min": 5})
    assert any("not yet integrated" in r.message.lower() for r in caplog.records)


def test_screen_accepts_non_list_iterable():
    fs = FundamentalScreener()
    tickers = tuple(["A", "B"])
    result = fs.screen(tickers, {})
    assert result == ["A", "B"]
