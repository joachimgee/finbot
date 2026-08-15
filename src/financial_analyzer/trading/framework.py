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


class HRPConstruction:
    """Construction **HRP** : le signal *sélectionne* les noms, HRP les *dimensionne*.

    Alternative enfichable à la construction BL. Le momentum choisit les titres à
    conviction longue (signal > 0) ; Hierarchical Risk Parity (López de Prado) les
    pondère de façon **robuste au bruit de covariance** (pas d'inversion de matrice),
    puis on applique la même finalisation (cap → vol → bande) que la construction par
    défaut. Données insuffisantes / trop peu de noms → repli sur la construction BL
    (fail-safe, jamais de crash).
    """

    def __init__(self, pipeline: object, lookback: int = 252, min_names: int = 3) -> None:
        self._p = pipeline
        self.lookback = lookback
        self.min_names = min_names

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        import pandas as pd

        from financial_analyzer.portfolio.hrp import hrp_weights

        longs = [s for s, v in (signals or {}).items() if v and v > 0]
        prices = (data or {}).get("prices", {}) or {}
        frames = {s: prices[s]["close"] for s in longs
                  if s in prices and prices[s] is not None
                  and not prices[s].empty and "close" in prices[s]}
        if len(frames) < self.min_names:
            return self._p._construct_weights(signals, data)  # repli BL
        try:
            close = pd.DataFrame(frames).dropna(how="all").tail(self.lookback + 1)
            rets = close.pct_change().dropna()
            w = hrp_weights(rets)
            weights = {s: float(x) for s, x in w.items() if x > 1e-9}
            if not weights:
                return self._p._construct_weights(signals, data)
            return self._p._finalize_weights(weights, data)
        except Exception:  # noqa: BLE001 - une construction ne doit jamais crasher le run
            return self._p._construct_weights(signals, data)


class MultiStrategyConstruction:
    """Construction **multi-stratégie** (momentum + PCA-résiduel + paires).

    Ignore le signal du pipeline et calcule le **book combiné long/short** depuis
    ``data['prices']`` (familles décorrélées, mélangées par risk-weighting). Repli
    sur la construction BL si données insuffisantes.

    ⚠️ Long/short + familles **non validées** (seul momentum l'est) → **paper
    uniquement** (forward-test). On ne passe **pas** par la finalisation long-only
    (cap/vol) : les poids sont déjà normalisés (brut = 1) par le book. En revanche,
    la **bande de non-transaction** (``pipeline.no_trade_band``, opt-in) est
    appliquée si activée : elle est sign-agnostique (``|cible − détenu|`` par actif),
    donc valable en long/short — elle ne bouge une ligne que si son poids change de
    plus que la bande, réduisant le churn du rééquilibrage quotidien (coûts).
    """

    def __init__(self, pipeline: object, family_weights: Dict[str, float] | None = None,
                 min_names: int = 10) -> None:
        self._p = pipeline
        self.family_weights = family_weights
        self.min_names = min_names

    def construct(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        import pandas as pd

        from financial_analyzer.trading.multi_strategy_book import combined_book

        prices = (data or {}).get("prices", {}) or {}
        frames = {s: df["close"] for s, df in prices.items()
                  if df is not None and not df.empty and "close" in df}
        if len(frames) < self.min_names:
            return self._p._construct_weights(signals, data)
        close = pd.DataFrame(frames).dropna(how="all")
        book = combined_book(close, self.family_weights)
        if not book:
            return self._p._construct_weights(signals, data)
        # Bande de non-transaction (opt-in) : tenir les lignes dont le poids bouge
        # de moins que la bande vs le book détenu — évite de churner le book pour
        # des micro-variations de signal (coûts). Sign-agnostique -> OK en long/short.
        if getattr(self._p, "no_trade_band", 0.0) > 0:
            book = self._p._apply_no_trade_band(book)
        return book


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


class ScheduledExecution:
    """ExecutionModel qui **découpe** chaque ordre en tranches enfants (algo TWAP /
    Almgren-Chriss), soumises via le **même gateway audité**.

    Chaque tranche porte une ``idempotency_key`` unique (indice de tranche) pour ne
    pas être dédupliquée par la clé dérivée. ``kappa=0`` ⇒ TWAP (tranches égales) ;
    ``kappa>0`` ⇒ front-loaded (Almgren-Chriss, urgence).

    ⚠️ **Étalement dans le temps** : ce modèle produit et soumet le *planning* ; le
    véritable espacement intraday exige un driver d'exécution temps-réel (hors
    périmètre). En synchrone, les tranches partent en séquence — l'intérêt est le
    *plumbing* (découpe + clés idempotentes + passage par le chokepoint), prêt à
    recevoir un driver. Le bénéfice d'impact ne se matérialise qu'avec l'espacement.
    """

    def __init__(self, pipeline: object, n_slices: int = 5, kappa: float = 0.0,
                 min_slice_qty: int = 1) -> None:
        self._p = pipeline
        self.n_slices = max(1, int(n_slices))
        self.kappa = float(kappa)
        self.min_slice_qty = max(1, int(min_slice_qty))

    def execute(
        self, target_weights: Dict[str, float], data: Dict, *, dry_run: bool
    ) -> List[Dict]:
        from financial_analyzer.trading.execution_algos import almgren_chriss_schedule

        parents = self._p._generate_orders(target_weights, data)
        children: List[Dict] = []
        for o in parents:
            qty = int(o.get("qty", 0))
            if qty <= 0 or qty < self.min_slice_qty:
                children.append(o)
                continue
            schedule = almgren_chriss_schedule(qty, self.n_slices, self.kappa)
            for i, child_qty in enumerate(schedule):
                if child_qty < self.min_slice_qty:
                    continue
                children.append({
                    **o, "qty": child_qty,
                    "idempotency_key": f"{o['symbol']}:{o['side']}:s{i}:{child_qty}",
                })
        return self._p._execute_orders_with_risk_checks(children, dry_run=dry_run)


__all__ = [
    "AlphaModel",
    "ExecutionModel",
    "HRPConstruction",
    "MultiStrategyConstruction",
    "PipelineAlpha",
    "PipelineConstruction",
    "PipelineExecution",
    "PipelineRisk",
    "PortfolioConstructionModel",
    "ScheduledExecution",
    "RiskModel",
]
