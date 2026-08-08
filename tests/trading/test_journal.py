"""Tests du journal d'exécution persistant (P5)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from financial_analyzer.trading.journal import TradingJournal
from financial_analyzer.trading.order_gateway import OrderGateway
from financial_analyzer.trading.risk_guard import RiskLimitExceeded


def test_records_and_reads_order(tmp_path):
    j = TradingJournal(tmp_path / "sub" / "journal.jsonl")  # parent dir auto-created
    j.record_order(
        symbol="AAPL", side="buy", qty=10, order_type="market",
        mode="paper", status="accepted", order_id="x1", price=150.0,
    )
    orders = j.orders()
    assert len(orders) == 1
    assert orders[0]["symbol"] == "AAPL"
    assert orders[0]["status"] == "accepted"
    assert "ts" in orders[0]  # timestamped


def test_append_only_and_filters(tmp_path):
    j = TradingJournal(tmp_path / "journal.jsonl")
    j.record_order(symbol="AAPL", side="buy", qty=1, order_type="market", mode="paper", status="accepted")
    j.record_snapshot(equity=100000.0, cash=50000.0, n_positions=3)
    j.record_order(symbol="MSFT", side="sell", qty=2, order_type="market", mode="paper", status="rejected")
    assert len(j.read()) == 3
    assert len(j.orders()) == 2
    assert len(j.snapshots()) == 1
    assert j.snapshots()[0]["equity"] == 100000.0


# --------------------------- gateway integration ---------------------------

def _gw(journal, mode="paper"):
    broker = MagicMock()
    broker.mode = mode
    broker.submit_order.return_value = {"order_id": "abc", "status": "accepted", "filled_qty": 10}
    risk = MagicMock()
    risk.validate_order.return_value = None
    return OrderGateway(broker, risk, journal=journal), broker, risk


def test_gateway_journals_submission(tmp_path):
    j = TradingJournal(tmp_path / "j.jsonl")
    gw, _, _ = _gw(j)
    gw.submit("AAPL", 10, "buy", price=150.0)
    orders = j.orders()
    assert len(orders) == 1
    assert orders[0]["status"] == "accepted"
    assert orders[0]["order_id"] == "abc"
    assert orders[0]["filled_qty"] == 10


def test_gateway_journals_rejection(tmp_path):
    j = TradingJournal(tmp_path / "j.jsonl")
    gw, broker, risk = _gw(j)
    risk.validate_order.side_effect = RiskLimitExceeded("too big")
    with pytest.raises(RiskLimitExceeded):
        gw.submit("AAPL", 99999, "buy", price=150.0)
    broker.submit_order.assert_not_called()
    orders = j.orders()
    assert len(orders) == 1
    assert orders[0]["status"] == "rejected"
    assert "too big" in orders[0]["reason"]


def test_gateway_journals_dry_run(tmp_path):
    j = TradingJournal(tmp_path / "j.jsonl")
    gw, _, _ = _gw(j)
    gw.submit("AAPL", 10, "buy", price=150.0, dry_run=True)
    assert j.orders()[0]["status"] == "dry_run"


def test_journal_failure_does_not_break_submit(tmp_path):
    bad = MagicMock()
    bad.record_order.side_effect = OSError("disk full")
    gw, broker, _ = _gw(bad)
    # Must still submit despite the journal blowing up.
    result = gw.submit("AAPL", 10, "buy", price=150.0)
    assert result["order_id"] == "abc"
    broker.submit_order.assert_called_once()


def test_gateway_without_journal_still_works(tmp_path):
    broker = MagicMock()
    broker.mode = "paper"
    broker.submit_order.return_value = {"order_id": "z"}
    gw = OrderGateway(broker, MagicMock())  # no journal
    assert gw.submit("AAPL", 1, "buy", price=1.0)["order_id"] == "z"
