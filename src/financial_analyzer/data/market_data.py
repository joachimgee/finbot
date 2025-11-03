"""
Module de récupération des données de marché financier.

Fournit une classe MarketDataFetcher qui combine:
- FinanceDatabase pour la recherche avancée de tickers (300k+ symboles)
- FinanceToolkit pour les données financières détaillées (150+ ratios)
- yfinance comme fallback (prix historiques gratuit)
- Alpha Vantage pour les données intraday temps réel

Usage:
    >>> from financial_analyzer.data.market_data import MarketDataFetcher
    >>> from financial_analyzer.config import API_KEYS
    >>> 
    >>> fetcher = MarketDataFetcher(api_key=API_KEYS['financial_modeling_prep'])
    >>> 
    >>> # Rechercher des tickers
    >>> tech = fetcher.search_tickers(sector="Technology", country="United States")
    >>> 
    >>> # Données historiques
    >>> prices = fetcher.get_historical_data(["AAPL", "MSFT"], period="1y")
    >>> 
    >>> # États financiers
    >>> statements = fetcher.get_financial_statements("AAPL")
"""

# 1. Stdlib
import os
from typing import List, Dict, Optional, Any, Union
import logging
from datetime import datetime

# 2. Données & Calculs
import pandas as pd
import numpy as np

# 3. Financier
from financedatabase import Equities
from financetoolkit import Toolkit
import yfinance as yf
from alpha_vantage.timeseries import TimeSeries

# 6. Projet local
from financial_analyzer.config import API_KEYS, CONSTANTS
from financial_analyzer.utils.helpers import get_logger, cache_result, validate_ticker


