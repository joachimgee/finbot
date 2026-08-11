"""Portail de validation à double critère (P1) — la règle qui décide ce qui trade.

Rien n'entre dans la décision réelle sans une preuve out-of-sample *chiffrée* :

    IC t-stat > 2   ET   Sharpe net de coûts > 0

Les deux critères sont nécessaires, et l'expérience du projet le prouve :

* Le **critère IC seul** laisse passer des signaux à IC significatif mais non
  rentables après coûts (fort turnover) — cf. sweep de rééquilibrage.
* Le **critère Sharpe seul** laisse passer un Sharpe *fabriqué* par une queue
  épaisse : le combinateur ridge sort IC t = −3.07 (négatif) et Sharpe net +0.50,
  ce dernier porté par un unique décile aberrant (cf.
  ``scripts/diagnose_combiner_anomaly.py``). Le double critère l'écarte.

Le seuil IC est **directionnel** (``t > +2``, pas ``|t| > 2``) : un signal doit
être *positivement* prédictif pour la convention long-haut / short-bas du chemin
canonique. Un signal à IC fortement négatif est rejeté (il faudrait l'inverser
avant de l'utiliser — ce qui est alors un *autre* signal à valider).

Ce module fournit :

* :func:`evaluate_signal_gate` — évalue un panel de scores OOS et rend un verdict.
* :data:`VALIDATED_SIGNALS` — le registre des signaux ayant passé le portail, avec
  leur preuve et leur configuration (source unique de vérité de « ce qui a le
  droit de trader »).
* :func:`is_validated` / :func:`require_validated` — garde d'exécution.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    SignalEvalResult,
    walk_forward_evaluate,
)

__all__ = [
    "VALIDATED_SIGNALS",
    "GateThresholds",
    "ValidatedSignal",
    "ValidationVerdict",
    "decide",
    "evaluate_signal_gate",
    "is_validated",
    "require_validated",
]


@dataclass(frozen=True)
class GateThresholds:
    """Seuils du portail. Directionnels : l'IC doit être *positif* et significatif."""

    ic_t_stat_min: float = 2.0
    net_sharpe_min: float = 0.0


DEFAULT_THRESHOLDS = GateThresholds()


def decide(
    ic_t_stat: float,
    net_sharpe: float,
    thresholds: GateThresholds = DEFAULT_THRESHOLDS,
) -> tuple[bool, tuple[str, ...]]:
    """Décision pure du portail à partir des deux métriques.

    Retourne ``(passed, reasons)`` — ``reasons`` liste les critères échoués
    (vide si tout passe). ``NaN`` est traité comme un échec (preuve insuffisante).
    """
    reasons: list[str] = []
    if math.isnan(ic_t_stat) or ic_t_stat <= thresholds.ic_t_stat_min:
        reasons.append(
            f"IC t={ic_t_stat:+.2f} ≤ {thresholds.ic_t_stat_min:+.2f} "
            "(pas positivement prédictif de façon significative)"
        )
    if math.isnan(net_sharpe) or net_sharpe <= thresholds.net_sharpe_min:
        reasons.append(
            f"Sharpe net={net_sharpe:+.2f} ≤ {thresholds.net_sharpe_min:+.2f} "
            "(non rentable après coûts)"
        )
    return (not reasons), tuple(reasons)


@dataclass(frozen=True)
class ValidationVerdict:
    """Verdict du portail pour un signal donné, avec la preuve chiffrée."""

    name: str
    ic_mean: float
    ic_t_stat: float
    net_sharpe: float
    avg_turnover: float
    n_periods: int
    passed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> str:
        verdict = "✅ VALIDÉ" if self.passed else "❌ REJETÉ"
        base = (
            f"{verdict} {self.name}: IC t={self.ic_t_stat:+.2f} "
            f"(IC={self.ic_mean:+.4f}), Sharpe net={self.net_sharpe:+.2f}, "
            f"turnover={self.avg_turnover:.2f}, {self.n_periods} pér."
        )
        if self.reasons:
            base += " | échec: " + " ; ".join(self.reasons)
        return base


