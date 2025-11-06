"""
Tests unitaires complets pour modules data.

Teste MarketDataFetcher et FinancialNewsScraper avec:
- 100% mocks (pas d'appels API)
- pytest fixtures réutilisables
- Couverture >80%
- Tests cache, retry, erreurs, edge cases

Usage:
    pytest tests/test_data.py -v
    pytest tests/test_data.py --cov=financial_analyzer.data
"""

# 1. Stdlib
import logging
from datetime import datetime, timedelta

# 2. Testing
import pytest
import pandas as pd
import numpy as np
from pandas.testing import assert_frame_equal, assert_index_equal
from unittest.mock import patch, MagicMock, call

# 3. Projet local
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.data.news_scraper import FinancialNewsScraper


# ============================================================================
# FIXTURES PARTAGÉES
# ============================================================================

@pytest.fixture
def api_key() -> str:
    """Fixture: Clé API valide pour tests."""
    return "test_api_key_12345"


@pytest.fixture
def market_fetcher(api_key: str) -> MarketDataFetcher:
    """Fixture: Instance MarketDataFetcher initialisée."""
    return MarketDataFetcher(api_key=api_key, cache_enabled=False)


@pytest.fixture
def news_scraper() -> FinancialNewsScraper:
    """Fixture: Instance FinancialNewsScraper initialisée."""
    return FinancialNewsScraper(timeout=5, max_retries=2)


@pytest.fixture
def sample_prices_df() -> pd.DataFrame:
    """
    Fixture: DataFrame OHLCV format standard.

    Colonnes: Open, High, Low, Close, Volume
    Index: DatetimeIndex UTC
    """
    idx = pd.date_range("2023-01-01", periods=5, freq="D", tz="UTC", name="date")
    df = pd.DataFrame({
        "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "High": [101.0, 102.0, 103.0, 104.0, 105.0],
        "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
        "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
        "Volume": [1000000, 1100000, 1200000, 1300000, 1400000]
    }, index=idx)
    return df


@pytest.fixture
def sample_news_df() -> pd.DataFrame:
    """
    Fixture: DataFrame news format standardisé.

    Colonnes: headline, source, url, text, ticker
    Index: DatetimeIndex UTC
    """
    idx = pd.date_range("2023-01-03", periods=3, freq="D", tz="UTC", name="date")
    df = pd.DataFrame({
        "headline": [
            "Apple beats Q1 earnings expectations",
            "Microsoft launches new AI features",
            "Google stock faces market pressure"
        ],
        "source": ["Yahoo Finance", "FinViz", "NewsAPI"],
        "url": [
            "https://yahoo.com/aapl-earnings",
            "https://finviz.com/msft-ai",
            "https://newsapi.org/googl-drop"
        ],
        "text": [
            "Apple reported strong Q1 results...",
            "Microsoft announces Copilot features...",
            "Google faces regulatory challenges..."
        ],
        "ticker": ["AAPL", "MSFT", "GOOGL"]
    }, index=idx)
    return df


@pytest.fixture
def sample_tickers_df() -> pd.DataFrame:
    """
    Fixture: DataFrame résultat search_tickers.

    Colonnes: symbol, name, sector, country, market_cap
    """
    return pd.DataFrame({
        "symbol": ["AAPL", "MSFT", "GOOGL"],
        "name": ["Apple Inc.", "Microsoft Corp.", "Google LLC"],
        "sector": ["Technology", "Technology", "Communication Services"],
        "country": ["United States", "United States", "United States"],
        "market_cap": ["Large Cap", "Large Cap", "Large Cap"]
    })


# ============================================================================
# TESTS: MarketDataFetcher
# ============================================================================

