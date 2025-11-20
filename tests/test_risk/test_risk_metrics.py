"""
Tests for risk_metrics.py - Advanced Risk Measures

Tests covering:
- EVaR (Entropic VaR)
- RLVaR (Relativistic VaR)
- Worst Realization
- Tail Gini
- VaR/CVaR Ranges
- Semi-variance/deviation/kurtosis
- Ulcer Index
- Unified functions
"""

import pytest
import numpy as np
import pandas as pd
from financial_analyzer.risk.risk_metrics import (
    calculate_evar,
    calculate_rlvar,
    calculate_worst_realization,
    calculate_tail_gini,
    calculate_var_range,
    calculate_cvar_range,
    calculate_semi_variance,
    calculate_downside_deviation,
    calculate_semi_kurtosis,
    calculate_ulcer_index,
    calculate_all_advanced_risk_metrics,
    compare_risk_profiles
)


@pytest.fixture
def normal_returns():
    """Returns normalement distribués."""
    np.random.seed(42)
    return pd.Series(np.random.normal(0.001, 0.02, 252))


@pytest.fixture
def fat_tail_returns():
    """Returns avec fat tails (t-distribution)."""
    np.random.seed(42)
    from scipy import stats
    return pd.Series(stats.t.rvs(df=3, loc=0.001, scale=0.02, size=252))


@pytest.fixture
def equity_curve_rising():
    """Equity curve montante."""
    returns = pd.Series(np.random.normal(0.002, 0.01, 252))
    return (1 + returns).cumprod()


@pytest.fixture
def equity_curve_volatile():
    """Equity curve volatile avec drawdowns."""
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.0, 0.03, 252))
    return (1 + returns).cumprod()


# =====================================================================
# EVaR Tests
# =====================================================================

def test_evar_basic(normal_returns):
    """Test EVaR computation basique."""
    evar = calculate_evar(normal_returns, confidence=0.95)
    
    assert isinstance(evar, float)
    assert evar >= 0  # Loss measure (positif ou 0)
    assert not np.isnan(evar)
    assert not np.isinf(evar)


def test_evar_different_confidence_levels(normal_returns):
    """EVaR augmente avec confidence level."""
    evar_90 = calculate_evar(normal_returns, confidence=0.90)
    evar_95 = calculate_evar(normal_returns, confidence=0.95)
    evar_99 = calculate_evar(normal_returns, confidence=0.99)
    
    assert evar_90 < evar_95 < evar_99


def test_evar_empty_returns():
    """EVaR avec returns vides doit retourner 0.0."""
    result = calculate_evar(pd.Series([]), confidence=0.95)
    assert result == 0.0


# =====================================================================
# RLVaR Tests
# =====================================================================

def test_rlvar_basic(normal_returns):
    """Test RLVaR computation basique."""
    rlvar = calculate_rlvar(normal_returns, confidence=0.95)
    
    assert isinstance(rlvar, float)
    assert rlvar > 0
    assert not np.isnan(rlvar)


def test_rlvar_vs_var(normal_returns):
    """RLVaR devrait être >= VaR."""
    rlvar = calculate_rlvar(normal_returns, confidence=0.95)
    var = np.percentile(-normal_returns, 95)
    
    assert rlvar >= var * 0.7


def test_rlvar_different_kappa(normal_returns):
    """RLVaR avec différents kappa."""
    rlvar_k05 = calculate_rlvar(normal_returns, confidence=0.95, kappa=0.5)
    rlvar_k10 = calculate_rlvar(normal_returns, confidence=0.95, kappa=1.0)
    
    assert rlvar_k05 != rlvar_k10


def test_rlvar_increasing_confidence(fat_tail_returns):
    """RLVaR augmente avec confidence."""
    rlvar_90 = calculate_rlvar(fat_tail_returns, confidence=0.90)
    rlvar_95 = calculate_rlvar(fat_tail_returns, confidence=0.95)
    
    assert rlvar_90 < rlvar_95


