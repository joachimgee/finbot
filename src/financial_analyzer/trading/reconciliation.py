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

__all__ = [
    "PositionReconciliationReport",
    "ReconciliationReport",
    "positions_from_orders",
    "reconcile_orders",
    "reconcile_positions",
]

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


# ---------------------------------------------------------------------------
# Réconciliation de POSITIONS — les jours où le book est tenu
# ---------------------------------------------------------------------------
#
# La réconciliation d'ordres ci-dessus ne peut s'exécuter que les jours de
# rééquilibrage : les autres jours, aucun ordre n'est émis. Or le book est tenu 20 jours
# sur 21. Sans contrôle ces jours-là, le critère « 20 runs consécutifs sans écart » du
# runbook n'avance que d'un cran toutes les 21 séances — soit ~1,7 an pour être
# satisfait, ce qui n'est pas une porte d'accès, c'est un mur.
#
# Le contrôle des jours tenus porte donc sur l'**état** plutôt que sur les événements :
# *chaque position détenue est-elle expliquée par l'historique d'ordres du broker ?*
# C'est la réconciliation de position au sens des moteurs d'exécution (reconstruire
# depuis les fills, comparer aux positions du venue).
#
# **Contrainte durable** : les journaux locaux ne survivent pas aux sessions éphémères
# (``logs/`` n'est pas versionné). La seule source de vérité qui persiste est le broker
# lui-même — même raison qui avait fait passer la garde de cadence sur l'historique
# d'ordres. La reconstruction part donc de ``get_orders``.
#
# **Asymétrie assumée, et c'est le cœur de la conception.** Les deux directions d'écart
# n'ont pas la même valeur de preuve :
#
# * **détenu sans explication** → écart RÉEL. Une position que l'historique d'ordres ne
#   justifie pas signifie qu'un ordre a contourné le chokepoint audité, ou qu'une
#   opération sur titre a créé une ligne. C'est exactement ce qu'on veut détecter, et
#   c'est robuste : mesuré 0/56 sur le compte réel.
# * **attendu sans être détenu** → INFORMATIF seulement. ``get_orders`` ne renvoie qu'une
#   fenêtre récente : un titre dont les achats sont hors fenêtre mais les ventes dedans
#   apparaît comme « attendu short, non détenu » alors que rien d'anormal ne s'est
#   produit. Mesuré sur le compte réel : 22 faux écarts de ce type, tous des large-caps
#   de l'ancien book momentum liquidé. En faire un échec reproduirait exactement le
#   défaut qu'on vient de corriger sur la réconciliation d'ordres — une alarme
#   perpétuellement rouge, donc ignorée.
#
# Une clôture normale ne crée aucun bruit : le net des ordres tombe à zéro et le symbole
# disparaît de l'attendu.


@dataclass
class PositionReconciliationReport:
    """Résultat d'une réconciliation positions détenues ↔ historique d'ordres."""

    matched: list[dict[str, Any]] = field(default_factory=list)
    unexpected: list[dict[str, Any]] = field(default_factory=list)
    qty_mismatch: list[dict[str, Any]] = field(default_factory=list)
    unexplained_expected: list[dict[str, Any]] = field(default_factory=list)
    history_truncated: bool = False

    @property
    def ok(self) -> bool:
        """Vrai si aucune position inexpliquée ni aucun écart de quantité/sens.

        ``unexplained_expected`` n'entre PAS dans le verdict (cf. l'asymétrie
        documentée ci-dessus : cette direction est contaminée par la troncature de
        l'historique du broker).
        """
        return not self.unexpected and not self.qty_mismatch

    def summary(self) -> str:
        trunc = " (historique tronqué)" if self.history_truncated else ""
        return (
            f"positions: {len(self.matched)} appariées, "
            f"{len(self.unexpected)} inexpliquées, "
            f"{len(self.qty_mismatch)} écarts de quantité, "
            f"{len(self.unexplained_expected)} attendues non détenues (informatif)"
            f"{trunc} → {'OK' if self.ok else 'ÉCART'}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "reconciliation",
            "scope": "positions",
            "ok": self.ok,
            "n_matched": len(self.matched),
            "unexpected": self.unexpected,
            "qty_mismatch": self.qty_mismatch,
            "unexplained_expected": self.unexplained_expected,
            "history_truncated": self.history_truncated,
        }


def positions_from_orders(broker_orders: list[dict[str, Any]]) -> dict[str, float]:
    """Reconstruit les positions attendues en sommant les ordres **remplis**.

    Achat = quantité positive, vente = négative. Les symboles au net nul (position
    ouverte puis refermée) sont écartés : ils ne sont pas « attendus ».

    Args:
        broker_orders: ordres du broker (``get_orders``), avec ``symbol``, ``side``,
            ``status`` et ``filled_qty`` (à défaut ``qty``).

    Returns:
        ``{symbole: quantité nette}``, symboles au net nul exclus.
    """
    from collections import defaultdict

    net: dict[str, float] = defaultdict(float)
    for o in broker_orders:
        if str(o.get("status", "")).lower() not in _FILLED:
            continue
        symbol = str(o.get("symbol") or "")
        if not symbol:
            continue
        raw = o.get("filled_qty")
        qty = float(raw if raw not in (None, "") else (o.get("qty") or 0) or 0)
        if str(o.get("side", "")).lower() == "sell":
            qty = -qty
        net[symbol] += qty
    return {s: q for s, q in net.items() if abs(q) > 1e-9}


def reconcile_positions(
    broker_orders: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    *,
    qty_tolerance: float = 1e-6,
    order_limit: int | None = None,
) -> PositionReconciliationReport:
    """Réconcilie les positions détenues avec l'historique d'ordres du broker.

    À utiliser les jours **sans rééquilibrage** : c'est le contrôle qui prouve que
    l'état du compte reste celui que le chemin audité a produit.

    Args:
        broker_orders: historique d'ordres du broker.
        positions: positions détenues (``get_positions``), avec ``symbol`` et ``qty``.
        qty_tolerance: écart de quantité toléré avant de déclarer un désaccord.
        order_limit: limite demandée à ``get_orders``. Si l'historique renvoyé atteint
            cette limite, il est probablement **tronqué** : on le signale (les positions
            anciennes peuvent alors paraître inexpliquées à tort).

    Returns:
        :class:`PositionReconciliationReport`.
    """
    expected = positions_from_orders(broker_orders)
    actual = {
        str(p.get("symbol")): float(p.get("qty", 0) or 0)
        for p in positions
        if p.get("symbol")
    }
    truncated = bool(order_limit) and len(broker_orders) >= int(order_limit)
    report = PositionReconciliationReport(history_truncated=truncated)

    for symbol, qty in sorted(actual.items()):
        if symbol not in expected:
            # Détenu sans qu'aucun ordre ne l'explique : drapeau rouge.
            report.unexpected.append({"symbol": symbol, "qty": qty})
            continue
        exp = expected[symbol]
        entry = {"symbol": symbol, "expected_qty": exp, "actual_qty": qty}
        if abs(exp - qty) > qty_tolerance:
            report.qty_mismatch.append(entry)
        else:
            report.matched.append(entry)

    for symbol, qty in sorted(expected.items()):
        if symbol not in actual:
            report.unexplained_expected.append({"symbol": symbol, "expected_qty": qty})

    return report