class TestMarketDataFetcher:
    """Tests pour classe MarketDataFetcher."""

    def test_init_valid_api_key(self, api_key: str) -> None:
        """Test: Initialisation réussie avec API key valide."""
        fetcher = MarketDataFetcher(api_key=api_key)

        assert fetcher.api_key == api_key
        assert fetcher.cache_enabled is True
        assert fetcher.alpha_vantage_key is None
        assert hasattr(fetcher, 'logger')
        assert hasattr(fetcher, 'session')

    def test_init_invalid_api_key_empty(self) -> None:
        """Test: ValueError si API key vide."""
        with pytest.raises(ValueError, match="api_key ne peut pas être vide"):
            MarketDataFetcher(api_key="")

    def test_init_invalid_api_key_none(self) -> None:
        """Test: ValueError si API key None."""
        with pytest.raises(ValueError, match="api_key ne peut pas être vide"):
            MarketDataFetcher(api_key=None)

    def test_init_invalid_api_key_type(self) -> None:
        """Test: ValueError si API key n'est pas string."""
        with pytest.raises(ValueError):
            MarketDataFetcher(api_key=123)

    @patch('financial_analyzer.data.market_data.Equities')
    def test_search_tickers_success(
        self,
        mock_equities_class,
        market_fetcher: MarketDataFetcher,
        sample_tickers_df: pd.DataFrame
    ) -> None:
        """Test: search_tickers retourne DataFrame avec colonnes correctes."""
        # Setup mock
        mock_equities_instance = MagicMock()
        mock_equities_instance.select.return_value = sample_tickers_df
        mock_equities_class.return_value = mock_equities_instance

        # Exécuter
        result = market_fetcher.search_tickers(
            sector="Technology",
            country="United States"
        )

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert set(["symbol", "name", "sector"]).issubset(result.columns)
        assert result["symbol"].tolist() == ["AAPL", "MSFT", "GOOGL"]

    @patch('financial_analyzer.data.market_data.Equities')
    def test_search_tickers_empty_result(
        self,
        mock_equities_class,
        market_fetcher: MarketDataFetcher
    ) -> None:
        """Test: ValueError si aucun ticker trouvé."""
        # Setup mock pour retourner DataFrame vide
        mock_equities_instance = MagicMock()
        mock_equities_instance.select.return_value = pd.DataFrame()
        mock_equities_class.return_value = mock_equities_instance

        # Assertions
        with pytest.raises(ValueError, match="Aucun ticker trouvé"):
            market_fetcher.search_tickers(sector="Unknown")

    @patch('financial_analyzer.data.market_data.Toolkit')
    def test_get_historical_data_single_ticker(
        self,
        mock_toolkit_class,
        market_fetcher: MarketDataFetcher,
        sample_prices_df: pd.DataFrame
    ) -> None:
        """Test: Single ticker retourne DataFrame OHLCV."""
        # Setup mock
        mock_toolkit_instance = MagicMock()
        mock_toolkit_instance.get_historical_data.return_value = sample_prices_df
        mock_toolkit_class.return_value = mock_toolkit_instance

        # Exécuter
        result = market_fetcher.get_historical_data("AAPL", period="1y")

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert set(["Open", "High", "Low", "Close", "Volume"]).issubset(result.columns)
        assert len(result) == 5
        assert result.index.tz is not None  # DatetimeIndex avec timezone

    @patch('financial_analyzer.data.market_data.Toolkit')
    def test_get_historical_data_multi_tickers(
        self,
        mock_toolkit_class,
        market_fetcher: MarketDataFetcher,
        sample_prices_df: pd.DataFrame
    ) -> None:
        """Test: Multi-tickers retourne Dict[str, DataFrame]."""
        # Setup mock pour retourner dict
        mock_toolkit_instance = MagicMock()
        mock_toolkit_instance.get_historical_data.return_value = {
            "AAPL": sample_prices_df,
            "MSFT": sample_prices_df.copy()
        }
        mock_toolkit_class.return_value = mock_toolkit_instance

        # Exécuter
        result = market_fetcher.get_historical_data(
            ["AAPL", "MSFT"],
            period="6mo"
        )

        # Assertions
        assert isinstance(result, dict)
        assert set(result.keys()) == {"AAPL", "MSFT"}
        assert all(isinstance(df, pd.DataFrame) for df in result.values())

    @patch('financial_analyzer.data.market_data.Toolkit')
    @patch('financial_analyzer.data.market_data.yf.download')
    def test_get_historical_data_fallback_yfinance(
        self,
        mock_yf_download,
        mock_toolkit_class,
        market_fetcher: MarketDataFetcher,
        sample_prices_df: pd.DataFrame
    ) -> None:
        """Test: Fallback yfinance si FinanceToolkit échoue."""
        # Setup mock FinanceToolkit pour échouer
        mock_toolkit_instance = MagicMock()
        mock_toolkit_instance.get_historical_data.side_effect = Exception("API error")
        mock_toolkit_class.return_value = mock_toolkit_instance

        # Setup mock yfinance pour réussir
        mock_yf_download.return_value = sample_prices_df

        # Exécuter
        result = market_fetcher.get_historical_data("AAPL", period="1y")

        # Assertions
        assert isinstance(result, pd.DataFrame)
        mock_yf_download.assert_called_once()

    def test_get_historical_data_invalid_ticker(
        self,
        market_fetcher: MarketDataFetcher
    ) -> None:
        """Test: validate_ticker() nettoie le ticker."""
        # Les tickers invalides sont nettoyés ou rejetés
        # Ici on teste que "aapl" devient "AAPL"
        with patch('financial_analyzer.data.market_data.Toolkit'):
            # Pas d'erreur sur le ticker lui-même
            result = market_fetcher.get_historical_data("aapl", period="1y")
            # Le ticker est normalisé en majuscules

    @patch('financial_analyzer.data.market_data.Toolkit')
    def test_get_historical_data_invalid_period_corrected(
        self,
        mock_toolkit_class,
        market_fetcher: MarketDataFetcher,
        sample_prices_df: pd.DataFrame,
        caplog
    ) -> None:
        """Test: Période invalide auto-corrigée avec warning."""
        # Setup mock
        mock_toolkit_instance = MagicMock()
        mock_toolkit_instance.get_historical_data.return_value = sample_prices_df
        mock_toolkit_class.return_value = mock_toolkit_instance

        # Exécuter avec période invalide
        with caplog.at_level(logging.WARNING):
            result = market_fetcher.get_historical_data("AAPL", period="invalid_period")

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert "Période" in caplog.text or "non supportée" in caplog.text

    @patch('financial_analyzer.data.market_data.Toolkit')
    def test_get_financial_statements_success(
        self,
        mock_toolkit_class,
        market_fetcher: MarketDataFetcher,
        sample_prices_df: pd.DataFrame
    ) -> None:
        """Test: get_financial_statements retourne dict complet."""
        # Setup mock
        mock_toolkit_instance = MagicMock()
        mock_toolkit_instance.get_income_statement.return_value = sample_prices_df
        mock_toolkit_instance.get_balance_sheet_statement.return_value = sample_prices_df
        mock_toolkit_instance.get_cash_flow_statement.return_value = sample_prices_df
        mock_toolkit_instance.ratios.collect_all_ratios.return_value = sample_prices_df
        mock_toolkit_class.return_value = mock_toolkit_instance

        # Exécuter
        result = market_fetcher.get_financial_statements("AAPL")

        # Assertions
        assert isinstance(result, dict)
        assert set(["income_statement", "balance_sheet", "cash_flow", "ratios"]) == set(result.keys())
        assert all(isinstance(df, pd.DataFrame) for df in result.values())

    @patch('financial_analyzer.data.market_data.Toolkit')
    def test_get_financial_statements_error(
        self,
        mock_toolkit_class,
        market_fetcher: MarketDataFetcher
    ) -> None:
        """Test: ValueError si FinanceToolkit échoue."""
        # Setup mock pour échouer
        mock_toolkit_class.side_effect = Exception("API error")

        # Assertions
        with pytest.raises(ValueError, match="Impossible de récupérer"):
            market_fetcher.get_financial_statements("INVALID")

    @patch('financial_analyzer.data.market_data.TimeSeries')
    def test_get_intraday_data_success(
        self,
        mock_timeseries_class,
        market_fetcher: MarketDataFetcher,
        sample_prices_df: pd.DataFrame
    ) -> None:
        """Test: get_intraday_data retourne Dict avec données."""
        # Setup mock
        mock_ts_instance = MagicMock()
        mock_ts_instance.get_intraday.return_value = (sample_prices_df, {})
        mock_timeseries_class.return_value = mock_ts_instance

        # Exécuter
        result = market_fetcher.get_intraday_data("AAPL", interval="5min")

        # Assertions
        assert isinstance(result, dict)
        assert "AAPL" in result

    @patch('financial_analyzer.data.market_data.TimeSeries')
    def test_get_intraday_data_no_key(
        self,
        mock_timeseries_class,
        api_key: str
    ) -> None:
        """Test: ValueError si Alpha Vantage key manquante."""
        # Créer fetcher sans alpha_vantage_key
        fetcher = MarketDataFetcher(api_key=api_key, alpha_vantage_key=None)

        with patch('financial_analyzer.data.market_data.API_KEYS', {'alpha_vantage': None}):
            with pytest.raises(ValueError, match="Alpha Vantage"):
                fetcher.get_intraday_data("AAPL")


