"""Tests de la réconciliation ordres journalisés ↔ broker (P5)."""
from __future__ import annotations

from financial_analyzer.trading.reconciliation import (
    positions_from_orders,
    reconcile_orders,
    reconcile_positions,
)


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


class TestSinceScoping:
    """Le bornage au début du run — sans lui le critère #1 du runbook est inatteignable.

    ``get_orders`` renvoie les N derniers ordres du COMPTE, stratégies précédentes
    comprises. Sans bornage, chacun est compté « inattendu chez le broker » (= ayant
    contourné le chokepoint) et la réconciliation sort ``ok=false`` à perpétuité.
    """

    @staticmethod
    def _broker(oid, ts, symbol="AAA"):
        return {"order_id": oid, "symbol": symbol, "status": "filled", "submitted_at": ts}

    def test_prior_session_orders_are_ignored(self) -> None:
        run_start = "2026-08-18T14:00:00+00:00"
        journal = [{"order_id": "new1", "symbol": "AAA", "status": "filled"}]
        broker = [
            self._broker("new1", "2026-08-18T14:05:00+00:00"),
            self._broker("old1", "2026-08-01T10:00:00+00:00", "ORCL"),  # session passée
        ]
        assert not reconcile_orders(journal, broker).ok      # sans bornage : faux écart
        rep = reconcile_orders(journal, broker, since=run_start)
        assert rep.ok and len(rep.matched) == 1 and not rep.unexpected_at_broker

    def test_unlogged_order_during_the_run_is_still_flagged(self) -> None:
        """Le bornage ne relâche pas le drapeau rouge : un ordre du run hors journal."""
        run_start = "2026-08-18T14:00:00+00:00"
        journal = [{"order_id": "new1", "symbol": "AAA", "status": "filled"}]
        broker = [
            self._broker("new1", "2026-08-18T14:05:00+00:00"),
            self._broker("rogue", "2026-08-18T14:07:00+00:00", "ZZZ"),  # hors chokepoint
        ]
        rep = reconcile_orders(journal, broker, since=run_start)
        assert not rep.ok
        assert [o["symbol"] for o in rep.unexpected_at_broker] == ["ZZZ"]

    def test_missing_at_broker_is_detected_regardless_of_since(self) -> None:
        """Un ordre journalisé introuvable chez le broker reste une alarme."""
        journal = [{"order_id": "lost", "symbol": "AAA", "status": "filled"}]
        rep = reconcile_orders(journal, [], since="2026-08-18T14:00:00+00:00")
        assert not rep.ok and len(rep.missing_at_broker) == 1

    def test_logged_order_older_than_since_is_still_matched(self) -> None:
        """Un ordre au journal mais antérieur au bornage doit rester apparié."""
        journal = [{"order_id": "early", "symbol": "AAA", "status": "filled"}]
        broker = [self._broker("early", "2026-08-18T13:59:00+00:00")]
        rep = reconcile_orders(journal, broker, since="2026-08-18T14:00:00+00:00")
        assert rep.ok and len(rep.matched) == 1 and not rep.missing_at_broker

    def test_without_since_behaviour_is_unchanged(self) -> None:
        journal = [{"order_id": "a", "symbol": "AAA", "status": "filled"}]
        broker = [self._broker("a", "2026-08-18T14:05:00+00:00")]
        assert reconcile_orders(journal, broker).ok


