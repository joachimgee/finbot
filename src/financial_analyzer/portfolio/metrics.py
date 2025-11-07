from __future__ import annotations

# 1. Stdlib
from typing import Dict

# 2. Third-party
import numpy as np
import pandas as pd

# 3. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def calculate_portfolio_return(weights: pd.Series, mean_returns: pd.Series) -> float:
    """Portfolio expected return (dot product, annualized if inputs are annualized).

    Args:
        weights: Poids par actif (somme 1)
        mean_returns: Rendements moyens (annualisés ou par période)

    Returns:
        Rendement attendu du portefeuille
    """
    w = weights.reindex(mean_returns.index).fillna(0.0)
    return float(np.dot(w.values, mean_returns.values))


def calculate_portfolio_volatility(weights: pd.Series, cov_matrix: pd.DataFrame) -> float:
    """Portfolio volatility (std dev).

    Args:
        weights: Poids par actif
        cov_matrix: Matrice de covariance (même ordre que weights)

    Returns:
        Volatilité (écart type)
    """
    w = weights.reindex(cov_matrix.columns).fillna(0.0).values
    cov = cov_matrix.loc[cov_matrix.index, cov_matrix.columns].values
    vol = float(np.sqrt(w @ cov @ w.T))
    return vol


def calculate_portfolio_sharpe(
    weights: pd.Series,
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """Portfolio Sharpe Ratio.

    Args:
        weights: Poids par actif
        mean_returns: Rendements moyens annualisés
        cov_matrix: Matrice de covariance annualisée
        risk_free_rate: Taux sans risque annuel
        periods_per_year: Périodes par an (si mean_returns non annualisé)

    Returns:
        Sharpe ratio
    """
    port_ret = calculate_portfolio_return(weights, mean_returns)
    port_vol = calculate_portfolio_volatility(weights, cov_matrix)
    if port_vol == 0:
        return np.nan
    sharpe = (port_ret - risk_free_rate) / port_vol
    return float(sharpe)


def calculate_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Correlation matrix."""
    return returns.corr()


def calculate_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical Value at Risk (VaR) at given confidence (positive number).

    Args:
        returns: Série de rendements (par période)
        confidence: Niveau de confiance (ex: 0.95)

    Returns:
        VaR (perte positive)
    """
    if returns.empty:
        return 0.0
    percentile = np.percentile(returns.dropna(), (1 - confidence) * 100)
    var = -float(percentile)
    return max(0.0, var)


def calculate_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """Conditional VaR (Expected Shortfall).

    Args:
        returns: Série rendements
        confidence: Niveau de confiance

    Returns:
        CVaR (perte positive)
    """
    if returns.empty:
        return 0.0
    threshold = np.percentile(returns.dropna(), (1 - confidence) * 100)
    tail_losses = returns[returns <= threshold]
    if len(tail_losses) == 0:
        return 0.0
    cvar = -float(tail_losses.mean())
    return max(0.0, cvar)


def calculate_diversification_ratio(weights: pd.Series, vols: pd.Series, portfolio_vol: float) -> float:
    """Diversification Ratio: sum(w_i * sigma_i) / sigma_p.

    Args:
        weights: Poids par actif
        vols: Volatilités individuelles
        portfolio_vol: Volatilité du portefeuille

    Returns:
        Diversification ratio (>= 1 si bénéfice diversification)
    """
    if portfolio_vol == 0:
        return np.nan
    w = weights.reindex(vols.index).fillna(0.0)
    top = float(np.sum(w.values * vols.values))
    return float(top / portfolio_vol)


def calculate_herfindahl_index(weights: pd.Series) -> float:
    """Herfindahl-Hirschman Index (concentration): sum(w^2)."""
    w = weights.values
    return float(np.sum(w ** 2))
