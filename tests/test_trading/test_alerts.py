"""Alerting ops (P4) — routage fail-safe des alertes."""
from __future__ import annotations

import json

from financial_analyzer.trading.alerts import AlertLevel, AlertManager


def _read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_alert_written_to_file(tmp_path) -> None:
    mgr = AlertManager(alert_log_path=tmp_path / "alerts.jsonl", mode="paper")
    mgr.critical("Écart de réconciliation", "2 manquants", detail={"missing": 2})
    rows = _read(tmp_path / "alerts.jsonl")
    assert len(rows) == 1
    assert rows[0]["level"] == "critical"
    assert rows[0]["title"] == "Écart de réconciliation"
    assert rows[0]["mode"] == "paper"
    assert rows[0]["detail"] == {"missing": 2}


def test_min_level_filters_lower_severities(tmp_path) -> None:
    mgr = AlertManager(alert_log_path=tmp_path / "a.jsonl", min_level=AlertLevel.ERROR)
    mgr.warning("bruit", "ignoré")   # < ERROR -> non émis
    mgr.error("vrai", "émis")
    rows = _read(tmp_path / "a.jsonl")
    assert [r["level"] for r in rows] == ["error"]


def test_convenience_levels(tmp_path) -> None:
    mgr = AlertManager(alert_log_path=tmp_path / "a.jsonl", min_level=AlertLevel.INFO)
    assert mgr.warning("w")["level"] == "warning"
    assert mgr.error("e")["level"] == "error"
    assert mgr.critical("c")["level"] == "critical"


def test_never_raises_on_bad_file_sink() -> None:
    # Chemin impossible (fichier comme dossier parent) -> l'alerte ne doit pas lever.
    mgr = AlertManager(alert_log_path="/dev/null/nope/alerts.jsonl")
    rec = mgr.critical("toujours", "malgré le sink cassé")
    assert rec["level"] == "critical"  # retourne l'enregistrement sans exception


def test_webhook_called_only_when_configured(tmp_path, monkeypatch) -> None:
    calls = []
    import requests
    monkeypatch.setattr(requests, "post", lambda url, **k: calls.append(url))

    # Sans URL -> pas d'appel webhook.
    AlertManager(alert_log_path=tmp_path / "a.jsonl", webhook_url=None).error("x")
    assert calls == []

    # Avec URL -> appel (et une erreur réseau resterait avalée).
    AlertManager(alert_log_path=tmp_path / "b.jsonl",
                 webhook_url="https://hook.example/x").error("y")
    assert calls == ["https://hook.example/x"]


def test_webhook_failure_is_swallowed(tmp_path, monkeypatch) -> None:
    import requests

    def _boom(*a, **k):
        raise RuntimeError("réseau down")

    monkeypatch.setattr(requests, "post", _boom)
    mgr = AlertManager(alert_log_path=tmp_path / "a.jsonl", webhook_url="https://hook/x")
    # Ne doit pas lever malgré le webhook qui explose.
    assert mgr.critical("resilience")["level"] == "critical"
    assert len(_read(tmp_path / "a.jsonl")) == 1  # le fichier a quand même reçu l'alerte
