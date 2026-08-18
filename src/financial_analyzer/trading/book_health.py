"""Contrôle de santé quotidien d'un book en forward-test.

Un book rééquilibré mensuellement n'est **pas** un book qu'on ignore 20 jours sur 21 :
entre deux rééquilibrages, il dérive (les prix bougent → les poids changent), des
positions peuvent manquer ou traîner, la neutralité de marché peut se perdre, et un
drawdown peut s'installer. Ce module fournit la **surveillance quotidienne** que la
garde de cadence, seule, ne fait pas.

Contrôles (chacun produit une alerte typée) :

* **dérive de neutralité** — |exposition nette| / equity au-delà d'un seuil ;
* **dérive de levier** — exposition brute hors de la plage attendue ;
* **positions inattendues** (détenues hors book) et **manquantes** (book non détenu) ;
* **concentration** — une ligne dépasse un poids maximal ;
* **drawdown** — repli depuis le pic d'equity observé (journaux) au-delà d'un seuil.

Lecture seule : ce module **observe et alerte**, il ne trade pas et ne corrige rien.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["BookHealth", "HealthThresholds", "check_book_health",
           "HaltState", "read_halt", "raise_halt", "clear_halt"]


@dataclass
class HealthThresholds:
    """Seuils d'alerte du contrôle quotidien."""

    max_net_exposure: float = 0.15      # |net| / equity (book market-neutral)
    min_gross_exposure: float = 0.50    # brut / equity attendu ≈ 1.0
    max_gross_exposure: float = 1.60
    max_position_pct: float = 0.08      # poids max d'une ligne
    max_drawdown_pct: float = -15.0     # depuis le pic d'equity (%)


@dataclass
class BookHealth:
    """Photographie de santé du book, avec alertes."""

    n_positions: int
    n_longs: int
    n_shorts: int
    equity: float
    gross_exposure: float
    net_exposure: float
    drawdown_pct: float
    peak_equity: float
    unexpected: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    concentrated: list[tuple[str, float]] = field(default_factory=list)
    worst: list[tuple[str, float]] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """``ok`` / ``warning`` / ``critical``."""
        if any(a.startswith("CRITIQUE") for a in self.alerts):
            return "critical"
        return "warning" if self.alerts else "ok"

    def summary(self) -> str:
        return (
            f"[{self.status.upper()}] {self.n_positions} positions "
            f"({self.n_longs}L/{self.n_shorts}S) | brut {self.gross_exposure:.2f}× "
            f"net {self.net_exposure:+.2f}× | drawdown {self.drawdown_pct:+.1f}% "
            f"| {len(self.alerts)} alerte(s)"
        )


def check_book_health(
    positions: list[dict],
    equity: float,
    *,
    target: dict[str, float] | None = None,
    peak_equity: float | None = None,
    thresholds: HealthThresholds | None = None,
) -> BookHealth:
    """Évalue la santé du book détenu.

    Args:
        positions: positions du broker (``symbol``, ``qty``, ``market_value``,
            ``unrealized_pl`` optionnel).
        equity: equity courante du compte.
        target: book cible ``{symbole: poids}`` s'il est connu (permet de détecter
            les positions inattendues/manquantes). ``None`` → ces contrôles sont sautés.
        peak_equity: pic d'equity observé (des journaux) pour le drawdown. ``None`` →
            on prend l'equity courante (drawdown 0).
        thresholds: seuils d'alerte.

    Returns:
        ``BookHealth`` — jamais d'exception ; un book vide renvoie un état cohérent.
    """
    th = thresholds or HealthThresholds()
    eq = float(equity) if equity else 0.0
    longs = [p for p in positions if float(p.get("qty", 0) or 0) > 0]
    shorts = [p for p in positions if float(p.get("qty", 0) or 0) < 0]
    mv = {str(p.get("symbol")): float(p.get("market_value", 0) or 0) for p in positions}
    gross = sum(abs(v) for v in mv.values()) / eq if eq > 0 else 0.0
    net = sum(mv.values()) / eq if eq > 0 else 0.0
    peak = float(peak_equity) if peak_equity else eq
    dd = ((eq - peak) / peak * 100.0) if peak > 0 else 0.0

    alerts: list[str] = []
    if eq > 0 and abs(net) > th.max_net_exposure:
        alerts.append(f"Dérive de neutralité : exposition nette {net:+.1%} "
                      f"(seuil ±{th.max_net_exposure:.0%})")
    if eq > 0 and positions and not (th.min_gross_exposure <= gross <= th.max_gross_exposure):
        alerts.append(f"Dérive de levier : exposition brute {gross:.2f}× "
                      f"(plage {th.min_gross_exposure:.2f}-{th.max_gross_exposure:.2f})")
    if dd <= th.max_drawdown_pct:
        alerts.append(f"CRITIQUE — drawdown {dd:+.1f}% ≤ seuil {th.max_drawdown_pct:+.1f}% "
                      f"(pic {peak:,.0f})")

    concentrated = []
    if eq > 0:
        for sym, v in mv.items():
            w = abs(v) / eq
            if w > th.max_position_pct:
                concentrated.append((sym, w))
    if concentrated:
        worst_c = max(concentrated, key=lambda kv: kv[1])
        alerts.append(f"Concentration : {len(concentrated)} ligne(s) > "
                      f"{th.max_position_pct:.0%} (max {worst_c[0]} {worst_c[1]:.1%})")

    unexpected: list[str] = []
    missing: list[str] = []
    if target is not None:
        tgt = {s for s, w in target.items() if abs(w) > 1e-9}
        held = {s for s, v in mv.items() if abs(v) > 1e-9}
        unexpected = sorted(held - tgt)
        missing = sorted(tgt - held)
        if unexpected:
            alerts.append(f"{len(unexpected)} position(s) hors book : "
                          f"{', '.join(unexpected[:5])}{'…' if len(unexpected) > 5 else ''}")
        if missing:
            alerts.append(f"{len(missing)} ligne(s) du book non détenue(s) : "
                          f"{', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}")

    worst = sorted(
        ((str(p.get("symbol")), float(p.get("unrealized_pl", 0) or 0)) for p in positions),
        key=lambda kv: kv[1],
    )[:5]

    return BookHealth(
        n_positions=len(positions), n_longs=len(longs), n_shorts=len(shorts),
        equity=eq, gross_exposure=gross, net_exposure=net,
        drawdown_pct=dd, peak_equity=peak,
        unexpected=unexpected, missing=missing, concentrated=concentrated,
        worst=worst, alerts=alerts,
    )


