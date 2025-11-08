# 🎯 PHASE 5.5 MODULE 3 - 3 SCREENERS PROMPT FOR COPILOT

## CONTEXT

Tu as déjà un **excellent `universe.py`** (9.2/10) avec UniverseSelector.

Nous ajoutons 3 **screeners complémentaires** pour Phase 5.5 Module 3 :
1. MarketSelector (top-N by market cap)
2. FundamentalScreener (P/E, ROE, Debt screens)
3. TechnicalScreener (SMA, RSI, trend screens)

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.5 MODULE 3 : UNIVERSE SCREENERS (3 FILES + TESTS)

Génère 3 fichiers + tests complets :

================================================================================
1. src/financial_analyzer/universe/market_selector.py (200 LOC)
================================================================================

"""
Market Selector - Top-N Universe by Market Cap.

Select top-N assets by market capitalization and liquidity for portfolio optimization.

Audit reference:
- AUDIT_FINANCEDATABASE.md (metadata extraction)
- Phase 5.5 architecture (universe selection patterns)

Example:
    >>> from financial_analyzer.universe import MarketSelector
    >>> market = MarketSelector()
    >>> universe = market.get_universe(
    ...     sector='Technology',
    ...     country='US',
    ...     n_assets=50,
    ...     min_marketcap_usd=1e9,
    ...     min_volume_usd=5e6
    ... )
    >>> len(universe)
    50
"""

Implement:

class MarketSelector:
    """
    Select top-N assets by market capitalization and liquidity.
    
    Process:
    1. Select universe via UniverseSelector (sector/country filters)
    2. Fetch metadata (market cap, volume, price)
    3. Filter by min market cap (default $1B)
    4. Filter by min daily volume (default $5M)
    5. Sort by market cap descending
    6. Return top N assets
    """
    
    def __init__(self, universe_selector=None):
        """Initialize MarketSelector."""
        pass
    
    def get_universe(
        self,
        sector: Optional[str] = None,
        country: str = 'US',
        n_assets: int = 50,
        min_marketcap_usd: float = 1e9,
        min_volume_usd: float = 5e6,
        market_cap_tier: Optional[str] = None
    ) -> List[str]:
        """
        Get top-N assets by market cap + liquidity.
        
        Returns:
            List of tickers (sorted by market cap descending)
        """
        # 1. Select base universe via UniverseSelector
        # 2. Get metadata via selector.get_metadata()
        # 3. Parse market cap strings to float (parse $1.5T → 1.5e12)
        # 4. Filter by min market cap
        # 5. Sort by market cap descending
        # 6. Return top N
        pass
    
    def _parse_market_cap(self, cap_str: str) -> float:
        """
        Parse market cap string to float.
        
        Examples:
        - '$2.5T' → 2.5e12
        - '$10.3B' → 10.3e9
        - '$500M' → 500e6
        
        Return:
            Market cap in USD
        """
        # Handle None/NaN
        # Remove '$' and commas
        # Map T/B/M/K to multipliers
        # Return float
        pass

================================================================================
2. src/financial_analyzer/universe/fundamental_screener.py (100 LOC)
================================================================================

"""
Fundamental Screener - Quality Filters.

Screen assets by fundamental metrics (P/E, ROE, Debt/Equity, Dividend Yield).

Note:
- Currently returns all tickers (no filtering)
- TODO: Integrate with FinanceToolkit in Phase 5.6 for real fundamental data
- TODO: Add yfinance fallback for key_ratios

Example:
    >>> from financial_analyzer.universe import FundamentalScreener
    >>> screener = FundamentalScreener()
    >>> quality_stocks = screener.screen(
    ...     tickers=['AAPL', 'MSFT', 'TSLA', 'AMZN'],
    ...     criteria={'pe_min': 10, 'pe_max': 30, 'roe_min': 0.15}
    ... )
"""

Implement:

class FundamentalScreener:
    """
    Screen assets by fundamental criteria.
    
    Criteria:
    - P/E ratio (10-30 reasonable range)
    - ROE > 15% (high-quality companies)
    - Debt/Equity < 1.5 (not overleveraged)
    - Dividend yield > 1% (optional income)
    
    Note:
    - MVP: Returns all tickers (no real filtering yet)
    - Integration with FinanceToolkit planned for Phase 5.6
    """
    
    def __init__(self):
        """Initialize FundamentalScreener."""
        pass
    
    def screen(
        self,
        tickers: List[str],
        criteria: Dict[str, float]
    ) -> List[str]:
        """
        Filter tickers by fundamental quality.
        
        Args:
            criteria: Dict with keys:
                - 'pe_min': Min P/E ratio (ex: 10)
                - 'pe_max': Max P/E ratio (ex: 30)
                - 'roe_min': Min ROE (ex: 0.15 = 15%)
                - 'debt_equity_max': Max Debt/Equity (ex: 1.5)
                - 'dividend_yield_min': Min dividend yield (ex: 0.01 = 1%)
        
        Returns:
            List of tickers passing all criteria
        
        NOTE: MVP returns all tickers (log warning that integration pending)
        """
        # Log: "FundamentalScreener not yet integrated with FinanceToolkit..."
        # TODO: Integrate with FinanceToolkit for real fundamental data
        # For now: return all tickers
        pass

