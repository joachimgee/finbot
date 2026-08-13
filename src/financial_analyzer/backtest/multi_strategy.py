"""Combinaison multi-stratégie — risk-weighting de familles décorrélées.

Loi fondamentale (Grinold-Kahn) : combiner des paris **indépendants** relève l'IR.
Ce module assemble plusieurs séries de rendements de stratégies en un book unique,
pondéré par le **risque** (pas par capital égal), pour ne pas laisser la stratégie
la plus volatile dominer :

* :func:`inverse_vol_weights` — poids ∝ 1/vol (simple, ignore les corrélations).
* :func:`risk_parity_weights` — **equal risk contribution** (ERC) : chaque stratégie
  contribue autant au risque total, *en tenant compte des corrélations*.
* :func:`combine` — série de rendements combinée + poids.
* :func:`strategy_report` — Sharpe par stratégie, matrice de corrélation, Sharpe combiné.

Pur : ne décide rien, ne trade rien — agrège des rendements déjà nets. La discipline
du portail s'applique en amont (une stratégie n'entre que si elle a un edge prouvé).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "combine",
    "inverse_vol_weights",
    "risk_parity_weights",
    "sharpe",
    "strategy_report",
]


def sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    r = pd.Series(returns).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(periods_per_year)) if len(r) > 1 and sd > 0 else 0.0


def _clean(returns: pd.DataFrame) -> pd.DataFrame:
    r = returns.dropna(how="all")
    keep = [c for c in r.columns if r[c].std(ddof=1) > 0]
    return r[keep].dropna()


def inverse_vol_weights(returns: pd.DataFrame) -> pd.Series:
    """Poids ∝ 1/écart-type par stratégie (somme = 1)."""
    r = _clean(returns)
    if r.shape[1] == 0:
        return pd.Series(dtype=float)
    inv = 1.0 / r.std(ddof=1)
    return inv / inv.sum()


def risk_parity_weights(returns: pd.DataFrame, iters: int = 500, tol: float = 1e-10) -> pd.Series:
    """Poids **equal risk contribution** (ERC) via la covariance des stratégies.

    Chaque stratégie contribue autant au risque total du book (corrélations
    incluses). Itération multiplicative amortie, convergente pour une covariance
    définie positive ; repli sur l'inverse-vol si dégénéré.
    """
    r = _clean(returns)
    n = r.shape[1]
    if n == 0:
        return pd.Series(dtype=float)
    if n == 1:
        return pd.Series([1.0], index=r.columns)
    cov = r.cov().to_numpy()
    w = 1.0 / np.sqrt(np.diag(cov))
    w = w / w.sum()
    for _ in range(iters):
        mrc = cov @ w                      # risque marginal
        rc = w * mrc                       # contribution au risque
        target = rc.mean()
        new = w * np.sqrt(target / np.where(rc > 0, rc, np.nan))
        new = np.nan_to_num(new, nan=0.0)
        if new.sum() <= 0:
            return inverse_vol_weights(returns)
        new /= new.sum()
        if np.max(np.abs(new - w)) < tol:
            w = new
            break
        w = new
    return pd.Series(w, index=r.columns)


def combine(returns: pd.DataFrame, method: str = "risk_parity") -> tuple[pd.Series, pd.Series]:
    """Combine des rendements de stratégies en un book unique.

    Args:
        returns: DataFrame (dates × stratégies) de rendements nets.
        method: ``'risk_parity'`` (ERC, défaut), ``'inverse_vol'`` ou ``'equal'``.

    Returns:
        ``(combined_returns, weights)``.
    """
    r = _clean(returns)
    if r.shape[1] == 0:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    if method == "equal":
        w = pd.Series(1.0 / r.shape[1], index=r.columns)
    elif method == "inverse_vol":
        w = inverse_vol_weights(returns)
    elif method == "risk_parity":
        w = risk_parity_weights(returns)
    else:
        raise ValueError(f"méthode inconnue : {method!r}")
    combined = (returns[w.index].fillna(0.0) * w).sum(axis=1)
    return combined, w


def strategy_report(returns: pd.DataFrame, method: str = "risk_parity") -> dict:
    """Rapport de combinaison : Sharpe par stratégie, corrélations, Sharpe combiné."""
    r = _clean(returns)
    combined, w = combine(returns, method=method)
    per = {c: sharpe(r[c]) for c in r.columns}
    return {
        "weights": w.to_dict(),
        "per_strategy_sharpe": per,
        "correlation": r.corr().round(3),
        "combined_sharpe": sharpe(combined),
        "best_single_sharpe": max(per.values()) if per else 0.0,
        "combined_returns": combined,
    }
