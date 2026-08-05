"""Tests du chokepoint d'exécution unique (OrderGateway, P0)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from financial_analyzer.trading.order_gateway import OrderGateway
from financial_analyzer.trading.risk_guard import (
    CircuitBreakerTriggered,
    RiskLimitExceeded,
)
from financial_analyzer.trading.safety import (
    LIVE_CONFIRM_TOKEN,
    LIVE_ENABLE_ENV,
    LiveTradingNotEnabledError,
)


@pytest.fixture(autouse=True)
def _clear_live_env(monkeypatch):
    monkeypatch.delenv(LIVE_ENABLE_ENV, raising=False)


def _make(mode: str = "paper"):
    broker = MagicMock()
    broker.mode = mode
    broker.submit_order.return_value = {"order_id": "abc123", "status": "accepted"}
    risk_guard = MagicMock()
    risk_guard.validate_order.return_value = None
    return OrderGateway(broker, risk_guard), broker, risk_guard


# --------------------------- chemin nominal ---------------------------


def test_happy_path_validates_then_submits():
    gw, broker, risk = _make()
    result = gw.submit("AAPL", 10, "buy", price=150.0)
    risk.validate_order.assert_called_once_with(symbol="AAPL", qty=10, side="buy", price=150.0)
    broker.submit_order.assert_called_once()
    assert result["order_id"] == "abc123"


def test_order_type_forwarded():
    gw, broker, _ = _make()
    gw.submit("AAPL", 5, "sell", price=10.0, order_type="limit")
    assert broker.submit_order.call_args.kwargs["order_type"] == "limit"


# --------------------------- garde de mode ---------------------------


def test_live_refused_when_disabled():
    gw, broker, risk = _make(mode="live")
    with pytest.raises(LiveTradingNotEnabledError):
        gw.submit("AAPL", 10, "buy", price=150.0)
    risk.validate_order.assert_not_called()
    broker.submit_order.assert_not_called()


def test_live_allowed_when_enabled(monkeypatch):
    monkeypatch.setenv(LIVE_ENABLE_ENV, LIVE_CONFIRM_TOKEN)
    gw, broker, _ = _make(mode="live")
    gw.submit("AAPL", 10, "buy", price=150.0)
    broker.submit_order.assert_called_once()


# --------------------------- risque -> pas de soumission ---------------------------


def test_risk_rejection_blocks_submission():
    gw, broker, risk = _make()
    risk.validate_order.side_effect = RiskLimitExceeded("too big")
    with pytest.raises(RiskLimitExceeded):
        gw.submit("AAPL", 10_000, "buy", price=150.0)
    broker.submit_order.assert_not_called()


def test_circuit_breaker_propagates():
    gw, broker, risk = _make()
    risk.validate_order.side_effect = CircuitBreakerTriggered("halt")
    with pytest.raises(CircuitBreakerTriggered):
        gw.submit("AAPL", 10, "buy", price=150.0)
    broker.submit_order.assert_not_called()


# --------------------------- idempotence ---------------------------


def test_idempotent_key_submitted_once():
    gw, broker, _ = _make()
    r1 = gw.submit("AAPL", 10, "buy", price=150.0, idempotency_key="daily-AAPL")
    r2 = gw.submit("AAPL", 10, "buy", price=150.0, idempotency_key="daily-AAPL")
    assert broker.submit_order.call_count == 1
    assert r1 == r2


def test_default_key_dedupes_identical_orders():
    gw, broker, _ = _make()
    gw.submit("AAPL", 10, "buy", price=150.0)
    gw.submit("AAPL", 10, "buy", price=151.0)  # même symbol/side/qty/type
    assert broker.submit_order.call_count == 1


def test_different_orders_not_deduped():
    gw, broker, _ = _make()
    gw.submit("AAPL", 10, "buy", price=150.0)
    gw.submit("AAPL", 20, "buy", price=150.0)
    assert broker.submit_order.call_count == 2


# --------------------------- dry_run ---------------------------


def test_dry_run_validates_but_does_not_submit():
    gw, broker, risk = _make()
    result = gw.submit("AAPL", 10, "buy", price=150.0, dry_run=True)
    risk.validate_order.assert_called_once()
    broker.submit_order.assert_not_called()
    assert result["status"] == "dry_run"


def test_dry_run_still_enforces_mode_guard():
    gw, _broker, _ = _make(mode="live")
    with pytest.raises(LiveTradingNotEnabledError):
        gw.submit("AAPL", 10, "buy", price=150.0, dry_run=True)