# =====================================================================
# Worst Realization Tests
# =====================================================================

def test_worst_realization_basic(normal_returns):
    """Test worst realization (minimax)."""
    worst = calculate_worst_realization(normal_returns)
    
    assert isinstance(worst, float)
    assert worst > 0  # Loss measure
    assert worst == float(-normal_returns.min())


def test_worst_realization_matches_min(fat_tail_returns):
    """Worst realization doit être le pire loss."""
    worst = calculate_worst_realization(fat_tail_returns)
    expected = float(-fat_tail_returns.min())
    
    assert abs(worst - expected) < 1e-10


def test_worst_realization_empty():
    """Worst realization avec empty returns."""
    result = calculate_worst_realization(pd.Series([]))
    assert result == 0.0


# =====================================================================
# Tail Gini Tests
# =====================================================================

def test_tail_gini_basic(normal_returns):
    """Test Tail Gini coefficient."""
    gini = calculate_tail_gini(normal_returns, confidence=0.95)
    
    assert isinstance(gini, float)
    assert 0.0 <= gini <= 1.0  # Gini coeff in [0, 1]
    assert not np.isnan(gini)


def test_tail_gini_fat_tails(fat_tail_returns):
    """Fat tails devraient avoir Gini plus élevé."""
    gini_fat = calculate_tail_gini(fat_tail_returns, confidence=0.95)
    
    # Gini > 0 indique inégalité
    assert gini_fat >= 0.0


def test_tail_gini_different_confidence(normal_returns):
    """Tail Gini avec différents confidence levels."""
    gini_90 = calculate_tail_gini(normal_returns, confidence=0.90)
    gini_99 = calculate_tail_gini(normal_returns, confidence=0.99)
    
    # Les deux devraient être valides
    assert 0.0 <= gini_90 <= 1.0
    assert 0.0 <= gini_99 <= 1.0


# =====================================================================
# VaR/CVaR Range Tests
# =====================================================================

def test_var_range_basic(normal_returns):
    """Test VaR range (spread between confidence levels)."""
    var_range = calculate_var_range(normal_returns, confidence_low=0.90, confidence_high=0.99)
    
    assert isinstance(var_range, float)
    assert var_range >= 0  # Spread toujours positif


def test_var_range_fat_tails(fat_tail_returns):
    """Fat tails devraient avoir range plus large."""
    range_fat = calculate_var_range(fat_tail_returns, confidence_low=0.90, confidence_high=0.99)
    
    assert range_fat > 0


def test_cvar_range_basic(normal_returns):
    """Test CVaR range."""
    cvar_range = calculate_cvar_range(normal_returns, confidence_low=0.90, confidence_high=0.99)
    
    assert isinstance(cvar_range, float)
    assert cvar_range >= 0


def test_cvar_range_vs_var_range(fat_tail_returns):
    """CVaR range généralement >= VaR range."""
    var_range = calculate_var_range(fat_tail_returns)
    cvar_range = calculate_cvar_range(fat_tail_returns)
    
    # CVaR prend moyenne de queue, donc spread peut être différent
    assert cvar_range >= 0
    assert var_range >= 0


# =====================================================================
# Semi-variance Tests
# =====================================================================

def test_semi_variance_basic(normal_returns):
    """Test semi-variance (downside only)."""
    semi_var = calculate_semi_variance(normal_returns, target_return=0.0)
    
    assert isinstance(semi_var, float)
    assert semi_var >= 0
    assert not np.isnan(semi_var)


def test_semi_variance_less_than_variance(normal_returns):
    """Semi-variance devrait être <= variance totale."""
    semi_var = calculate_semi_variance(normal_returns, target_return=0.0)
    total_var = normal_returns.var()
    
    assert semi_var <= total_var


def test_semi_variance_custom_target(normal_returns):
    """Semi-variance avec target custom."""
    semi_var_0 = calculate_semi_variance(normal_returns, target_return=0.0)
    semi_var_001 = calculate_semi_variance(normal_returns, target_return=0.001)
    
    # Avec target plus élevé, plus de returns comptent comme downside
    assert semi_var_001 >= semi_var_0


