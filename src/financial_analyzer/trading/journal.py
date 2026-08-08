"""Journal d'exécution persistant (observabilité P5).

Trace durable, append-only, de tout ce qui touche au chemin argent : chaque
ordre (intention → résultat, y compris rejets et dry-run) et des snapshots de
compte par run. Écrit en JSONL (une ligne JSON horodatée par événement) pour
rester lisible, greppable et facile à agréger pour du suivi P&L / réconciliation.

Responsabilité unique : persister et relire des événements d'exécution. Aucune
décision de trading ici — le journal observe, il ne juge pas.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["TradingJournal"]


class TradingJournal:
    """Journal JSONL append-only des ordres et snapshots de compte."""

    def __init__(self, path: str | Path) -> None:
        """
        Args:
            path: fichier JSONL de destination (créé, avec ses dossiers parents).
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _append(self, record: dict[str, Any]) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
        line = json.dumps(record, default=str, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def record_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        order_type: str,
        mode: str,
        status: str,
        order_id: str | None = None,
        price: float | None = None,
        filled_qty: float | None = None,
        reason: str | None = None,
        dry_run: bool = False,
    ) -> None:
        """Enregistre un événement d'ordre (soumis, dry-run, rejeté, dédupliqué)."""
        self._append(
            {
                "kind": "order",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "order_type": order_type,
                "mode": mode,
                "status": status,
                "order_id": order_id,
                "price": price,
                "filled_qty": filled_qty,
                "reason": reason,
                "dry_run": dry_run,
            }
        )

    def record_snapshot(
        self,
        *,
        equity: float,
        cash: float | None = None,
        n_positions: int | None = None,
        **extra: Any,
    ) -> None:
        """Enregistre un snapshot de compte (pour suivi P&L / réconciliation)."""
        self._append(
            {
                "kind": "snapshot",
                "equity": equity,
                "cash": cash,
                "n_positions": n_positions,
                **extra,
            }
        )

    def record_reconciliation(self, report: dict[str, Any]) -> None:
        """Enregistre un rapport de réconciliation (déjà sérialisé en dict)."""
        self._append(report)

    def record_manifest(self, manifest: dict[str, Any]) -> None:
        """Enregistre un manifeste de run (commit git, versions, config…)."""
        self._append(manifest)

    def read(self) -> list[dict[str, Any]]:
        """Relit tous les événements du journal (ordre chronologique d'écriture)."""
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def orders(self) -> list[dict[str, Any]]:
        """Relit uniquement les événements d'ordre."""
        return [r for r in self.read() if r.get("kind") == "order"]

    def snapshots(self) -> list[dict[str, Any]]:
        """Relit uniquement les snapshots de compte."""
        return [r for r in self.read() if r.get("kind") == "snapshot"]
