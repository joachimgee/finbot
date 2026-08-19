"""Réconciliation ordres journalisés ↔ ordres réels du broker (observabilité P5).

Après un run, on veut savoir si ce qui a été *décidé et journalisé* correspond à
ce qui existe réellement chez le broker. Trois écarts comptent :

- **manquant chez le broker** : un ordre journalisé comme soumis est introuvable
  côté broker → soumission perdue / échouée silencieusement.
- **inattendu chez le broker** : un ordre existe chez le broker sans trace dans
  le journal → il a contourné le chokepoint audité (drapeau rouge de sûreté).
- **non rempli** : un ordre apparié dont le statut broker final n'est pas rempli
  (rejeté / annulé / en attente).

Fonction pure : elle compare deux listes de dicts normalisés, sans I/O — donc
facile à tester et à brancher (le daemon fournit les ordres du broker).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ReconciliationReport", "reconcile_orders"]

# Statuts journalisés qui NE correspondent pas à un ordre réellement envoyé.
_NON_SUBMITTED = {"rejected", "dry_run", "duplicate_skipped"}
# Statuts broker considérés comme "rempli" (au moins partiellement).
_FILLED = {"filled", "partially_filled"}


def _oid(order: dict[str, Any]) -> str | None:
    """Identifiant d'ordre, tolérant aux deux conventions de clé."""
    val = order.get("order_id") or order.get("id")
    return str(val) if val not in (None, "") else None


@dataclass
class ReconciliationReport:
    """Résultat d'une réconciliation ordres journalisés ↔ broker."""

    matched: list[dict[str, Any]] = field(default_factory=list)
    missing_at_broker: list[dict[str, Any]] = field(default_factory=list)
    unexpected_at_broker: list[dict[str, Any]] = field(default_factory=list)
    not_filled: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Vrai si aucun écart critique (ni perdu, ni inattendu)."""
        return not self.missing_at_broker and not self.unexpected_at_broker

    def summary(self) -> str:
        return (
            f"réconciliation: {len(self.matched)} appariés, "
            f"{len(self.missing_at_broker)} manquants broker, "
            f"{len(self.unexpected_at_broker)} inattendus broker, "
            f"{len(self.not_filled)} non remplis "
            f"→ {'OK' if self.ok else 'ÉCART'}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "reconciliation",
            "ok": self.ok,
            "n_matched": len(self.matched),
            "missing_at_broker": self.missing_at_broker,
            "unexpected_at_broker": self.unexpected_at_broker,
            "not_filled": self.not_filled,
        }


def _submitted_at(order: dict[str, Any]) -> str | None:
    """Horodatage de soumission côté broker, en texte ISO (comparable lexicalement)."""
    val = order.get("submitted_at") or order.get("created_at") or order.get("filled_at")
    return str(val) if val not in (None, "") else None


def reconcile_orders(
    journal_orders: list[dict[str, Any]],
    broker_orders: list[dict[str, Any]],
    since: str | None = None,
) -> ReconciliationReport:
    """Compare les ordres journalisés (réellement soumis) aux ordres du broker.

    Args:
        journal_orders: événements d'ordre du journal (:class:`TradingJournal`).
            Seuls ceux réellement soumis (statut hors rejeté/dry_run/dédup et
            portant un ``order_id``) sont réconciliés.
        broker_orders: ordres tels que rapportés par le broker (``get_orders``),
            avec un identifiant (``order_id`` ou ``id``) et un ``status``.
        since: horodatage ISO du **début du run**. Les ordres du broker soumis
            AVANT ce moment sont ignorés du test « inattendu chez le broker ».

            Sans ce bornage, le test est structurellement voué à l'échec sur tout
            compte ayant un historique : ``get_orders`` renvoie les N derniers
            ordres du compte — y compris ceux des stratégies précédentes — et
            chacun est compté comme un ordre ayant contourné le chokepoint. C'est
            exactement ce qui s'est produit ici : le seul rapport écrit sortait
            ``ok=false`` à cause d'ordres ORCL/ABT d'une session antérieure, ce qui
            rendait le critère #1 du runbook (20 runs propres) **inatteignable**.
            Une alarme qui ne peut jamais s'éteindre n'est plus une alarme.

            Le bornage ne relâche rien du côté qui compte : un ordre journalisé
            introuvable chez le broker (``missing_at_broker``) reste détecté quel
            que soit ``since``, et tout ordre postérieur au début du run qui n'est
            pas au journal reste un drapeau rouge.

    Returns:
        :class:`ReconciliationReport`.
    """
    submitted = [
        o
        for o in journal_orders
        if o.get("status") not in _NON_SUBMITTED and _oid(o) is not None
    ]
    journal_id_set = {_oid(o) for o in submitted}
    if since:
        broker_orders = [
            o for o in broker_orders
            # On garde un ordre antérieur au run s'il est au journal (il doit
            # rester apparié), et tout ordre postérieur au début du run.
            if _oid(o) in journal_id_set
            or (_submitted_at(o) or "") >= since
        ]
    broker_by_id = {_oid(o): o for o in broker_orders if _oid(o) is not None}
    journal_ids = journal_id_set

    report = ReconciliationReport()

    for o in submitted:
        oid = _oid(o)
        broker = broker_by_id.get(oid)
        if broker is None:
            report.missing_at_broker.append(o)
            continue
        broker_status = str(broker.get("status", "")).lower()
        entry = {
            "order_id": oid,
            "symbol": o.get("symbol"),
            "journal_status": o.get("status"),
            "broker_status": broker_status,
        }
        report.matched.append(entry)
        if broker_status not in _FILLED:
            report.not_filled.append(entry)

    for oid, broker in broker_by_id.items():
        if oid not in journal_ids:
            report.unexpected_at_broker.append(broker)

    return report
