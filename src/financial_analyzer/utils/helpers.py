"""
Fonctions utilitaires communes à tous les modules.

Ce module fournit des fonctions réutilisables pour:
- Logging centralisé
- Caching des résultats
- Validation des données
- Calculs financiers
- Mesure de performance

Usage:
    >>> from financial_analyzer.utils.helpers import get_logger, cache_result
    >>> logger = get_logger(__name__)
    >>> 
    >>> @cache_result("stock_{ticker}", expiry_hours=24)
    >>> def get_stock_data(ticker: str):
    >>>     return fetch_data(ticker)
"""

import logging
import pickle
from pathlib import Path
from typing import Any, Callable, TypeVar, Optional
from functools import wraps
import pandas as pd
from datetime import datetime

from financial_analyzer.config import CACHE_DIR, LOG_LEVEL, CACHE_ENABLED


# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# TypeVar pour typage des décorateurs
F = TypeVar('F', bound=Callable[..., Any])


def get_logger(name: str) -> logging.Logger:
    """
    Créer et retourner un logger avec le nom spécifié.
    
    Args:
        name: Nom du logger (généralement __name__)
    
    Returns:
        Logger configuré et prêt à l'usage
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Démarrage de l'application")
        >>> logger.error("Erreur critique", exc_info=True)
    """
    return logging.getLogger(name)


def cache_result(cache_key: str = "", expiry_hours: Optional[int] = None, ttl: Optional[int] = None) -> Callable[[F], F]:
    """
    Décorateur pour cacher les résultats de fonctions.
    
    Sauvegarde le résultat dans un fichier pickle avec expiration.
    Le caching peut être désactivé via config.CACHE_ENABLED.
    
    Args:
        cache_key: Clé unique pour le cache (support format strings, optionnel)
        expiry_hours: Durée de validité du cache en heures (défaut: 24h)
        ttl: Time-to-live en secondes (alternative à expiry_hours)
    
    Returns:
        Décorateur qui cache le résultat de la fonction
    
    Raises:
        ValueError: Si la clé de cache est invalide
    
    Example:
        >>> @cache_result("stock_data_{ticker}_{period}", expiry_hours=12)
        >>> def get_stock_data(ticker: str, period: str) -> pd.DataFrame:
        >>>     # ... fetch data ...
        >>>     return data
        >>> 
        >>> # Ou avec ttl en secondes
        >>> @cache_result(ttl=7200)  # 2 heures
        >>> def get_data():
        >>>     return expensive_operation()
        >>> 
        >>> # Premier appel: récupère et cache
        >>> data = get_stock_data("AAPL", "1y")
        >>> 
        >>> # Deuxième appel: charge depuis cache
        >>> data = get_stock_data("AAPL", "1y")
    """
    # Calculer expiry_hours depuis ttl si fourni
    if ttl is not None:
        expiry_hours = ttl / 3600
    elif expiry_hours is None:
        expiry_hours = 24
    
    # Générer cache_key par défaut si non fourni
    if not cache_key:
        cache_key = "cache_{func.__name__}"
    
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Évalue dynamiquement CACHE_ENABLED depuis le module de config
            try:
                from financial_analyzer import config as _config  # import local pour refléter monkeypatch
                cache_enabled = getattr(_config, 'CACHE_ENABLED', True)
                cache_dir = getattr(_config, 'CACHE_DIR', CACHE_DIR)
            except Exception:
                cache_enabled = True
                cache_dir = CACHE_DIR

            if not cache_enabled:
                return func(*args, **kwargs)
            
            logger = get_logger(func.__module__)
            
            try:
                # Créer la clé de cache avec les arguments
                formatted_key = cache_key.format(*args, **kwargs)
            except (IndexError, KeyError) as e:
                logger.warning(f"Cache key format error: {e}. Skipping cache.")
                return func(*args, **kwargs)
            
            cache_file = cache_dir / f"{formatted_key}.pkl"
            
            # Vérifier si le cache existe et est valide
            if cache_file.exists():
                try:
                    file_age_hours = (
                        datetime.now() - 
                        datetime.fromtimestamp(cache_file.stat().st_mtime)
                    ).total_seconds() / 3600
                    
                    if file_age_hours < expiry_hours:
                        logger.debug(f"Cache hit: {formatted_key}")
                        with open(cache_file, 'rb') as f:
                            return pickle.load(f)
                except Exception as e:
                    logger.warning(f"Cache load error: {e}. Recomputing.")
            
            # Exécuter la fonction et cacher le résultat
            result = func(*args, **kwargs)
            
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(cache_file, 'wb') as f:
                    pickle.dump(result, f)
                
                logger.debug(f"Cache saved: {formatted_key}")
            except Exception as e:
                logger.warning(f"Cache save error: {e}. Result still returned.")
            
            return result
        
        return wrapper
    
    return decorator


