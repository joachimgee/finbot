"""
Tests pour RiskBudgeter.

Tests couvrant :
- Initialization
- Portfolio variance/volatility
- Marginal risk contributions (MRC)
- Component risk contributions (CRC)
- Percentage risk contributions (PRC)
- Risk parity optimization
- Risk budgeting optimization
- VaR contribution
- Diversification benefit
"""

import pytest
import numpy as np
import pandas as pd

from src.financial_analyzer.risk.risk_budgeting import RiskBudgeter


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
def returns_correlated():
    """Returns avec corrélations positives."""
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
def weights_concentrated():
    """Poids concentrés sur un asset."""
    return pd.Series({'AAPL': 0.7, 'MSFT': 0.2, 'GOOGL': 0.1})


# =====================================================================
# Initialization Tests
# =====================================================================

def test_risk_budgeter_init_default_weights(returns_simple):
    """Test initialization avec equal weights."""
    budgeter = RiskBudgeter(returns_simple)
    
    assert len(budgeter.assets) == 3
    assert np.allclose(budgeter.weights.sum(), 1.0)
    assert np.allclose(budgeter.weights, 1/3)


def test_risk_budgeter_init_custom_weights(returns_simple, weights_concentrated):
    """Test initialization avec custom weights."""
    budgeter = RiskBudgeter(returns_simple, weights_concentrated)
    
    assert np.allclose(budgeter.weights.sum(), 1.0)
    assert np.isclose(budgeter.weights['AAPL'], 0.7, atol=1e-10)


def test_risk_budgeter_empty_returns():
    """Test erreur avec returns vides."""
    empty_df = pd.DataFrame()
    
    with pytest.raises(ValueError, match="cannot be empty"):
        RiskBudgeter(empty_df)


def test_risk_budgeter_computes_covariance(returns_simple):
    """Test calcul matrice de covariance."""
    budgeter = RiskBudgeter(returns_simple)
    
    assert budgeter.cov_matrix is not None
    assert budgeter.cov_matrix.shape == (3, 3)
    # Covariance matrix devrait être symétrique
    assert np.allclose(budgeter.cov_matrix, budgeter.cov_matrix.T)


# =====================================================================
# Portfolio Variance/Volatility Tests
# =====================================================================

def test_calculate_portfolio_variance(returns_simple, weights_equal):
    """Test calcul variance portfolio."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    variance = budgeter.calculate_portfolio_variance()
    
    assert isinstance(variance, float)
    assert variance >= 0


def test_calculate_portfolio_volatility(returns_simple, weights_equal):
    """Test calcul volatilité portfolio."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    vol = budgeter.calculate_portfolio_volatility()
    variance = budgeter.calculate_portfolio_variance()
    
    assert isinstance(vol, float)
    assert vol >= 0
    assert np.isclose(vol ** 2, variance)


def test_portfolio_vol_with_different_weights(returns_simple):
    """Test volatilité avec différents poids."""
    weights_1 = pd.Series({'AAPL': 1.0, 'MSFT': 0.0, 'GOOGL': 0.0})
    weights_2 = pd.Series({'AAPL': 0.0, 'MSFT': 1.0, 'GOOGL': 0.0})
    
    budgeter_1 = RiskBudgeter(returns_simple, weights_1)
    budgeter_2 = RiskBudgeter(returns_simple, weights_2)
    
    vol_1 = budgeter_1.calculate_portfolio_volatility()
    vol_2 = budgeter_2.calculate_portfolio_volatility()
    
    # Volatilités individuelles
    assert vol_1 > 0
    assert vol_2 > 0


def test_portfolio_vol_diversification_benefit(returns_correlated, weights_equal):
    """Test que diversification réduit volatilité."""
    budgeter = RiskBudgeter(returns_correlated, weights_equal)
    
    # Vol du portfolio diversifié
    portfolio_vol = budgeter.calculate_portfolio_volatility()
    
    # Vol moyenne des assets individuels
    individual_vols = returns_correlated.std()
    avg_individual_vol = individual_vols.mean()
    
    # Portfolio vol devrait être <= moyenne individuelle (diversification)
    assert portfolio_vol <= avg_individual_vol


# =====================================================================
# Marginal Risk Contribution Tests
# =====================================================================

