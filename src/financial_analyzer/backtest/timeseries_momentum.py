"""Time-series (trend) momentum — signal *indépendant* candidat (Tier 2).

Moskowitz, Ooi & Pedersen (2012) : le rendement *passé propre* d'un actif prédit
son rendement futur (trend-following), un effet distinct du momentum
*cross-section* (winners vs losers). Sa valeur pour FinBot est la **breadth**
(loi fondamentale de Grinold-Kahn, IR ≈ IC·√Breadth) : un pari *décorrélé* du seul
edge prouvé (``momentum_12_1``) augmente l'IR même à IC égal.

Ce module produit un **score de force de tendance** par actif — un ensemble
vol-normalisé des rendements propres sur plusieurs horizons (1/3/12 mois) :

    score_i(t) = moyenne_h [ (P_i(t−skip)/P_i(t−h−skip) − 1) / (σ_i·√h) ]

La normalisation par la vol réalisée rend les tendances comparables entre actifs
(un +10 % sur un titre calme « pèse » plus qu'un +10 % sur un titre agité). « Plus
haut = tendance haussière vol-ajustée plus forte » : orientation compatible avec la
convention long-haut / short-bas du portail. **Aucune fuite du futur** : tous les
``shift`` n'utilisent que des prix ≤ t.

Responsabilité unique : calculer le score. La *validation* (IC t, Sharpe net, DSR)
et l'*inscription* passent par ``validation_gate`` — rien n'entre dans la décision
sans franchir le portail.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["tsmom_ensemble_score"]


def tsmom_ensemble_score(
    prices: pd.DataFrame,
    lookbacks: tuple[int, ...] = (21, 63, 252),
    skip: int = 0,
    vol_lookback: int = 63,
) -> pd.DataFrame:
    """Score d'ensemble de *time-series momentum* vol-normalisé (dates × tickers).

    Args:
        prices: panel de clôtures ajustées (dates × tickers).
        lookbacks: horizons de tendance en jours (défaut ~1/3/12 mois).
        skip: jours sautés en fin de fenêtre (0 = tendance pure ; 21 sauterait le
            dernier mois comme le momentum cross-section pour éviter le reversal).
        vol_lookback: fenêtre de vol réalisée pour la normalisation.

    Returns:
        Panel de scores (mêmes index/colonnes que ``prices``). NaN tant que
        l'historique est insuffisant (géré en aval par le z-score/masquage du
        portail). Valeurs ``inf`` (vol nulle) remplacées par NaN.
    """
    if not lookbacks:
        raise ValueError("lookbacks ne peut pas être vide")
    rets = prices.pct_change()
    daily_vol = rets.rolling(vol_lookback).std()
    components = []
    for h in lookbacks:
        if h <= 0:
            raise ValueError(f"lookback doit être > 0, reçu {h}")
        trailing = prices.shift(skip) / prices.shift(h + skip) - 1.0
        # Normalisation par la vol *cumulée* de l'horizon (σ_jour·√h) : un t-stat
        # de tendance, comparable entre actifs de volatilités différentes.
        components.append(trailing / (daily_vol * np.sqrt(h)))
    score = sum(components) / len(components)
    return score.replace([np.inf, -np.inf], np.nan)
