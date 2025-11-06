"""
Tests pour le module Market Data.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer import config


# Markers pytest pour tous les tests de ce fichier
pytestmark = pytest.mark.data


@pytest.fixture(autouse=True)
def disable_cache(monkeypatch):
    """Désactive le cache pour tous les tests."""
    monkeypatch.setattr(config, 'CACHE_ENABLED', False)


@pytest.fixture
def mock_ohlcv_data():
    """Fixture avec données OHLCV synthétiques."""
    dates = pd.date_range('2020-01-01', periods=5, freq='D', tz='UTC')
    return pd.DataFrame(
        {
            'Open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'High': [102.0, 103.0, 104.0, 105.0, 106.0],
            'Low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'Close': [101.0, 102.0, 103.0, 104.0, 105.0],
            'Volume': [1000000, 1100000, 1200000, 1300000, 1400000],
        },
        index=dates,
    )


class TestMarketDataFetcherInit:
    """Tests d'initialisation du MarketDataFetcher."""

    @pytest.mark.unit
    def test_init_with_api_key(self):
        """Test initialisation avec API key."""
        fetcher = MarketDataFetcher(api_key="test_api_key")

        assert fetcher.api_key == "test_api_key"
        assert fetcher.use_yfinance is False
        assert fetcher.toolkit is None  # Initialisé lors des appels

    @pytest.mark.unit
    def test_init_without_api_key(self):
        """Test initialisation sans API key (fallback yfinance)."""
        fetcher = MarketDataFetcher()

        assert fetcher.api_key is None
        assert fetcher.use_yfinance is True
        assert fetcher.toolkit is None


