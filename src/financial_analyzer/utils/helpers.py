"""
Fonctions utilitaires communes à tous les modules.
"""
import logging
import pickle
from pathlib import Path
from typing import Any, Callable
from functools import wraps
import pandas as pd
from datetime import datetime

from financial_analyzer.config import CACHE_DIR, LOG_LEVEL, CACHE_ENABLED

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def get_logger(name: str) -> logging.Logger:
    """
    Créer un logger avec le nom spécifié.
    
    Args:
        name: Nom du logger (généralement __name__)
    
    Returns:
        Logger configuré
    """
    return logging.getLogger(name)


def cache_result(cache_key: str, expiry_hours: int = 24):
    """
    Décorateur pour cacher les résultats de fonctions.
    
    Args:
        cache_key: Clé unique pour le cache
        expiry_hours: Durée de validité du cache en heures
    
    Example:
        >>> @cache_result("stock_data_{ticker}_{period}", expiry_hours=12)
        >>> def get_stock_data(ticker: str, period: str):
        >>>     # ... fetch data ...
        >>>     return data
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED:
                return func(*args, **kwargs)
            
            # Créer la clé de cache avec les arguments
            formatted_key = cache_key.format(*args, **kwargs)
            cache_file = CACHE_DIR / f"{formatted_key}.pkl"
            
            # Vérifier si le cache existe et est valide
            if cache_file.exists():
                file_age_hours = (datetime.now() - datetime.fromtimestamp(
                    cache_file.stat().st_mtime
                )).total_seconds() / 3600
                
                if file_age_hours < expiry_hours:
                    logger = get_logger(__name__)
                    logger.info(f"Loading from cache: {formatted_key}")
                    with open(cache_file, 'rb') as f:
                        return pickle.load(f)
            
            # Exécuter la fonction et cacher le résultat
            result = func(*args, **kwargs)
            
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
            
            return result
        
        return wrapper
    return decorator


def validate_ticker(ticker: str) -> str:
    """
    Valider et nettoyer un ticker symbol.
    
    Args:
        ticker: Ticker symbol
    
    Returns:
        Ticker nettoyé en majuscules
    
    Raises:
        ValueError: Si ticker invalide
    """
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Ticker must be a non-empty string")
    
    ticker = ticker.strip().upper()
    
    if not ticker.isalnum() and '.' not in ticker:
        raise ValueError(f"Invalid ticker format: {ticker}")
    
    return ticker


def validate_date(date_str: str) -> str:
    """
    Valider un format de date.
    
    Args:
        date_str: Date au format 'YYYY-MM-DD'
    
    Returns:
        Date validée
    
    Raises:
        ValueError: Si format invalide
    """
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use 'YYYY-MM-DD'")


def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculer les returns d'une série de prix.
    
    Args:
        prices: Série de prix
    
    Returns:
        Série de returns (pourcentage)
    """
    return prices.pct_change().dropna()


def calculate_volatility(returns: pd.Series, window: int = 20) -> pd.Series:
    """
    Calculer la volatilité glissante.
    
    Args:
        returns: Série de returns
        window: Fenêtre de calcul
    
    Returns:
        Série de volatilité annualisée
    """
    from financial_analyzer.config import CONSTANTS
    trading_days = CONSTANTS['trading_days_per_year']
    return returns.rolling(window=window).std() * (trading_days ** 0.5)


def log_execution_time(func: Callable) -> Callable:
    """
    Décorateur pour logger le temps d'exécution.
    
    Example:
        >>> @log_execution_time
        >>> def expensive_function():
        >>>     # ... code ...
        >>>     pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start = datetime.now()
        logger.info(f"Starting {func.__name__}")
        
        result = func(*args, **kwargs)
        
        duration = (datetime.now() - start).total_seconds()
        logger.info(f"Completed {func.__name__} in {duration:.2f}s")
        
        return result
    
    return wrapper