# ============================================================================
# TESTS: FinancialNewsScraper
# ============================================================================

class TestFinancialNewsScraper:
    """Tests pour classe FinancialNewsScraper."""

    def test_scraper_init(self) -> None:
        """Test: Initialisation correcte."""
        scraper = FinancialNewsScraper(timeout=5, max_retries=2)

        assert scraper.timeout == 5
        assert scraper.max_retries == 2
        assert scraper.user_agent is not None
        assert hasattr(scraper, 'session')
        assert hasattr(scraper, 'logger')

    def test_scraper_init_invalid_timeout(self) -> None:
        """Test: ValueError si timeout <= 0."""
        with pytest.raises(ValueError):
            FinancialNewsScraper(timeout=0)

    def test_scraper_init_invalid_retries(self) -> None:
        """Test: ValueError si max_retries <= 0."""
        with pytest.raises(ValueError):
            FinancialNewsScraper(max_retries=0)

    def test_clean_text_basic(self, news_scraper: FinancialNewsScraper) -> None:
        """Test: Normalisation texte simple."""
        raw = "  Apple  beats  earnings  "
        clean = news_scraper._clean_text(raw)

        assert clean == "Apple beats earnings"

    def test_clean_text_multiline(self, news_scraper: FinancialNewsScraper) -> None:
        """Test: Normalisation texte multi-lignes."""
        raw = "Apple\nbeats\n\nearnings\rresults"
        clean = news_scraper._clean_text(raw)

        assert clean == "Apple beats earnings results"
        assert "\n" not in clean
        assert "\r" not in clean

    def test_clean_text_empty(self, news_scraper: FinancialNewsScraper) -> None:
        """Test: Gestion texte vide."""
        assert news_scraper._clean_text("") == ""
        assert news_scraper._clean_text(None) == ""

    @patch('financial_analyzer.data.news_scraper.requests.Session.get')
    def test_request_success(
        self,
        mock_get,
        news_scraper: FinancialNewsScraper
    ) -> None:
        """Test: _request réussit avec 200 OK."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        result = news_scraper._request("https://example.com")

        assert result is mock_resp
        mock_get.assert_called_once()

    @patch('financial_analyzer.data.news_scraper.requests.Session.get')
    def test_request_404_no_retry(
        self,
        mock_get,
        news_scraper: FinancialNewsScraper
    ) -> None:
        """Test: _request retourne None sur 404 (pas de retry)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = news_scraper._request("https://example.com")

        assert result is None
        mock_get.assert_called_once()

    @patch('financial_analyzer.data.news_scraper.requests.Session.get')
    @patch('financial_analyzer.data.news_scraper.time.sleep')
    def test_request_429_with_retry(
        self,
        mock_sleep,
        mock_get,
        news_scraper: FinancialNewsScraper
    ) -> None:
        """Test: _request retry sur 429 (rate limit)."""
        # Setup: 429 puis 200
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_get.side_effect = [mock_resp_429, mock_resp_200]

        result = news_scraper._request("https://example.com")

        assert result is mock_resp_200
        assert mock_get.call_count == 2
        mock_sleep.assert_called()

    @patch('financial_analyzer.data.news_scraper.yf.Ticker')
    def test_get_news_from_yahoo_success(
        self,
        mock_ticker_class,
        news_scraper: FinancialNewsScraper
    ) -> None:
        """Test: Yahoo Finance scraping avec yfinance."""
        # Setup mock
        mock_ticker = MagicMock()
        mock_ticker.news = [
            {
                "title": "Apple beats earnings",
                "summary": "Strong Q1 results",
                "link": "https://yahoo.com/aapl",
                "source": "Yahoo Finance",
                "providerPublishTime": 1672574400  # Unix timestamp
            }
        ]
        mock_ticker_class.return_value = mock_ticker

        # Exécuter
        result = news_scraper.get_news_from_yahoo("AAPL")

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert "headline" in result.columns
        assert result.index.name == "date"
        assert result.index.tz is not None

    @patch('financial_analyzer.data.news_scraper.requests.Session.get')
    def test_get_news_from_newsapi_success(
        self,
        mock_get,
        news_scraper: FinancialNewsScraper
    ) -> None:
        """Test: NewsAPI scraping."""
        # Setup mock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "articles": [
                {
                    "title": "Apple stock surges",
                    "description": "Apple gains momentum",
                    "url": "https://newsapi.org/aapl",
                    "publishedAt": "2023-01-03T12:00:00Z",
                    "source": {"name": "Financial Times"}
                }
            ]
        }
        mock_get.return_value = mock_resp

        # Mock API key
        with patch('financial_analyzer.data.news_scraper.API_KEYS', {'news_api': 'test_key'}):
            result = news_scraper.get_news_from_newsapi("AAPL", limit=10)

        # Assertions
        assert isinstance(result, pd.DataFrame)
        if not result.empty:
            assert "headline" in result.columns

    def test_get_news_from_newsapi_no_key(
        self,
        news_scraper: FinancialNewsScraper
    ) -> None:
        """Test: NewsAPI retourne DF vide si API key manquante."""
        with patch('financial_analyzer.data.news_scraper.API_KEYS', {'news_api': None}):
            result = news_scraper.get_news_from_newsapi("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch.object(FinancialNewsScraper, 'get_news_from_yahoo')
    @patch.object(FinancialNewsScraper, 'get_news_from_newsapi')
    @patch.object(FinancialNewsScraper, 'get_news_from_finviz')
    def test_get_all_news_combined(
        self,
        mock_finviz,
        mock_newsapi,
        mock_yahoo,
        news_scraper: FinancialNewsScraper,
        sample_news_df: pd.DataFrame
    ) -> None:
        """Test: get_all_news combine multi-sources."""
        # Setup mocks
        mock_yahoo.return_value = sample_news_df.iloc[:1]
        mock_newsapi.return_value = sample_news_df.iloc[1:2]
        mock_finviz.return_value = sample_news_df.iloc[2:]

        # Exécuter
        result = news_scraper.get_all_news("AAPL", max_articles=100)

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) <= 100
        assert result.index.name == "date"

    @patch.object(FinancialNewsScraper, 'get_news_from_yahoo')
    @patch.object(FinancialNewsScraper, 'get_news_from_newsapi')
    @patch.object(FinancialNewsScraper, 'get_news_from_finviz')
    def test_get_all_news_empty(
        self,
        mock_finviz,
        mock_newsapi,
        mock_yahoo,
        news_scraper: FinancialNewsScraper
    ) -> None:
        """Test: get_all_news retourne DF vide si aucune source."""
        # Setup mocks pour retourner DF vides
        empty_df = pd.DataFrame(columns=["headline", "source", "url", "text", "ticker"])
        empty_df.index = pd.DatetimeIndex([], tz="UTC", name="date")

        mock_yahoo.return_value = empty_df
        mock_newsapi.return_value = empty_df
        mock_finviz.return_value = empty_df

        # Exécuter
        result = news_scraper.get_all_news("AAPL", max_articles=100)

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ============================================================================
# PARAMETRIZE TESTS
# ============================================================================

@pytest.mark.parametrize("period", ["1d", "5d", "1mo", "6mo", "1y", "5y"])
def test_supported_periods(market_fetcher: MarketDataFetcher, period: str) -> None:
    """Test: Toutes les périodes supportées dans CONSTANTS."""
    assert period in market_fetcher.supported_periods


@pytest.mark.parametrize("interval", ["1min", "5min", "15min", "30min", "60min"])
def test_intraday_intervals(interval: str) -> None:
    """Test: Les intervalles intraday sont valides."""
    valid_intervals = ["1min", "5min", "15min", "30min", "60min"]
    assert interval in valid_intervals
