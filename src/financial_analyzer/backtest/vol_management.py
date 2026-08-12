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
    "ex_ante_vol",
    "exposure_scalar",
    "sharpe",
    "trend_scalar",
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


# --- Overlay au niveau du PORTEFEUILLE (ex-ante) — pour le sizing du pipeline ---

def ex_ante_vol(
    weights: dict[str, float], close: pd.DataFrame,
    lookback: int = 126, periods_per_year: int = 252,
) -> float | None:
    """Volatilité **ex-ante** annualisée du portefeuille : ``sqrt(wᵀ Σ w)``.

    Args:
        weights: {ticker: poids} (peuvent ne pas sommer à 1).
        close: panel de clôtures (dates × tickers).
        lookback: fenêtre de covariance (jours).

    Returns:
        Vol annualisée, ou ``None`` si données insuffisantes (le sizing doit alors
        s'abstenir de scaler — pas de valeur inventée).
    """
    syms = [s for s in weights if s in close.columns and weights[s] != 0]
    if len(syms) < 1:
        return None
    rets = close[syms].pct_change().tail(lookback).dropna(how="all")
    if len(rets) < max(20, lookback // 4):
        return None
    cov = rets.cov().to_numpy()
    w = np.array([weights[s] for s in syms], dtype=float)
    var = float(w @ cov @ w)
    if var <= 0:
        return None
    return float(np.sqrt(var) * np.sqrt(periods_per_year))


def trend_scalar(
    close: pd.DataFrame, ma_window: int = 200, risk_off_factor: float = 0.5,
) -> float:
    """Filtre de tendance marché (risk-off) : 1.0 si l'indice est au-dessus de sa
    moyenne mobile, ``risk_off_factor`` sinon.

    L'indice « marché » est l'équipondéré des clôtures normalisées de l'univers
    (proxy auto-suffisant, pas besoin d'un ticker externe). Données insuffisantes
    → 1.0 (pas de réduction fabriquée).
    """
    if close.empty or len(close) < ma_window:
        return 1.0
    idx = close.div(close.iloc[0]).mean(axis=1)  # indice équipondéré normalisé
    ma = idx.rolling(ma_window).mean()
    if pd.isna(ma.iloc[-1]):
        return 1.0
    return 1.0 if idx.iloc[-1] >= ma.iloc[-1] else float(risk_off_factor)


def exposure_scalar(
    weights: dict[str, float], close: pd.DataFrame, *,
    target_vol: float = 0.10, lookback: int = 126, max_exposure: float = 1.0,
    ma_window: int = 200, risk_off_factor: float = 0.5,
) -> tuple[float, dict[str, float]]:
    """Facteur d'exposition = ciblage de vol ex-ante × filtre de tendance.

    ``exposure = min(max_exposure, target_vol / vol_ex_ante) × trend_scalar``.

    Avec ``max_exposure=1.0`` (défaut, sûreté d'abord), l'overlay ne peut que
    **réduire** l'exposition (de-risk) — jamais lever au-delà du plein
    investissement. Retourne aussi un dict de diagnostic.
    """
    va = ex_ante_vol(weights, close, lookback=lookback)
    vol_scalar = 1.0 if va is None or va <= 0 else min(max_exposure, target_vol / va)
    trend = trend_scalar(close, ma_window=ma_window, risk_off_factor=risk_off_factor)
    exposure = float(max(0.0, vol_scalar * trend))
    return exposure, {"ex_ante_vol": va, "vol_scalar": vol_scalar, "trend_scalar": trend}
