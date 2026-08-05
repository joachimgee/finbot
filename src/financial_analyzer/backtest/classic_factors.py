"""Facteurs cross-sectionnels classiques calculés depuis les prix.

Ne dépend que d'un panel de clôtures ajustées (dates × tickers) — donc
entièrement calculable hors-ligne, sans fuite du futur (chaque facteur en t
n'utilise que l'information disponible jusqu'en t). Chaque facteur devient une
« source » pour le combinateur B ; l'orientation est choisie pour que « plus
haut = rendement futur attendu plus élevé ».

Facteurs (documentés dans la littérature factorielle) :
- momentum_12_1 : rendement 12 mois en excluant le dernier mois (winners).
- reversal_5    : opposé du rendement 5 jours (les perdants récents rebondissent).
- low_vol       : opposé de la volatilité 20 jours (prime au faible risque).
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

__all__ = ["daily_returns", "compute_classic_factors"]


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Rendements simples journaliers."""
    return prices.pct_change()


def compute_classic_factors(prices: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Retourne un dict {nom_facteur: panel (dates × tickers)}.

    Toutes les valeurs en t reposent uniquement sur des prix <= t.
    """
    rets = daily_returns(prices)

    # Momentum 12-1 mois (~252 jours de base, saut du dernier ~21 jours)
    momentum_12_1 = prices.shift(21) / prices.shift(252) - 1.0

    # Reversal court terme : opposé du rendement 5 jours
    reversal_5 = -(prices / prices.shift(5) - 1.0)

    # Low-vol : opposé de la vol réalisée 20 jours
    low_vol = -(rets.rolling(20).std())

    factors = {
        "momentum_12_1": momentum_12_1,
        "reversal_5": reversal_5,
        "low_vol": low_vol,
    }
    # Remplace inf éventuels par NaN (gérés en aval par le z-score/masquage)
    return {k: v.replace([np.inf, -np.inf], np.nan) for k, v in factors.items()}