================================================================================
3. src/financial_analyzer/universe/technical_screener.py (100 LOC)
================================================================================

"""
Technical Screener - Technical Health Filters.

Screen assets by technical criteria (SMA200, RSI, trend strength).

Note:
- Currently returns all tickers (no filtering)
- TODO: Integrate with yfinance price data in Phase 5.6
- TODO: Calculate SMA200, RSI, ADX indicators

Example:
    >>> from financial_analyzer.universe import TechnicalScreener
    >>> screener = TechnicalScreener()
    >>> healthy_stocks = screener.screen(
    ...     tickers=['AAPL', 'MSFT', 'TSLA'],
    ...     criteria={'above_sma200': True, 'rsi_min': 30, 'rsi_max': 70}
    ... )
"""

Implement:

class TechnicalScreener:
    """
    Screen assets by technical criteria.
    
    Criteria:
    - Price > SMA200 (in uptrend)
    - RSI not extreme (30-70 healthy range)
    - Not in strong downtrend (ADX < 25)
    
    Note:
    - MVP: Returns all tickers (no real filtering yet)
    - Integration with yfinance/TechnicalFeatures planned for Phase 5.6
    """
    
    def __init__(self):
        """Initialize TechnicalScreener."""
        pass
    
    def screen(
        self,
        tickers: List[str],
        criteria: Dict
    ) -> List[str]:
        """
        Filter by technical health.
        
        Args:
            criteria: Dict with keys:
                - 'above_sma200': bool (price > SMA200)
                - 'rsi_min': Min RSI (ex: 30)
                - 'rsi_max': Max RSI (ex: 70)
                - 'adx_max': Max ADX for weak trends (ex: 25)
        
        Returns:
            List of tickers passing criteria
        
        NOTE: MVP returns all tickers (log warning that integration pending)
        """
        # Log: "TechnicalScreener not yet integrated with price data..."
        # TODO: Integrate with yfinance for price data
        # For now: return all tickers
        pass

================================================================================
4. TESTS (35 TOTAL)
================================================================================

Create 3 test files:

tests/test_universe/test_market_selector.py (15 tests)
- test_init_default()
- test_get_universe_basic()
- test_get_universe_top_n()
- test_parse_market_cap_trillion()
- test_parse_market_cap_billion()
- test_parse_market_cap_million()
- test_parse_market_cap_invalid()
- test_parse_market_cap_none()
- test_get_universe_empty_sector()
- test_get_universe_filters()
- test_market_cap_sorting()
- test_metadata_extraction()
- test_market_cap_tier_filter()
- test_min_marketcap_filter()
- test_return_type_list_of_strings()

tests/test_universe/test_fundamental_screener.py (10 tests)
- test_init_default()
- test_screen_basic()
- test_screen_returns_list()
- test_screen_empty_tickers()
- test_screen_all_criteria()
- test_screen_pe_criteria()
- test_screen_roe_criteria()
- test_screen_debt_equity_criteria()
- test_screen_dividend_yield_criteria()
- test_screen_mocked_data()

tests/test_universe/test_technical_screener.py (10 tests)
- test_init_default()
- test_screen_basic()
- test_screen_returns_list()
- test_screen_empty_tickers()
- test_screen_above_sma200()
- test_screen_rsi_range()
- test_screen_adx_filter()
- test_screen_all_criteria()
- test_screen_mocked_prices()
- test_screen_real_tickers()

================================================================================
REQUIREMENTS
================================================================================

✅ All 3 files implement exact specifications above
✅ Type hints 100%
✅ Google docstrings 100%
✅ 35 tests total (15 + 10 + 10)
✅ All tests passing 100%
✅ Logging at info/warning/error levels
✅ Error handling with try/except + logging
✅ Zero Pylance errors
✅ Production-ready code

NOTES:
- FundamentalScreener & TechnicalScreener are MVP (return all tickers)
- TODO comments mark integration points for Phase 5.6
- MarketSelector fully functional (uses existing UniverseSelector)
- Use mock data for tests (don't make real API calls)

Refs: AUDIT_FINANCEDATABASE.md, AUDIT_RISKFOLIO_LIB.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `market_selector.py` (200 LOC) - FULL IMPLEMENTATION
2. ✅ `fundamental_screener.py` (100 LOC) - MVP (return all tickers, log TODO)
3. ✅ `technical_screener.py` (100 LOC) - MVP (return all tickers, log TODO)
4. ✅ 3 test files (35 tests total)

**Key points:**
- MarketSelector: Fully functional
- FundamentalScreener & TechnicalScreener: MVP with TODO comments (to integrate in Phase 5.6)
- All tests mock data (no real API calls)
- Type hints + docstrings 100%

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ market_selector.py (200 LOC)
✅ fundamental_screener.py (100 LOC)
✅ technical_screener.py (100 LOC)
✅ test_market_selector.py (15 tests)
✅ test_fundamental_screener.py (10 tests)
✅ test_technical_screener.py (10 tests)

Total: 400 LOC + 35 tests
All passing: 35/35 ✅
```

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀
