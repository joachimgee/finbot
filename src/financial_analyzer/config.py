"""
Configuration centralisée pour l'application.
Charge les variables d'environnement depuis .env

Module Configuration:
    - Gère tous les chemins (BASE_DIR, DATA_DIR, CACHE_DIR, etc.)
    - Charge les variables d'environnement depuis .env
    - Configure les clés API, ML, trading
    - Crée automatiquement les dossiers nécessaires

Usage:
    >>> from financial_analyzer.config import API_KEYS, CACHE_DIR, LOG_LEVEL
    >>> print(API_KEYS['financial_modeling_prep'])
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict

from dotenv import load_dotenv


# Charger les variables d'environnement
load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# PATHS CONFIGURATION
# ============================================================================

BASE_DIR: Path = Path(__file__).parent.parent.parent
"""Répertoire racine du projet"""

DATA_DIR: Path = BASE_DIR / "data"
"""Répertoire des données"""

RAW_DATA_DIR: Path = DATA_DIR / "raw"
"""Répertoire des données brutes"""

PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
"""Répertoire des données traitées"""

CACHE_DIR: Path = DATA_DIR / "cache"
"""Répertoire du cache"""

LOGS_DIR: Path = BASE_DIR / "logs"
"""Répertoire des logs"""


# Créer les dossiers s'ils n'existent pas
for dir_path in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, CACHE_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


# ============================================================================
# API KEYS CONFIGURATION
# ============================================================================

API_KEYS: Dict[str, str] = {
    "financial_modeling_prep": os.getenv("FINANCIAL_MODELING_PREP_API_KEY", ""),
    "alpha_vantage": os.getenv("ALPHA_VANTAGE_API_KEY", ""),
    "news_api": os.getenv("NEWS_API_KEY", ""),
    "coingecko": os.getenv("COINGECKO_API_KEY", ""),
    "twitter": os.getenv("TWITTER_API_KEY", ""),
}
"""Configuration des clés API pour les différents services externes"""

# Vérifier les clés API manquantes
_missing_keys: List[str] = [k for k, v in API_KEYS.items() if not v]
if _missing_keys:
    logger.warning(
        f"Missing API keys: {', '.join(_missing_keys)}. "
        "Some features may not work. Check your .env file."
    )
    # Log détaillé pour chaque clé manquante
    for key in _missing_keys:
        logger.debug(f"API key '{key}' is not configured. Set {key.upper()}_API_KEY in .env")


# ============================================================================
# GENERAL CONFIGURATION
# ============================================================================

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
"""Environnement d'exécution (development, staging, production)"""

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
"""Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)"""

CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
"""Active/désactive le caching des résultats"""


# ============================================================================
# MACHINE LEARNING CONFIGURATION
# ============================================================================

@dataclass
class MLConfig:
    """Configuration des modèles ML.

    Notes:
        Utiliser cette dataclass plutôt que le dict ML_CONFIG pour les nouveaux
        développements. Le dict reste disponible pour compatibilité.
    """
    device: str = os.getenv("MODEL_DEVICE", "cpu")
    batch_size: int = int(os.getenv("BATCH_SIZE", "32"))
    finbert_model: str = os.getenv("FINBERT_MODEL", "ProsusAI/finbert")
    lookback_window: int = int(os.getenv("ML_LOOKBACK_WINDOW", "60"))
    forecast_horizon: int = int(os.getenv("ML_FORECAST_HORIZON", "5"))
    lstm_units: int = int(os.getenv("ML_LSTM_UNITS", "64"))


ML_CONFIG_D = MLConfig()
ML_CONFIG: Dict[str, Union[str, int]] = asdict(ML_CONFIG_D)
"""Compatibilité: dictionnaire reflétant ML_CONFIG_D (préférer ML_CONFIG_D)."""


# ============================================================================
# TRADING CONFIGURATION
# ============================================================================

@dataclass
class TradingConfig:
    """Configuration du trading et backtesting."""
    initial_capital: float = float(os.getenv("INITIAL_CAPITAL", "100000"))
    commission_rate: float = float(os.getenv("COMMISSION_RATE", "0.002"))
    sentiment_threshold: float = float(os.getenv("SENTIMENT_THRESHOLD", "0.3"))
    order_delta_threshold: float = float(os.getenv("ORDER_DELTA_THRESHOLD", "0.001"))


TRADING_CONFIG_D = TradingConfig()
TRADING_CONFIG: Dict[str, float] = {
    "initial_capital": TRADING_CONFIG_D.initial_capital,
    "commission_rate": TRADING_CONFIG_D.commission_rate,
    "sentiment_threshold": TRADING_CONFIG_D.sentiment_threshold,
    "order_delta_threshold": TRADING_CONFIG_D.order_delta_threshold,
}
"""Compatibilité: dictionnaire reflétant TRADING_CONFIG_D (préférer TRADING_CONFIG_D)."""


# ============================================================================
# CONSTANTS
# ============================================================================

CONSTANTS: Dict[str, Union[float, int, List[str]]] = {
    "risk_free_rate": 0.02,  # 2% taux sans risque annuel (US Treasury)
    "trading_days_per_year": 252,  # Nombre de jours de trading par an
    "supported_periods": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"],
}
"""
Constantes financières et trading.

Keys:
    risk_free_rate (float): Taux sans risque annuel (US Treasury, ~2%)
    trading_days_per_year (int): Nombre de jours de trading par an (252)
    supported_periods (List[str]): Périodes supportées pour données historiques
"""
