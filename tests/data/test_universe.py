"""
Tests pour le module Universe Selection.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer import config


# Markers pytest pour tous les tests de ce fichier
pytestmark = pytest.mark.data


@pytest.fixture(autouse=True)
def disable_cache(monkeypatch):
    """Désactive le cache pour tous les tests."""
    monkeypatch.setattr(config, 'CACHE_ENABLED', False)


@pytest.fixture
def mock_equities_data():
    """Fixture avec données synthétiques d'actions."""
    return pd.DataFrame(
        {
            'name': ['Apple Inc.', 'Microsoft Corp.', 'Alphabet Inc.', 'Tesla Inc.'],
            'sector': ['Technology', 'Technology', 'Technology', 'Consumer Discretionary'],
            'industry': ['Consumer Electronics', 'Software', 'Internet', 'Automobiles'],
            'market_cap': ['Large Cap', 'Large Cap', 'Large Cap', 'Large Cap'],
            'country': ['US', 'US', 'US', 'US'],
            'exchange': ['NASDAQ', 'NASDAQ', 'NASDAQ', 'NASDAQ'],
            'currency': ['USD', 'USD', 'USD', 'USD'],
        },
        index=['AAPL', 'MSFT', 'GOOGL', 'TSLA'],
    )


@pytest.fixture
def mock_etfs_data():
    """Fixture avec données synthétiques d'ETFs."""
    return pd.DataFrame(
        {
            'name': ['SPDR S&P 500 ETF', 'Invesco QQQ Trust', 'iShares Russell 2000'],
            'category': ['Equity', 'Equity', 'Equity'],
            'family': ['SPDR', 'Invesco', 'iShares'],
            'exchange': ['NYSE', 'NASDAQ', 'NYSE'],
        },
        index=['SPY', 'QQQ', 'IWM'],
    )


@pytest.fixture
def mock_funds_data():
    """Fixture avec données synthétiques de fonds."""
    return pd.DataFrame(
        {
            'name': ['Vanguard 500 Index Fund', 'Fidelity 500 Index Fund'],
            'category': ['Index Fund', 'Index Fund'],
            'family': ['Vanguard', 'Fidelity'],
        },
        index=['VFIAX', 'FXAIX'],
    )


@pytest.fixture
def mock_crypto_data():
    """Fixture avec données synthétiques de crypto."""
    return pd.DataFrame(
        {
            'name': ['Bitcoin', 'Ethereum', 'Binance Coin'],
            'symbol': ['BTC', 'ETH', 'BNB'],
            'exchange': ['Binance', 'Binance', 'Binance'],
        },
        index=['BTC-USD', 'ETH-USD', 'BNB-USD'],
    )


@pytest.fixture
def mock_indices_data():
    """Fixture avec données synthétiques d'indices."""
    return pd.DataFrame(
        {
            'name': ['S&P 500', 'Dow Jones Industrial Average', 'NASDAQ Composite'],
            'market': ['US', 'US', 'US'],
            'region': ['North America', 'North America', 'North America'],
        },
        index=['^GSPC', '^DJI', '^IXIC'],
    )


