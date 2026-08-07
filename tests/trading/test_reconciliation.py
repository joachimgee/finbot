"""Tests de la réconciliation ordres journalisés ↔ broker (P5)."""
from __future__ import annotations

from financial_analyzer.trading.reconciliation import reconcile_orders


def _j(order_id, symbol="AAPL", status="accepted"):
    return {"kind": "order", "symbol": symbol, "status": status, "order_id": order_id}


def _b(order_id, status="filled"):
    return {"order_id": order_id, "status": status}


def test_all_matched_and_filled():
    rep = reconcile_orders([_j("1"), _j("2")], [_b("1"), _b("2")])
    assert rep.ok
    assert len(rep.matched) == 2
    assert not rep.not_filled


def test_missing_at_broker_flagged():
    rep = reconcile_orders([_j("1"), _j("2")], [_b("1")])
    assert not rep.ok
    assert len(rep.missing_at_broker) == 1
    assert rep.missing_at_broker[0]["order_id"] == "2"


def test_unexpected_at_broker_flagged():
    # An order at the broker with no journal trace = bypassed the chokepoint.
    rep = reconcile_orders([_j("1")], [_b("1"), _b("99")])
    assert not rep.ok
    assert len(rep.unexpected_at_broker) == 1
    assert rep.unexpected_at_broker[0]["order_id"] == "99"


def test_not_filled_reported_but_still_ok():
    # A matched-but-unfilled order is noted, but is not a critical discrepancy.
    rep = reconcile_orders([_j("1")], [_b("1", status="canceled")])
    assert rep.ok  # matched, just not filled
    assert len(rep.not_filled) == 1
    assert rep.not_filled[0]["broker_status"] == "canceled"


def test_non_submitted_journal_entries_ignored():
    # rejected / dry_run / duplicate journal entries are not expected at broker.
    journal = [
        _j("1", status="rejected"),
        _j(None, status="dry_run"),
        {"kind": "order", "symbol": "X", "status": "duplicate_skipped", "order_id": "d"},
        _j("2", status="accepted"),
    ]
    rep = reconcile_orders(journal, [_b("2")])
    assert rep.ok
    assert len(rep.matched) == 1


def test_id_key_tolerance():
    # broker may key on 'id' instead of 'order_id'.
    rep = reconcile_orders([_j("1")], [{"id": "1", "status": "filled"}])
    assert rep.ok
    assert len(rep.matched) == 1


def test_summary_mentions_discrepancy():
    rep = reconcile_orders([_j("1")], [_b("2")])
    assert "ÉCART" in rep.summary()


def test_report_round_trips_through_journal(tmp_path):
    from financial_analyzer.trading.journal import TradingJournal
    j = TradingJournal(tmp_path / "j.jsonl")
    rep = reconcile_orders([_j("1")], [_b("2")])  # 1 missing, 1 unexpected
    j.record_reconciliation(rep.to_dict())
    events = [e for e in j.read() if e.get("kind") == "reconciliation"]
    assert len(events) == 1
    assert events[0]["ok"] is False
    assert len(events[0]["missing_at_broker"]) == 1
    assert len(events[0]["unexpected_at_broker"]) == 1
