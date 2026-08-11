"""P0 — invariants de sûreté du chemin réellement exécuté (le daemon canonique).

Le daemon ``professional_analysis_daemon.py`` est le SEUL chemin qui place des
ordres en production. Deux invariants non négociables doivent tenir en CI :

1. **Aucun ordre ne contourne l'``OrderGateway``.** Le daemon ne doit jamais
   appeler ``broker.submit_order`` en direct : toute soumission passe par le
   chokepoint audité (garde de mode + RiskGuard + idempotence + journal). On le
   vérifie statiquement (AST) pour attraper toute régression future — un appel
   direct réintroduirait un ordre non validé.

2. **Le signal qui décide n'est jamais une constante.** Le score composite du
   ``SignalFusionEngine`` (chemin de décision réel) doit être une vraie fonction
   de ses entrées : deux jeux de signaux différents → deux scores différents,
   entrées identiques → score identique (déterministe). C'était précisément le
   bug P0 (sources stub injectant 0.5) : ce test empêche sa réapparition.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from financial_analyzer.integration.signal_fusion_engine import (
    SignalComponent,
    SignalFusionEngine,
)

_DAEMON_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "professional_analysis_daemon.py"
)


def _daemon_source() -> str:
    return _DAEMON_PATH.read_text(encoding="utf-8")


# --- Invariant 1 : aucun contournement du gateway ---------------------------

def test_daemon_never_calls_submit_order_directly() -> None:
    """Aucun appel ``*.submit_order(...)`` dans le daemon (AST, pas texte).

    L'unique endroit autorisé à appeler ``broker.submit_order`` est
    ``OrderGateway.submit`` — jamais le daemon lui-même.
    """
    tree = ast.parse(_daemon_source(), filename=str(_DAEMON_PATH))
    direct_calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "submit_order"
    ]
    assert direct_calls == [], (
        f"Appel direct à submit_order (contourne le gateway) aux lignes {direct_calls}"
    )


def test_daemon_routes_orders_through_gateway() -> None:
    """Câblage positif : le daemon construit un OrderGateway et soumet via lui."""
    tree = ast.parse(_daemon_source(), filename=str(_DAEMON_PATH))

    constructs_gateway = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "OrderGateway"
        for node in ast.walk(tree)
    )
    submits_via_gateway = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "submit"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "gateway"
        for node in ast.walk(tree)
    )
    assert constructs_gateway, "le daemon doit instancier OrderGateway"
    assert submits_via_gateway, "le daemon doit soumettre via gateway.submit(...)"


# --- Invariant 1bis : cadence de rééquilibrage câblée -----------------------

def test_daemon_wires_rebalance_cadence_gate() -> None:
    """Le déploiement de nouvelles positions est gaté par la cadence validée.

    Vérifie statiquement que le daemon (a) construit une RebalanceGate, (b) calcule
    un `rebalance_due`, et (c) ré-arme la cadence via `.record(...)`. Sans ce
    câblage, le book momentum serait rééquilibré chaque jour et paierait un
    turnover que l'edge validé ne rembourse pas (reb=10 bat le quotidien).
    """
    src = _daemon_source()
    tree = ast.parse(src, filename=str(_DAEMON_PATH))

    builds_gate = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "from_validated_signal"
        for node in ast.walk(tree)
    ) or "RebalanceGate(" in src
    assigns_due = any(
        isinstance(node, ast.Name) and node.id == "rebalance_due"
        for node in ast.walk(tree)
    )
    records = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "record"
        for node in ast.walk(tree)
    )
    assert builds_gate, "le daemon doit construire une RebalanceGate"
    assert assigns_due, "le daemon doit calculer rebalance_due"
    assert records, "le daemon doit ré-armer la cadence via gate.record(...)"


# --- Invariant 2 : le score de décision n'est pas une constante -------------

def _force_two_real_sources(engine: SignalFusionEngine, tech: float, sent: float) -> None:
    engine._get_technical_signal = lambda symbol, pdata: SignalComponent(  # type: ignore[assignment]
        source="technical", score=tech, confidence=0.75,
        weight=engine.source_weights.get("technical", 1.0),
    )
    engine._get_sentiment_signal = lambda symbol, **kw: SignalComponent(  # type: ignore[assignment]
        source="sentiment", score=sent, confidence=0.60,
        weight=engine.source_weights.get("sentiment", 1.0),
    )


def test_composite_varies_with_input() -> None:
    """Deux jeux de signaux distincts produisent deux scores composites distincts."""
    import pandas as pd

    price = pd.DataFrame({"close": [100.0, 101.0, 102.0]})

    e1 = SignalFusionEngine(min_sources=2)
    _force_two_real_sources(e1, tech=0.9, sent=0.8)
    high = e1.generate_signal("AAA", price, use_cache=False)

    e2 = SignalFusionEngine(min_sources=2)
    _force_two_real_sources(e2, tech=0.2, sent=0.1)
    low = e2.generate_signal("AAA", price, use_cache=False)

    assert high is not None and low is not None
    assert high.composite_score != low.composite_score
    assert high.composite_score > low.composite_score  # signal plus fort -> score plus haut


def test_composite_is_deterministic_for_same_input() -> None:
    """Entrées identiques -> score identique (fonction, pas de bruit caché)."""
    import pandas as pd

    price = pd.DataFrame({"close": [100.0, 101.0, 102.0]})
    scores = []
    for _ in range(2):
        e = SignalFusionEngine(min_sources=2)
        _force_two_real_sources(e, tech=0.7, sent=0.55)
        fused = e.generate_signal("AAA", price, use_cache=False)
        assert fused is not None
        scores.append(fused.composite_score)
    assert scores[0] == pytest.approx(scores[1], rel=1e-12)
