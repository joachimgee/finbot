"""
Script d'exemple pour démarrer rapidement avec FinBot.
Démontre les fonctionnalités de base une fois le module data implémenté.
"""
from financial_analyzer.config import API_KEYS, TRADING_CONFIG, CONSTANTS
from financial_analyzer.utils.helpers import get_logger, validate_ticker

logger = get_logger(__name__)


def main():
    """
    Script d'exemple pour tester l'installation.
    """
    logger.info("🚀 FinBot - Financial Market Analyzer")
    logger.info("=" * 50)
    
    # Afficher la configuration
    logger.info("\n📋 Configuration:")
    logger.info(f"  - API Keys configured: {bool(API_KEYS['financial_modeling_prep'])}")
    logger.info(f"  - Initial capital: ${TRADING_CONFIG['initial_capital']:,.2f}")
    logger.info(f"  - Commission rate: {TRADING_CONFIG['commission_rate']*100}%")
    logger.info(f"  - Risk-free rate: {CONSTANTS['risk_free_rate']*100}%")
    
    # Test de validation
    logger.info("\n✅ Testing utilities:")
    test_tickers = ["AAPL", "msft", " GOOGL "]
    for ticker in test_tickers:
        validated = validate_ticker(ticker)
        logger.info(f"  - Validated ticker: '{ticker}' -> '{validated}'")
    
    logger.info("\n✨ Installation successful!")
    logger.info("Next steps:")
    logger.info("  1. Edit .env file with your API keys")
    logger.info("  2. Run: make test")
    logger.info("  3. Start implementing the data module")
    logger.info("\n📚 See README.md for more information")


if __name__ == "__main__":
    main()
