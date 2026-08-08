"""Facteurs cross-sectionnels classiques calculés depuis les prix.

Ne dépend que d'un panel de clôtures ajustées (dates × tickers) — donc
entièrement calculable hors-ligne, sans fuite du futur (chaque facteur en t
n'utilise que l'information disponible jusqu'en t). Chaque facteur devient une
« source » pour le combinateur B ; l'orientation est choisie pour que « plus
haut = rendement futur attendu plus élevé ».

Facteurs (documentés dans la littérature factorielle) :
- momentum_12_1 : rendement 12 mois en excluant le dernier mois (winners).
- momentum_6_1  : momentum intermédiaire 6 mois hors dernier mois.
- reversal_5    : opposé du rendement 5 jours (les perdants récents rebondissent).
- reversal_21   : reversal court terme 1 mois (Jegadeesh 1990).
- low_vol       : opposé de la volatilité 20 jours (prime au faible risque).
- low_vol_60    : même prime, horizon 60 jours (plus stable).
- max_lottery   : opposé du rendement journalier max sur 21 jours — effet MAX,
                  les titres « loterie » sous-performent (Bali-Cakici-Whitelaw 2011).
- high_52w      : proximité du plus-haut 52 semaines (George-Hwang 2004), les
                  titres proches de leur plus-haut continuent de surperformer.
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

    # Momentum intermédiaire 6-1 mois (~126 jours, saut du dernier ~21 jours)
    momentum_6_1 = prices.shift(21) / prices.shift(126) - 1.0

    # Reversal court terme : opposé du rendement 5 jours
    reversal_5 = -(prices / prices.shift(5) - 1.0)

    # Reversal 1 mois : opposé du rendement 21 jours
    reversal_21 = -(prices / prices.shift(21) - 1.0)

    # Low-vol : opposé de la vol réalisée 20 / 60 jours
    low_vol = -(rets.rolling(20).std())
    low_vol_60 = -(rets.rolling(60).std())

    # Effet MAX : opposé du plus fort rendement journalier sur 21 jours.
    max_lottery = -(rets.rolling(21).max())

    # Plus-haut 52 semaines : prix courant rapporté au plus-haut ~252 jours
    # (dans (0, 1] ; proche de 1 = proche du plus-haut). N'utilise que des
    # prix <= t (la fenêtre roulante inclut t, information connue en t).
    high_52w = prices / prices.rolling(252, min_periods=63).max()

    factors = {
        "momentum_12_1": momentum_12_1,
        "momentum_6_1": momentum_6_1,
        "reversal_5": reversal_5,
        "reversal_21": reversal_21,
        "low_vol": low_vol,
        "low_vol_60": low_vol_60,
        "max_lottery": max_lottery,
        "high_52w": high_52w,
    }
    # Remplace inf éventuels par NaN (gérés en aval par le z-score/masquage)
    return {k: v.replace([np.inf, -np.inf], np.nan) for k, v in factors.items()}
