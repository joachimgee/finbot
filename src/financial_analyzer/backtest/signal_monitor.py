"""Moniteur de décroissance des signaux du registre (garde-fou du point unique).

FinBot ne trade **qu'un** signal validé (`momentum_12_1`). Le portail le valide
**une fois** ; rien ne détecte s'il se **dégrade** ensuite (un facteur peut cesser
de marcher — *factor decay*, crowding). C'est le risque le plus grave d'un système
à edge unique. Ce module ré-évalue la **santé récente** d'un signal du registre sur
une fenêtre glissante, avec **exactement le portail existant** (`evaluate_signal`,
coûts Alpaca calibrés), et la compare à la ligne de base enregistrée.

Discipline anti-fausse-alarme : sur une fenêtre **courte** (~252 j), le t-stat de
l'IC est mécaniquement plus faible qu'à la base (mesurée sur ~627 périodes) — t croît
en √n. On **n'alarme donc PAS** sur la magnitude de l'IC t. Les déclencheurs sont
**scale-free** :

* **Sharpe net récent < 0** — l'edge économique a disparu (coûts inclus) ;
* **IC moyen récent < 0** — l'edge cross-section s'est *inversé*.

L'IC t récent reste **informatif** (affiché), pas un gate. Statuts : ``healthy`` /
``degraded`` (une des deux grandeurs négative) / ``dead`` (les deux). Lecture seule :
ce module *observe et alerte*, il ne modifie pas le registre ni ne trade.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["SignalHealth", "evaluate_signal_health"]


@dataclass
class SignalHealth:
    """Santé récente d'un signal vs sa ligne de base au registre."""

    name: str
    status: str  # "healthy" | "degraded" | "dead"
    ic_mean: float
    ic_t_stat: float
    net_sharpe: float
    n_periods: int
    baseline_ic_t: float
    baseline_net_sharpe: float
    reasons: list[str] = field(default_factory=list)

    @property
    def level(self) -> str:
        """Sévérité d'alerte associée (aligne sur AlertManager)."""
        return {"healthy": "info", "degraded": "warning", "dead": "error"}[self.status]

    def summary(self) -> str:
        return (
            f"[{self.status.upper()}] {self.name} (fenêtre récente, {self.n_periods} pér.) : "
            f"IC moyen {self.ic_mean:+.4f} (t={self.ic_t_stat:+.2f}), "
            f"Sharpe net {self.net_sharpe:+.2f} "
            f"| base : IC t={self.baseline_ic_t:+.2f}, Sharpe net={self.baseline_net_sharpe:+.2f}"
            + (f" | {' ; '.join(self.reasons)}" if self.reasons else "")
        )


def evaluate_signal_health(
    name: str,
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    lookback: int = 252,
    rebalance_every: int | None = None,
    cost_model: object | None = None,
    sharpe_floor: float = 0.0,
) -> SignalHealth:
    """Évalue la santé récente d'un signal du registre sur la dernière fenêtre.

    Args:
        name: nom du signal (doit figurer au registre ``VALIDATED_SIGNALS``).
        scores: panel de scores (dates × actifs), score à t prédit le rdt t→t+1.
        returns: panel de rendements simples (dates × actifs).
        lookback: nb de périodes récentes à évaluer (défaut 252 ≈ 1 an).
        rebalance_every: cadence ; défaut = celle du registre pour ce signal.
        cost_model: modèle de coûts ; défaut = ``CostModel.alpaca_equities()``.
        sharpe_floor: seuil de Sharpe net sous lequel l'edge est jugé perdu (0.0).

    Returns:
        ``SignalHealth`` — statut + métriques récentes vs base. Fail-safe : jamais
        d'exception propagée (un moniteur ne doit pas casser le run qui l'appelle).
    """
    from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
    from financial_analyzer.backtest.validation_gate import (
        DECLASSED_SIGNALS,
        VALIDATED_SIGNALS,
    )

    # Un signal **déclassé** garde une base de comparaison : surveiller sa dérive reste
    # utile (c'est même ce qui dirait qu'il mérite d'être re-testé), alors qu'il n'a
    # plus le droit de trader. Le registre validé prime s'il contient le nom.
    baseline = VALIDATED_SIGNALS.get(name) or DECLASSED_SIGNALS.get(name)
    base_ic_t = float(getattr(baseline, "ic_t_stat", 0.0) or 0.0)
    base_sharpe = float(getattr(baseline, "net_sharpe", 0.0) or 0.0)
    if rebalance_every is None:
        rebalance_every = int(getattr(baseline, "rebalance_every", 10) or 10)
    cm = cost_model or CostModel.alpaca_equities()

    try:
        # Fenêtre récente commune scores/rendements.
        idx = scores.index.intersection(returns.index)
        recent = idx[-lookback:] if len(idx) > lookback else idx
        s = scores.reindex(recent)
        r = returns.reindex(recent)
        res = evaluate_signal(s, r, cost_model=cm, rebalance_every=rebalance_every)
        ic_mean, ic_t, sharpe, n = (
            res.ic_mean, res.ic_t_stat, res.net_sharpe, res.n_periods)
    except Exception as e:  # noqa: BLE001 - un moniteur ne doit jamais crasher l'appelant
        logger.warning("Éval de santé de '%s' impossible (%s) — statut inconnu.", name, e)
        return SignalHealth(
            name=name, status="degraded", ic_mean=0.0, ic_t_stat=0.0, net_sharpe=0.0,
            n_periods=0, baseline_ic_t=base_ic_t, baseline_net_sharpe=base_sharpe,
            reasons=[f"évaluation impossible ({e})"])

    # Évaluation dégénérée (données insuffisantes → 0 période ou métriques NaN) :
    # ne PAS conclure « sain » (un Sharpe/IC nul-par-défaut passerait les tests
    # scale-free). Statut dégradé + raison explicite.
    import math

    if n == 0 or not (math.isfinite(ic_mean) and math.isfinite(sharpe)):
        return SignalHealth(
            name=name, status="degraded", ic_mean=0.0, ic_t_stat=0.0, net_sharpe=0.0,
            n_periods=int(n or 0), baseline_ic_t=base_ic_t, baseline_net_sharpe=base_sharpe,
            reasons=["évaluation dégénérée (données récentes insuffisantes)"])

    reasons: list[str] = []
    sharpe_neg = sharpe < sharpe_floor
    ic_neg = ic_mean < 0.0
    if sharpe_neg:
        reasons.append(f"Sharpe net {sharpe:+.2f} < {sharpe_floor:g} (edge économique perdu)")
    if ic_neg:
        reasons.append(f"IC moyen {ic_mean:+.4f} < 0 (edge cross-section inversé)")

    if sharpe_neg and ic_neg:
        status = "dead"
    elif sharpe_neg or ic_neg:
        status = "degraded"
    else:
        status = "healthy"
        # Signal informatif (pas un gate) : IC t récent nettement sous la base.
        if base_ic_t > 0 and ic_t < 0.5 * base_ic_t:
            reasons.append(
                f"IC t récent {ic_t:+.2f} < 50 % de la base {base_ic_t:+.2f} "
                f"(fenêtre courte — informatif, non bloquant)")

    return SignalHealth(
        name=name, status=status, ic_mean=ic_mean, ic_t_stat=ic_t, net_sharpe=sharpe,
        n_periods=n, baseline_ic_t=base_ic_t, baseline_net_sharpe=base_sharpe,
        reasons=reasons)
