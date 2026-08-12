"""Momentum *résiduel* (idiosyncratique) — le pari décorrélé (Tier 2 ter).

Le test de breadth l'a montré empiriquement : ajouter des titres corrélés
n'augmente pas la breadth *effective* (paris indépendants). Blitz, Huij & Martens
(2011) proposent le levier : **retirer l'exposition marché de chaque titre, puis
faire du momentum sur le résidu**. Le momentum résiduel a historiquement un Sharpe
supérieur et des drawdowns bien moindres que le momentum brut — et surtout il est
**orthogonal au marché**, donc *décorrélé* du momentum cross-section classique →
c'est de la vraie breadth.

Construction (sans look-ahead) :

1. rendement marché ``m_t`` = moyenne équipondérée cross-section des rendements ;
2. **β glissant** par titre sur une fenêtre passée : ``βᵢ = Cov(rᵢ, m)/Var(m)`` ;
3. **résidu** ``eᵢ,t = rᵢ,t − βᵢ,t·m_t`` (part idiosyncratique) ;
4. **score** = résidu cumulé sur la fenêtre de formation (12 mois hors dernier),
   standardisé par la vol résiduelle : un t-stat de tendance idiosyncratique.

« Plus haut = tendance idiosyncratique haussière plus forte » (convention
long-haut du portail). Chaque β/résidu à la date s n'utilise que des prix ≤ s, et
le score en t n'utilise que des résidus ≤ t−skip : aucune fuite du rendement futur.

Responsabilité unique : produire le score. Validation et inscription passent par le
portail — rien n'entre dans la décision sans le franchir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["market_residuals", "residual_momentum_score"]


def market_residuals(prices: pd.DataFrame, beta_window: int = 126) -> pd.DataFrame:
    """Résidus idiosyncratiques quotidiens vs le marché équipondéré (β glissant).

    ``eᵢ,t = rᵢ,t − βᵢ,t·m_t`` où ``m_t`` est le rendement moyen cross-section et
    ``βᵢ,t`` la pente glissante (fenêtre ``beta_window``, données ≤ t). NaN tant que
    la fenêtre n'est pas remplie.
    """
    rets = prices.pct_change()
    mkt = rets.mean(axis=1)  # marché équipondéré (proxy auto-suffisant)
    var_m = mkt.rolling(beta_window).var()
    # Cov(rᵢ, m) glissante, colonne par colonne (rolling.cov aligne sur l'index).
    cov = rets.rolling(beta_window).cov(mkt)
    beta = cov.div(var_m, axis=0)
    resid = rets.sub(beta.mul(mkt, axis=0))
    return resid


def residual_momentum_score(
    prices: pd.DataFrame,
    beta_window: int = 126,
    form: int = 252,
    skip: int = 21,
    min_obs: int | None = None,
) -> pd.DataFrame:
    """Score de momentum résiduel standardisé (dates × tickers).

    Args:
        prices: panel de clôtures ajustées (dates × tickers).
        beta_window: fenêtre d'estimation du β marché glissant.
        form: fenêtre de formation du momentum (≈ 12 mois).
        skip: dernier mois sauté (≈ 21 j) pour éviter le reversal court terme.
        min_obs: nb min de résidus non-nuls dans la fenêtre (défaut ~moitié).

    Returns:
        Panel de scores (mêmes index/colonnes). NaN si historique insuffisant ;
        ``inf`` (vol résiduelle nulle) remplacé par NaN.
    """
    if form <= skip:
        raise ValueError(f"form ({form}) doit être > skip ({skip})")
    resid = market_residuals(prices, beta_window=beta_window)
    win = form - skip
    mp = min_obs if min_obs is not None else max(20, win // 2)
    # Résidus de la fenêtre [t-form, t-skip] : on décale de skip puis on agrège.
    r = resid.shift(skip)
    cum = r.rolling(win, min_periods=mp).sum()
    vol = r.rolling(win, min_periods=mp).std(ddof=1)
    score = cum / (vol * np.sqrt(win))  # t-stat de tendance idiosyncratique
    return score.replace([np.inf, -np.inf], np.nan)
