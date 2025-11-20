"""
Module pour calculer les pondérations market-cap réelles.

Utilise yfinance pour récupérer les vraies capitalisations boursières
au lieu d'un proxy inverse-volatilité.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import yfinance as yf
from datetime import datetime

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def get_market_caps(tickers: List[str], reference_date: Optional[str] = None) -> pd.Series:
    """
    Récupère les market caps réelles via yfinance.
    
    Args:
        tickers: Liste de tickers
        reference_date: Date de référence (si None, utilise données actuelles)
    
    Returns:
        Series avec market caps (index = tickers)
    
    Example:
        >>> caps = get_market_caps(['AAPL', 'MSFT', 'GOOGL'])
        >>> print(caps)
        AAPL    4.0e12
        MSFT    3.5e12
        GOOGL   2.1e12
    """
    market_caps = {}
    failed = []
    
    logger.info(f"Fetching market caps for {len(tickers)} tickers...")
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Essayer plusieurs clés possibles
            market_cap = (
                info.get('marketCap') or 
                info.get('enterpriseValue') or
                info.get('sharesOutstanding', 0) * info.get('currentPrice', 0)
            )
            
            if market_cap and market_cap > 0:
                market_caps[ticker] = float(market_cap)
            else:
                logger.warning(f"No valid market cap for {ticker}")
                failed.append(ticker)
                
        except Exception as e:
            logger.error(f"Failed to fetch market cap for {ticker}: {e}")
            failed.append(ticker)
    
    if failed:
        logger.warning(f"Failed to get market caps for {len(failed)} tickers: {failed}")
    
    caps_series = pd.Series(market_caps)
    logger.info(f"Successfully fetched {len(caps_series)} market caps")
    
    return caps_series


def calculate_market_cap_weights(
    tickers: List[str],
    reference_date: Optional[str] = None,
    min_weight: float = 0.005,
    max_weight: float = 0.10
) -> pd.Series:
    """
    Calcule pondérations market-cap weighted avec contraintes.
    
    Args:
        tickers: Liste de tickers
        reference_date: Date de référence pour market caps
        min_weight: Poids minimum par actif (défaut 0.5%)
        max_weight: Poids maximum par actif (défaut 10%)
    
    Returns:
        Series de poids normalisés (somme = 1.0)
    
    Example:
        >>> weights = calculate_market_cap_weights(['AAPL', 'MSFT', 'NVDA'])
        >>> print(weights.sum())
        1.0
    """
    caps = get_market_caps(tickers, reference_date)
    
    if caps.empty:
        logger.error("No market caps retrieved, using equal weights")
        return pd.Series(1.0 / len(tickers), index=tickers)
    
    # Calculer poids bruts
    total_cap = caps.sum()
    weights = caps / total_cap
    
    # Appliquer contraintes min/max
    weights = weights.clip(lower=min_weight, upper=max_weight)
    
    # Renormaliser après contraintes
    weights = weights / weights.sum()
    
    logger.info(f"Market-cap weights calculated:")
    logger.info(f"  Min weight: {weights.min():.2%}")
    logger.info(f"  Max weight: {weights.max():.2%}")
    logger.info(f"  Top 5: {weights.nlargest(5).to_dict()}")
    
    return weights


def compare_weighting_schemes(
    returns: pd.DataFrame,
    reference_date: Optional[str] = None
) -> Dict[str, pd.Series]:
    """
    Compare différents schémas de pondération.
    
    Args:
        returns: DataFrame de rendements
        reference_date: Date de référence
    
    Returns:
        Dict avec {scheme_name: weights_series}
    
    Example:
        >>> schemes = compare_weighting_schemes(returns_df)
        >>> for name, weights in schemes.items():
        ...     print(f"{name}: {weights.sum()}")
    """
    tickers = list(returns.columns)
    
    schemes = {
        'equal_weight': pd.Series(1.0 / len(tickers), index=tickers),
        'market_cap': calculate_market_cap_weights(tickers, reference_date),
        'inverse_vol': _inverse_vol_weights(returns),
        'min_variance': _min_variance_weights(returns)
    }
    
    logger.info("Weighting schemes comparison:")
    for name, weights in schemes.items():
        port_vol = np.sqrt(weights @ returns.cov() @ weights) * np.sqrt(252)
        logger.info(f"  {name}: vol={port_vol:.2%}, max_weight={weights.max():.2%}")
    
    return schemes


def _inverse_vol_weights(returns: pd.DataFrame) -> pd.Series:
    """Pondérations inverse-volatilité."""
    vols = returns.std()
    inv_vols = 1.0 / vols
    return inv_vols / inv_vols.sum()


def _min_variance_weights(returns: pd.DataFrame) -> pd.Series:
    """Pondérations minimum variance (Markowitz)."""
    cov = returns.cov()
    n = len(returns.columns)
    
    # Min variance: w = inv(Σ) @ 1 / (1' @ inv(Σ) @ 1)
    try:
        inv_cov = np.linalg.inv(cov.values)
        ones = np.ones(n)
        weights = inv_cov @ ones
        weights = weights / weights.sum()
        return pd.Series(weights, index=returns.columns)
    except np.linalg.LinAlgError:
        logger.warning("Singular covariance matrix, using equal weights")
        return pd.Series(1.0 / n, index=returns.columns)
