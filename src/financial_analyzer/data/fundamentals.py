"""
Module de récupération des données fondamentales.

Wrapper FinanceToolkit pour récupération de 150+ ratios financiers,
états financiers (income statement, balance sheet, cash flow).

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from typing import Dict, List, Optional, Union

import pandas as pd
from financetoolkit import Toolkit

from financial_analyzer.utils.helpers import cache_result, get_logger

logger = get_logger(__name__)


class FundamentalsProvider:
    """
    Provider pour données fondamentales (ratios, états financiers).

    Utilise FinanceToolkit (Financial Modeling Prep API) pour récupérer:
    - 150+ ratios financiers (PE, PB, ROE, Debt/Equity, etc.)
    - Income statement (Revenue, EBIT, Net Income, etc.)
    - Balance sheet (Assets, Liabilities, Equity, etc.)
    - Cash flow statement (Operating CF, Investing CF, Financing CF, etc.)

    Attributes:
        api_key: Clé API Financial Modeling Prep (obligatoire)
        toolkit: Instance FinanceToolkit

    Example:
        >>> provider = FundamentalsProvider(api_key="your_api_key")
        >>> ratios = provider.get_all_ratios('AAPL', period='quarterly', limit=4)
        >>> print(ratios.shape)
        (4, 150)  # 4 quarters × 150 ratios
    """

    def __init__(self, api_key: str):
        """
        Initialise le provider avec API key obligatoire.

        Args:
            api_key: Clé API Financial Modeling Prep (obligatoire)

        Raises:
            ValueError: Si api_key est None ou vide

        Example:
            >>> provider = FundamentalsProvider(api_key="your_key")
            >>> # ValueError si api_key None
            >>> provider = FundamentalsProvider(api_key=None)
            Traceback (most recent call last):
            ...
            ValueError: API key obligatoire pour FundamentalsProvider
        """
        if not api_key:
            raise ValueError("API key obligatoire pour FundamentalsProvider")

        self.api_key = api_key
        self.toolkit = None  # Sera initialisé par ticker dans les méthodes
        logger.info("FundamentalsProvider initialisé avec Financial Modeling Prep API")

    @cache_result("fundamentals_ratios", ttl=21600)  # 6 heures
    def get_all_ratios(
        self,
        tickers: Union[str, List[str]],
        period: str = 'quarterly',
        limit: int = 4,
    ) -> pd.DataFrame:
        """
        Récupère tous les ratios financiers (150+) pour un ou plusieurs tickers.

        Args:
            tickers: Ticker unique (str) ou liste de tickers
            period: 'annual' ou 'quarterly'
            limit: Nombre de périodes à récupérer

        Returns:
            DataFrame avec Multi-index (ticker × date) et colonnes ratios
            - Single ticker: Index=dates, Columns=ratios (150+)
            - Multi-tickers: MultiIndex(ticker, date), Columns=ratios

        Raises:
            ValueError: Si period invalide (pas 'annual' ou 'quarterly')

        Example:
            >>> provider = FundamentalsProvider(api_key="your_key")
            >>> # Single ticker
            >>> ratios = provider.get_all_ratios('AAPL', period='quarterly', limit=8)
            >>> print(ratios.columns[:5])
            Index(['PE_Ratio', 'PB_Ratio', 'PS_Ratio', 'ROE', 'ROA'], dtype='object')
            >>>
            >>> # Multi-tickers
            >>> ratios = provider.get_all_ratios(['AAPL', 'MSFT'], period='annual', limit=5)
            >>> print(ratios.index.names)
            ['ticker', 'date']
        """
        logger.info(
            f"Récupération ratios: tickers={tickers}, period={period}, limit={limit}"
        )

        # Validation period
        if period not in ['annual', 'quarterly']:
            raise ValueError(f"Period invalide: {period}. Doit être 'annual' ou 'quarterly'")

        # Normaliser tickers en liste
        is_single_ticker = isinstance(tickers, str)
        ticker_list = [tickers] if is_single_ticker else tickers

        # Récupérer ratios pour chaque ticker
        all_ratios = []
        for ticker in ticker_list:
            try:
                ratios_df = self._fetch_ratios_single_ticker(ticker, period, limit)
                if not ratios_df.empty:
                    ratios_df['ticker'] = ticker
                    all_ratios.append(ratios_df)
                else:
                    logger.warning(f"Pas de ratios pour {ticker}")
            except Exception as e:
                logger.error(f"Erreur récupération ratios {ticker}: {e}")

        # Combiner résultats
        if not all_ratios:
            logger.warning("Aucun ratio récupéré")
            return pd.DataFrame()

        combined = pd.concat(all_ratios, axis=0)

        # Format selon input
        if is_single_ticker:
            # Single ticker: enlever colonne 'ticker', index=dates
            combined = combined.drop(columns=['ticker'])
            logger.info(f"Récupéré {len(combined)} périodes × {len(combined.columns)} ratios")
            return combined
        else:
            # Multi-tickers: MultiIndex (ticker, date)
            combined = combined.set_index('ticker', append=True)
            combined = combined.reorder_levels(['ticker', combined.index.names[0]])
            logger.info(f"Récupéré {len(ticker_list)} tickers × {len(combined.columns)} ratios")
            return combined

    def _fetch_ratios_single_ticker(
        self,
        ticker: str,
        period: str,
        limit: int,
    ) -> pd.DataFrame:
        """Récupère ratios pour un seul ticker."""
        try:
            # Initialiser Toolkit pour ce ticker
            toolkit = Toolkit(tickers=ticker, api_key=self.api_key)

            # Récupérer ratios via FinanceToolkit
            # Note: get_financial_ratios() retourne un DataFrame
            ratios = toolkit.ratios.collect_financial_ratios(
                period=period,
                progress_bar=False,
            )

            # Limiter au nombre de périodes demandé
            if not ratios.empty:
                ratios = ratios.tail(limit)
                logger.debug(f"Récupéré {len(ratios)} périodes pour {ticker}")

            return ratios

        except Exception as e:
            logger.error(f"Erreur FinanceToolkit ratios {ticker}: {e}")
            return pd.DataFrame()

    @cache_result("fundamentals_income", ttl=21600)  # 6 heures
    def get_income_statement(
        self,
        tickers: Union[str, List[str]],
        period: str = 'quarterly',
        limit: int = 4,
    ) -> pd.DataFrame:
        """
        Récupère l'income statement pour un ou plusieurs tickers.

        Args:
            tickers: Ticker unique (str) ou liste de tickers
            period: 'annual' ou 'quarterly'
            limit: Nombre de périodes à récupérer

        Returns:
            DataFrame avec colonnes: Revenue, EBIT, Net Income, EPS, etc.
            - Single ticker: Index=dates
            - Multi-tickers: MultiIndex(ticker, date)

        Example:
            >>> provider = FundamentalsProvider(api_key="your_key")
            >>> income = provider.get_income_statement('AAPL', period='annual', limit=5)
            >>> print(income.columns[:5])
            Index(['Revenue', 'Cost_of_Revenue', 'Gross_Profit', 'Operating_Expenses', 'EBIT'], dtype='object')
        """
        logger.info(
            f"Récupération income statement: tickers={tickers}, period={period}, limit={limit}"
        )

        # Validation period
        if period not in ['annual', 'quarterly']:
            raise ValueError(f"Period invalide: {period}. Doit être 'annual' ou 'quarterly'")

        # Normaliser tickers en liste
        is_single_ticker = isinstance(tickers, str)
        ticker_list = [tickers] if is_single_ticker else tickers

        # Récupérer income statement pour chaque ticker
        all_statements = []
        for ticker in ticker_list:
            try:
                stmt_df = self._fetch_income_statement_single_ticker(ticker, period, limit)
                if not stmt_df.empty:
                    stmt_df['ticker'] = ticker
                    all_statements.append(stmt_df)
                else:
                    logger.warning(f"Pas d'income statement pour {ticker}")
            except Exception as e:
                logger.error(f"Erreur récupération income statement {ticker}: {e}")

        # Combiner résultats
        if not all_statements:
            logger.warning("Aucun income statement récupéré")
            return pd.DataFrame()

        combined = pd.concat(all_statements, axis=0)

        # Format selon input
        if is_single_ticker:
            combined = combined.drop(columns=['ticker'])
            logger.info(f"Récupéré {len(combined)} périodes × {len(combined.columns)} colonnes")
            return combined
        else:
            combined = combined.set_index('ticker', append=True)
            combined = combined.reorder_levels(['ticker', combined.index.names[0]])
            logger.info(f"Récupéré {len(ticker_list)} tickers")
            return combined

    def _fetch_income_statement_single_ticker(
        self,
        ticker: str,
        period: str,
        limit: int,
    ) -> pd.DataFrame:
        """Récupère income statement pour un seul ticker."""
        try:
            # Initialiser Toolkit pour ce ticker
            toolkit = Toolkit(tickers=ticker, api_key=self.api_key)

            # Récupérer income statement
            income = toolkit.get_income_statement(
                period=period,
                progress_bar=False,
            )

            # Limiter au nombre de périodes demandé
            if not income.empty:
                income = income.tail(limit)
                logger.debug(f"Récupéré {len(income)} périodes income statement pour {ticker}")

            return income

        except Exception as e:
            logger.error(f"Erreur FinanceToolkit income statement {ticker}: {e}")
            return pd.DataFrame()

    @cache_result("fundamentals_balance", ttl=21600)  # 6 heures
    def get_balance_sheet(
        self,
        tickers: Union[str, List[str]],
        period: str = 'quarterly',
        limit: int = 4,
    ) -> pd.DataFrame:
        """
        Récupère le balance sheet pour un ou plusieurs tickers.

        Args:
            tickers: Ticker unique (str) ou liste de tickers
            period: 'annual' ou 'quarterly'
            limit: Nombre de périodes à récupérer

        Returns:
            DataFrame avec colonnes: Assets, Liabilities, Equity, Cash, Debt, etc.
            - Single ticker: Index=dates
            - Multi-tickers: MultiIndex(ticker, date)

        Example:
            >>> provider = FundamentalsProvider(api_key="your_key")
            >>> balance = provider.get_balance_sheet('AAPL', period='quarterly', limit=4)
            >>> print(balance.columns[:5])
            Index(['Total_Assets', 'Total_Liabilities', 'Total_Equity', 'Cash', 'Debt'], dtype='object')
        """
        logger.info(
            f"Récupération balance sheet: tickers={tickers}, period={period}, limit={limit}"
        )

        # Validation period
        if period not in ['annual', 'quarterly']:
            raise ValueError(f"Period invalide: {period}. Doit être 'annual' ou 'quarterly'")

        # Normaliser tickers en liste
        is_single_ticker = isinstance(tickers, str)
        ticker_list = [tickers] if is_single_ticker else tickers

        # Récupérer balance sheet pour chaque ticker
        all_statements = []
        for ticker in ticker_list:
            try:
                stmt_df = self._fetch_balance_sheet_single_ticker(ticker, period, limit)
                if not stmt_df.empty:
                    stmt_df['ticker'] = ticker
                    all_statements.append(stmt_df)
                else:
                    logger.warning(f"Pas de balance sheet pour {ticker}")
            except Exception as e:
                logger.error(f"Erreur récupération balance sheet {ticker}: {e}")

        # Combiner résultats
        if not all_statements:
            logger.warning("Aucun balance sheet récupéré")
            return pd.DataFrame()

        combined = pd.concat(all_statements, axis=0)

        # Format selon input
        if is_single_ticker:
            combined = combined.drop(columns=['ticker'])
            logger.info(f"Récupéré {len(combined)} périodes × {len(combined.columns)} colonnes")
            return combined
        else:
            combined = combined.set_index('ticker', append=True)
            combined = combined.reorder_levels(['ticker', combined.index.names[0]])
            logger.info(f"Récupéré {len(ticker_list)} tickers")
            return combined

    def _fetch_balance_sheet_single_ticker(
        self,
        ticker: str,
        period: str,
        limit: int,
    ) -> pd.DataFrame:
        """Récupère balance sheet pour un seul ticker."""
        try:
            # Initialiser Toolkit pour ce ticker
            toolkit = Toolkit(tickers=ticker, api_key=self.api_key)

            # Récupérer balance sheet
            balance = toolkit.get_balance_sheet_statement(
                period=period,
                progress_bar=False,
            )

            # Limiter au nombre de périodes demandé
            if not balance.empty:
                balance = balance.tail(limit)
                logger.debug(f"Récupéré {len(balance)} périodes balance sheet pour {ticker}")

            return balance

        except Exception as e:
            logger.error(f"Erreur FinanceToolkit balance sheet {ticker}: {e}")
            return pd.DataFrame()

    @cache_result("fundamentals_cashflow", ttl=21600)  # 6 heures
    def get_cash_flow(
        self,
        tickers: Union[str, List[str]],
        period: str = 'quarterly',
        limit: int = 4,
    ) -> pd.DataFrame:
        """
        Récupère le cash flow statement pour un ou plusieurs tickers.

        Args:
            tickers: Ticker unique (str) ou liste de tickers
            period: 'annual' ou 'quarterly'
            limit: Nombre de périodes à récupérer

        Returns:
            DataFrame avec colonnes: Operating CF, Investing CF, Financing CF, Free CF, etc.
            - Single ticker: Index=dates
            - Multi-tickers: MultiIndex(ticker, date)

        Example:
            >>> provider = FundamentalsProvider(api_key="your_key")
            >>> cashflow = provider.get_cash_flow('AAPL', period='annual', limit=5)
            >>> print(cashflow.columns[:5])
            Index(['Operating_Cash_Flow', 'Investing_Cash_Flow', 'Financing_Cash_Flow', 'Free_Cash_Flow', 'CapEx'], dtype='object')
        """
        logger.info(
            f"Récupération cash flow: tickers={tickers}, period={period}, limit={limit}"
        )

        # Validation period
        if period not in ['annual', 'quarterly']:
            raise ValueError(f"Period invalide: {period}. Doit être 'annual' ou 'quarterly'")

        # Normaliser tickers en liste
        is_single_ticker = isinstance(tickers, str)
        ticker_list = [tickers] if is_single_ticker else tickers

        # Récupérer cash flow pour chaque ticker
        all_statements = []
        for ticker in ticker_list:
            try:
                stmt_df = self._fetch_cash_flow_single_ticker(ticker, period, limit)
                if not stmt_df.empty:
                    stmt_df['ticker'] = ticker
                    all_statements.append(stmt_df)
                else:
                    logger.warning(f"Pas de cash flow pour {ticker}")
            except Exception as e:
                logger.error(f"Erreur récupération cash flow {ticker}: {e}")

        # Combiner résultats
        if not all_statements:
            logger.warning("Aucun cash flow récupéré")
            return pd.DataFrame()

        combined = pd.concat(all_statements, axis=0)

        # Format selon input
        if is_single_ticker:
            combined = combined.drop(columns=['ticker'])
            logger.info(f"Récupéré {len(combined)} périodes × {len(combined.columns)} colonnes")
            return combined
        else:
            combined = combined.set_index('ticker', append=True)
            combined = combined.reorder_levels(['ticker', combined.index.names[0]])
            logger.info(f"Récupéré {len(ticker_list)} tickers")
            return combined

    def _fetch_cash_flow_single_ticker(
        self,
        ticker: str,
        period: str,
        limit: int,
    ) -> pd.DataFrame:
        """Récupère cash flow statement pour un seul ticker."""
        try:
            # Initialiser Toolkit pour ce ticker
            toolkit = Toolkit(tickers=ticker, api_key=self.api_key)

            # Récupérer cash flow statement
            cashflow = toolkit.get_cash_flow_statement(
                period=period,
                progress_bar=False,
            )

            # Limiter au nombre de périodes demandé
            if not cashflow.empty:
                cashflow = cashflow.tail(limit)
                logger.debug(f"Récupéré {len(cashflow)} périodes cash flow pour {ticker}")

            return cashflow

        except Exception as e:
            logger.error(f"Erreur FinanceToolkit cash flow {ticker}: {e}")
            return pd.DataFrame()