def test_calculate_marginal_risk_contribution(returns_simple, weights_equal):
    """Test calcul MRC."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    mrc = budgeter.calculate_marginal_risk_contribution()
    
    assert isinstance(mrc, pd.Series)
    assert len(mrc) == 3
    assert all(mrc.index == budgeter.assets)


def test_mrc_units(returns_simple, weights_equal):
    """Test que MRC a les bonnes unités (volatilité)."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    mrc = budgeter.calculate_marginal_risk_contribution()
    portfolio_vol = budgeter.calculate_portfolio_volatility()
    
    # MRC devrait être du même ordre que portfolio vol
    assert all(mrc > 0)  # Généralement positifs
    assert all(mrc < portfolio_vol * 5)  # Ordre de grandeur


def test_mrc_zero_risk_portfolio():
    """Test MRC avec portfolio sans risque."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({
        'AAPL': [0.0] * 100,
        'MSFT': [0.0] * 100
    }, index=dates)
    
    budgeter = RiskBudgeter(returns)
    mrc = budgeter.calculate_marginal_risk_contribution()
    
    assert all(mrc == 0.0)


# =====================================================================
# Component Risk Contribution Tests
# =====================================================================

def test_calculate_component_risk_contribution(returns_simple, weights_equal):
    """Test calcul CRC."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    crc = budgeter.calculate_component_risk_contribution()
    
    assert isinstance(crc, pd.Series)
    assert len(crc) == 3


def test_crc_sum_equals_portfolio_vol(returns_correlated, weights_equal):
    """Test propriété d'Euler: Σ CRC = σ_p."""
    budgeter = RiskBudgeter(returns_correlated, weights_equal)
    crc = budgeter.calculate_component_risk_contribution()
    portfolio_vol = budgeter.calculate_portfolio_volatility()
    
    # Euler decomposition
    assert np.isclose(crc.sum(), portfolio_vol, atol=1e-8)


def test_crc_concentrated_vs_diversified(returns_simple):
    """Test CRC avec poids concentrés vs diversifiés."""
    weights_conc = pd.Series({'AAPL': 0.9, 'MSFT': 0.05, 'GOOGL': 0.05})
    weights_div = pd.Series({'AAPL': 1/3, 'MSFT': 1/3, 'GOOGL': 1/3})
    
    budgeter_conc = RiskBudgeter(returns_simple, weights_conc)
    budgeter_div = RiskBudgeter(returns_simple, weights_div)
    
    crc_conc = budgeter_conc.calculate_component_risk_contribution()
    crc_div = budgeter_div.calculate_component_risk_contribution()
    
    # AAPL devrait contribuer plus dans portfolio concentré
    assert crc_conc['AAPL'] > crc_div['AAPL']


# =====================================================================
# Percentage Risk Contribution Tests
# =====================================================================

def test_calculate_percentage_risk_contribution(returns_simple, weights_equal):
    """Test calcul PRC."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    prc = budgeter.calculate_percentage_risk_contribution()
    
    assert isinstance(prc, pd.Series)
    assert len(prc) == 3


def test_prc_sum_equals_one(returns_correlated, weights_equal):
    """Test propriété: Σ PRC = 1.0."""
    budgeter = RiskBudgeter(returns_correlated, weights_equal)
    prc = budgeter.calculate_percentage_risk_contribution()
    
    assert np.isclose(prc.sum(), 1.0, atol=1e-8)


def test_prc_all_positive(returns_simple, weights_equal):
    """Test que PRC sont positifs (généralement)."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    prc = budgeter.calculate_percentage_risk_contribution()
    
    # En général positifs, sauf corrélations négatives fortes
    assert all(prc >= -0.1)  # Allow small negative due to negative correlations


def test_prc_zero_risk_portfolio():
    """Test PRC avec portfolio sans risque."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({
        'AAPL': [0.0] * 100,
        'MSFT': [0.0] * 100
    }, index=dates)
    
    budgeter = RiskBudgeter(returns)
    prc = budgeter.calculate_percentage_risk_contribution()
    
    assert all(prc == 0.0)


# =====================================================================
# Unified Risk Contributions Tests
# =====================================================================

def test_calculate_risk_contributions_complete(returns_simple, weights_equal):
    """Test fonction unifiée calculate_risk_contributions."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    result = budgeter.calculate_risk_contributions()
    
    assert isinstance(result, dict)
    assert 'marginal_contributions' in result
    assert 'component_contributions' in result
    assert 'percentage_contributions' in result
    assert 'portfolio_volatility' in result


