"""Alerting ops (P4) — notifier les événements critiques du chemin argent.

Au-delà du simple log ERROR, ce module route les alertes (échec de run, circuit
breaker, écart de réconciliation) vers des **puits** configurables :

- **log** (toujours) — via le logger du projet, au niveau adéquat.
- **fichier JSONL** (toujours si un chemin est fourni) — piste d'audit durable
  des alertes, greppable comme le journal d'exécution.
- **webhook** (optionnel) — POST JSON vers ``FINBOT_ALERT_WEBHOOK`` (Slack,
  Discord, PagerDuty…), si la variable est définie.

Principe **fail-safe absolu** : l'alerting ne doit JAMAIS interrompre le trading.
Toute défaillance d'un puits (réseau, disque) est avalée et journalisée — une
alerte perdue est préférable à un run qui plante en tentant d'alerter.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["AlertLevel", "AlertManager"]

_WEBHOOK_ENV = "FINBOT_ALERT_WEBHOOK"


class AlertLevel(str, Enum):
    """Sévérité d'une alerte (ordonnée)."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertManager:
    """Route les alertes vers log + fichier + webhook, sans jamais lever.

    Args:
        alert_log_path: fichier JSONL des alertes (créé si fourni). None = pas de
            persistance fichier (log/webhook seulement).
        webhook_url: URL de webhook ; défaut = variable ``FINBOT_ALERT_WEBHOOK``.
        mode: étiquette de contexte (``"paper"``/``"live"``) ajoutée aux alertes.
        min_level: sévérité minimale émise (les niveaux inférieurs sont ignorés).
    """

    alert_log_path: str | Path | None = None
    webhook_url: str | None = None
    mode: str = "paper"
    min_level: AlertLevel = AlertLevel.WARNING

    _ORDER = (AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL)

    def __post_init__(self) -> None:
        if self.webhook_url is None:
            self.webhook_url = os.environ.get(_WEBHOOK_ENV) or None
        if self.alert_log_path is not None:
            self.alert_log_path = Path(self.alert_log_path)
            try:
                self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:  # noqa: BLE001 - ne jamais casser à l'init
                logger.warning("Alertes: dossier non créable (%s): %s", self.alert_log_path, e)

    def _enabled(self, level: AlertLevel) -> bool:
        return self._ORDER.index(level) >= self._ORDER.index(self.min_level)

    def alert(self, level: AlertLevel, title: str, message: str = "", **context: Any) -> dict[str, Any]:
        """Émet une alerte vers tous les puits. Retourne l'enregistrement (pour test).

        Ne lève jamais : chaque puits est protégé indépendamment.
        """
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "alert",
            "level": level.value,
            "mode": self.mode,
            "title": title,
            "message": message,
            **context,
        }
        if not self._enabled(level):
            return record

        self._to_log(level, record)
        if self.alert_log_path is not None:
            self._to_file(record)
        if self.webhook_url:
            self._to_webhook(record)
        return record

    # Convenance -------------------------------------------------------------
    def warning(self, title: str, message: str = "", **ctx: Any) -> dict[str, Any]:
        return self.alert(AlertLevel.WARNING, title, message, **ctx)

    def error(self, title: str, message: str = "", **ctx: Any) -> dict[str, Any]:
        return self.alert(AlertLevel.ERROR, title, message, **ctx)

    def critical(self, title: str, message: str = "", **ctx: Any) -> dict[str, Any]:
        return self.alert(AlertLevel.CRITICAL, title, message, **ctx)

    # Puits (chacun fail-safe) ----------------------------------------------
    def _to_log(self, level: AlertLevel, record: dict[str, Any]) -> None:
        try:
            line = f"ALERT[{level.value}] {record['title']} — {record['message']}"
            if level in (AlertLevel.CRITICAL, AlertLevel.ERROR):
                logger.error(line)
            else:
                logger.warning(line)
        except Exception:  # noqa: BLE001, S110 - si le log lui-même échoue, rien à faire
            pass

    def _to_file(self, record: dict[str, Any]) -> None:
        try:
            with Path(self.alert_log_path).open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            logger.warning("Alertes: écriture fichier échouée: %s", e)

    def _to_webhook(self, record: dict[str, Any]) -> None:
        try:
            import requests

            requests.post(self.webhook_url, json=record, timeout=5)
        except Exception as e:  # noqa: BLE001 - réseau best-effort, jamais bloquant
            logger.warning("Alertes: webhook échoué: %s", e)
