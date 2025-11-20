"""
Market universe selection utilities.

This module provides a MarketSelector that leverages the existing
UniverseSelector (FinanceDatabase wrapper) to:
- fetch an initial equity universe by sector and country
- retrieve metadata for the tickers
- parse textual market cap strings (e.g., "$2.5T", "1.3B", "250M", "120K")
- filter by minimum market cap (USD) and volume (USD)
- sort by market cap descending and return the top N assets

Notes
-----
- All external calls are wrapped with try/except and logged.
- No network access is performed in tests; tests mock UniverseSelector.

Example
-------
>>> from financial_analyzer.universe.market_selector import MarketSelector
>>> ms = MarketSelector()
>>> tickers = ms.get_universe(
...     sector="Technology", country="US", n_assets=50,
...     min_marketcap_usd=1e9, min_volume_usd=5e6
... )
>>> isinstance(tickers, list)
True
"""

from __future__ import annotations

from typing import List, Optional, Union
import logging
import re

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.universe.selector import UniverseSelector

logger = get_logger(__name__)


class MarketSelector:
    """
    Select a liquid, large-cap equity universe using FinanceDatabase metadata.

    This class reuses the existing UniverseSelector to obtain tickers and
    metadata, then applies numeric filters and sorting.

    Attributes
    ----------
    universe_selector: UniverseSelector
        The data-layer selector to retrieve tickers and metadata.
    """

    def __init__(self, universe_selector: Optional[UniverseSelector] = None) -> None:
        """Initialize MarketSelector.

        Args:
            universe_selector: Optional UniverseSelector instance. If None,
                a default instance is created.
        """
        self.universe_selector = universe_selector or UniverseSelector()
        logger.info("MarketSelector initialized")

    def get_universe(
        self,
        sector: Optional[str],
        country: Optional[str],
        n_assets: int = 50,
        min_marketcap_usd: float = 1e9,
        min_volume_usd: float = 5e6,
    ) -> List[str]:
        """
        Build an equity universe filtered by size and liquidity.

        Args:
            sector: GICS sector filter (e.g., "Technology"). If None, no sector filter.
            country: Country code (e.g., "US"). If None, no country filter.
            n_assets: Maximum number of assets to return (sorted by market cap desc).
            min_marketcap_usd: Minimum market capitalization in USD.
            min_volume_usd: Minimum average trading volume in USD.

        Returns:
            List of ticker symbols meeting the filters, sorted by market cap desc.

        Raises:
            ValueError: If n_assets <= 0 or thresholds are negative.
        """
        if n_assets <= 0:
            raise ValueError("n_assets must be > 0")
        if min_marketcap_usd < 0 or min_volume_usd < 0:
            raise ValueError("min_marketcap_usd and min_volume_usd must be >= 0")

        # Step 1: use UniverseSelector to get tickers
        try:
            tickers = self.universe_selector.select_equities(
                sector=sector, country=country
            )
        except Exception as e:
            logger.error(f"Universe selection failed: {e}")
            return []

        if not tickers:
            logger.warning("No tickers returned by UniverseSelector")
            return []

        # Step 2: get metadata
        try:
            md = self.universe_selector.get_metadata(tickers, asset_type="equities")
        except Exception as e:
            logger.error(f"Metadata fetch failed: {e}")
            return []

        if md is None or md.empty:
            logger.warning("Empty metadata; cannot build universe")
            return []

        # Ensure a 'symbol' column exists
        if 'symbol' not in md.columns:
            # Fall back to index if present
            md = md.copy()
            md['symbol'] = md.index.astype(str)

        # Step 3: derive numeric market_cap_usd and volume_usd
        md = md.copy()
        md['market_cap_usd_num'] = _coerce_numeric_series(
            md, preferred_cols=['market_cap_usd', 'market_cap', 'marketcap', 'market_capitalization']
        )
        md['volume_usd_num'] = _coerce_numeric_series(
            md, preferred_cols=['volume_usd', 'volume', 'avg_volume_usd']
        )

        # Step 4: filter by thresholds
        filtered = md[
            (md['market_cap_usd_num'] >= float(min_marketcap_usd))
            & (md['volume_usd_num'] >= float(min_volume_usd))
        ]

        if filtered.empty:
            logger.warning("No assets meet the market cap/volume thresholds")
            return []

        # Step 5: sort by market cap desc and return top N symbols
        filtered = filtered.sort_values('market_cap_usd_num', ascending=False)
        top = filtered.head(n_assets)
        result = top['symbol'].astype(str).tolist()

        logger.info(
            f"Universe built: total={len(tickers)}, kept={len(result)}, "
            f"min_mcap={min_marketcap_usd}, min_vol={min_volume_usd}"
        )
        return result

    def select_by_fundamental_criteria(
        self,
        n_assets: int = 20,
        sectors: Optional[List[str]] = None,
        country: str = "United States"
    ) -> List[str]:
        """
        Select universe using FinanceDatabase with NO market cap restriction.
        
        This method integrates FinanceDatabase.Equities() for realistic
        universe selection with proper sector mapping and fallback.
        
        Args:
            n_assets: Number of assets to return (default: 20 for diversification)
            sectors: List of sectors to filter (e.g., ['Technology', 'Healthcare'])
            country: Country filter (default: 'United States')
        
        Returns:
            List of ticker symbols (falls back to curated list if API fails)
        
        Example:
            >>> selector = MarketSelector()
            >>> tickers = selector.select_by_fundamental_criteria(
            ...     n_assets=20,
            ...     sectors=['Technology', 'Healthcare']
            ... )
            >>> len(tickers) <= 20
            True
        """
        try:
            # Import FinanceDatabase
            from financedatabase import Equities
            
            logger.info(f"Fetching {n_assets} equities from FinanceDatabase...")
            logger.info(f"Sectors: {sectors}, Country: {country}")
            
            # Sector mapping (user-friendly -> FinanceDatabase format)
            sector_mapping = {
                'Technology': 'Information Technology',
                'Healthcare': 'Health Care',
                'Finance': 'Financials',
                'Consumer': 'Consumer Discretionary',
                'Industrial': 'Industrials',
                'Energy': 'Energy',
                'Materials': 'Materials',
                'Utilities': 'Utilities',
                'Real Estate': 'Real Estate',
                'Communication': 'Communication Services'
            }
            
            # Initialize Equities
            equities_db = Equities()
            
            # Search with filters
            search_params = {'country': country}
            
            # Apply sector filtering
            if sectors:
                mapped_sectors = [sector_mapping.get(s, s) for s in sectors]
                logger.info(f"Mapped sectors: {mapped_sectors}")
                # Get equities for each sector and combine
                all_results = pd.DataFrame()
                for sector in mapped_sectors:
                    sector_data = equities_db.search(sector=sector, country=country)
                    if isinstance(sector_data, dict) and sector_data:
                        all_results = pd.concat([all_results, pd.DataFrame(sector_data).T])
            else:
                # No sector filter - get all equities for country
                result_data = equities_db.search(country=country)
                if isinstance(result_data, dict) and result_data:
                    all_results = pd.DataFrame(result_data).T
                else:
                    all_results = pd.DataFrame()
            
            if not all_results.empty:
                # Extract tickers from index or 'symbol' column
                if 'symbol' in all_results.columns:
                    tickers = all_results['symbol'].dropna().unique().tolist()
                else:
                    tickers = all_results.index.tolist()
                
                # Limit to n_assets
                tickers = tickers[:n_assets]
                
                logger.info(f"✅ FinanceDatabase returned {len(tickers)} tickers")
                logger.info(f"Sample: {tickers[:5]}")
                
                return tickers
            else:
                logger.warning("FinanceDatabase returned empty results, using fallback")
                return self._get_fallback_tickers(n_assets, sectors)
        
        except Exception as e:
            logger.warning(f"FinanceDatabase error: {e}, using fallback tickers")
            return self._get_fallback_tickers(n_assets, sectors)
    
    def _get_fallback_tickers(
        self,
        n_assets: int,
        sectors: Optional[List[str]] = None
    ) -> List[str]:
        """
        Fallback ticker list when FinanceDatabase unavailable.
        
        Returns curated list of liquid, diversified US equities.
        
        Args:
            n_assets: Number of tickers to return
            sectors: Sector filter (optional)
        
        Returns:
            List of ticker symbols
        """
        fallback_tickers = {
            'Technology': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'AMD', 'CRM'],
            'Healthcare': ['UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'PFE', 'BMY'],
            'Finance': ['BRK.B', 'JPM', 'V', 'MA', 'BAC', 'WFC', 'MS', 'GS', 'BLK', 'C'],
            'Consumer': ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW', 'TJX', 'BKNG'],
            'Industrial': ['UPS', 'HON', 'UNP', 'BA', 'CAT', 'RTX', 'GE', 'LMT', 'MMM', 'DE'],
            'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HAL'],
            'Materials': ['LIN', 'SHW', 'APD', 'ECL', 'DD', 'NEM', 'FCX', 'CTVA', 'DOW', 'ALB'],
            'Utilities': ['NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'SRE', 'PCG', 'XEL', 'ED'],
            'Real Estate': ['PLD', 'AMT', 'CCI', 'EQIX', 'PSA', 'SPG', 'O', 'WELL', 'DLR', 'AVB'],
            'Communication': ['GOOGL', 'META', 'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'TMUS', 'CHTR', 'EA']
        }
        
        if sectors:
            # Filter by requested sectors
            result = []
            for sector in sectors:
                if sector in fallback_tickers:
                    result.extend(fallback_tickers[sector])
            # Remove duplicates and limit
            result = list(dict.fromkeys(result))[:n_assets]
        else:
            # Return mix from all sectors
            result = []
            for ticker_list in fallback_tickers.values():
                result.extend(ticker_list[:2])  # 2 from each sector
            result = list(dict.fromkeys(result))[:n_assets]
        
        logger.info(f"📋 Using fallback tickers: {len(result)} assets")
        return result

    @staticmethod
    def _parse_market_cap(cap_str: Union[str, float, int, None]) -> float:
        """
        Parse a market cap or volume string with suffixes into a float USD value.

        Supported suffixes (case-insensitive):
        - T (trillion, 1e12)
        - B (billion, 1e9)
        - M (million, 1e6)
        - K (thousand, 1e3)

        The string may optionally include currency symbols (e.g., "$"),
        commas, and whitespace. Returns 0.0 for invalid/unknown values.

        Examples
        --------
        >>> MarketSelector._parse_market_cap("$2.5T")
        2500000000000.0
        >>> MarketSelector._parse_market_cap("1.2B")
        1200000000.0
        >>> MarketSelector._parse_market_cap("250M")
        250000000.0
        >>> MarketSelector._parse_market_cap("120K")
        120000.0
        >>> MarketSelector._parse_market_cap("123456789")
        123456789.0
        >>> MarketSelector._parse_market_cap(None)
        0.0
        """
        if cap_str is None:
            return 0.0
        if isinstance(cap_str, (int, float)):
            return float(cap_str)
        if not isinstance(cap_str, str):
            return 0.0

        s = cap_str.strip().upper().replace(',', '')
        # remove leading currency symbols
        s = re.sub(r"^[^0-9\.-]+", "", s)
        if s == "" or s in {"N/A", "NA", "NONE"}:
            return 0.0

        # Match number with optional decimal and optional suffix
        m = re.match(r"^([0-9]*\.?[0-9]+)\s*([TBMK])?$", s)
        if not m:
            # If pure number with other trailing text fails, try to extract number part
            m2 = re.search(r"([0-9]*\.?[0-9]+)", s)
            if not m2:
                return 0.0
            num = float(m2.group(1))
            return num

        num = float(m.group(1))
        suffix = m.group(2)
        mult = 1.0
        if suffix == 'T':
            mult = 1e12
        elif suffix == 'B':
            mult = 1e9
        elif suffix == 'M':
            mult = 1e6
        elif suffix == 'K':
            mult = 1e3
        return num * mult


def _coerce_numeric_series(df: pd.DataFrame, preferred_cols: List[str]) -> pd.Series:
    """Build a numeric series from the first available preferred column.

    If the selected column is numeric, return as float. If it's strings with
    suffixes, parse via MarketSelector._parse_market_cap. If none exist, return
    zeros with the DataFrame length.

    Args:
        df: Metadata DataFrame.
        preferred_cols: Column names to try in order of preference.

    Returns:
        pd.Series of dtype float with same length as df.
    """
    col = None
    for name in preferred_cols:
        if name in df.columns:
            col = name
            break
    if col is None:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    series = df[col]
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)

    # parse string values
    parsed = series.apply(MarketSelector._parse_market_cap)
    return parsed.astype(float)


__all__ = ["MarketSelector"]
