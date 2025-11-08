"""
Fundamental Screener (MVP).

Phase 5.6 will integrate FinanceToolkit to apply real filters.
For now, this MVP returns all tickers and logs a warning.

Supported criteria (planned):
- pe_min, pe_max
- roe_min
- debt_equity_max
- dividend_yield_min

Example
-------
>>> fs = FundamentalScreener()
>>> fs.screen(["AAPL", "MSFT"], {"pe_min": 5, "pe_max": 30})
['AAPL', 'MSFT']
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FundamentalScreener:
    """MVP fundamental screener that returns all input tickers.

    Notes
    -----
    - Integration with FinanceToolkit will be added in Phase 5.6.
    - Current behavior: log a warning and return the original tickers.
    """

    def __init__(self) -> None:
        logger.info("FundamentalScreener initialized (MVP mode)")

    def screen(self, tickers: Iterable[str], criteria: Optional[Dict[str, float]] = None) -> List[str]:
        """Return tickers unchanged (no filtering in MVP).

        Args:
            tickers: Iterable of ticker symbols.
            criteria: Screening criteria (ignored in MVP). Supported keys (planned):
                'pe_min', 'pe_max', 'roe_min', 'debt_equity_max', 'dividend_yield_min'.

        Returns:
            List of tickers (same as input order).

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
            "FundamentalScreener not yet integrated with FinanceToolkit (MVP). "
            "Returning all tickers without filtering."
        )
        # TODO(Phase 5.6): Integrate FinanceToolkit ratios to filter by criteria
        _ = criteria  # explicitly unused in MVP
        return result


__all__ = ["FundamentalScreener"]
