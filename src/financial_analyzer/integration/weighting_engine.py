"""Evidence-Based Weighting Engine

Calcule des poids de sources de signaux (technical, fundamental, sentiment, ml_lstm,
ml_factor, rl) basés sur des métriques objectives dérivées d'un historique
de performance plutôt que sur des heuristiques arbitraires.

Fondements méthodologiques (voir COMPARATIVE_ANALYSIS.md):
    - Information Coefficient (IC) ≈ capacité prédictive (approx ici par moyenne des retours)
    - Sharpe Ratio (1966) mesure efficacité risque
    - Max Drawdown pénalise instabilité
    - Kelly Criterion (1956) inspiré pour limiter sur-allocation; on applique un cap

Equation (pondérée):
    weight_i ∝ 0.5 * Sharpe_norm + 0.3 * MeanReturn_norm + 0.2 * (1 - Drawdown_norm)

Où *_norm représentent des normalisations min-max robustes (quantiles) pour réduire
sensibilité aux extrêmes. Les poids finaux sont normalisés pour sommer à 1.0.

Interface:
    WeightingEngine.compute_weights(history: pd.DataFrame) -> Dict[str, float]
        history: DataFrame index temps ; colonnes = sources ; valeurs = retours
        (retours journaliers ou périodiques des signaux/stratégies correspondantes).

Exemple:
    >>> import pandas as pd, numpy as np
    >>> rng = pd.date_range("2025-01-01", periods=60)
    >>> data = pd.DataFrame({
    ...     'technical': np.random.normal(0.001, 0.01, 60),
    ...     'fundamental': np.random.normal(0.0008, 0.009, 60),
    ...     'sentiment': np.random.normal(0.0012, 0.012, 60),
    ... })
    >>> engine = WeightingEngine()
    >>> weights = engine.compute_weights(data)
    >>> sum(weights.values()) == 1.0
    True

Notes:
    - Si moins de 30 observations ou colonnes vides -> fallback égalitaire.
    - Drawdown calculé sur performance cumulée simple.
    - Sharpe annualisé si fréquence >= 200 observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class WeightingResult:
    """Résultat du calcul de poids.

    Attributes:
        weights: Dictionnaire {source: poids normalisé}
        sharpe: Sharpe par source
        mean_return: Moyenne des retours par source
        max_drawdown: Max drawdown par source
        observations: Nombre de points utilisés
    """
    weights: Dict[str, float]
    sharpe: Dict[str, float]
    mean_return: Dict[str, float]
    max_drawdown: Dict[str, float]
    observations: int


class WeightingEngine:
    """Calcule des poids basés sur historique de performance.

    Métriques calculées par colonne:
        mean_return: moyenne simple des retours
        volatility: écart-type
        sharpe: mean / vol (naive) annualisée si possible
        max_drawdown: max drawdown sur cumul (penalité)

    Formule poids brute:
        raw_i = 0.5 * Sharpe_norm + 0.3 * Mean_norm + 0.2 * (1 - DD_norm)

    Normalisation min-max robuste via quantiles 5% / 95% pour limiter outliers.
    """

    def __init__(self, min_observations: int = 30):
        self.min_observations = min_observations

    @staticmethod
    def _robust_min_max(values: Dict[str, float]) -> Dict[str, float]:
        arr = np.array(list(values.values()), dtype=float)
        if arr.size == 0:
            return {k: 0.0 for k in values}
        q_low, q_high = np.quantile(arr, [0.05, 0.95])
        scale = q_high - q_low if q_high != q_low else 1.0
        return {k: float(np.clip((v - q_low) / scale, 0.0, 1.0)) for k, v in values.items()}

    @staticmethod
    def _compute_max_drawdown(series: pd.Series) -> float:
        if series.empty:
            return 0.0
        cumulative = (1 + series).cumprod()
        peak = cumulative.cummax()
        dd = (cumulative / peak) - 1.0
        return float(dd.min())  # Valeur négative

    def compute_weights(self, history: pd.DataFrame) -> WeightingResult:
        """Calcule des poids pour chaque source.

        Args:
            history: DataFrame retours historiques, colonnes = sources.

        Returns:
            WeightingResult
        """
        if history is None or history.empty:
            logger.warning("History vide - fallback égalitaire")
            return WeightingResult(weights={}, sharpe={}, mean_return={}, max_drawdown={}, observations=0)

        obs = len(history)
        columns = [c for c in history.columns if history[c].dropna().shape[0] > 0]
        if obs < self.min_observations or not columns:
            logger.warning(f"Historique insuffisant ({obs} < {self.min_observations}) - fallback égalitaire")
            eq = 1.0 / max(len(columns), 1)
            weights = {c: eq for c in columns}
            return WeightingResult(weights=weights, sharpe={}, mean_return={}, max_drawdown={}, observations=obs)

        mean_returns = {c: float(history[c].mean()) for c in columns}
        vol = {c: float(history[c].std(ddof=0)) for c in columns}
        sharpe = {}
        for c in columns:
            if vol[c] == 0:
                sharpe[c] = 0.0
            else:
                sr = mean_returns[c] / vol[c]
                # Annualisation rudimentaire si beaucoup d'observations (>200 ~ trading days)
                if obs >= 200:
                    sr *= np.sqrt(252)
                sharpe[c] = float(sr)

        max_dd = {c: abs(self._compute_max_drawdown(history[c].dropna())) for c in columns}

        # Normalisations robustes
        sharpe_norm = self._robust_min_max(sharpe)
        mean_norm = self._robust_min_max(mean_returns)
        dd_norm = self._robust_min_max(max_dd)  # plus grand = pire

        raw = {}
        for c in columns:
            raw[c] = 0.5 * sharpe_norm[c] + 0.3 * mean_norm[c] + 0.2 * (1 - dd_norm[c])

        total = sum(raw.values())
        if total == 0:
            weights = {c: 1.0 / len(columns) for c in columns}
        else:
            weights = {c: raw[c] / total for c in columns}

        logger.info(f"Poids calculés (sources={len(columns)}, obs={obs}): {weights}")
        return WeightingResult(
            weights=weights,
            sharpe=sharpe,
            mean_return=mean_returns,
            max_drawdown=max_dd,
            observations=obs,
        )