class TestUniverseSelectorInit:
    """Tests d'initialisation du UniverseSelector."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_init_success(self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities):
        """Test initialisation réussie."""
        selector = UniverseSelector()
        assert selector is not None
        assert hasattr(selector, '_equities_db')
        assert hasattr(selector, '_etfs_db')
        assert hasattr(selector, '_funds_db')
        assert hasattr(selector, '_crypto_db')
        assert hasattr(selector, '_indices_db')

    @patch('financial_analyzer.data.universe.Equities', side_effect=Exception("DB Error"))
    @pytest.mark.unit
    def test_init_failure(self, mock_equities):
        """Test échec initialisation."""
        with pytest.raises(Exception, match="DB Error"):
            UniverseSelector()


class TestSelectEquities:
    """Tests de sélection d'actions."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_equities_valid_sector(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_equities_data
    ):
        """Test sélection d'actions avec secteur valide."""
        mock_equities.return_value.select.return_value = mock_equities_data[
            mock_equities_data['sector'] == 'Technology'
        ]

        selector = UniverseSelector()
        result = selector.select_equities(sector='Technology')

        assert isinstance(result, list)
        assert len(result) == 3
        assert 'AAPL' in result
        assert 'MSFT' in result
        assert 'GOOGL' in result

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_select_equities_invalid_sector(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities
    ):
        """Test sélection avec secteur invalide (doit lever ValueError)."""
        selector = UniverseSelector()
        with pytest.raises(ValueError, match="Sector invalide"):
            selector.select_equities(sector='InvalidSector')

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_equities_with_multiple_filters(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_equities_data
    ):
        """Test sélection avec plusieurs filtres."""
        filtered = mock_equities_data[
            (mock_equities_data['sector'] == 'Technology')
            & (mock_equities_data['market_cap'] == 'Large Cap')
            & (mock_equities_data['country'] == 'US')
        ]
        mock_equities.return_value.select.return_value = filtered

        selector = UniverseSelector()
        result = selector.select_equities(sector='Technology', market_cap='Large Cap', country='US')

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(ticker in ['AAPL', 'MSFT', 'GOOGL'] for ticker in result)

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_select_equities_invalid_market_cap(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities
    ):
        """Test sélection avec market cap invalide."""
        selector = UniverseSelector()
        with pytest.raises(ValueError, match="Market cap invalide"):
            selector.select_equities(market_cap='Invalid Cap')

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_select_equities_api_error(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities
    ):
        """Test gestion d'erreur API (doit retourner liste vide)."""
        mock_equities.return_value.select.side_effect = Exception("API Error")

        selector = UniverseSelector()
        result = selector.select_equities(sector='Technology')

        assert isinstance(result, list)
        assert len(result) == 0


class TestSelectETFs:
    """Tests de sélection d'ETFs."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_etfs_valid(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_etfs_data
    ):
        """Test sélection d'ETFs valide."""
        mock_etfs.return_value.select.return_value = mock_etfs_data

        selector = UniverseSelector()
        result = selector.select_etfs(category='Equity')

        assert isinstance(result, list)
        assert len(result) == 3
        assert 'SPY' in result
        assert 'QQQ' in result

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_select_etfs_invalid_category(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities
    ):
        """Test sélection ETFs avec catégorie invalide."""
        selector = UniverseSelector()
        with pytest.raises(ValueError, match="Category invalide"):
            selector.select_etfs(category='InvalidCategory')

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_etfs_with_family(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_etfs_data
    ):
        """Test sélection ETFs avec filtre famille."""
        filtered = mock_etfs_data[mock_etfs_data['family'] == 'SPDR']
        mock_etfs.return_value.select.return_value = filtered

        selector = UniverseSelector()
        result = selector.select_etfs(family='SPDR')

        assert isinstance(result, list)
        assert 'SPY' in result


class TestSelectFunds:
    """Tests de sélection de fonds."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_funds_valid(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_funds_data
    ):
        """Test sélection de fonds valide."""
        mock_funds.return_value.select.return_value = mock_funds_data

        selector = UniverseSelector()
        result = selector.select_funds(fund_type='Index Fund')

        assert isinstance(result, list)
        assert len(result) == 2
        assert 'VFIAX' in result
        assert 'FXAIX' in result

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_select_funds_invalid_type(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities
    ):
        """Test sélection fonds avec type invalide."""
        selector = UniverseSelector()
        with pytest.raises(ValueError, match="Fund type invalide"):
            selector.select_funds(fund_type='InvalidType')


class TestSelectCrypto:
    """Tests de sélection de cryptomonnaies."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_crypto_valid(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_crypto_data
    ):
        """Test sélection de cryptomonnaies valide."""
        mock_crypto.return_value.select.return_value = mock_crypto_data

        selector = UniverseSelector()
        result = selector.select_crypto()

        assert isinstance(result, list)
        assert len(result) == 3
        assert 'BTC-USD' in result
        assert 'ETH-USD' in result

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_crypto_with_exchange(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_crypto_data
    ):
        """Test sélection crypto avec filtre exchange."""
        filtered = mock_crypto_data[mock_crypto_data['exchange'] == 'Binance']
        mock_crypto.return_value.select.return_value = filtered

        selector = UniverseSelector()
        result = selector.select_crypto(exchange='Binance')

        assert isinstance(result, list)
        assert len(result) == 3


