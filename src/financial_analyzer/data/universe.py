"""
Universe Selection Module - FinanceDatabase Wrapper.

Ce module fournit une interface unifiée pour sélectionner des symboles financiers
à partir de FinanceDatabase (300K+ symboles : Equities, ETFs, Funds, Crypto, Indices).

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

import logging
from typing import Dict, List, Optional, Union

import pandas as pd
from financedatabase import Cryptos, ETFs, Equities, Funds, Indices

from financial_analyzer.utils.helpers import cache_result, get_logger

logger = get_logger(__name__)


# Constantes de validation
VALID_SECTORS = [
    'Technology',
    'Healthcare',
    'Financials',
    'Consumer Discretionary',
    'Communication Services',
    'Industrials',
    'Consumer Staples',
    'Energy',
    'Utilities',
    'Real Estate',
    'Materials',
    'Basic Materials',
]

VALID_MARKET_CAPS = ['Large Cap', 'Mid Cap', 'Small Cap', 'Mega Cap', 'Micro Cap', 'Nano Cap']

VALID_ETF_CATEGORIES = [
    'Equity',
    'Bond',
    'Commodity',
    'Currency',
    'Real Estate',
    'Alternative',
    'Multi-Asset',
]

VALID_FUND_TYPES = [
    'Equity',
    'Bond',
    'Balanced',
    'Money Market',
    'Index Fund',
    'Mutual Fund',
]


class UniverseSelector:
    """
    Wrapper FinanceDatabase pour sélection de symboles financiers.

    Cette classe fournit des méthodes pour sélectionner des actions, ETFs, fonds,
    cryptomonnaies et indices selon divers critères (secteur, industrie, market cap, etc.).

    Attributes:
        _equities_db: Instance FinanceDatabase.Equities
        _etfs_db: Instance FinanceDatabase.ETFs
        _funds_db: Instance FinanceDatabase.Funds
        _crypto_db: Instance FinanceDatabase.Cryptocurrencies
        _indices_db: Instance FinanceDatabase.Indices

    Example:
        >>> selector = UniverseSelector()
        >>> tech_stocks = selector.select_equities(sector='Technology', country='US')
        >>> len(tech_stocks)
        150
    """

    def __init__(self):
        """Initialise les instances FinanceDatabase."""
        logger.info("Initialisation UniverseSelector")
        try:
            self._equities_db = Equities()
            self._etfs_db = ETFs()
            self._funds_db = Funds()
            self._crypto_db = Cryptos()
            self._indices_db = Indices()
            logger.info("FinanceDatabase initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur initialisation FinanceDatabase: {e}")
            raise

    @cache_result("universe_equities", ttl=7200)
    def select_equities(
        self,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        market_cap: Optional[str] = None,
        country: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[str]:
        """
        Sélectionne actions selon critères GICS.

        Args:
            sector: Secteur GICS (ex: 'Technology', 'Healthcare')
            industry: Industrie GICS (ex: 'Software', 'Pharmaceuticals')
            market_cap: Capitalisation ('Large Cap', 'Mid Cap', 'Small Cap')
            country: Pays ISO 2-letter code (ex: 'US', 'FR')
            exchange: Bourse (ex: 'NASDAQ', 'NYSE')

        Returns:
            Liste de tickers (ex: ['AAPL', 'MSFT', 'GOOGL'])

        Raises:
            ValueError: Si sector ou market_cap invalide

        Example:
            >>> selector = UniverseSelector()
            >>> tech_stocks = selector.select_equities(
            ...     sector='Technology',
            ...     market_cap='Large Cap',
            ...     country='US'
            ... )
            >>> len(tech_stocks)
            150
        """
        logger.info(
            f"Sélection equities: sector={sector}, industry={industry}, "
            f"market_cap={market_cap}, country={country}, exchange={exchange}"
        )

        # Validation inputs
        if sector and sector not in VALID_SECTORS:
            raise ValueError(f"Sector invalide: {sector}. Valides: {VALID_SECTORS}")

        if market_cap and market_cap not in VALID_MARKET_CAPS:
            raise ValueError(f"Market cap invalide: {market_cap}. Valides: {VALID_MARKET_CAPS}")

        try:
            # Construction dictionnaire de filtres (only non-None values)
            filters = {}
            if sector:
                filters['sector'] = sector
            if industry:
                filters['industry'] = industry
            if market_cap:
                filters['market_cap'] = market_cap
            if country:
                filters['country'] = country
            if exchange:
                filters['exchange'] = exchange

            # Appel FinanceDatabase
            result = self._equities_db.select(**filters) if filters else self._equities_db.select()

            # Extraction des tickers (index du DataFrame)
            tickers = result.index.tolist() if isinstance(result, pd.DataFrame) else []

            logger.info(f"Trouvé {len(tickers)} equities correspondant aux critères")
            return tickers

        except Exception as e:
            logger.error(f"Erreur sélection equities: {e}")
            return []

    @cache_result(ttl=7200)
    def select_etfs(
        self,
        category: Optional[str] = None,
        family: Optional[str] = None,
    ) -> List[str]:
        """
        Sélectionne ETFs selon critères.

        Args:
            category: Catégorie ETF (ex: 'Equity', 'Bond', 'Commodity')
            family: Famille (ex: 'iShares', 'Vanguard', 'SPDR')

        Returns:
            Liste de tickers ETF (ex: ['SPY', 'QQQ', 'IWM'])

        Raises:
            ValueError: Si category invalide

        Example:
            >>> selector = UniverseSelector()
            >>> equity_etfs = selector.select_etfs(category='Equity', family='Vanguard')
            >>> 'VOO' in equity_etfs
            True
        """
        logger.info(f"Sélection ETFs: category={category}, family={family}")

        # Validation inputs
        if category and category not in VALID_ETF_CATEGORIES:
            raise ValueError(f"Category invalide: {category}. Valides: {VALID_ETF_CATEGORIES}")

        try:
            # Construction dictionnaire de filtres
            filters = {}
            if category:
                filters['category'] = category
            if family:
                filters['family'] = family

            # Appel FinanceDatabase
            result = self._etfs_db.select(**filters) if filters else self._etfs_db.select()

            # Extraction des tickers
            tickers = result.index.tolist() if isinstance(result, pd.DataFrame) else []

            logger.info(f"Trouvé {len(tickers)} ETFs correspondant aux critères")
            return tickers

        except Exception as e:
            logger.error(f"Erreur sélection ETFs: {e}")
            return []

    @cache_result(ttl=7200)
    def select_funds(
        self,
        fund_type: Optional[str] = None,
        family: Optional[str] = None,
    ) -> List[str]:
        """
        Sélectionne fonds mutuels.

        Args:
            fund_type: Type de fonds (ex: 'Equity', 'Bond', 'Balanced', 'Index Fund')
            family: Famille (ex: 'Fidelity', 'Vanguard', 'T. Rowe Price')

        Returns:
            Liste de tickers fonds (ex: ['VFIAX', 'FXAIX', 'SWPPX'])

        Raises:
            ValueError: Si fund_type invalide

        Example:
            >>> selector = UniverseSelector()
            >>> index_funds = selector.select_funds(fund_type='Index Fund', family='Vanguard')
            >>> 'VFIAX' in index_funds
            True
        """
        logger.info(f"Sélection Funds: fund_type={fund_type}, family={family}")

        # Validation inputs
        if fund_type and fund_type not in VALID_FUND_TYPES:
            raise ValueError(f"Fund type invalide: {fund_type}. Valides: {VALID_FUND_TYPES}")

        try:
            # Construction dictionnaire de filtres
            filters = {}
            if fund_type:
                filters['category'] = fund_type  # FinanceDatabase uses 'category' for funds
            if family:
                filters['family'] = family

            # Appel FinanceDatabase
            result = self._funds_db.select(**filters) if filters else self._funds_db.select()

            # Extraction des tickers
            tickers = result.index.tolist() if isinstance(result, pd.DataFrame) else []

            logger.info(f"Trouvé {len(tickers)} fonds correspondant aux critères")
            return tickers

        except Exception as e:
            logger.error(f"Erreur sélection fonds: {e}")
            return []

    @cache_result(ttl=7200)
    def select_crypto(
        self,
        exchange: Optional[str] = None,
    ) -> List[str]:
        """
        Sélectionne cryptomonnaies.

        Args:
            exchange: Exchange (ex: 'Binance', 'Coinbase', 'Kraken')

        Returns:
            Liste de symboles crypto (ex: ['BTC-USD', 'ETH-USD', 'BNB-USD'])

        Example:
            >>> selector = UniverseSelector()
            >>> cryptos = selector.select_crypto()
            >>> 'BTC-USD' in cryptos or 'BTC' in cryptos
            True
        """
        logger.info(f"Sélection Crypto: exchange={exchange}")

        try:
            # Construction dictionnaire de filtres
            filters = {}
            if exchange:
                filters['exchange'] = exchange

            # Appel FinanceDatabase
            result = self._crypto_db.select(**filters) if filters else self._crypto_db.select()

            # Extraction des symboles
            symbols = result.index.tolist() if isinstance(result, pd.DataFrame) else []

            logger.info(f"Trouvé {len(symbols)} cryptomonnaies correspondant aux critères")
            return symbols

        except Exception as e:
            logger.error(f"Erreur sélection crypto: {e}")
            return []

    @cache_result(ttl=7200)
    def select_indices(
        self,
        market: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[str]:
        """
        Sélectionne indices boursiers.

        Args:
            market: Marché (ex: 'US', 'Europe', 'Asia')
            region: Région géographique (ex: 'North America', 'Europe', 'Asia-Pacific')

        Returns:
            Liste de symboles d'indices (ex: ['^GSPC', '^DJI', '^IXIC'])

        Example:
            >>> selector = UniverseSelector()
            >>> us_indices = selector.select_indices(market='US')
            >>> '^GSPC' in us_indices or 'SPX' in us_indices
            True
        """
        logger.info(f"Sélection Indices: market={market}, region={region}")

        try:
            # Construction dictionnaire de filtres
            filters = {}
            if market:
                filters['market'] = market
            if region:
                filters['region'] = region

            # Appel FinanceDatabase
            result = self._indices_db.select(**filters) if filters else self._indices_db.select()

            # Extraction des symboles
            symbols = result.index.tolist() if isinstance(result, pd.DataFrame) else []

            logger.info(f"Trouvé {len(symbols)} indices correspondant aux critères")
            return symbols

        except Exception as e:
            logger.error(f"Erreur sélection indices: {e}")
            return []

    def get_metadata(
        self,
        tickers: Union[str, List[str]],
        asset_type: str = 'equities',
    ) -> pd.DataFrame:
        """
        Récupère métadonnées pour liste de tickers.

        Args:
            tickers: Ticker unique ou liste de tickers
            asset_type: Type d'actif ('equities', 'etfs', 'funds', 'crypto', 'indices')

        Returns:
            DataFrame avec colonnes disponibles selon asset_type:
            - symbol (index)
            - name
            - sector (equities)
            - industry (equities)
            - market_cap (equities)
            - country
            - exchange
            - currency
            - summary
            Et autres métadonnées selon disponibilité

        Raises:
            ValueError: Si asset_type invalide

        Example:
            >>> selector = UniverseSelector()
            >>> metadata = selector.get_metadata(['AAPL', 'MSFT', 'GOOGL'])
            >>> metadata[['symbol', 'name', 'sector']].head()
               symbol              name         sector
            0   AAPL         Apple Inc.     Technology
            1   MSFT  Microsoft Corp.     Technology
            2  GOOGL     Alphabet Inc.     Technology
        """
        logger.info(f"Récupération métadonnées pour {tickers} (type: {asset_type})")

        # Conversion ticker unique en liste
        if isinstance(tickers, str):
            tickers = [tickers]

        # Validation asset_type
        valid_types = ['equities', 'etfs', 'funds', 'crypto', 'indices']
        if asset_type not in valid_types:
            raise ValueError(f"Asset type invalide: {asset_type}. Valides: {valid_types}")

        try:
            # Sélection de la DB appropriée
            db_map = {
                'equities': self._equities_db,
                'etfs': self._etfs_db,
                'funds': self._funds_db,
                'crypto': self._crypto_db,
                'indices': self._indices_db,
            }
            db = db_map[asset_type]

            # Récupération des données complètes
            all_data = db.select()

            # Filtrage des tickers demandés
            metadata = all_data.loc[all_data.index.isin(tickers)]

            # Gérer différents formats d'index
            if metadata.index.name and metadata.index.name not in metadata.columns:
                metadata = metadata.reset_index()
                metadata = metadata.rename(columns={metadata.columns[0]: 'symbol'})
            elif 'index' in metadata.columns:
                metadata = metadata.rename(columns={'index': 'symbol'})
            elif 'symbol' not in metadata.columns:
                # Si pas de colonne symbol après reset, l'ajouter depuis l'index
                metadata = metadata.reset_index()
                if 'index' in metadata.columns:
                    metadata = metadata.rename(columns={'index': 'symbol'})
                elif metadata.index.name:
                    metadata = metadata.reset_index()
                    metadata = metadata.rename(columns={metadata.columns[0]: 'symbol'})

            logger.info(f"Métadonnées récupérées pour {len(metadata)} symboles")
            return metadata

        except Exception as e:
            logger.error(f"Erreur récupération métadonnées: {e}")
            # Retourner DataFrame vide avec colonnes de base
            return pd.DataFrame(columns=['symbol', 'name'])

    def get_all_sectors(self) -> List[str]:
        """
        Retourne la liste de tous les secteurs GICS disponibles.

        Returns:
            Liste de secteurs GICS

        Example:
            >>> selector = UniverseSelector()
            >>> sectors = selector.get_all_sectors()
            >>> 'Technology' in sectors
            True
        """
        return VALID_SECTORS.copy()

    def get_all_market_caps(self) -> List[str]:
        """
        Retourne la liste de toutes les catégories de market cap.

        Returns:
            Liste de market cap categories

        Example:
            >>> selector = UniverseSelector()
            >>> caps = selector.get_all_market_caps()
            >>> 'Large Cap' in caps
            True
        """
        return VALID_MARKET_CAPS.copy()

    def get_statistics(self) -> Dict[str, int]:
        """
        Retourne statistiques sur la base de données FinanceDatabase.

        Returns:
            Dictionnaire avec nombre d'actifs par type

        Example:
            >>> selector = UniverseSelector()
            >>> stats = selector.get_statistics()
            >>> stats['equities'] > 10000
            True
        """
        logger.info("Calcul statistiques FinanceDatabase")
        try:
            stats = {
                'equities': len(self._equities_db.select()),
                'etfs': len(self._etfs_db.select()),
                'funds': len(self._funds_db.select()),
                'crypto': len(self._crypto_db.select()),
                'indices': len(self._indices_db.select()),
            }
            stats['total'] = sum(stats.values())
            logger.info(f"Statistiques: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Erreur calcul statistiques: {e}")
            return {
                'equities': 0,
                'etfs': 0,
                'funds': 0,
                'crypto': 0,
                'indices': 0,
                'total': 0,
            }
