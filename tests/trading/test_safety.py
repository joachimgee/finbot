"""Tests du garde-fou de sûreté du mode de trading (P0)."""

import pytest

from financial_analyzer.trading.safety import (
    LIVE_BASE_URL,
    LIVE_CONFIRM_TOKEN,
    LIVE_ENABLE_ENV,
    PAPER_BASE_URL,
    LiveTradingNotEnabledError,
    TradingMode,
    assert_live_allowed,
    base_url_for_mode,
    live_trading_enabled,
    resolve_trading_mode,
)


@pytest.fixture(autouse=True)
def _clear_live_env(monkeypatch):
    """Chaque test part d'un environnement sans activation live."""
    monkeypatch.delenv(LIVE_ENABLE_ENV, raising=False)


# --------------------------- live_trading_enabled ---------------------------


def test_live_disabled_by_default():
    assert live_trading_enabled() is False


@pytest.mark.parametrize("val", ["", "true", "1", "yes", "live", "I_UNDERSTAND", "  "])
def test_live_stays_disabled_on_wrong_values(monkeypatch, val):
    monkeypatch.setenv(LIVE_ENABLE_ENV, val)
    assert live_trading_enabled() is False


def test_live_enabled_only_on_exact_token(monkeypatch):
    monkeypatch.setenv(LIVE_ENABLE_ENV, LIVE_CONFIRM_TOKEN)
    assert live_trading_enabled() is True


def test_live_token_tolerates_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv(LIVE_ENABLE_ENV, f"  {LIVE_CONFIRM_TOKEN}  ")
    assert live_trading_enabled() is True


# --------------------------- resolve_trading_mode ---------------------------


def test_paper_always_resolves_paper():
    assert resolve_trading_mode("paper") is TradingMode.PAPER


def test_live_downgraded_to_paper_when_disabled():
    assert resolve_trading_mode("live") is TradingMode.PAPER


def test_live_honored_when_enabled(monkeypatch):
    monkeypatch.setenv(LIVE_ENABLE_ENV, LIVE_CONFIRM_TOKEN)
    assert resolve_trading_mode("live") is TradingMode.LIVE


def test_resolve_is_case_insensitive():
    assert resolve_trading_mode("PAPER") is TradingMode.PAPER
    assert resolve_trading_mode(TradingMode.LIVE) is TradingMode.PAPER  # disabled


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        resolve_trading_mode("simulation")


# --------------------------- base_url_for_mode ---------------------------


def test_base_url_paper():
    assert base_url_for_mode("paper") == PAPER_BASE_URL


def test_base_url_live():
    assert base_url_for_mode("live") == LIVE_BASE_URL


# --------------------------- assert_live_allowed ---------------------------


def test_assert_paper_never_raises():
    assert_live_allowed("paper")  # ne lève pas


def test_assert_live_raises_when_disabled():
    with pytest.raises(LiveTradingNotEnabledError):
        assert_live_allowed("live")


def test_assert_live_ok_when_enabled(monkeypatch):
    monkeypatch.setenv(LIVE_ENABLE_ENV, LIVE_CONFIRM_TOKEN)
    assert_live_allowed("live")  # ne lève pas