class MarketDataFetcher:
    """
    Classe pour la recherche avancée de tickers et la récupération de données de marché.

    Combine plusieurs sources de données:
    - FinanceDatabase: 300k+ tickers, filtrage par secteur/pays/industrie
    - FinanceToolkit: États financiers, 150+ ratios, métriques détaillées
    - yfinance: Fallback pour prix historiques (gratuit, fiable)
    - Alpha Vantage: Données intraday temps réel (1min à 60min)

    Attributes:
        api_key: Clé API FinanceToolkit (Financial Modeling Prep)
        cache_enabled: Active le cache local (défaut: True)
        alpha_vantage_key: Clé API Alpha Vantage (optionnel)
        logger: Logger structuré

    Raises:
        ValueError: Si api_key vide/invalide

    Example:
        >>> fetcher = MarketDataFetcher(api_key=API_KEYS['financial_modeling_prep'])
        >>> 
        >>> # Cas 1: Rechercher des tickers
        >>> df_tech = fetcher.search_tickers(
        ...     sector="Technology",
        ...     country="United States",
        ...     min_market_cap="Large Cap"
        ... )
        >>> print(f"Trouvé {len(df_tech)} tickers tech US")
        >>> 
        >>> # Cas 2: Données historiques (single ticker)
        >>> aapl = fetcher.get_historical_data("AAPL", period="1y")
        >>> print(f"AAPL: {aapl.shape[0]} jours de données")
        >>> 
        >>> # Cas 3: Données historiques (multi-tickers)
        >>> prices = fetcher.get_historical_data(
        ...     ["AAPL", "MSFT", "GOOGL"],
        ...     period="6mo"
        ... )
        >>> for ticker, df in prices.items():
        ...     print(f"{ticker}: {df.shape}")
        >>> 
        >>> # Cas 4: États financiers
        >>> statements = fetcher.get_financial_statements("AAPL")
        >>> revenue = statements['income_statement'].loc['Revenue']
        >>> print(revenue)
        >>> 
        >>> # Cas 5: Données intraday temps réel
        >>> intraday = fetcher.get_intraday_data("AAPL", interval="5min")
        >>> print(intraday['AAPL'].head())
    """

    def __init__(
        self,
        api_key: str,
        cache_enabled: bool = True,
        alpha_vantage_key: Optional[str] = None
    ) -> None:
        """
        Initialiser MarketDataFetcher.

        Args:
            api_key: Clé API FinanceToolkit (requis)
            cache_enabled: Activer cache local (défaut: True)
            alpha_vantage_key: Clé API Alpha Vantage (optionnel)

        Raises:
            ValueError: Si api_key vide/non-string
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key ne peut pas être vide ou invalide")

        self.api_key = api_key
        self.alpha_vantage_key = alpha_vantage_key or API_KEYS.get("alpha_vantage")
        self.cache_enabled = cache_enabled
        self.logger = get_logger(__name__)
        self.supported_periods = CONSTANTS["supported_periods"]

        self.logger.info(
            f"MarketDataFetcher initialisé | "
            f"Cache: {'✓' if cache_enabled else '✗'} | "
            f"AlphaVantage: {'✓' if self.alpha_vantage_key else '✗'}"
        )

    @cache_result("search_tickers_{sector}_{country}_{industry}_{min_market_cap}", expiry_hours=24)
    def search_tickers(
        self,
        sector: Optional[str] = None,
        country: Optional[str] = None,
        industry: Optional[str] = None,
        min_market_cap: str = "Large Cap"
    ) -> pd.DataFrame:
        """
        Rechercher avancée de tickers avec FinanceDatabase.

        Filtre par secteur, pays, industrie, market cap.
        Résultat en cache 24h.

        Args:
            sector: Secteur d'activité ('Technology', 'Finance', etc.)
            country: Pays ('United States', 'France', etc.)
            industry: Industrie spécifique ('Semiconductors', 'Banks', etc.)
            min_market_cap: Filtre capital ('Large Cap', 'Mid Cap', etc.)

        Returns:
            DataFrame avec colonnes:
            - symbol: Ticker symbol
            - name: Company name
            - country: Country of listing
            - market_cap: Market capitalization category
            - sector: Economic sector
            - industry_group: Industry group
            - industry: Industry classification
            - exchange: Stock exchange
            - currency: Trading currency
            - website: Company website
            - isin: ISIN code
            - cusip: CUSIP code
            (+ 10+ autres colonnes)

        Raises:
            ValueError: Si aucun ticker trouvé pour critères

        Example:
            >>> # Tech US Large Cap
            >>> tech = fetcher.search_tickers(
            ...     sector="Technology",
            ...     country="United States",
            ...     min_market_cap="Large Cap"
            ... )
            >>> print(f"{len(tech)} tickers trouvés")
            >>> print(tech[['symbol', 'name', 'market_cap']].head())
            >>> 
            >>> # Banques françaises
            >>> banks_fr = fetcher.search_tickers(
            ...     country="France",
            ...     industry="Banks"
            ... )
        """
        self.logger.info(
            f"Recherche tickers | sector={sector} | country={country} | "
            f"industry={industry} | min_market_cap={min_market_cap}"
        )

        try:
            equities = Equities()
            df = equities.select(
                sector=sector,
                country=country,
                industry=industry,
                market_cap=min_market_cap
            )

            if df.empty:
                msg = f"Aucun ticker trouvé pour: sector={sector}, country={country}, industry={industry}"
                self.logger.warning(msg)
                raise ValueError(msg)

            self.logger.info(f"✓ Recherche: {len(df)} tickers trouvés")
            self.logger.debug(f"Colonnes: {df.columns.tolist()}")

            return df

        except Exception as e:
            self.logger.error(f"✗ Erreur FinanceDatabase: {type(e).__name__}: {str(e)}")
            raise

    @cache_result("prices_{tickers}_{period}_{start_date}_{end_date}", expiry_hours=12)
    def get_historical_data(
        self,
        tickers: Union[str, List[str]],
        period: str = "1y",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Récupérer données OHLCV historiques pour 1+ tickers.

        Supporte cache 12h. Fallback auto yfinance si FinanceToolkit échoue.

        Args:
            tickers: Ticker(s):
                - str: "AAPL"
                - list: ["AAPL", "MSFT", "GOOGL"]
            period: Période prédéfinie ('1d', '5d', '1mo', '3mo', '6mo', '1y', etc.)
            start_date: Date début 'YYYY-MM-DD' (remplace period)
            end_date: Date fin 'YYYY-MM-DD'

        Returns:
            - Single ticker (str): DataFrame OHLCV
            - Multiple tickers (list): Dict[ticker, DataFrame]

            Colonnes: ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends']
            Index: DatetimeIndex UTC

        Raises:
            ValueError: Si ticker invalide, données non trouvées

        Example:
            >>> # Single ticker, 1 an
            >>> aapl = fetcher.get_historical_data("AAPL", period="1y")
            >>> print(aapl.shape)  # (252, 6)
            >>> print(aapl[['Close']].head())
            >>> 
            >>> # Multi-tickers, 6 mois
            >>> multi = fetcher.get_historical_data(
            ...     ["AAPL", "MSFT", "GOOGL"],
            ...     period="6mo"
            ... )
            >>> for ticker, df in multi.items():
            ...     print(f"{ticker}: {df.shape[0]} jours")
            >>> 
            >>> # Période personnalisée
            >>> custom = fetcher.get_historical_data(
            ...     "AAPL",
            ...     start_date="2023-01-01",
            ...     end_date="2023-12-31"
            ... )
        """
        # Normaliser input
        is_single = isinstance(tickers, str)
        tickers_list = [validate_ticker(tickers)] if is_single else [validate_ticker(t) for t in tickers]

        # Valider période
        if period not in self.supported_periods:
            self.logger.warning(f"Période '{period}' non supportée. Utilisation '1y' à la place.")
            period = "1y"

        self.logger.info(
            f"Récupération données | tickers={tickers_list} | period={period} | "
            f"start={start_date} | end={end_date}"
        )

        # ===== Tentative FinanceToolkit =====
        try:
            self.logger.debug(f"Tentative FinanceToolkit...")
            toolkit = Toolkit(tickers_list, api_key=self.api_key)
            df_toolkit = toolkit.get_historical_data(period=period)

            if df_toolkit.empty:
                raise ValueError("FinanceToolkit: DataFrame vide")

            self.logger.debug(f"✓ FinanceToolkit réussi: {df_toolkit.shape}")

            # Retourner approprié selon nombre de tickers
            if is_single:
                return df_toolkit
            else:
                # Multi-ticker: séparer
                result = {}
                for ticker in tickers_list:
                    if ticker in df_toolkit.columns:
                        result[ticker] = df_toolkit[ticker]
                        self.logger.debug(f"  {ticker}: {result[ticker].shape}")

                if not result:
                    raise ValueError(f"FinanceToolkit: Aucun ticker valide")

                return result

        except Exception as e:
            self.logger.warning(f"⚠ FinanceToolkit échoué: {type(e).__name__}: {str(e)}")
            self.logger.info("Fallback sur yfinance...")

        # ===== Fallback yfinance =====
        try:
            if start_date and end_date:
                self.logger.debug(f"yfinance: période custom {start_date} → {end_date}")
                df_yf = yf.download(
                    tickers_list,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    group_by="ticker" if not is_single else None
                )
            else:
                self.logger.debug(f"yfinance: période prédéfinie {period}")
                df_yf = yf.download(
                    tickers_list,
                    period=period,
                    progress=False,
                    group_by="ticker" if not is_single else None
                )

            if isinstance(df_yf, pd.DataFrame) and df_yf.empty:
                raise ValueError("yfinance: DataFrame vide")

            self.logger.debug(f"✓ yfinance réussi: {df_yf.shape if isinstance(df_yf, pd.DataFrame) else 'dict'}")

            # Retourner approprié
            if is_single:
                if isinstance(df_yf, dict):
                    return df_yf.get(tickers_list[0], pd.DataFrame())
                else:
                    return df_yf
            else:
                if isinstance(df_yf, dict):
                    result = {k: v for k, v in df_yf.items() if not v.empty}
                    for ticker, df in result.items():
                        self.logger.debug(f"  {ticker}: {df.shape}")
                    return result
                else:
                    # DataFrame multi-index → dict
                    result = {}
                    for ticker in tickers_list:
                        try:
                            result[ticker] = df_yf[ticker]
                            self.logger.debug(f"  {ticker}: {result[ticker].shape}")
                        except KeyError:
                            self.logger.debug(f"  {ticker}: pas de données")
                    return result if result else {}

        except Exception as e:
            self.logger.error(f"✗ yfinance aussi échoué: {type(e).__name__}: {str(e)}")
            raise ValueError(f"Impossible de récupérer données pour {tickers_list}")

    @cache_result("statements_{ticker}", expiry_hours=24)
    def get_financial_statements(
        self,
        ticker: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Récupérer états financiers complets pour un ticker.

        Inclut: income, balance, cash flow, 150+ ratios.
        Cache 24h.

        Args:
            ticker: Ticker symbol (ex: 'AAPL')

        Returns:
            Dict avec clés:
            - 'income_statement': Revenue, expenses, net income (annuel/trimestriel)
            - 'balance_sheet': Assets, liabilities, equity
            - 'cash_flow': Operating, investing, financing CF
            - 'ratios': Profitability, liquidity, solvency, efficiency (150+ ratios)

        Raises:
            ValueError: Si ticker invalide ou données non trouvées

        Example:
            >>> statements = fetcher.get_financial_statements("AAPL")
            >>> 
            >>> # Accéder aux données
            >>> revenue = statements['income_statement'].loc['Revenue']
            >>> print(revenue)
            >>> 
            >>> assets = statements['balance_sheet'].loc['Total Assets']
            >>> pe = statements['ratios'].loc['PE Ratio']
            >>> 
            >>> # Analyser structure
            >>> print("Income Statement shape:", statements['income_statement'].shape)
            >>> print("Balance Sheet shape:", statements['balance_sheet'].shape)
            >>> print("Ratios disponibles:", statements['ratios'].shape[0])
        """
        ticker = validate_ticker(ticker)

        self.logger.info(f"Récupération états financiers | ticker={ticker}")

        try:
            toolkit = Toolkit([ticker], api_key=self.api_key)

            income = toolkit.get_income_statement()
            balance = toolkit.get_balance_sheet_statement()
            cash = toolkit.get_cash_flow_statement()
            ratios = toolkit.ratios.collect_all_ratios()

            self.logger.debug(
                f"✓ États financiers récupérés | "
                f"Income {income.shape} | Balance {balance.shape} | "
                f"Cash {cash.shape} | Ratios {ratios.shape}"
            )

            return {
                "income_statement": income,
                "balance_sheet": balance,
                "cash_flow": cash,
                "ratios": ratios
            }

        except Exception as e:
            self.logger.error(f"✗ Erreur états financiers: {type(e).__name__}: {str(e)}")
            raise ValueError(f"Impossible de récupérer états financiers pour {ticker}")

    @cache_result("intraday_{tickers}_{interval}_{outputsize}", expiry_hours=1)
    def get_intraday_data(
        self,
        tickers: Union[str, List[str]],
        interval: str = "5min",
        outputsize: str = "compact"
    ) -> Dict[str, pd.DataFrame]:
        """
        Récupérer données intraday temps réel via Alpha Vantage.

        Support 1min à 60min. Cache 1h.

        Args:
            tickers: Ticker(s) ('AAPL' ou ['AAPL', 'MSFT'])
            interval: '1min', '5min', '15min', '30min', '60min'
            outputsize: 'compact' (100 points) ou 'full' (20k points)

        Returns:
            Dict[ticker, DataFrame] avec colonnes OHLCV
            Index: DatetimeIndex

        Raises:
            ValueError: Si Alpha Vantage key manquante ou données non trouvées

        Example:
            >>> # Single ticker, 5min
            >>> intra = fetcher.get_intraday_data("AAPL", interval="5min")
            >>> print(intra['AAPL'].head())
            >>> 
            >>> # Multi-tickers, 1min complet
            >>> multi = fetcher.get_intraday_data(
            ...     ["AAPL", "MSFT"],
            ...     interval="1min",
            ...     outputsize="full"
            ... )
            >>> for ticker, df in multi.items():
            ...     print(f"{ticker}: {df.shape}")
        """
        if not self.alpha_vantage_key:
            msg = "Alpha Vantage key manquante. Configurez ALPHA_VANTAGE_API_KEY dans .env"
            self.logger.error(msg)
            raise ValueError(msg)

        # Normaliser input
        tickers_list = [validate_ticker(tickers)] if isinstance(tickers, str) else [validate_ticker(t) for t in tickers]

        # Valider intervalle
        valid_intervals = ["1min", "5min", "15min", "30min", "60min"]
        if interval not in valid_intervals:
            self.logger.warning(f"Intervalle '{interval}' invalide. Utilisation '5min'.")
            interval = "5min"

        self.logger.info(f"Récupération intraday | tickers={tickers_list} | interval={interval} | outputsize={outputsize}")

        ts = TimeSeries(key=self.alpha_vantage_key, output_format='pandas')
        results = {}

        for ticker in tickers_list:
            try:
                self.logger.debug(f"Alpha Vantage: {ticker}...")
                data, meta = ts.get_intraday(symbol=ticker, interval=interval, outputsize=outputsize)

                if data.empty:
                    self.logger.warning(f"  {ticker}: aucune donnée")
                    continue

                self.logger.debug(f"  ✓ {ticker}: {data.shape}")
                results[ticker] = data

            except Exception as e:
                self.logger.warning(f"  ✗ {ticker} échoué: {type(e).__name__}: {str(e)}")

        if not results:
            raise ValueError(f"Aucune donnée intraday récupérée pour {tickers_list}")

        self.logger.info(f"✓ {len(results)}/{len(tickers_list)} tickers intraday")

        return results
