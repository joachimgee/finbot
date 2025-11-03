"""
Configuration centralisée pour l'application.
Charge les variables d'environnement depuis .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
LOGS_DIR = BASE_DIR / "logs"

# Créer les dossiers s'ils n'existent pas
for dir_path in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, CACHE_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# API Keys
API_KEYS = {
    "financial_modeling_prep": os.getenv("FINANCIAL_MODELING_PREP_API_KEY", ""),
    "alpha_vantage": os.getenv("ALPHA_VANTAGE_API_KEY", ""),
    "news_api": os.getenv("NEWS_API_KEY", ""),
}

# Configuration générale
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"

# Configuration ML
ML_CONFIG = {
    "device": os.getenv("MODEL_DEVICE", "cpu"),
    "batch_size": int(os.getenv("BATCH_SIZE", 32)),
    "finbert_model": "ProsusAI/finbert",
}

# Configuration Trading
TRADING_CONFIG = {
    "initial_capital": float(os.getenv("INITIAL_CAPITAL", 10000)),
    "commission_rate": float(os.getenv("COMMISSION_RATE", 0.002)),
    "sentiment_threshold": float(os.getenv("SENTIMENT_THRESHOLD", 0.3)),
}

# Constants
CONSTANTS = {
    "risk_free_rate": 0.02,  # 2% taux sans risque
    "trading_days_per_year": 252,
    "supported_periods": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"],
}