def evaluate_signal_gate(
    name: str,
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    cost_model: CostModel | None = None,
    rebalance_every: int = 1,
    n_splits: int = 5,
    quantile: float = 0.2,
    long_short: bool = True,
    periods_per_year: int = 252,
    thresholds: GateThresholds = DEFAULT_THRESHOLDS,
) -> ValidationVerdict:
    """Passe un signal au portail : validation walk-forward OOS + double critère.

    Args:
        name: nom du signal (pour le verdict/log).
        scores: panel (dates × actifs) — le score en t prédit le rendement t→t+1.
        returns: panel de rendements simples par période.
        cost_model: modèle de coûts (défaut ``CostModel()``).
        rebalance_every: cadence de rééquilibrage retenue pour ce signal.
        n_splits: nombre de fenêtres walk-forward.

    Returns:
        ValidationVerdict — ``passed`` vrai seulement si IC t > seuil ET Sharpe
        net > seuil sur l'agrégat OOS.
    """
    out = walk_forward_evaluate(
        scores, returns, n_splits=n_splits, cost_model=cost_model,
        quantile=quantile, long_short=long_short, periods_per_year=periods_per_year,
        rebalance_every=rebalance_every,
    )
    oos: SignalEvalResult | None = out["oos"]
    if oos is None:
        return ValidationVerdict(
            name=name, ic_mean=float("nan"), ic_t_stat=float("nan"),
            net_sharpe=float("nan"), avg_turnover=float("nan"), n_periods=0,
            passed=False, reasons=("aucune fenêtre OOS exploitable",),
        )
    passed, reasons = decide(oos.ic_t_stat, oos.net_sharpe, thresholds)
    return ValidationVerdict(
        name=name,
        ic_mean=oos.ic_mean,
        ic_t_stat=oos.ic_t_stat,
        net_sharpe=oos.net_sharpe,
        avg_turnover=oos.avg_turnover,
        n_periods=oos.n_periods,
        passed=passed,
        reasons=reasons,
    )


@dataclass(frozen=True)
class ValidatedSignal:
    """Signal ayant passé le portail — preuve OOS et configuration retenue.

    C'est la source de vérité : un signal n'a le droit de trader que s'il figure
    ici, avec des métriques qui satisfont réellement le portail (vérifié en test).
    """

    name: str
    rebalance_every: int
    ic_t_stat: float
    net_sharpe: float
    evidence: str

    def verdict(self, thresholds: GateThresholds = DEFAULT_THRESHOLDS) -> ValidationVerdict:
        passed, reasons = decide(self.ic_t_stat, self.net_sharpe, thresholds)
        return ValidationVerdict(
            name=self.name, ic_mean=float("nan"), ic_t_stat=self.ic_t_stat,
            net_sharpe=self.net_sharpe, avg_turnover=float("nan"), n_periods=0,
            passed=passed, reasons=reasons,
        )


# Registre des signaux validés OOS sur données Alpaca réelles (2023-08 → 2026-07).
# Chiffres issus de scripts/run_factor_validation_alpaca.py et
# scripts/run_rebalance_sweep_alpaca.py. Ajouter une entrée EXIGE d'avoir fait
# passer le signal par evaluate_signal_gate (test verrouillé dans la suite).
VALIDATED_SIGNALS: dict[str, ValidatedSignal] = {
    "momentum_12_1": ValidatedSignal(
        name="momentum_12_1",
        rebalance_every=10,
        ic_t_stat=2.56,
        net_sharpe=0.73,
        evidence="run_rebalance_sweep_alpaca.py — 80 US large-caps, 5 fenêtres OOS, "
                 "coûts 5+3 bps : meilleur à reb=10.",
    ),
}


def is_validated(name: str) -> bool:
    """Vrai si ``name`` figure au registre des signaux validés."""
    return name in VALIDATED_SIGNALS


def require_validated(name: str) -> ValidatedSignal:
    """Renvoie le signal validé ou lève ``ValueError`` — garde d'exécution.

    À appeler avant de laisser un nouveau facteur/source influencer la décision :
    tant qu'il n'a pas passé le portail et n'est pas au registre, il est refusé.
    """
    signal = VALIDATED_SIGNALS.get(name)
    if signal is None:
        raise ValueError(
            f"Signal '{name}' non validé : absent du registre VALIDATED_SIGNALS. "
            "Le faire passer par evaluate_signal_gate (IC t > 2 ET Sharpe net > 0) "
            "et l'enregistrer avant tout usage décisionnel."
        )
    return signal
