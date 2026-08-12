"""Kill-switch paper↔live (P4) — la procédure d'arrêt du runbook, testée.

Le runbook (`docs/RUNBOOK_PAPER_TO_LIVE.md`) définit l'arrêt d'urgence comme :
*retirer* la variable ``FINBOT_ENABLE_LIVE_TRADING``. Ce test exerce le cycle
complet activation → live autorisé → **retrait** → live de nouveau refusé, au
niveau de la politique de sûreté ET du chokepoint d'exécution (OrderGateway).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from financial_analyzer.trading.order_gateway import OrderGateway
from financial_analyzer.trading.safety import (
    LIVE_CONFIRM_TOKEN,
    LIVE_ENABLE_ENV,
    LiveTradingNotEnabledError,
    assert_live_allowed,
    live_trading_enabled,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(LIVE_ENABLE_ENV, raising=False)


def _live_gateway():
    broker = MagicMock()
    broker.mode = "live"
    broker.submit_order.return_value = {"order_id": "x", "status": "accepted"}
    risk = MagicMock()
    risk.validate_order.return_value = None
    return OrderGateway(broker, risk), broker


def test_kill_switch_full_cycle(monkeypatch) -> None:
    """Activer -> live passe ; retirer le jeton -> live re-refusé (arrêt effectif)."""
    gw, broker = _live_gateway()

    # 1) Désactivé par défaut : le live est refusé au chokepoint.
    with pytest.raises(LiveTradingNotEnabledError):
        gw.submit("AAPL", 1, "buy", price=100.0)
    broker.submit_order.assert_not_called()

    # 2) Activation : jeton exact -> le live passe.
    monkeypatch.setenv(LIVE_ENABLE_ENV, LIVE_CONFIRM_TOKEN)
    assert live_trading_enabled() is True
    gw.submit("AAPL", 1, "buy", price=100.0, idempotency_key="live-1")
    assert broker.submit_order.call_count == 1

    # 3) KILL-SWITCH : on retire la variable -> live immédiatement re-verrouillé.
    monkeypatch.delenv(LIVE_ENABLE_ENV, raising=False)
    assert live_trading_enabled() is False
    with pytest.raises(LiveTradingNotEnabledError):
        gw.submit("AAPL", 1, "buy", price=100.0, idempotency_key="live-2")
    assert broker.submit_order.call_count == 1  # aucune nouvelle soumission


def test_kill_switch_wrong_token_stays_locked(monkeypatch) -> None:
    """Une valeur approchante ne déverrouille pas (fail-safe strict)."""
    for bad in ("true", "1", "yes", LIVE_CONFIRM_TOKEN.lower(), "I_UNDERSTAND"):
        monkeypatch.setenv(LIVE_ENABLE_ENV, bad)
        assert live_trading_enabled() is False
        with pytest.raises(LiveTradingNotEnabledError):
            assert_live_allowed("live")


def test_paper_unaffected_by_kill_switch() -> None:
    """Le paper n'est jamais concerné par le kill-switch (toujours autorisé)."""
    assert_live_allowed("paper")  # ne lève pas, jeton ou non