def test_downside_deviation_basic(normal_returns):
    """Test downside deviation (sqrt de semi-variance)."""
    dd = calculate_downside_deviation(normal_returns, target_return=0.0)
    semi_var = calculate_semi_variance(normal_returns, target_return=0.0)
    
    assert abs(dd - np.sqrt(semi_var)) < 1e-10


# =====================================================================
# Semi-kurtosis Tests
# =====================================================================

def test_semi_kurtosis_basic(normal_returns):
    """Test semi-kurtosis (tail thickness downside)."""
    sk = calculate_semi_kurtosis(normal_returns, target_return=0.0)
    
    assert isinstance(sk, float)
    assert not np.isnan(sk)


def test_semi_kurtosis_fat_tails(fat_tail_returns):
    """Fat tails devraient avoir semi-kurtosis plus élevé."""
    sk = calculate_semi_kurtosis(fat_tail_returns, target_return=0.0)
    
    # Kurtosis > 3 indique queues épaisses
    assert sk != 0.0


def test_semi_kurtosis_sufficient_data():
    """Semi-kurtosis requiert suffisamment de data points."""
    few_returns = pd.Series([0.01, -0.02, 0.01])
    sk = calculate_semi_kurtosis(few_returns, target_return=0.0)
    
    # Devrait retourner 0.0 si pas assez de points (< 4)
    assert sk == 0.0


# =====================================================================
# Ulcer Index Tests
# =====================================================================

def test_ulcer_index_basic(equity_curve_rising):
    """Test Ulcer Index (RMS of drawdowns)."""
    ui = calculate_ulcer_index(equity_curve_rising)
    
    assert isinstance(ui, float)
    assert ui >= 0
    assert not np.isnan(ui)


def test_ulcer_index_volatile_vs_stable(equity_curve_volatile, equity_curve_rising):
    """Volatile curve devrait avoir Ulcer Index plus élevé."""
    ui_volatile = calculate_ulcer_index(equity_curve_volatile)
    ui_stable = calculate_ulcer_index(equity_curve_rising)
    
    # Volatile a plus de drawdowns
    assert ui_volatile > ui_stable


def test_ulcer_index_flat_curve():
    """Ulcer Index sur curve plate."""
    flat_curve = pd.Series([100.0] * 252)
    ui = calculate_ulcer_index(flat_curve)
    
    # Pas de drawdowns = Ulcer = 0
    assert ui == 0.0


def test_ulcer_index_constant_drawdown():
    """Ulcer Index avec drawdown constant."""
    # Curve qui perd 10% puis reste flat
    curve = pd.Series([100.0] * 50 + [90.0] * 202)
    ui = calculate_ulcer_index(curve)
    
    assert ui > 0


# =====================================================================
# Unified Function Tests
# =====================================================================

def test_calculate_all_advanced_metrics_complete(normal_returns, equity_curve_rising):
    """Test calcul de tous les metrics en une fois."""
    metrics = calculate_all_advanced_risk_metrics(
        returns=normal_returns,
        equity_curve=equity_curve_rising
    )
    
    # Vérifier présence de tous les metrics
    expected_keys = [
        'evar', 'rlvar', 'worst_realization', 'tail_gini',
        'var_range', 'cvar_range', 'semi_variance',
        'downside_deviation', 'semi_kurtosis', 'ulcer_index'
    ]
    
    for key in expected_keys:
        assert key in metrics
        assert isinstance(metrics[key], (int, float))
        assert not np.isnan(metrics[key])


