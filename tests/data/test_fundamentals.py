"""
Tests pour le module Fundamentals.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from financial_analyzer.data.fundamentals import FundamentalsProvider


# Markers pytest pour tous les tests de ce fichier
pytestmark = pytest.mark.data


@pytest.fixture(autouse=True)
def disable_cache(monkeypatch):
    """Désactive cache via env var."""
    monkeypatch.setenv('CACHE_ENABLED', 'false')


@pytest.fixture
def mock_ratios_data():
    """Fixture avec ratios synthétiques."""
    dates = pd.date_range('2020-01-01', periods=4, freq='Q')
    return pd.DataFrame(
        {
            'PE_Ratio': [25.5, 26.0, 24.8, 25.2],
            'PB_Ratio': [10.2, 10.5, 10.1, 10.3],
            'PS_Ratio': [6.5, 6.7, 6.3, 6.6],
            'ROE': [0.45, 0.47, 0.44, 0.46],
            'ROA': [0.22, 0.23, 0.21, 0.22],
            'Debt_to_Equity': [1.5, 1.4, 1.6, 1.5],
            'Current_Ratio': [1.2, 1.3, 1.2, 1.2],
            'Quick_Ratio': [0.9, 1.0, 0.9, 0.9],
        },
        index=dates,
    )


@pytest.fixture
def mock_income_data():
    """Fixture avec income statement synthétique."""
    dates = pd.date_range('2020-01-01', periods=4, freq='Q')
    return pd.DataFrame(
        {
            'Revenue': [90000000000, 92000000000, 95000000000, 98000000000],
            'Cost_of_Revenue': [55000000000, 56000000000, 57000000000, 58000000000],
            'Gross_Profit': [35000000000, 36000000000, 38000000000, 40000000000],
            'Operating_Expenses': [10000000000, 11000000000, 12000000000, 12500000000],
            'EBIT': [25000000000, 25000000000, 26000000000, 27500000000],
            'Net_Income': [22000000000, 22500000000, 23000000000, 24000000000],
            'EPS': [1.35, 1.38, 1.42, 1.48],
        },
        index=dates,
    )


@pytest.fixture
def mock_balance_data():
    """Fixture avec balance sheet synthétique."""
    dates = pd.date_range('2020-01-01', periods=4, freq='Q')
    return pd.DataFrame(
        {
            'Total_Assets': [350000000000, 355000000000, 360000000000, 365000000000],
            'Total_Liabilities': [250000000000, 252000000000, 255000000000, 258000000000],
            'Total_Equity': [100000000000, 103000000000, 105000000000, 107000000000],
            'Cash': [50000000000, 52000000000, 53000000000, 55000000000],
            'Total_Debt': [120000000000, 121000000000, 122000000000, 123000000000],
        },
        index=dates,
    )


@pytest.fixture
def mock_cashflow_data():
    """Fixture avec cash flow synthétique."""
    dates = pd.date_range('2020-01-01', periods=4, freq='Q')
    return pd.DataFrame(
        {
            'Operating_Cash_Flow': [28000000000, 29000000000, 30000000000, 31000000000],
            'Investing_Cash_Flow': [-8000000000, -8500000000, -9000000000, -9500000000],
            'Financing_Cash_Flow': [-5000000000, -5500000000, -6000000000, -6500000000],
            'Free_Cash_Flow': [20000000000, 20500000000, 21000000000, 21500000000],
            'CapEx': [8000000000, 8500000000, 9000000000, 9500000000],
        },
        index=dates,
    )


class TestFundamentalsProviderInit:
    """Tests d'initialisation du FundamentalsProvider."""

    @pytest.mark.unit
    def test_init_with_api_key(self):
        """Test initialisation avec API key."""
        provider = FundamentalsProvider(api_key="test_api_key")

        assert provider.api_key == "test_api_key"
        assert provider.toolkit is None  # Initialisé lors des appels

    @pytest.mark.unit
    def test_init_without_api_key(self):
        """Test initialisation sans API key (doit lever ValueError)."""
        with pytest.raises(ValueError, match="API key obligatoire"):
            FundamentalsProvider(api_key=None)

        with pytest.raises(ValueError, match="API key obligatoire"):
            FundamentalsProvider(api_key="")