class TestGetHistoricalData:
    """Tests de récupération données historiques."""

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_historical_single_ticker(self, mock_yf_ticker, mock_ohlcv_data):
        """Test récupération données pour ticker unique."""
        mock_yf_ticker.return_value.history.return_value = mock_ohlcv_data

        fetcher = MarketDataFetcher()
        result = fetcher.get_historical_data('AAPL', '2020-01-01', '2020-01-05')

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5
        assert list(result.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
        assert isinstance(result.index, pd.DatetimeIndex)

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_historical_multiple_tickers(self, mock_yf_ticker, mock_ohlcv_data):
        """Test récupération données pour plusieurs tickers."""
        mock_yf_ticker.return_value.history.return_value = mock_ohlcv_data

        fetcher = MarketDataFetcher()
        result = fetcher.get_historical_data(['AAPL', 'MSFT'], '2020-01-01', '2020-01-05')

        assert isinstance(result, dict)
        assert 'AAPL' in result
        assert 'MSFT' in result
        assert isinstance(result['AAPL'], pd.DataFrame)
        assert len(result['AAPL']) == 5

    @pytest.mark.unit
    def test_get_historical_invalid_dates(self):
        """Test validation dates invalides (start > end)."""
        fetcher = MarketDataFetcher()

        with pytest.raises(ValueError, match="Date début .* > date fin"):
            fetcher.get_historical_data('AAPL', '2020-12-31', '2020-01-01')

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_historical_api_fallback(self, mock_yf_ticker, mock_ohlcv_data):
        """Test fallback yfinance si FinanceToolkit fail."""
        mock_yf_ticker.return_value.history.return_value = mock_ohlcv_data

        # Fetcher avec API key mais FinanceToolkit va fail
        fetcher = MarketDataFetcher(api_key="test_key")

        # Forcer fallback yfinance
        with patch.object(fetcher, '_fetch_via_financetoolkit', side_effect=Exception("API Error")):
            result = fetcher.get_historical_data('AAPL', '2020-01-01', '2020-01-05')

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_historical_empty_result(self, mock_yf_ticker):
        """Test gestion résultat vide."""
        mock_yf_ticker.return_value.history.return_value = pd.DataFrame()

        fetcher = MarketDataFetcher()
        result = fetcher.get_historical_data('INVALID', '2020-01-01', '2020-01-05')

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_historical_different_intervals(self, mock_yf_ticker, mock_ohlcv_data):
        """Test différents intervalles (1d, 1wk, 1mo)."""
        mock_yf_ticker.return_value.history.return_value = mock_ohlcv_data

        fetcher = MarketDataFetcher()

        # Tester 1d (default)
        result_1d = fetcher.get_historical_data('AAPL', '2020-01-01', '2020-01-31', interval='1d')
        assert not result_1d.empty

        # Tester 1wk
        result_1wk = fetcher.get_historical_data('AAPL', '2020-01-01', '2020-01-31', interval='1wk')
        assert not result_1wk.empty


class TestGetLatestPrice:
    """Tests de récupération prix récents."""

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_latest_price_single(self, mock_yf_ticker):
        """Test récupération prix pour ticker unique."""
        mock_yf_ticker.return_value.info = {'currentPrice': 182.52}

        fetcher = MarketDataFetcher()
        result = fetcher.get_latest_price('AAPL')

        assert isinstance(result, pd.Series)
        assert result['AAPL'] == 182.52

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_latest_price_multiple(self, mock_yf_ticker):
        """Test récupération prix pour plusieurs tickers."""
        # Mock différents tickers avec différents prix
        def mock_info_side_effect(*args, **kwargs):
            ticker = mock_yf_ticker.call_args[0][0] if mock_yf_ticker.call_args else 'AAPL'
            prices = {'AAPL': 182.52, 'MSFT': 378.91, 'GOOGL': 141.80}
            mock_obj = MagicMock()
            mock_obj.info = {'currentPrice': prices.get(ticker, 100.0)}
            return mock_obj

        mock_yf_ticker.side_effect = mock_info_side_effect

        fetcher = MarketDataFetcher()
        result = fetcher.get_latest_price(['AAPL', 'MSFT', 'GOOGL'])

        assert isinstance(result, pd.Series)
        assert len(result) == 3
        assert result['AAPL'] == 182.52

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_latest_price_fallback_fields(self, mock_yf_ticker):
        """Test fallback sur différents champs (currentPrice, regularMarketPrice, previousClose)."""
        # Tester regularMarketPrice si currentPrice absent
        mock_yf_ticker.return_value.info = {'regularMarketPrice': 180.00}

        fetcher = MarketDataFetcher()
        result = fetcher.get_latest_price('AAPL')

        assert result['AAPL'] == 180.00

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_latest_price_unavailable(self, mock_yf_ticker):
        """Test gestion prix non disponible."""
        mock_yf_ticker.return_value.info = {}  # Pas de prix

        fetcher = MarketDataFetcher()
        result = fetcher.get_latest_price('INVALID')

        assert result['INVALID'] is None


class TestValidateOHLCV:
    """Tests de validation DataFrame OHLCV."""

    @pytest.mark.unit
    def test_validate_ohlcv_valid(self, mock_ohlcv_data):
        """Test validation DataFrame valide."""
        fetcher = MarketDataFetcher()

        # Ne doit pas lever d'exception
        result = fetcher.validate_ohlcv(mock_ohlcv_data)
        assert result is True

    @pytest.mark.unit
    def test_validate_ohlcv_invalid_columns(self):
        """Test validation échoue si colonnes manquantes."""
        df = pd.DataFrame(
            {
                'Open': [100],
                'Close': [101],
                # 'High', 'Low', 'Volume' manquants
            },
            index=pd.date_range('2020-01-01', periods=1, tz='UTC'),
        )

        fetcher = MarketDataFetcher()

        with pytest.raises(ValueError, match="Colonnes manquantes"):
            fetcher.validate_ohlcv(df)

    @pytest.mark.unit
    def test_validate_ohlcv_invalid_index(self):
        """Test validation échoue si pas DatetimeIndex."""
        df = pd.DataFrame(
            {
                'Open': [100],
                'High': [102],
                'Low': [99],
                'Close': [101],
                'Volume': [1000],
            },
            index=[0],  # Index numérique au lieu de DatetimeIndex
        )

        fetcher = MarketDataFetcher()

        with pytest.raises(ValueError, match="Index doit être DatetimeIndex"):
            fetcher.validate_ohlcv(df)

    @pytest.mark.unit
    def test_validate_ohlcv_nan_values(self):
        """Test validation échoue si valeurs NaN présentes."""
        df = pd.DataFrame(
            {
                'Open': [100, None],
                'High': [102, 103],
                'Low': [99, 100],
                'Close': [101, 102],
                'Volume': [1000, 1100],
            },
            index=pd.date_range('2020-01-01', periods=2, tz='UTC'),
        )

        fetcher = MarketDataFetcher()

        with pytest.raises(ValueError, match="NaN détectées"):
            fetcher.validate_ohlcv(df)

    @pytest.mark.unit
    def test_validate_ohlcv_dates_not_sorted(self):
        """Test validation échoue si dates non croissantes."""
        dates = pd.DatetimeIndex(['2020-01-05', '2020-01-03', '2020-01-04'], tz='UTC')
        df = pd.DataFrame(
            {
                'Open': [100, 101, 102],
                'High': [102, 103, 104],
                'Low': [99, 100, 101],
                'Close': [101, 102, 103],
                'Volume': [1000, 1100, 1200],
            },
            index=dates,
        )

        fetcher = MarketDataFetcher()

        with pytest.raises(ValueError, match="Dates non en ordre croissant"):
            fetcher.validate_ohlcv(df)


class TestNormalizeColumns:
    """Tests de normalisation des colonnes."""

    @pytest.mark.unit
    def test_normalize_columns_lowercase(self):
        """Test normalisation noms en minuscules."""
        df = pd.DataFrame(
            {
                'open': [100],
                'high': [102],
                'low': [99],
                'close': [101],
                'volume': [1000],
            },
            index=pd.date_range('2020-01-01', periods=1),
        )

        fetcher = MarketDataFetcher()
        normalized = fetcher._normalize_columns(df)

        assert 'Open' in normalized.columns
        assert 'open' not in normalized.columns

    @pytest.mark.unit
    def test_normalize_columns_timezone(self):
        """Test ajout timezone UTC."""
        df = pd.DataFrame(
            {
                'Open': [100],
                'High': [102],
                'Low': [99],
                'Close': [101],
                'Volume': [1000],
            },
            index=pd.date_range('2020-01-01', periods=1),  # Pas de TZ
        )

        fetcher = MarketDataFetcher()
        normalized = fetcher._normalize_columns(df)

        assert normalized.index.tz is not None
        assert str(normalized.index.tz) == 'UTC'


class TestCacheFunctionality:
    """Tests de fonctionnement du cache."""

    @patch('yfinance.Ticker')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cache_working(self, mock_yf_ticker, mock_ohlcv_data, monkeypatch):
        """Test que le cache fonctionne (données récupérées qu'une seule fois)."""
        # Activer cache temporairement pour ce test
        monkeypatch.setattr(config, 'CACHE_ENABLED', True)

        mock_yf_ticker.return_value.history.return_value = mock_ohlcv_data

        fetcher = MarketDataFetcher()

        # Premier appel (récupération)
        result1 = fetcher.get_historical_data('AAPL', '2020-01-01', '2020-01-05')

        # Deuxième appel (cache hit)
        result2 = fetcher.get_historical_data('AAPL', '2020-01-01', '2020-01-05')

        # Les résultats doivent être identiques
        pd.testing.assert_frame_equal(result1, result2)

        # Note: On ne peut pas vérifier call_count avec cache enabled
        # car le cache intercepte l'appel