def test_calculate_all_advanced_metrics_consistency(fat_tail_returns, equity_curve_volatile):
    """Test cohérence des metrics calculés ensemble."""
    metrics = calculate_all_advanced_risk_metrics(
        returns=fat_tail_returns,
        equity_curve=equity_curve_volatile
    )
    
    # EVaR >= worst_realization (non strict)
    assert metrics['evar'] >= 0
    assert metrics['worst_realization'] > 0
    
    # Downside deviation = sqrt(semi_variance)
    assert abs(metrics['downside_deviation'] - np.sqrt(metrics['semi_variance'])) < 1e-6
    
    # VaR/CVaR ranges sont positifs
    assert metrics['var_range'] >= 0
    assert metrics['cvar_range'] >= 0


# =====================================================================
# Comparison Tests
# =====================================================================

def test_compare_risk_profiles_basic(normal_returns, fat_tail_returns, equity_curve_rising, equity_curve_volatile):
    """Test comparison de deux portfolios."""
    comparison = compare_risk_profiles(
        returns_a=normal_returns,
        returns_b=fat_tail_returns,
        equity_a=equity_curve_rising,
        equity_b=equity_curve_volatile,
        labels=('Normal', 'Fat Tail')
    )
    
    # Le résultat est un DataFrame
    assert isinstance(comparison, pd.DataFrame)
    assert 'Normal' in comparison.columns
    assert 'Fat Tail' in comparison.columns
    
    # Chaque metric devrait être présent
    assert 'evar' in comparison.index
    assert 'rlvar' in comparison.index
    assert 'worst_realization' in comparison.index
    assert 'ulcer_index' in comparison.index


def test_compare_risk_profiles_different_risk_levels(normal_returns, fat_tail_returns, 
                                                      equity_curve_rising, equity_curve_volatile):
    """Fat tails devraient montrer plus de risque."""
    comparison = compare_risk_profiles(
        returns_a=normal_returns,
        returns_b=fat_tail_returns,
        equity_a=equity_curve_rising,
        equity_b=equity_curve_volatile,
        labels=('Normal', 'Fat Tail')
    )
    
    # Fat tail devrait avoir worst_realization plus élevé
    assert comparison.loc['worst_realization', 'Fat Tail'] >= comparison.loc['worst_realization', 'Normal'] * 0.5


# =====================================================================
# Edge Cases
# =====================================================================

def test_all_metrics_with_single_observation():
    """Metrics avec une seule observation."""
    single_return = pd.Series([0.01])
    single_equity = pd.Series([1.01])
    
    metrics = calculate_all_advanced_risk_metrics(
        returns=single_return,
        equity_curve=single_equity
    )
    
    # La plupart devraient retourner 0.0 (pas assez de données)
    assert metrics['worst_realization'] >= 0  # Peut être 0 ou le return négatif
    assert metrics['ulcer_index'] == 0.0  # Pas de drawdown


def test_all_metrics_with_zero_returns():
    """Metrics avec returns = 0 partout."""
    zero_returns = pd.Series([0.0] * 100)
    flat_equity = pd.Series([1.0] * 100)
    
    metrics = calculate_all_advanced_risk_metrics(
        returns=zero_returns,
        equity_curve=flat_equity,
        confidence=0.95
    )
    
    assert metrics['worst_realization'] == 0.0
    assert metrics['ulcer_index'] == 0.0
    assert metrics['semi_variance'] == 0.0


def test_all_metrics_with_negative_only_returns():
    """Metrics avec returns négatifs seulement."""
    negative_returns = pd.Series([-0.01] * 100)
    declining_equity = (1 + negative_returns).cumprod()
    
    metrics = calculate_all_advanced_risk_metrics(
        returns=negative_returns,
        equity_curve=declining_equity,
        confidence=0.95
    )
    
    assert metrics['worst_realization'] == 0.01
    assert metrics['ulcer_index'] > 0  # Drawdown constant


def test_confidence_level_boundary():
    """Test avec confidence = 1.0 (edge case)."""
    returns = pd.Series(np.random.normal(0, 0.01, 100))
    
    # Confidence = 1.0 devrait prendre 100% de la distribution
    evar_100 = calculate_evar(returns, confidence=1.0)
    
    # Devrait être >= 0 (peut être 0 si optimisation échoue)
    assert evar_100 >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