def validate_ticker(ticker: str) -> str:
    """
    Valider et nettoyer un ticker symbol.
    
    Accepte les formats: AAPL, BRK.B, 0001.HK
    
    Args:
        ticker: Ticker symbol à valider
    
    Returns:
        Ticker nettoyé en majuscules
    
    Raises:
        ValueError: Si ticker invalide (vide, format incorrect)
    
    Example:
        >>> validate_ticker("aapl")
        'AAPL'
        >>> validate_ticker("BRK.B")
        'BRK.B'
        >>> validate_ticker("")
        ValueError: Ticker must be a non-empty string
    """
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Ticker must be a non-empty string")
    
    ticker = ticker.strip().upper()
    
    # Accepter: alphanumériques et points (pour tickers comme BRK.B)
    if not all(c.isalnum() or c == '.' or c == '-' for c in ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
    
    return ticker


def validate_date(date_str: str) -> str:
    """
    Valider un format de date 'YYYY-MM-DD'.
    
    Args:
        date_str: Date au format 'YYYY-MM-DD'
    
    Returns:
        Date validée (même format)
    
    Raises:
        ValueError: Si format invalide
    
    Example:
        >>> validate_date("2023-01-15")
        '2023-01-15'
        >>> validate_date("15-01-2023")
        ValueError: Invalid date format...
    """
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        raise ValueError(
            f"Invalid date format: {date_str}. Use 'YYYY-MM-DD'"
        )


def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculer les returns (rendements) d'une série de prix.
    
    Utilise la formule: (P_t - P_t-1) / P_t-1
    
    Args:
        prices: pd.Series de prix (en ordre chronologique)
    
    Returns:
        pd.Series des returns en pourcentage (NaN pour le premier point)
    
    Example:
        >>> prices = pd.Series([100, 102, 101, 103])
        >>> returns = calculate_returns(prices)
        >>> print(returns)
        # 0      NaN
        # 1     0.02      (2% return)
        # 2    -0.0098    (-0.98% return)
        # 3     0.0198    (1.98% return)
    """
    return prices.pct_change().dropna()


def calculate_volatility(
    returns: pd.Series,
    window: int = 20
) -> pd.Series:
    """
    Calculer la volatilité glissante annualisée.
    
    Utilise la volatilité glissante (rolling std) annualisée par sqrt(252)
    (nombre de jours trading par an).
    
    Args:
        returns: pd.Series des returns (en décimal, ex: 0.02 = 2%)
        window: Fenêtre de calcul glissante en jours (défaut: 20)
    
    Returns:
        pd.Series de volatilité annualisée
    
    Example:
        >>> returns = pd.Series([0.01, 0.02, -0.01, 0.015])
        >>> volatility = calculate_volatility(returns, window=2)
        >>> print(volatility)
    """
    from financial_analyzer.config import CONSTANTS
    
    trading_days = CONSTANTS['trading_days_per_year']
    return returns.rolling(window=window).std() * (trading_days ** 0.5)


def log_execution_time(func: F) -> F:
    """
    Décorateur pour logger le temps d'exécution d'une fonction.
    
    Enregistre le démarrage, la fin et la durée d'exécution.
    
    Args:
        func: Fonction à décorer
    
    Returns:
        Fonction décorée avec timing
    
    Example:
        >>> @log_execution_time
        >>> def expensive_operation():
        >>>     time.sleep(2)
        >>>     return "done"
        >>> 
        >>> expensive_operation()
        # INFO - Starting expensive_operation
        # INFO - Completed expensive_operation in 2.00s
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        logger = get_logger(func.__module__)
        start = datetime.now()
        logger.info(f"Starting {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Completed {func.__name__} in {duration:.2f}s")
            return result
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(
                f"Failed {func.__name__} after {duration:.2f}s: {e}",
                exc_info=True
            )
            raise
    
    return wrapper
