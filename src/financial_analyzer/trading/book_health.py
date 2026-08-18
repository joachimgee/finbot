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

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["BookHealth", "HealthThresholds", "check_book_health"]


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