# ---------------------------------------------------------------------------
# Politique de réponse aux anomalies : HALTE (pas de liquidation automatique)
# ---------------------------------------------------------------------------
#
# Que faire quand l'audit détecte une anomalie ? La littérature et la pratique
# convergent sur une réponse **graduée**, et surtout sur ce qu'il ne faut PAS faire :
#
# * **Alerter seul** sur une anomalie mineure (dérive de neutralité, concentration) :
#   un book market-neutral dérive naturellement entre deux rééquilibrages ; réagir à
#   chaque bruit détruit de la valeur en coûts de transaction.
# * **Halte des nouvelles prises de risque** sur une anomalie grave (drawdown au-delà
#   du seuil) : on cesse de rééquilibrer et on exige une revue humaine.
# * **NE PAS liquider automatiquement.** C'est le point le plus important et le plus
#   contre-intuitif. Pour une stratégie de retour à la moyenne / market-neutral, un
#   stop-loss sur drawdown vend structurellement au pire moment et transforme une perte
#   latente en perte réalisée, sans améliorer l'espérance (cf. la littérature sur les
#   règles de stop : Kaminski & Lo, *When Do Stop-Loss Rules Stop Losses?* (2014) —
#   les stops n'ajoutent de la valeur que pour des rendements à **momentum**, et en
#   détruisent pour des rendements à **retour à la moyenne**). Le runbook du projet suit
#   déjà cette logique : le kill-switch **bloque les nouveaux ordres** et ne liquide pas.
#
# La halte est donc un **fichier d'état** : présent → le prochain rééquilibrage est
# refusé jusqu'à levée **manuelle** (revue humaine). Les positions existantes restent
# en place ; l'opérateur décide en connaissance de cause.

DEFAULT_HALT_PATH = "logs/book_halt.json"


@dataclass
class HaltState:
    """État de halte d'un book (présent = rééquilibrages bloqués)."""

    active: bool
    reason: str = ""
    raised_at: str = ""
    metrics: dict = field(default_factory=dict)


def read_halt(path: str | Path = DEFAULT_HALT_PATH) -> HaltState:
    """Lit l'état de halte. Fichier absent/illisible → pas de halte (fail-open).

    *Fail-open assumé* : une halte est une décision de risque explicite ; un fichier
    corrompu ne doit pas geler le book silencieusement (l'audit ré-alertera de toute
    façon au prochain cycle si l'anomalie persiste).
    """
    import json

    p = Path(path)
    if not p.exists():
        return HaltState(active=False)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return HaltState(active=bool(d.get("active", True)), reason=str(d.get("reason", "")),
                         raised_at=str(d.get("raised_at", "")), metrics=d.get("metrics", {}))
    except Exception as e:  # noqa: BLE001
        logger.warning("État de halte illisible (%s) — pas de halte appliquée.", e)
        return HaltState(active=False)


def raise_halt(reason: str, metrics: dict | None = None,
               path: str | Path = DEFAULT_HALT_PATH) -> HaltState:
    """Lève une halte : les prochains rééquilibrages seront refusés (levée manuelle)."""
    import json
    from datetime import datetime, timezone

    p = Path(path)
    state = {"active": True, "reason": reason,
             "raised_at": datetime.now(timezone.utc).isoformat(),
             "metrics": metrics or {}}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.critical("HALTE levée sur le book : %s", reason)
    except Exception as e:  # noqa: BLE001
        logger.error("Impossible d'écrire l'état de halte (%s)", e)
    return HaltState(active=True, reason=reason, raised_at=state["raised_at"],
                     metrics=state["metrics"])


def clear_halt(path: str | Path = DEFAULT_HALT_PATH) -> bool:
    """Lève la halte (action **manuelle** après revue). True si un état existait."""
    p = Path(path)
    if p.exists():
        p.unlink()
        logger.info("Halte levée manuellement (%s supprimé).", p)
        return True
    return False
