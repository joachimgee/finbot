"""Hierarchical Risk Parity (HRP) — allocation robuste au bruit de covariance.

López de Prado (2016, *Advances in Financial ML* ch.16). Contrairement à la
moyenne-variance (qui **inverse** une matrice de covariance — instable et
sur-concentrée quand la covariance est estimée sur peu de données), HRP :

1. mesure la **codépendance** (distance ``√((1−ρ)/2)``),
2. **cluster** les actifs hiérarchiquement (scipy),
3. **quasi-diagonalise** (réordonne pour rapprocher les actifs corrélés),
4. répartit le capital par **bisection récursive** inverse-variance entre clusters.

Aucune inversion de matrice → **robuste au bruit d'estimation**, out-of-sample
souvent meilleur que la moyenne-variance sur petits échantillons — précisément le
point faible de FinBot (covariance sur ~3 ans). Long-only, poids ≥ 0, somme = 1.

Fonction pure : ``returns`` (dates × actifs) → poids. Aucune décision de trading.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

__all__ = ["hrp_weights"]


def _inverse_variance_weights(cov: pd.DataFrame) -> np.ndarray:
    ivp = 1.0 / np.diag(cov.to_numpy())
    return ivp / ivp.sum()


def _cluster_variance(cov: pd.DataFrame, items: list[str]) -> float:
    sub = cov.loc[items, items]
    w = _inverse_variance_weights(sub).reshape(-1, 1)
    return float((w.T @ sub.to_numpy() @ w)[0, 0])


def _quasi_diagonal_order(link: np.ndarray, n: int) -> list[int]:
    """Ordre des feuilles issu du linkage (actifs corrélés adjacents)."""
    link = link.astype(int)
    order = pd.Series([link[-1, 0], link[-1, 1]])
    while order.max() >= n:
        order.index = range(0, order.shape[0] * 2, 2)  # espacer
        clusters = order[order >= n]
        idx = clusters.index
        cl = clusters.to_numpy() - n
        order[idx] = link[cl, 0]  # remplacer par le 1er enfant
        second = pd.Series(link[cl, 1], index=idx + 1)  # ajouter le 2nd
        order = pd.concat([order, second]).sort_index()
        order.index = range(order.shape[0])
    return order.tolist()


def hrp_weights(returns: pd.DataFrame, linkage_method: str = "single") -> pd.Series:
    """Poids Hierarchical Risk Parity (long-only, somme = 1).

    Args:
        returns: panel de rendements (dates × actifs). Colonnes à variance nulle
            ou tout-NaN écartées.
        linkage_method: méthode de linkage scipy ('single' par défaut, comme LdP).

    Returns:
        Series de poids indexée par actif (somme 1). Vide si < 2 actifs exploitables ;
        pour 1 actif, poids 1.0.
    """
    r = returns.dropna(axis=1, how="all")
    # Écarter les actifs sans variance (colonnes constantes) — indéfinis en corr.
    var = r.var(ddof=1)
    r = r[[c for c in r.columns if var.get(c, 0.0) > 0]]
    r = r.dropna()  # lignes complètes pour une covariance cohérente
    cols = list(r.columns)
    if len(cols) == 0:
        return pd.Series(dtype=float)
    if len(cols) == 1:
        return pd.Series([1.0], index=cols)

    cov = r.cov()
    corr = r.corr().clip(-1.0, 1.0)
    dist = np.sqrt((1.0 - corr.to_numpy()) / 2.0)
    np.fill_diagonal(dist, 0.0)
    link = linkage(squareform(dist, checks=False), method=linkage_method)
    order = [cols[i] for i in _quasi_diagonal_order(link, len(cols))]

    weights = pd.Series(1.0, index=order)
    clusters = [order]
    while clusters:
        clusters = [
            c[j:k] for c in clusters
            for j, k in ((0, len(c) // 2), (len(c) // 2, len(c)))
            if len(c) > 1
        ]
        for i in range(0, len(clusters), 2):
            c0, c1 = clusters[i], clusters[i + 1]
            v0, v1 = _cluster_variance(cov, c0), _cluster_variance(cov, c1)
            alpha = 1.0 - v0 / (v0 + v1) if (v0 + v1) > 0 else 0.5
            weights[c0] *= alpha
            weights[c1] *= 1.0 - alpha
    return weights.reindex(cols).fillna(0.0)
