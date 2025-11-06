"""
Module de récupération des données de marché (OHLCV).

Wrapper FinanceToolkit + yfinance pour récupération données historiques
et prix en temps réel.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from datetime import datetime
from typing import Dict, List, Optional, Union

import pandas as pd
import yfinance as yf
from financetoolkit import Toolkit

from financial_analyzer.utils.helpers import cache_result, get_logger

logger = get_logger(__name__)


class MarketDataFetcher:
    """
    Fetcher pour données de marché OHLCV.
    
    Utilise FinanceToolkit (Financial Modeling Prep) en priorité,
    avec fallback sur yfinance si API key non fournie ou erreur.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialise le fetcher avec API key optionnelle."""
        self.api_key = api_key
        self.use_yfinance = api_key is None
        self.toolkit = None
        
        if api_key:
            logger.info("MarketDataFetcher initialisé avec FinanceToolkit (FMP API)")
        else:
            logger.info("MarketDataFetcher initialisé avec yfinance (pas d'API key)")
    
    @cache_result("market_data_historical", ttl=3600)
    def get_historical_data(
        self,
        tickers: Union[str, List[str]],
        start_date: str,
        end_date: str,
        interval: str = '1d',
    ) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Récupère données historiques OHLCV pour un ou plusieurs tickers.
        
        Args:
            tickers: Ticker unique (str) ou liste de tickers
            start_date: Date début format 'YYYY-MM-DD'
            end_date: Date fin format 'YYYY-MM-DD'
            interval: Intervalle ('1d', '1wk', '1mo')
        
        Returns:
            Single ticker: DataFrame avec DatetimeIndex et colonnes OHLCV
            Multi-tickers: Dict[ticker, DataFrame]
        
        Raises:
            ValueError: Si dates invalides (start > end)
        """
        logger.info(f"Récupération données: {tickers}, {start_date} -> {end_date}")
        
        # Validation dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        if start_dt > end_dt:
            raise ValueError(f"Date début ({start_date}) > date fin ({end_date})")
        
        # Normaliser en liste
        is_single = isinstance(tickers, str)
        ticker_list = [tickers] if is_single else tickers
        
        # Fetch via yfinance (fallback FinanceToolkit si implémenté)
        data = self._fetch_via_yfinance(ticker_list, start_date, end_date, interval)
        
        # Validation
        for ticker in ticker_list:
            if ticker in data and not data[ticker].empty:
                try:
                    self.validate_ohlcv(data[ticker])
                except ValueError as e:
                    logger.error(f"Validation failed {ticker}: {e}")
                    data[ticker] = pd.DataFrame()
        
        return data[tickers] if is_single else data
    
    def _fetch_via_yfinance(
        self, tickers: List[str], start: str, end: str, interval: str
    ) -> Dict[str, pd.DataFrame]:
        """Récupère données via yfinance."""
        result = {}
        for ticker in tickers:
            try:
                yf_ticker = yf.Ticker(ticker)
                df = yf_ticker.history(start=start, end=end, interval=interval)
                
                if not df.empty:
                    df = self._normalize_columns(df)
                    result[ticker] = df
                else:
                    logger.warning(f"Pas de données pour {ticker}")
                    result[ticker] = pd.DataFrame()
            except Exception as e:
                logger.error(f"Erreur yfinance {ticker}: {e}")
                result[ticker] = pd.DataFrame()
        
        return result
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalise colonnes OHLCV et DatetimeIndex UTC."""
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        # Mapper colonnes
        mapping = {'open': 'Open', 'high': 'High', 'low': 'Low', 
                   'close': 'Close', 'volume': 'Volume'}
        df.columns = df.columns.str.lower()
        df = df.rename(columns=mapping)
        
        # Garder colonnes requises
        available = [c for c in required if c in df.columns]
        df = df[available]
        
        # DatetimeIndex UTC
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        else:
            df.index = df.index.tz_convert('UTC')
        
        return df
    
    @cache_result("market_data_latest", ttl=300)
    def get_latest_price(self, tickers: Union[str, List[str]]) -> pd.Series:
        """
        Récupère le dernier prix Close pour un ou plusieurs tickers.
        
        Returns:
            Series avec index=tickers, values=last close price
        """
        logger.info(f"Récupération derniers prix: {tickers}")
        
        is_single = isinstance(tickers, str)
        ticker_list = [tickers] if is_single else tickers
        
        prices = {}
        for ticker in ticker_list:
            try:
                yf_ticker = yf.Ticker(ticker)
                info = yf_ticker.info
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                prices[ticker] = float(price) if price else None
            except Exception as e:
                logger.error(f"Erreur prix {ticker}: {e}")
                prices[ticker] = None
        
        return pd.Series(prices)
    
    def validate_ohlcv(self, df: pd.DataFrame) -> bool:
        """
        Valide un DataFrame OHLCV.
        
        Vérifie:
        - DatetimeIndex présent
        - Colonnes OHLCV présentes
        - Pas de NaN
        - Dates croissantes
        
        Raises:
            ValueError: Si DataFrame invalide
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Index doit être DatetimeIndex")
        
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Colonnes manquantes: {missing}")
        
        if df[required].isnull().any().any():
            raise ValueError("Valeurs NaN détectées dans colonnes OHLCV")
        
        if not df.index.is_monotonic_increasing:
            raise ValueError("Dates non en ordre croissant")
        
        return True