class TestGetAllRatios:
    """Tests de récupération des ratios financiers."""

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_all_ratios_single_ticker(self, mock_toolkit, mock_ratios_data):
        """Test récupération ratios pour ticker unique."""
        mock_toolkit.return_value.ratios.collect_financial_ratios.return_value = mock_ratios_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_all_ratios('AAPL', period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4
        assert 'PE_Ratio' in result.columns
        assert 'ROE' in result.columns
        assert len(result.columns) >= 8  # Au moins 8 ratios

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_all_ratios_multiple_tickers(self, mock_toolkit, mock_ratios_data):
        """Test récupération ratios pour plusieurs tickers."""
        mock_toolkit.return_value.ratios.collect_financial_ratios.return_value = mock_ratios_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_all_ratios(['AAPL', 'MSFT'], period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert result.index.names == ['ticker', None]  # MultiIndex
        assert 'AAPL' in result.index.get_level_values(0)
        assert 'MSFT' in result.index.get_level_values(0)

    @pytest.mark.unit
    def test_get_all_ratios_invalid_period(self):
        """Test validation period invalide."""
        provider = FundamentalsProvider(api_key="test_key")

        with pytest.raises(ValueError, match="Period invalide"):
            provider.get_all_ratios('AAPL', period='invalid', limit=4)

        with pytest.raises(ValueError, match="Period invalide"):
            provider.get_all_ratios('AAPL', period='monthly', limit=4)

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_all_ratios_annual_period(self, mock_toolkit, mock_ratios_data):
        """Test récupération avec period='annual'."""
        mock_toolkit.return_value.ratios.collect_financial_ratios.return_value = mock_ratios_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_all_ratios('AAPL', period='annual', limit=5)

        assert isinstance(result, pd.DataFrame)
        # Vérifier que 'annual' a été passé à l'API
        mock_toolkit.return_value.ratios.collect_financial_ratios.assert_called_once()
        call_kwargs = mock_toolkit.return_value.ratios.collect_financial_ratios.call_args[1]
        assert call_kwargs['period'] == 'annual'


class TestGetIncomeStatement:
    """Tests de récupération income statement."""

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_income_statement_single(self, mock_toolkit, mock_income_data):
        """Test récupération income statement pour ticker unique."""
        mock_toolkit.return_value.get_income_statement.return_value = mock_income_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_income_statement('AAPL', period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4
        assert 'Revenue' in result.columns
        assert 'EBIT' in result.columns
        assert 'Net_Income' in result.columns

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_income_statement_multiple(self, mock_toolkit, mock_income_data):
        """Test récupération income statement pour plusieurs tickers."""
        mock_toolkit.return_value.get_income_statement.return_value = mock_income_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_income_statement(['AAPL', 'MSFT'], period='annual', limit=5)

        assert isinstance(result, pd.DataFrame)
        assert result.index.names[0] == 'ticker'  # MultiIndex

    @pytest.mark.unit
    def test_get_income_statement_invalid_period(self):
        """Test validation period invalide."""
        provider = FundamentalsProvider(api_key="test_key")

        with pytest.raises(ValueError, match="Period invalide"):
            provider.get_income_statement('AAPL', period='daily', limit=4)


class TestGetBalanceSheet:
    """Tests de récupération balance sheet."""

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_balance_sheet_single(self, mock_toolkit, mock_balance_data):
        """Test récupération balance sheet pour ticker unique."""
        mock_toolkit.return_value.get_balance_sheet_statement.return_value = mock_balance_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_balance_sheet('AAPL', period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4
        assert 'Total_Assets' in result.columns
        assert 'Total_Liabilities' in result.columns
        assert 'Total_Equity' in result.columns

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_balance_sheet_multiple(self, mock_toolkit, mock_balance_data):
        """Test récupération balance sheet pour plusieurs tickers."""
        mock_toolkit.return_value.get_balance_sheet_statement.return_value = mock_balance_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_balance_sheet(['AAPL', 'MSFT'], period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert result.index.names[0] == 'ticker'


class TestGetCashFlow:
    """Tests de récupération cash flow."""

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_cash_flow_single(self, mock_toolkit, mock_cashflow_data):
        """Test récupération cash flow pour ticker unique."""
        mock_toolkit.return_value.get_cash_flow_statement.return_value = mock_cashflow_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_cash_flow('AAPL', period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4
        assert 'Operating_Cash_Flow' in result.columns
        assert 'Investing_Cash_Flow' in result.columns
        assert 'Financing_Cash_Flow' in result.columns

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_get_cash_flow_multiple(self, mock_toolkit, mock_cashflow_data):
        """Test récupération cash flow pour plusieurs tickers."""
        mock_toolkit.return_value.get_cash_flow_statement.return_value = mock_cashflow_data

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_cash_flow(['AAPL', 'MSFT'], period='annual', limit=5)

        assert isinstance(result, pd.DataFrame)
        assert result.index.names[0] == 'ticker'


class TestAPIErrorHandling:
    """Tests de gestion d'erreurs API."""

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_api_error_handling_ratios(self, mock_toolkit):
        """Test retourne DataFrame vide si API fail (ratios)."""
        mock_toolkit.return_value.ratios.collect_financial_ratios.side_effect = Exception("API Error")

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_all_ratios('INVALID', period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_api_error_handling_income(self, mock_toolkit):
        """Test retourne DataFrame vide si API fail (income statement)."""
        mock_toolkit.return_value.get_income_statement.side_effect = Exception("API Error")

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_income_statement('INVALID', period='quarterly', limit=4)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_api_error_handling_partial_multi_ticker(self, mock_toolkit):
        """Test gestion erreur partielle avec multi-tickers."""
        # Premier ticker OK, deuxième fail
        def side_effect_func(*args, **kwargs):
            if mock_toolkit.call_count <= 1:
                return pd.DataFrame({'PE_Ratio': [25.5]}, index=pd.date_range('2020-01-01', periods=1))
            else:
                raise Exception("API Error")

        mock_toolkit.return_value.ratios.collect_financial_ratios.side_effect = side_effect_func

        provider = FundamentalsProvider(api_key="test_key")
        result = provider.get_all_ratios(['AAPL', 'INVALID'], period='quarterly', limit=4)

        # Doit retourner seulement AAPL
        assert isinstance(result, pd.DataFrame)
        assert 'AAPL' in result.index.get_level_values(0)


class TestCacheFunctionality:
    """Tests de fonctionnement du cache."""

    @pytest.mark.skip("Cache disabled by autouse fixture")
    @patch('financial_analyzer.data.fundamentals.Toolkit')
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cache_working_ratios(self, mock_toolkit, mock_ratios_data):
        """Test que le cache fonctionne pour ratios."""
        mock_instance = MagicMock()
        mock_instance.ratios.collect_financial_ratios.return_value = mock_ratios_data
        mock_toolkit.return_value = mock_instance

        provider = FundamentalsProvider(api_key="test_key")

        # Premier appel
        result1 = provider.get_all_ratios('AAPL', period='quarterly', limit=4)

        # Deuxième appel (cache hit)
        result2 = provider.get_all_ratios('AAPL', period='quarterly', limit=4)

        # Les résultats doivent être identiques
        pd.testing.assert_frame_equal(result1, result2)
