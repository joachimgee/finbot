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

ML_CONFIG: Dict[str, Union[str, int]] = {
    "device": os.getenv("MODEL_DEVICE", "cpu"),
    "batch_size": int(os.getenv("BATCH_SIZE", "32")),
    "finbert_model": "ProsusAI/finbert",
}
"""
Configuration des modèles ML.

Keys:
    device (str): Device pour exécution ('cpu', 'cuda', 'mps')
    batch_size (int): Taille des batches pour traitement
    finbert_model (str): Nom du modèle FinBERT sur HuggingFace
"""


# ============================================================================
# TRADING CONFIGURATION
# ============================================================================

TRADING_CONFIG: Dict[str, float] = {
    "initial_capital": float(os.getenv("INITIAL_CAPITAL", "10000")),
    "commission_rate": float(os.getenv("COMMISSION_RATE", "0.002")),
    "sentiment_threshold": float(os.getenv("SENTIMENT_THRESHOLD", "0.3")),
}
"""
Configuration du trading et backtesting.

Keys:
    initial_capital (float): Capital initial en dollars pour backtesting
    commission_rate (float): Commission par transaction (ex: 0.002 = 0.2%)
    sentiment_threshold (float): Seuil de sentiment pour signaux (-1 à 1)
"""


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