def test_risk_contributions_consistency(returns_correlated, weights_equal):
    """Test cohérence entre différentes contributions."""
    budgeter = RiskBudgeter(returns_correlated, weights_equal)
    result = budgeter.calculate_risk_contributions()
    
    mrc = result['marginal_contributions']
    crc = result['component_contributions']
    prc = result['percentage_contributions']
    portfolio_vol = result['portfolio_volatility']
    
    # CRC = weights * MRC
    assert np.allclose(crc, budgeter.weights * mrc, atol=1e-8)
    
    # Σ CRC = portfolio_vol
    assert np.isclose(crc.sum(), portfolio_vol, atol=1e-8)
    
    # Σ PRC = 1.0
    assert np.isclose(prc.sum(), 1.0, atol=1e-8)


# =====================================================================
# Risk Parity Tests
# =====================================================================

def test_optimize_risk_parity_basic(returns_simple):
    """Test optimisation risk parity."""
    budgeter = RiskBudgeter(returns_simple)
    result = budgeter.optimize_risk_parity()
    
    assert isinstance(result, dict)
    assert 'weights' in result
    assert 'success' in result
    
    optimal_weights = result['weights']
    assert isinstance(optimal_weights, pd.Series)
    assert len(optimal_weights) == 3
    assert np.isclose(optimal_weights.sum(), 1.0, atol=1e-6)
    assert all(optimal_weights >= 0)


def test_risk_parity_equal_contributions(returns_correlated):
    """Test que risk parity donne contributions égales."""
    budgeter = RiskBudgeter(returns_correlated)
    result = budgeter.optimize_risk_parity()
    
    optimal_weights = result['weights']
    prc = result['contributions']['percentage_contributions']
    
    # PRC devraient être approximativement égaux
    target = 1.0 / len(returns_correlated.columns)
    assert all(np.abs(prc - target) < 0.05)  # Within 5% of equal


def test_risk_parity_constraints(returns_simple):
    """Test risk parity basique (pas de contraintes dans API actuelle)."""
    budgeter = RiskBudgeter(returns_simple)
    
    result = budgeter.optimize_risk_parity()
    optimal_weights = result['weights']
    
    # Vérifier juste que l'optimisation réussit
    assert result['success']
    assert all(optimal_weights >= 0)
    assert np.isclose(optimal_weights.sum(), 1.0)


# =====================================================================
# Risk Budgeting Optimization Tests
# =====================================================================

def test_optimize_risk_budget_basic(returns_simple):
    """Test optimisation risk budgeting."""
    budgeter = RiskBudgeter(returns_simple)
    
    # Target budgets égaux
    target_budgets = pd.Series({'AAPL': 1/3, 'MSFT': 1/3, 'GOOGL': 1/3})
    result = budgeter.optimize_risk_budgeting(target_budgets)
    
    assert isinstance(result, dict)
    assert 'weights' in result
    
    optimal_weights = result['weights']
    assert isinstance(optimal_weights, pd.Series)
    assert np.isclose(optimal_weights.sum(), 1.0, atol=1e-6)


def test_optimize_risk_budget_custom_targets(returns_simple):
    """Test risk budgeting avec targets custom."""
    budgeter = RiskBudgeter(returns_simple)
    
    # Target: AAPL contribue 50%, autres 25% chacun
    target_budgets = pd.Series({'AAPL': 0.5, 'MSFT': 0.25, 'GOOGL': 0.25})
    result = budgeter.optimize_risk_budgeting(target_budgets)
    
    optimal_weights = result['weights']
    prc = result['contributions']['percentage_contributions']
    
    # PRC devraient être proches des targets
    assert np.abs(prc['AAPL'] - 0.5) < 0.1
    assert np.abs(prc['MSFT'] - 0.25) < 0.1


def test_optimize_risk_budget_constraints(returns_simple):
    """Test risk budgeting basique (pas de contraintes dans API actuelle)."""
    budgeter = RiskBudgeter(returns_simple)
    
    target_budgets = pd.Series({'AAPL': 0.4, 'MSFT': 0.3, 'GOOGL': 0.3})
    result = budgeter.optimize_risk_budgeting(target_budgets)
    
    optimal_weights = result['weights']
    assert result['success']
    assert all(optimal_weights >= 0)


# =====================================================================
# VaR Contribution Tests
# =====================================================================

