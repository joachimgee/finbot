"""Gestion de la volatilité (Tier 1 — *risk-managed momentum*).

Barroso & Santa-Clara (2015) : le risque du momentum est prévisible par sa propre
variance réalisée ; **scaler l'exposition par l'inverse de la vol réalisée** (vers
une vol cible) élimine quasi les krachs et améliore fortement le Sharpe. Même
principe chez Moskowitz-Ooi-Pedersen / AQR (ciblage de vol constante).

Ce module fournit l'overlay **sans look-ahead** : le levier à la date t n'utilise
que la vol réalisée **jusqu'à t-1** (``shift(1)``). Appliqué aux rendements d'une
stratégie (ou d'un portefeuille), il produit la série *risk-managed*.

Responsabilité unique : transformer une série de rendements en série vol-ciblée +
le levier appliqué. Aucune décision de trading ici.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "annualized_vol",
    "apply_vol_target",
    "sharpe",
    "vol_target_leverage",
]


def sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Sharpe annualisé d'une série de rendements par période (0 si dégénéré)."""
    r = pd.Series(returns).dropna()
    sd = r.std(ddof=1)
    if len(r) < 2 or sd == 0:
        return 0.0
    return float(r.mean() / sd * np.sqrt(periods_per_year))


def annualized_vol(
    returns: pd.Series, lookback: int = 126, periods_per_year: int = 252,
    min_periods: int | None = None,
) -> pd.Series:
    """Vol réalisée annualisée en fenêtre glissante (défaut ~6 mois de bourse)."""
    r = pd.Series(returns)
    mp = min_periods if min_periods is not None else max(20, lookback // 4)
    return r.rolling(lookback, min_periods=mp).std(ddof=1) * np.sqrt(periods_per_year)


def vol_target_leverage(
    returns: pd.Series,
    target_vol: float = 0.10,
    lookback: int = 126,
    max_leverage: float = 2.0,
    periods_per_year: int = 252,
) -> pd.Series:
    """Levier ``target_vol / vol_réalisée`` — **décalé d'une période** (tradeable).

    Le levier à t n'utilise que l'information jusqu'à t-1 (``shift(1)``). Pendant le
    warm-up (vol non disponible) ou si la vol est nulle, le levier vaut 1.0. Borné
    à ``[0, max_leverage]``.
    """
    vol = annualized_vol(returns, lookback=lookback, periods_per_year=periods_per_year)
    lev = (target_vol / vol.shift(1)).replace([np.inf, -np.inf], np.nan)
    return lev.clip(lower=0.0, upper=max_leverage).fillna(1.0)


def apply_vol_target(
    returns: pd.Series,
    target_vol: float = 0.10,
    lookback: int = 126,
    max_leverage: float = 2.0,
    periods_per_year: int = 252,
) -> tuple[pd.Series, pd.Series]:
    """Applique le ciblage de vol à une série de rendements.

    Returns:
        ``(scaled_returns, leverage)`` — les rendements *risk-managed* (levier × brut)
        et la série de levier effectivement appliquée.
    """
    r = pd.Series(returns).astype(float)
    lev = vol_target_leverage(
        r, target_vol=target_vol, lookback=lookback,
        max_leverage=max_leverage, periods_per_year=periods_per_year,
    )
    return r * lev, lev
