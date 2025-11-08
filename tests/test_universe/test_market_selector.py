"""
Tests for MarketSelector (universe selection).

Coverage:
- Initialization and basic flow
- Parsing market cap strings (T/B/M/K, numbers, commas, currency)
- Filters and sorting
- Empty data handling and type validation
- Calls to UniverseSelector with expected arguments
"""

from datetime import datetime
from typing import List
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.universe.market_selector import MarketSelector


@pytest.fixture
def mock_selector():
    sel = MagicMock()
    return sel


def _make_md(symbols: List[str], mcaps: List[str], vols: List[str | float]):
    df = pd.DataFrame({
        'symbol': symbols,
        'market_cap': mcaps,
        'volume_usd': vols,
        'name': [f"Name_{i}" for i in range(len(symbols))],
    })
    return df


def test_init_default():
    ms = MarketSelector(universe_selector=MagicMock())
    assert ms is not None


def test_parse_market_cap_variants():
    p = MarketSelector._parse_market_cap
    assert p("$2.5T") == pytest.approx(2.5e12)
    assert p("1.2B") == pytest.approx(1.2e9)
    assert p("250M") == pytest.approx(250e6)
    assert p("120K") == pytest.approx(120e3)
    assert p("123,456,789") == pytest.approx(123456789)
    assert p(42) == 42.0
    assert p(None) == 0.0
    assert p("N/A") == 0.0
    assert p("2.5t") == pytest.approx(2.5e12)
    assert p("  $ 1.5 b ") == pytest.approx(1.5e9)


def test_get_universe_basic_flow(mock_selector):
    mock_selector.select_equities.return_value = ["AAA", "BBB", "CCC", "DDD"]
    md = _make_md(
        ["AAA", "BBB", "CCC", "DDD"],
        ["$2T", "$500B", "$10B", "$1B"],
        [1e8, 2e7, 1e7, 1e6],
    )
    mock_selector.get_metadata.return_value = md

    ms = MarketSelector(universe_selector=mock_selector)
    res = ms.get_universe(
        sector="Technology", country="US", n_assets=3, min_marketcap_usd=1e9, min_volume_usd=1e6
    )
    # Sorted by market cap desc -> AAA (2T), BBB (500B), CCC (10B)
    assert res == ["AAA", "BBB", "CCC"]


def test_get_universe_filters_applied(mock_selector):
    mock_selector.select_equities.return_value = ["X", "Y", "Z"]
    md = _make_md(["X", "Y", "Z"], ["900M", "1.1B", "2.0B"], [1e7, 1e4, 1e8])
    mock_selector.get_metadata.return_value = md

    ms = MarketSelector(universe_selector=mock_selector)
    res = ms.get_universe(
        sector=None, country="US", n_assets=10, min_marketcap_usd=1e9, min_volume_usd=1e6
    )
    # Only Y (1.1B, vol 1e4 fails) and Z (2.0B, vol ok) meet mcap, but volume excludes Y
    assert res == ["Z"]


def test_get_universe_empty_tickers(mock_selector):
    mock_selector.select_equities.return_value = []
    ms = MarketSelector(universe_selector=mock_selector)
    assert ms.get_universe("Tech", "US") == []


def test_get_universe_empty_metadata(mock_selector):
    mock_selector.select_equities.return_value = ["AAA"]
    mock_selector.get_metadata.return_value = pd.DataFrame()
    ms = MarketSelector(universe_selector=mock_selector)
    assert ms.get_universe("Tech", "US") == []


def test_get_universe_missing_symbol_uses_index(mock_selector):
    mock_selector.select_equities.return_value = ["AAA", "BBB"]
    df = pd.DataFrame(index=["AAA", "BBB"], data={
        'market_cap': ["2B", "1B"],
        'volume_usd': [1e7, 1e6],
    })
    mock_selector.get_metadata.return_value = df
    ms = MarketSelector(universe_selector=mock_selector)
    res = ms.get_universe("Tech", "US", n_assets=2, min_marketcap_usd=1e9, min_volume_usd=1e6)
    assert res == ["AAA", "BBB"]


