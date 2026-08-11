"""Garde de cadence de rééquilibrage (P1) — réaliser l'edge net de coûts.

Verrouille : cadence lue depuis le registre validé, persistance de l'état
(survit à un nouvel objet / redémarrage), fenêtre en jours ouvrés, et
dégradation gracieuse (état absent/corrompu -> rééquilibrage autorisé).
"""
from __future__ import annotations

from datetime import date

import numpy as np

from financial_analyzer.trading.rebalance_gate import RebalanceGate


def _bd_offset(d: date, n: int) -> date:
    """Date décalée de n jours ouvrés (via numpy busday)."""
    return date.fromisoformat(str(np.busday_offset(d.isoformat(), n)))


def test_reads_cadence_from_validated_registry(tmp_path) -> None:
    gate = RebalanceGate.from_validated_signal(tmp_path / "state.json")
    assert gate.rebalance_every == 10  # momentum_12_1 @ reb=10


def test_unknown_signal_falls_back_open(tmp_path) -> None:
    """Signal absent du registre -> pas de gate (cadence 1) plutôt qu'échec."""
    gate = RebalanceGate.from_validated_signal(tmp_path / "s.json", name="inexistant")
    assert gate.rebalance_every == 1
    assert gate.is_due(date(2026, 1, 5))


def test_due_when_never_rebalanced(tmp_path) -> None:
    gate = RebalanceGate(tmp_path / "s.json", rebalance_every=10)
    assert gate.is_due(date(2026, 8, 11)) is True
    assert gate.sessions_since(date(2026, 8, 11)) is None
    assert gate.sessions_until_due(date(2026, 8, 11)) == 0


def test_not_due_same_day_after_record(tmp_path) -> None:
    gate = RebalanceGate(tmp_path / "s.json", rebalance_every=10)
    d0 = date(2026, 8, 11)
    gate.record(d0)
    assert gate.is_due(d0) is False
    assert gate.sessions_since(d0) == 0
    assert gate.sessions_until_due(d0) == 10


def test_due_boundary_is_exact_business_days(tmp_path) -> None:
    gate = RebalanceGate(tmp_path / "s.json", rebalance_every=10)
    d0 = date(2026, 8, 11)
    gate.record(d0)
    # 9 jours ouvrés : pas encore dû ; 10 : dû (seuil >=).
    assert gate.is_due(_bd_offset(d0, 9)) is False
    assert gate.sessions_until_due(_bd_offset(d0, 9)) == 1
    assert gate.is_due(_bd_offset(d0, 10)) is True
    assert gate.sessions_until_due(_bd_offset(d0, 10)) == 0


def test_state_persists_across_instances(tmp_path) -> None:
    """La cadence survit à un nouvel objet (donc à un redémarrage de conteneur)."""
    path = tmp_path / "s.json"
    RebalanceGate(path, rebalance_every=10).record(date(2026, 8, 11))
    fresh = RebalanceGate(path, rebalance_every=10)
    assert fresh.is_due(date(2026, 8, 11)) is False
    assert fresh.sessions_since(date(2026, 8, 11)) == 0


def test_clock_skew_does_not_go_negative(tmp_path) -> None:
    gate = RebalanceGate(tmp_path / "s.json", rebalance_every=10)
    gate.record(date(2026, 8, 11))
    # "now" antérieur au dernier rééquilibrage -> 0, pas de valeur négative.
    assert gate.sessions_since(date(2026, 8, 1)) == 0
    assert gate.is_due(date(2026, 8, 1)) is False


def test_corrupt_state_fails_open(tmp_path) -> None:
    """Un état illisible n'immobilise pas le trading : rééquilibrage autorisé."""
    path = tmp_path / "s.json"
    path.write_text("{ not valid json", encoding="utf-8")
    gate = RebalanceGate(path, rebalance_every=10)
    assert gate.is_due(date(2026, 8, 11)) is True
    assert gate.sessions_since(date(2026, 8, 11)) is None


def test_cadence_one_is_always_due(tmp_path) -> None:
    gate = RebalanceGate(tmp_path / "s.json", rebalance_every=1)
    d0 = date(2026, 8, 11)
    gate.record(d0)
    assert gate.is_due(_bd_offset(d0, 1)) is True