class TestSelectIndices:
    """Tests de sélection d'indices."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_select_indices_valid(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_indices_data
    ):
        """Test sélection d'indices valide."""
        mock_indices.return_value.select.return_value = mock_indices_data

        selector = UniverseSelector()
        result = selector.select_indices(market='US')

        assert isinstance(result, list)
        assert len(result) == 3
        assert '^GSPC' in result
        assert '^DJI' in result


class TestGetMetadata:
    """Tests de récupération de métadonnées."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_metadata_single_ticker(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_equities_data
    ):
        """Test récupération métadonnées pour un seul ticker."""
        mock_equities.return_value.select.return_value = mock_equities_data

        selector = UniverseSelector()
        result = selector.get_metadata('AAPL', asset_type='equities')

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert 'symbol' in result.columns
        assert result.iloc[0]['symbol'] == 'AAPL'

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_metadata_multiple_tickers(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_equities_data
    ):
        """Test récupération métadonnées pour plusieurs tickers."""
        mock_equities.return_value.select.return_value = mock_equities_data

        selector = UniverseSelector()
        result = selector.get_metadata(['AAPL', 'MSFT', 'GOOGL'], asset_type='equities')

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert 'symbol' in result.columns
        assert 'name' in result.columns
        assert set(result['symbol'].tolist()) == {'AAPL', 'MSFT', 'GOOGL'}

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_get_metadata_invalid_asset_type(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities
    ):
        """Test métadonnées avec asset_type invalide."""
        selector = UniverseSelector()
        with pytest.raises(ValueError, match="Asset type invalide"):
            selector.get_metadata('AAPL', asset_type='invalid')


class TestCacheFunctionality:
    """Tests du fonctionnement du cache."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cache_working(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities, mock_equities_data
    ):
        """Test que le cache fonctionne (mock appelé 1 seule fois)."""
        mock_select = mock_equities.return_value.select
        mock_select.return_value = mock_equities_data

        selector = UniverseSelector()

        # Premier appel (sans cache)
        result1 = selector.select_equities(sector='Technology')
        assert mock_select.call_count == 1  # Premier appel au mock

        # Deuxième appel (avec cache)
        result2 = selector.select_equities(sector='Technology')
        assert mock_select.call_count == 1  # Cache utilisé, pas de 2e appel au mock

        # Vérifier que résultats identiques
        assert result1 == result2


class TestHelperMethods:
    """Tests des méthodes utilitaires."""

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_get_all_sectors(self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities):
        """Test récupération de tous les secteurs."""
        selector = UniverseSelector()
        sectors = selector.get_all_sectors()

        assert isinstance(sectors, list)
        assert 'Technology' in sectors
        assert 'Healthcare' in sectors
        assert len(sectors) > 0

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_get_all_market_caps(
        self, mock_indices, mock_crypto, mock_funds, mock_etfs, mock_equities
    ):
        """Test récupération de toutes les market caps."""
        selector = UniverseSelector()
        caps = selector.get_all_market_caps()

        assert isinstance(caps, list)
        assert 'Large Cap' in caps
        assert 'Mid Cap' in caps
        assert 'Small Cap' in caps

    @patch('financedatabase.Equities')
    @patch('financedatabase.ETFs')
    @patch('financedatabase.Funds')
    @patch('financedatabase.Cryptos')
    @patch('financedatabase.Indices')
    @pytest.mark.unit
    def test_get_statistics(
        self,
        mock_indices,
        mock_crypto,
        mock_funds,
        mock_etfs,
        mock_equities,
        mock_equities_data,
        mock_etfs_data,
        mock_funds_data,
        mock_crypto_data,
        mock_indices_data,
    ):
        """Test calcul des statistiques."""
        mock_equities.return_value.select.return_value = mock_equities_data
        mock_etfs.return_value.select.return_value = mock_etfs_data
        mock_funds.return_value.select.return_value = mock_funds_data
        mock_crypto.return_value.select.return_value = mock_crypto_data
        mock_indices.return_value.select.return_value = mock_indices_data

        selector = UniverseSelector()
        stats = selector.get_statistics()

        assert isinstance(stats, dict)
        assert 'equities' in stats
        assert 'etfs' in stats
        assert 'funds' in stats
        assert 'crypto' in stats
        assert 'indices' in stats
        assert 'total' in stats
        assert stats['total'] == sum(
            [stats['equities'], stats['etfs'], stats['funds'], stats['crypto'], stats['indices']]
        )