class TestPositionReconciliation:
    """Contrôle des jours où le book est TENU : positions ↔ historique d'ordres.

    Sans ce contrôle, le critère #1 du runbook n'avance qu'un jour sur 21 (~1,7 an).
    Mais un contrôle qui ne peut pas échouer serait pire que rien : les tests
    ci-dessous vérifient d'abord qu'il **échoue quand il doit**.
    """

    @staticmethod
    def _order(symbol, side, qty, status="filled"):
        return {"symbol": symbol, "side": side, "filled_qty": qty, "status": status,
                "order_id": f"{symbol}-{side}-{qty}"}

    @staticmethod
    def _pos(symbol, qty):
        return {"symbol": symbol, "qty": qty}

    # --- reconstruction ---

    def test_positions_are_rebuilt_from_fills(self) -> None:
        orders = [self._order("AAA", "buy", 100), self._order("BBB", "sell", 50)]
        assert positions_from_orders(orders) == {"AAA": 100.0, "BBB": -50.0}

    def test_closed_position_disappears_from_expectation(self) -> None:
        """Une clôture normale ne doit produire aucun bruit (net nul → écarté)."""
        orders = [self._order("AAA", "buy", 100), self._order("AAA", "sell", 100)]
        assert positions_from_orders(orders) == {}

    def test_unfilled_orders_are_ignored(self) -> None:
        orders = [self._order("AAA", "buy", 100),
                  self._order("AAA", "buy", 999, status="canceled")]
        assert positions_from_orders(orders) == {"AAA": 100.0}

    # --- le contrôle échoue quand il doit ---

    def test_position_with_no_matching_order_is_flagged(self) -> None:
        """Drapeau rouge : une ligne détenue qu'aucun ordre n'explique."""
        rep = reconcile_positions([self._order("AAA", "buy", 100)],
                                  [self._pos("AAA", 100), self._pos("ROGUE", 42)])
        assert not rep.ok
        assert [u["symbol"] for u in rep.unexpected] == ["ROGUE"]

    def test_quantity_mismatch_is_flagged(self) -> None:
        rep = reconcile_positions([self._order("AAA", "buy", 100)],
                                  [self._pos("AAA", 137)])
        assert not rep.ok
        assert rep.qty_mismatch[0]["expected_qty"] == 100
        assert rep.qty_mismatch[0]["actual_qty"] == 137

    def test_side_flip_is_flagged_as_mismatch(self) -> None:
        """Un short devenu long est un écart, pas un appariement."""
        rep = reconcile_positions([self._order("AAA", "sell", 100)],
                                  [self._pos("AAA", 100)])
        assert not rep.ok and rep.qty_mismatch

    # --- ... et reste vert quand tout va bien ---

    def test_clean_book_reconciles(self) -> None:
        orders = [self._order("AAA", "buy", 100), self._order("BBB", "sell", 50)]
        rep = reconcile_positions(orders, [self._pos("AAA", 100), self._pos("BBB", -50)])
        assert rep.ok and len(rep.matched) == 2 and not rep.unexpected

    def test_truncated_history_does_not_fail_the_run(self) -> None:
        """L'asymétrie assumée : « attendu non détenu » est INFORMATIF.

        ``get_orders`` ne renvoie qu'une fenêtre : un titre dont les achats sont hors
        fenêtre et les ventes dedans apparaît attendu-short sans anomalie réelle
        (mesuré : 22 faux écarts de ce type sur le compte réel). En faire un échec
        reproduirait le défaut qu'on vient de corriger — une alarme toujours rouge.
        """
        orders = [self._order("AAA", "buy", 100), self._order("OLD", "sell", 30)]
        rep = reconcile_positions(orders, [self._pos("AAA", 100)])
        assert rep.ok
        assert [u["symbol"] for u in rep.unexplained_expected] == ["OLD"]

    def test_truncation_is_reported_when_history_hits_the_limit(self) -> None:
        orders = [self._order(f"S{i}", "buy", 1) for i in range(10)]
        positions = [self._pos(f"S{i}", 1) for i in range(10)]
        assert reconcile_positions(orders, positions, order_limit=10).history_truncated
        assert not reconcile_positions(orders, positions, order_limit=50).history_truncated

    # --- intégration avec le critère de readiness ---

    def test_report_is_countable_by_the_readiness_criterion(self) -> None:
        """Le rapport doit porter le même ``kind`` que celui des ordres, sinon le
        critère #1 ne le compte pas — c'est tout l'objet du correctif."""
        rep = reconcile_positions([self._order("AAA", "buy", 100)], [self._pos("AAA", 100)])
        d = rep.to_dict()
        assert d["kind"] == "reconciliation" and d["ok"] is True
        assert d["scope"] == "positions"      # distingue les deux portées à la lecture

    def test_empty_book_reconciles(self) -> None:
        assert reconcile_positions([], []).ok
