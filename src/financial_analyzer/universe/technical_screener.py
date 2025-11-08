"""
Technical Screener (MVP).

Phase 5.6 will integrate real price data (e.g., yfinance / internal market data)
to compute technical indicators. Current MVP returns all tickers untouched.

Supported criteria (planned):
- above_sma200: bool
- rsi_min, rsi_max: floats
- adx_max: float

Example
-------
>>> ts = TechnicalScreener()
>>> ts.screen(["AAPL", "MSFT"], {"rsi_min": 30, "rsi_max": 70})
['AAPL', 'MSFT']
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class TechnicalScreener:
    """MVP technical screener that returns all input tickers.

    Notes
    -----
    - Phase 5.6 will provide indicator-based filtering.
    - Current implementation logs a warning about missing integration.
    """

    def __init__(self) -> None:
        logger.info("TechnicalScreener initialized (MVP mode)")

    def screen(self, tickers: Iterable[str], criteria: Optional[Dict[str, float]] = None) -> List[str]:
        """Return tickers unchanged (no technical filtering in MVP).

        Args:
            tickers: Iterable of ticker symbols.
            criteria: Planned criteria dict (ignored in MVP). Supported keys (planned):
                'above_sma200', 'rsi_min', 'rsi_max', 'adx_max'.

        Returns:
            List[str]: Original tickers as list.

        Notes:
            Logs a warning indicating the lack of integration.
        """
        if tickers is None:
            return []

        try:
            result = list(tickers)
        except Exception as e:
            logger.error(f"Invalid tickers iterable: {e}")
            return []

        logger.warning(
            "TechnicalScreener not yet integrated with price data (MVP). "
            "Returning all tickers without filtering."
        )
        # TODO(Phase 5.6): Integrate price data + TA indicators
        _ = criteria  # explicitly unused in MVP
        return result


__all__ = ["TechnicalScreener"]
