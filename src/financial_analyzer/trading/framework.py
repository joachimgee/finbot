"""Cadre d'exécution en couches enfichables (audit #5, inspiré de LEAN).

Sépare la décision de trading en **quatre étages remplaçables**, chacun avec un
contrat clair — au lieu d'un ``LiveTradingPipeline`` monolithique :

    Alpha  ─►  PortfolioConstruction  ─►  Risk  ─►  Execution
    data→signaux   signaux→poids cibles    veto/ajuste   poids→ordres soumis

Intérêt : tester/remplacer un étage sans toucher aux autres (p.ex. brancher un
autre modèle d'alpha, ou un exécuteur TWAP), et rendre le contrat de chaque couche
explicite. Les implémentations **par défaut** (``Pipeline*``) délèguent à la logique
déjà validée du pipeline : le comportement live est **inchangé**, seule la couture
devient explicite et injectable.

Les adaptateurs par défaut sont *duck-typed* sur un objet « pipeline » (ils
appellent ses méthodes) — ce module n'importe donc pas ``live_trading_pipeline``
(pas de cycle d'import).
"""
from __future__ import annotations

from typing import Dict, List, Protocol, Tuple, runtime_checkable


@runtime_checkable
class AlphaModel(Protocol):
    """Données de marché → signaux ``{symbole: score ∈ [-1,1]}``.

    Convention : un score ≤ 0 (ou l'absence de clé) = abstention / pas de conviction
    longue. Le modèle ne décide *pas* de la taille — c'est la construction.
    """

    def generate(self, data: Dict) -> Dict[str, float]:
        ...


@runtime_checkable
class PortfolioConstructionModel(Protocol):
    """Signaux → poids cibles ``{symbole: poids}`` (long-only, somme ≤ 1).

    C'est ici que vivent l'optimisation (Black-Litterman), le cap de concentration,
    l'overlay de volatilité et la bande de non-transaction (cost-aware).
    """

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        ...


@runtime_checkable
class RiskModel(Protocol):
    """Contrôle **pré-trade portefeuille** : valide (et peut ajuster) le book cible.

    Retourne ``(ok, weights)`` — ``ok=False`` => on s'abstient du rééquilibrage.
    Corrélation-aware (vol ex-ante / VaR / concentration).
    """

    def evaluate(
        self, weights: Dict[str, float], data: Dict
    ) -> Tuple[bool, Dict[str, float]]:
        ...


@runtime_checkable
class ExecutionModel(Protocol):
    """Poids cibles → ordres soumis (via l'unique gateway audité). Retourne les
    résultats d'exécution. ``dry_run`` applique tout sauf la soumission réelle."""

    def execute(
        self, target_weights: Dict[str, float], data: Dict, *, dry_run: bool
    ) -> List[Dict]:
        ...


# --- Implémentations par défaut : délèguent au pipeline (comportement inchangé) ---


class PipelineAlpha:
    """Alpha par défaut : signaux validés + abstention (``_generate_signals``)."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def generate(self, data: Dict) -> Dict[str, float]:
        return self._p._generate_signals(data)


class PipelineConstruction:
    """Construction par défaut : BL + cap + overlay vol + bande cost-aware."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        return self._p._construct_weights(signals, data)


class PipelineRisk:
    """Risque par défaut : contrôle pré-trade portefeuille (``_portfolio_risk_ok``)."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def evaluate(
        self, weights: Dict[str, float], data: Dict
    ) -> Tuple[bool, Dict[str, float]]:
        ok = True if not weights else self._p._portfolio_risk_ok(weights, data)
        return ok, weights


class PipelineExecution:
    """Exécution par défaut : génération d'ordres + chokepoint audité."""

    def __init__(self, pipeline: object) -> None:
        self._p = pipeline

    def execute(
        self, target_weights: Dict[str, float], data: Dict, *, dry_run: bool
    ) -> List[Dict]:
        orders = self._p._generate_orders(target_weights, data)
        return self._p._execute_orders_with_risk_checks(orders, dry_run=dry_run)


__all__ = [
    "AlphaModel",
    "ExecutionModel",
    "PipelineAlpha",
    "PipelineConstruction",
    "PipelineExecution",
    "PipelineRisk",
    "PortfolioConstructionModel",
    "RiskModel",
]