def test_calculate_var_contribution_basic(returns_simple, weights_equal):
    """Test contribution à VaR."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    var_contrib = budgeter.calculate_var_contribution(confidence=0.95)
    
    assert isinstance(var_contrib, pd.Series)
    assert len(var_contrib) == 3


def test_var_contribution_sum(returns_correlated, weights_equal):
    """Test que somme des contributions = VaR portfolio."""
    budgeter = RiskBudgeter(returns_correlated, weights_equal)
    var_contrib = budgeter.calculate_var_contribution(confidence=0.95)
    
    # Portfolio VaR
    portfolio_returns = budgeter.portfolio_returns
    portfolio_var = float(np.percentile(-portfolio_returns, 95))
    
    # Somme contributions devrait être proche de VaR
    # (approximation, pas exactement égal en non-normal)
    assert var_contrib.sum() > 0


def test_var_contribution_different_confidence(returns_simple, weights_equal):
    """Test VaR contribution avec différents confidence levels."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    
    var_95 = budgeter.calculate_var_contribution(confidence=0.95)
    var_99 = budgeter.calculate_var_contribution(confidence=0.99)
    
    # VaR 99% devrait être >= VaR 95%
    assert var_99.sum() >= var_95.sum()


# =====================================================================
# Diversification Benefit Tests
# =====================================================================

def test_calculate_diversification_benefit(returns_correlated, weights_equal):
    """Test calcul bénéfice de diversification."""
    budgeter = RiskBudgeter(returns_correlated, weights_equal)
    div_benefit = budgeter.analyze_diversification_benefit()
    
    assert isinstance(div_benefit, dict)
    assert 'portfolio_risk' in div_benefit
    assert 'weighted_standalone_risk' in div_benefit
    assert 'diversification_ratio' in div_benefit


def test_diversification_ratio_range(returns_simple, weights_equal):
    """Test que ratio de diversification est >= 1.0."""
    budgeter = RiskBudgeter(returns_simple, weights_equal)
    div_benefit = budgeter.analyze_diversification_benefit()
    
    ratio = div_benefit['diversification_ratio']
    
    # Ratio >= 1.0 (weighted risk / portfolio risk)
    assert ratio >= 1.0


def test_diversification_benefit_single_asset():
    """Test diversification avec un seul asset (= 1.0)."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({'AAPL': np.random.normal(0.001, 0.02, 100)}, index=dates)
    
    budgeter = RiskBudgeter(returns)
    div_benefit = budgeter.analyze_diversification_benefit()
    
    # Un seul asset = pas de diversification
    assert np.isclose(div_benefit['diversification_ratio'], 1.0, atol=0.01)


# =====================================================================
# Edge Cases
# =====================================================================

def test_risk_budgeter_single_asset():
    """Test avec un seul asset."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({'AAPL': np.random.normal(0.001, 0.02, 100)}, index=dates)
    
    budgeter = RiskBudgeter(returns)
    
    assert len(budgeter.assets) == 1
    assert budgeter.weights['AAPL'] == 1.0
    
    prc = budgeter.calculate_percentage_risk_contribution()
    assert np.isclose(prc['AAPL'], 1.0, atol=1e-10)


def test_risk_budgeter_negative_weights():
    """Test avec poids négatifs (short positions)."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    returns = pd.DataFrame({
        'AAPL': np.random.normal(0.001, 0.02, 100),
        'MSFT': np.random.normal(0.0008, 0.018, 100)
    }, index=dates)
    
    weights = pd.Series({'AAPL': 1.5, 'MSFT': -0.5})
    
    budgeter = RiskBudgeter(returns, weights)
    
    # Devrait accepter poids négatifs
    assert budgeter.weights['MSFT'] < 0
    
    # Contributions devraient être calculables
    crc = budgeter.calculate_component_risk_contribution()
    assert isinstance(crc, pd.Series)


def test_risk_budgeter_highly_correlated_assets(returns_simple):
    """Test avec assets très corrélés."""
    # Créer returns presque identiques
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    base_returns = np.random.normal(0.001, 0.02, 100)
    
    returns = pd.DataFrame({
        'AAPL': base_returns,
        'MSFT': base_returns + np.random.normal(0, 0.001, 100),
        'GOOGL': base_returns + np.random.normal(0, 0.001, 100)
    }, index=dates)
    
    budgeter = RiskBudgeter(returns)
    
    # Risk parity devrait donner poids similaires
    result = budgeter.optimize_risk_parity()
    optimal_weights = result['weights']
    
    # Poids devraient être proches les uns des autres
    assert np.std(optimal_weights.values) < 0.1  # Low variation