def test_get_universe_sorting_desc(mock_selector):
    mock_selector.select_equities.return_value = ["S", "M", "L"]
    md = _make_md(["S", "M", "L"], ["1B", "10B", "100B"], [1e6, 1e6, 1e6])
    mock_selector.get_metadata.return_value = md

    ms = MarketSelector(universe_selector=mock_selector)
    res = ms.get_universe("Tech", "US", n_assets=3, min_volume_usd=1e6)
    assert res == ["L", "M", "S"]


def test_get_universe_type_validation():
    ms = MarketSelector(universe_selector=MagicMock())
    with pytest.raises(ValueError):
        ms.get_universe("Tech", "US", n_assets=0)
    with pytest.raises(ValueError):
        ms.get_universe("Tech", "US", n_assets=10, min_marketcap_usd=-1)


def test_calls_to_universe_selector(mock_selector):
    mock_selector.select_equities.return_value = ["AAA"]
    md = _make_md(["AAA"], ["2B"], [1e7])
    mock_selector.get_metadata.return_value = md

    ms = MarketSelector(universe_selector=mock_selector)
    _ = ms.get_universe(sector="Healthcare", country="FR", n_assets=1)
    mock_selector.select_equities.assert_called_once_with(sector="Healthcare", country="FR")
    mock_selector.get_metadata.assert_called_once()


def test_volume_parsing_from_string(mock_selector):
    mock_selector.select_equities.return_value = ["AAA", "BBB"]
    df = pd.DataFrame({
        'symbol': ["AAA", "BBB"],
        'market_cap': ["2B", "1B"],
        'volume': ["12M", "500K"],  # no volume_usd column, fallback to 'volume'
    })
    mock_selector.get_metadata.return_value = df
    ms = MarketSelector(universe_selector=mock_selector)
    res = ms.get_universe("Tech", "US", n_assets=2, min_marketcap_usd=5e8, min_volume_usd=1e6)
    assert res == ["AAA"]


def test_parse_market_cap_weird_strings():
    p = MarketSelector._parse_market_cap
    assert p("USD 3.4 Billion") == pytest.approx(3.4)
    # It extracts the numeric part only; conservative parsing to avoid false multipliers
    assert p("~5,000,000 ") == pytest.approx(5_000_000)


def test_no_assets_meet_thresholds(mock_selector):
    mock_selector.select_equities.return_value = ["A", "B"]
    md = _make_md(["A", "B"], ["900M", "800M"], [1e5, 1e5])
    mock_selector.get_metadata.return_value = md
    ms = MarketSelector(universe_selector=mock_selector)
    res = ms.get_universe("Tech", "US", min_marketcap_usd=1e9, min_volume_usd=1e6)
    assert res == []


def test_metadata_called_with_equities_asset_type(mock_selector):
    mock_selector.select_equities.return_value = ["AAA"]
    md = _make_md(["AAA"], ["2B"], [1e7])
    mock_selector.get_metadata.return_value = md

    ms = MarketSelector(universe_selector=mock_selector)
    _ = ms.get_universe("Tech", "US")
    # Verify second positional arg was asset_type='equities'
    args, kwargs = mock_selector.get_metadata.call_args
    assert kwargs.get('asset_type') == 'equities' or (len(args) >= 2 and args[1] == 'equities')


def test_missing_required_columns_leads_to_empty_result(mock_selector):
    """If metadata lacks market cap and volume info, no asset should pass filters."""
    mock_selector.select_equities.return_value = ["AAA", "BBB"]
    df = pd.DataFrame({
        'symbol': ["AAA", "BBB"],
        'name': ["A", "B"],
        # No market_cap/volume columns
    })
    mock_selector.get_metadata.return_value = df

    ms = MarketSelector(universe_selector=mock_selector)
    res = ms.get_universe("Tech", "US", min_marketcap_usd=1e6, min_volume_usd=1e3)
    assert res == []
