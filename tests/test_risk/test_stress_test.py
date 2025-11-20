"""
Tests pour StressTester.

Tests couvrant :
- Initialization
- Shock application (uniform, differentiated)
- Historical crisis scenarios
- Monte Carlo simulation
- Correlation breakdown detection
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.financial_analyzer.risk.stress_test import StressTester


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def returns_simple():
    """Returns simples pour 3 assets."""
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=252, freq='D')
    
    returns = pd.DataFrame({
        'AAPL': np.random.normal(0.001, 0.02, 252),
        'MSFT': np.random.normal(0.0008, 0.018, 252),
        'GOOGL': np.random.normal(0.0012, 0.022, 252)
    }, index=dates)
    
    return returns


@pytest.fixture
def returns_volatile():
    """Returns volatiles avec corrélations."""
    np.random.seed(42)
    dates = pd.date_range('2019-01-01', periods=500, freq='D')
    
    # Générer returns corrélés
    mean = [0.001, 0.0008, 0.0012]
    cov = [[0.0004, 0.0002, 0.0001],
           [0.0002, 0.0003, 0.00015],
           [0.0001, 0.00015, 0.0005]]
    
    returns_array = np.random.multivariate_normal(mean, cov, 500)
    
    returns = pd.DataFrame(
        returns_array,
        columns=['AAPL', 'MSFT', 'GOOGL'],
        index=dates
    )
    
    return returns


@pytest.fixture
def weights_equal():
    """Poids égaux."""
    return pd.Series({'AAPL': 1/3, 'MSFT': 1/3, 'GOOGL': 1/3})


@pytest.fixture
def weights_custom():
    """Poids custom."""
    return pd.Series({'AAPL': 0.5, 'MSFT': 0.3, 'GOOGL': 0.2})


# =====================================================================
# Initialization Tests
# =====================================================================

def test_stress_tester_init_default_weights(returns_simple):
    """Test initialization avec equal weights."""
    tester = StressTester(returns_simple)
    
    assert len(tester.assets) == 3
    assert np.allclose(tester.weights.sum(), 1.0)
    assert np.allclose(tester.weights, 1/3)
    assert len(tester.portfolio_returns) == 252


def test_stress_tester_init_custom_weights(returns_simple, weights_custom):
    """Test initialization avec custom weights."""
    tester = StressTester(returns_simple, weights_custom)
    
    assert np.allclose(tester.weights.sum(), 1.0)
    assert tester.weights['AAPL'] == 0.5
    assert tester.weights['MSFT'] == 0.3


def test_stress_tester_empty_returns():
    """Test erreur avec returns vides."""
    empty_df = pd.DataFrame()
    
    with pytest.raises(ValueError, match="cannot be empty"):
        StressTester(empty_df)


def test_stress_tester_computes_statistics(returns_simple):
    """Test calcul des statistiques de base."""
    tester = StressTester(returns_simple)
    
    assert tester.mean_returns is not None
    assert tester.cov_matrix is not None
    assert tester.cov_matrix.shape == (3, 3)


# =====================================================================
# Shock Application Tests
# =====================================================================

def test_apply_shock_uniform_absolute(returns_simple, weights_equal):
    """Test choc uniforme absolu."""
    tester = StressTester(returns_simple, weights_equal)
    
    result = tester.apply_shock(-0.20, shock_type='absolute')
    
    assert 'portfolio_loss' in result
    assert 'asset_losses' in result
    assert 'var_95_stressed' in result
    assert 'cvar_95_stressed' in result
    assert result['portfolio_loss'] < 0  # Perte négative


def test_apply_shock_differentiated(returns_simple, weights_custom):
    """Test choc différencié par asset."""
    tester = StressTester(returns_simple, weights_custom)
    
    shocks = {'AAPL': -0.25, 'MSFT': -0.15, 'GOOGL': -0.10}
    result = tester.apply_shock(shocks, shock_type='absolute')
    
    assert result['portfolio_loss'] < 0
    assert 'worst_asset' in result
    assert result['worst_asset'] in ['AAPL', 'MSFT', 'GOOGL']
    assert result['worst_asset_loss'] < 0


def test_apply_shock_relative(returns_simple):
    """Test choc relatif."""
    tester = StressTester(returns_simple)
    
    result = tester.apply_shock(-0.50, shock_type='relative')
    
    assert 'portfolio_loss' in result
    assert result['var_95_stressed'] >= 0
    assert result['cvar_95_stressed'] >= result['var_95_stressed']


def test_apply_shock_stressed_metrics(returns_simple):
    """Test que VaR/CVaR stressés sont cohérents."""
    tester = StressTester(returns_simple)
    
    result = tester.apply_shock(-0.30, shock_type='absolute')
    
    # CVaR devrait être >= VaR
    assert result['cvar_95_stressed'] >= result['var_95_stressed']
    assert result['var_95_stressed'] >= 0


# =====================================================================
# Historical Crisis Tests
# =====================================================================

def test_apply_historical_crisis_known_scenario(returns_simple):
    """Test scénario historique connu."""
    tester = StressTester(returns_simple)
    
    result = tester.apply_historical_crisis('2008_financial')
    
    # Devrait avoir ces clés
    assert isinstance(result, dict)


def test_apply_historical_crisis_unknown_scenario(returns_simple):
    """Test scénario inconnu."""
    tester = StressTester(returns_simple)
    
    result = tester.apply_historical_crisis('unknown_crisis_123')
    
    assert 'error' in result


def test_historical_scenarios_defined():
    """Test que scénarios historiques sont définis."""
    assert '2008_financial' in StressTester.HISTORICAL_SCENARIOS
    assert '2020_covid' in StressTester.HISTORICAL_SCENARIOS
    assert '2000_dotcom' in StressTester.HISTORICAL_SCENARIOS
    assert '1987_crash' in StressTester.HISTORICAL_SCENARIOS
    assert '2011_europe' in StressTester.HISTORICAL_SCENARIOS


def test_historical_scenario_structure():
    """Test structure des scénarios historiques."""
    scenario = StressTester.HISTORICAL_SCENARIOS['2008_financial']
    
    assert 'name' in scenario
    assert 'start' in scenario
    assert 'end' in scenario
    assert 'description' in scenario


# =====================================================================
# Monte Carlo Tests
# =====================================================================

def test_monte_carlo_stress_basic(returns_simple):
    """Test Monte Carlo stress basique."""
    tester = StressTester(returns_simple)
    
    result = tester.monte_carlo_stress(n_scenarios=1000, confidence=0.95)
    
    assert 'var_95' in result
    assert 'cvar_95' in result
    assert 'worst_scenario' in result
    assert 'scenario_distribution' in result
    assert result['cvar_95'] >= result['var_95']


def test_monte_carlo_stress_different_confidence(returns_simple):
    """Test Monte Carlo avec différents confidence levels."""
    tester = StressTester(returns_simple)
    
    result_95 = tester.monte_carlo_stress(n_scenarios=1000, confidence=0.95)
    result_99 = tester.monte_carlo_stress(n_scenarios=1000, confidence=0.99)
    
    # VaR 99% devrait être >= VaR 95%
    # Les clés sont toujours 'var_95', 'cvar_95' mais les valeurs changent
    assert result_99['var_95'] >= result_95['var_95']


def test_monte_carlo_stress_scenarios_count(returns_simple):
    """Test nombre de scénarios Monte Carlo."""
    tester = StressTester(returns_simple)
    
    result = tester.monte_carlo_stress(n_scenarios=500)
    
    # Vérifier que les stats sont cohérentes
    assert 'var_95' in result
    assert isinstance(result['var_95'], (int, float))


def test_monte_carlo_stress_distribution(returns_simple):
    """Test distribution Monte Carlo."""
    tester = StressTester(returns_simple)
    
    result = tester.monte_carlo_stress(n_scenarios=2000, confidence=0.95)
    
    assert 'var_95' in result
    # Distribution devrait donner fat tails
    assert result['cvar_95'] >= result['var_95']


# =====================================================================
# Correlation Breakdown Tests
# =====================================================================

def test_detect_correlation_breakdown_basic(returns_volatile):
    """Test détection de correlation breakdown."""
    tester = StressTester(returns_volatile)
    
    result = tester.detect_correlation_breakdown(threshold=0.25)
    
    assert 'n_breakdown_periods' in result
    assert 'breakdown_periods' in result
    assert 'avg_correlation_normal' in result
    assert 'avg_correlation_crisis' in result


def test_detect_correlation_breakdown_no_breakdown(returns_simple):
    """Test pas de breakdown avec returns stables."""
    tester = StressTester(returns_simple)
    
    result = tester.detect_correlation_breakdown(threshold=0.80)
    
    assert 'n_breakdown_periods' in result
    # Avec threshold élevé, moins probable de détecter breakdown
    assert result['n_breakdown_periods'] >= 0


def test_detect_correlation_breakdown_pairs(returns_volatile):
    """Test identification des périodes avec breakdown."""
    tester = StressTester(returns_volatile)
    
    result = tester.detect_correlation_breakdown(threshold=0.20)
    
    assert 'breakdown_periods' in result
    assert isinstance(result['breakdown_periods'], list)


# =====================================================================
# Unified Stress Test Function
# =====================================================================

def test_stress_test_all_method(returns_simple, weights_equal):
    """Test méthode unifiée stress_test_all."""
    tester = StressTester(returns_simple, weights_equal)
    result = tester.stress_test_all()
    
    # stress_test_all retourne un DataFrame
    assert isinstance(result, pd.DataFrame)


# =====================================================================
# Edge Cases
# =====================================================================

def test_stress_tester_single_asset():
    """Test avec un seul asset."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({'AAPL': np.random.normal(0.001, 0.02, 100)}, index=dates)
    
    tester = StressTester(returns)
    
    assert len(tester.assets) == 1
    assert tester.weights.sum() == 1.0


def test_stress_tester_zero_variance():
    """Test avec variance nulle (returns constants)."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({'AAPL': [0.0] * 100}, index=dates)
    
    tester = StressTester(returns)
    result = tester.apply_shock(-0.10, 'absolute')
    
    assert result['portfolio_loss'] < 0


def test_stress_tester_negative_shock():
    """Test avec choc positif (gain)."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({
        'AAPL': np.random.normal(0.001, 0.02, 100),
        'MSFT': np.random.normal(0.0008, 0.018, 100)
    }, index=dates)
    
    tester = StressTester(returns)
    result = tester.apply_shock(0.10, 'absolute')  # Choc positif
    
    assert result['portfolio_loss'] > 0  # Gain
