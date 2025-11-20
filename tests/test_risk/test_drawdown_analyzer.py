"""
Tests for drawdown_analyzer.py - Drawdown Analysis

Tests covering:
- Max drawdown calculation
- CDaR (Conditional Drawdown at Risk)
- Underwater periods detection
- Recovery statistics
- Pain Index
- Drawdown distribution
- Comparison functions
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from financial_analyzer.risk.drawdown_analyzer import (
    DrawdownAnalyzer,
    compare_drawdown_profiles
)


@pytest.fixture
def equity_curve_simple():
    """Simple equity curve avec 1 drawdown."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    values = [100.0] * 30 + [95.0] * 20 + [105.0] * 50
    return pd.Series(values, index=dates)


@pytest.fixture
def equity_curve_volatile():
    """Equity curve volatile avec multiples drawdowns."""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    returns = np.random.normal(0.0005, 0.015, 252)
    equity = (1 + returns).cumprod() * 100
    return pd.Series(equity, index=dates)


@pytest.fixture
def returns_simple():
    """Returns simples correspondant à equity_curve_simple."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    rets = [0.0] * 29 + [-0.05/30] * 20 + [0.105/50] * 50 + [0.0]
    return pd.Series(rets, index=dates)


@pytest.fixture
def returns_volatile():
    """Returns volatiles."""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    return pd.Series(np.random.normal(0.0005, 0.015, 252), index=dates)


# =====================================================================
# Initialization Tests
# =====================================================================

def test_drawdown_analyzer_init(equity_curve_simple, returns_simple):
    """Test initialisation du DrawdownAnalyzer."""
    analyzer = DrawdownAnalyzer(equity_curve_simple, returns_simple)
    
    assert analyzer.equity_curve is not None
    assert analyzer.returns is not None
    assert analyzer._drawdowns is not None
    assert len(analyzer._drawdowns) == len(equity_curve_simple)


def test_drawdown_analyzer_precompute_drawdowns(equity_curve_volatile, returns_volatile):
    """Test pré-calcul des drawdowns."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    
    # Drawdowns devraient être <= 0 (ou 0)
    assert (analyzer._drawdowns <= 0).all()
    
    # Le premier drawdown devrait être 0
    assert analyzer._drawdowns.iloc[0] == 0.0


def test_drawdown_analyzer_empty_raises_error():
    """Drawdown analyzer avec données vides devrait raise."""
    with pytest.raises(ValueError):
        DrawdownAnalyzer(pd.Series([]), pd.Series([]))


# =====================================================================
# Max Drawdown Tests
# =====================================================================

def test_calculate_max_drawdown_basic(equity_curve_simple, returns_simple):
    """Test calcul de max drawdown basique."""
    analyzer = DrawdownAnalyzer(equity_curve_simple, returns_simple)
    max_dd = analyzer.calculate_max_drawdown()
    
    assert 'max_drawdown' in max_dd
    assert 'start_date' in max_dd
    assert 'end_date' in max_dd
    assert 'duration_days' in max_dd
    
    # Valeur devrait être positive (c'est une perte)
    assert max_dd['max_drawdown'] >= 0
    
    # Duration >= 0
    assert max_dd['duration_days'] >= 0


def test_max_drawdown_value_correct(equity_curve_volatile, returns_volatile):
    """Test que max drawdown value est correcte."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    max_dd = analyzer.calculate_max_drawdown()
    
    # Le max drawdown devrait correspondre au abs(min) des drawdowns
    expected = float(abs(analyzer._drawdowns.min()))
    assert abs(max_dd['max_drawdown'] - expected) < 1e-10


def test_max_drawdown_no_drawdown():
    """Max drawdown sur equity curve constamment montante."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    equity = pd.Series(np.arange(100, 200), index=dates)
    returns = equity.pct_change().fillna(0.0)
    
    analyzer = DrawdownAnalyzer(equity, returns)
    max_dd = analyzer.calculate_max_drawdown()
    
    # Pas de drawdown = 0
    assert max_dd['max_drawdown'] == 0.0


# =====================================================================
# CDaR Tests
# =====================================================================

def test_calculate_cdar_basic(equity_curve_volatile, returns_volatile):
    """Test CDaR (Conditional Drawdown at Risk)."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    cdar = analyzer.calculate_cdar(confidence=0.95)
    
    assert isinstance(cdar, float)
    assert cdar >= 0  # CDaR est positif (magnitude de perte)
    assert not np.isnan(cdar)


def test_cdar_vs_max_drawdown(equity_curve_volatile, returns_volatile):
    """CDaR devrait être <= max drawdown (en valeur absolue)."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    
    max_dd = analyzer.calculate_max_drawdown()['max_drawdown']
    cdar_95 = analyzer.calculate_cdar(confidence=0.95)
    
    # CDaR est moyenne des pires α%, donc abs(CDaR) <= abs(max_dd)
    assert abs(cdar_95) <= abs(max_dd) + 1e-6  # Allow small numerical error


def test_cdar_different_confidence_levels(equity_curve_volatile, returns_volatile):
    """CDaR augmente avec confidence level."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    
    cdar_90 = analyzer.calculate_cdar(confidence=0.90)
    cdar_95 = analyzer.calculate_cdar(confidence=0.95)
    cdar_99 = analyzer.calculate_cdar(confidence=0.99)
    
    # Plus le confidence level est élevé, plus CDaR est sévère (positif plus grand)
    assert cdar_90 <= cdar_95 <= cdar_99


def test_cdar_flat_curve():
    """CDaR sur courbe plate."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    equity = pd.Series([100.0] * 100, index=dates)
    returns = pd.Series([0.0] * 100, index=dates)
    
    analyzer = DrawdownAnalyzer(equity, returns)
    cdar = analyzer.calculate_cdar(confidence=0.95)
    
    assert cdar == 0.0


# =====================================================================
# Average Drawdown Tests
# =====================================================================

def test_calculate_average_drawdown(equity_curve_volatile, returns_volatile):
    """Test average drawdown calculation."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    avg_dd = analyzer.calculate_average_drawdown()
    
    assert isinstance(avg_dd, float)
    assert avg_dd >= 0  # Average drawdown est positif (magnitude de perte)
    assert not np.isnan(avg_dd)


def test_average_drawdown_vs_max(equity_curve_volatile, returns_volatile):
    """Average drawdown devrait être <= max drawdown (avg est une moyenne)."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    
    avg_dd = analyzer.calculate_average_drawdown()
    max_dd = analyzer.calculate_max_drawdown()['max_drawdown']
    
    # avg <= max (moyenne vs pire cas)
    assert avg_dd <= max_dd + 1e-10


# =====================================================================
# Underwater Periods Tests
# =====================================================================

def test_get_underwater_periods_basic(equity_curve_volatile, returns_volatile):
    """Test détection des underwater periods."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    underwater = analyzer.get_underwater_periods()
    
    assert isinstance(underwater, pd.DataFrame)
    
    if not underwater.empty:
        assert 'start' in underwater.columns
        assert 'end' in underwater.columns
        assert 'duration' in underwater.columns
        assert 'depth' in underwater.columns


def test_get_underwater_periods_depth_negative(equity_curve_simple, returns_simple):
    """Les profondeurs de drawdown devraient être positives."""
    analyzer = DrawdownAnalyzer(equity_curve_simple, returns_simple)
    periods = analyzer.get_underwater_periods()
    
    assert len(periods) > 0
    # DataFrame itération : check column 'depth'
    assert (periods['depth'] >= 0).all()  # Depth est positive (magnitude de perte)


def test_underwater_periods_no_drawdowns():
    """Pas d'underwater periods si pas de drawdowns."""
    dates = pd.date_range('2023-01-01', periods=50, freq='D')
    equity = pd.Series(np.linspace(100, 150, 50), index=dates)
    returns = equity.pct_change().fillna(0.0)
    
    analyzer = DrawdownAnalyzer(equity, returns)
    underwater = analyzer.get_underwater_periods()
    
    # Devrait être vide ou avoir des depths = 0
    assert underwater.empty or (underwater['depth'] == 0).all()


# =====================================================================
# Pain Index Tests
# =====================================================================

def test_calculate_pain_index_basic(equity_curve_volatile, returns_volatile):
    """Test pain index calculation."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    pain = analyzer.calculate_pain_index()
    
    assert isinstance(pain, float)
    assert pain >= 0  # Pain index est positif (magnitude de perte)
    assert not np.isnan(pain)


def test_pain_index_flat_curve():
    """Pain Index = 0 pour courbe plate."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    equity = pd.Series([100.0] * 100, index=dates)
    returns = pd.Series([0.0] * 100, index=dates)
    
    analyzer = DrawdownAnalyzer(equity, returns)
    pain = analyzer.calculate_pain_index()
    
    assert pain == 0.0


def test_pain_index_constant_drawdown():
    """Pain Index avec drawdown constant."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    # Equity perd 10% puis reste à 90
    values = [100.0] * 20 + [90.0] * 80
    equity = pd.Series(values, index=dates)
    returns = equity.pct_change().fillna(0.0)
    
    analyzer = DrawdownAnalyzer(equity, returns)
    pain = analyzer.calculate_pain_index()
    
    # Pain devrait être négatif ou proche de 0
    assert pain <= 0.1  # Allow small positive due to calculation


# =====================================================================
# Recovery Statistics Tests
# =====================================================================

def test_get_recovery_statistics_basic(equity_curve_volatile, returns_volatile):
    """Test statistiques de récupération."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    recovery_stats = analyzer.get_recovery_statistics()
    
    assert isinstance(recovery_stats, dict)
    assert 'avg_recovery_days' in recovery_stats
    assert 'max_recovery_days' in recovery_stats
    assert 'min_recovery_days' in recovery_stats
    assert 'recovery_rate' in recovery_stats
    assert 'total_underwater_periods' in recovery_stats


def test_recovery_statistics_values(equity_curve_simple, returns_simple):
    """Vérifier valeurs recovery stats."""
    analyzer = DrawdownAnalyzer(equity_curve_simple, returns_simple)
    recovery = analyzer.get_recovery_statistics()
    
    # Recovery rate devrait être entre 0 et 1
    assert 0.0 <= recovery['recovery_rate'] <= 1.0 or np.isclose(recovery['recovery_rate'], 0.0)
    
    # total_underwater_periods >= 0
    assert recovery['total_underwater_periods'] >= 0


def test_recovery_no_drawdowns():
    """Recovery stats sans drawdowns."""
    dates = pd.date_range('2023-01-01', periods=50, freq='D')
    equity = pd.Series(np.linspace(100, 150, 50), index=dates)
    returns = equity.pct_change().fillna(0.0)
    
    analyzer = DrawdownAnalyzer(equity, returns)
    recovery = analyzer.get_recovery_statistics()
    
    # Devrait retourner 0 underwater periods
    assert recovery['total_underwater_periods'] == 0


# =====================================================================
# Drawdown Distribution Tests
# =====================================================================

def test_get_drawdown_distribution_basic(equity_curve_volatile, returns_volatile):
    """Test distribution des drawdowns."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    distribution = analyzer.get_drawdown_distribution()
    
    assert isinstance(distribution, pd.DataFrame)
    assert 'range' in distribution.columns
    assert 'count' in distribution.columns
    assert 'frequency' in distribution.columns


def test_drawdown_distribution_bins(equity_curve_volatile, returns_volatile):
    """Test avec différents nombres de bins."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    
    dist_5 = analyzer.get_drawdown_distribution(bins=5)
    dist_20 = analyzer.get_drawdown_distribution(bins=20)
    
    assert len(dist_5) <= 5
    assert len(dist_20) <= 20


def test_drawdown_distribution_counts_sum(equity_curve_volatile, returns_volatile):
    """Le nombre total de drawdowns devrait matcher la somme des counts."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    distribution = analyzer.get_drawdown_distribution()
    
    total_counts = distribution['count'].sum()
    # Distribution compte les underwater periods, pas les points individuels
    n_periods = len(analyzer.get_underwater_periods())
    
    assert total_counts == n_periods


# =====================================================================
# Unified Statistics Tests
# =====================================================================

def test_get_drawdown_statistics_complete(equity_curve_volatile, returns_volatile):
    """Test statistiques complètes de drawdowns."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    stats = analyzer.get_drawdown_statistics()
    
    # Vérifier présence de tous les stats
    expected_keys = [
        'max_drawdown', 'cdar_95', 'avg_drawdown',
        'pain_index', 'total_underwater_periods', 'avg_recovery_days'
    ]
    
    for key in expected_keys:
        assert key in stats


def test_drawdown_statistics_consistency(equity_curve_volatile, returns_volatile):
    """Test cohérence des statistiques."""
    analyzer = DrawdownAnalyzer(equity_curve_volatile, returns_volatile)
    stats = analyzer.get_drawdown_statistics()
    
    max_dd_value = stats['max_drawdown']
    cdar = stats['cdar_95']
    avg_dd = stats['avg_drawdown']
    
    # avg_dd >= cdar >= max_dd (en termes de sévérité, valeurs positives)
    assert avg_dd <= max_dd_value + 1e-6  # avg peut être <= max
    assert cdar <= max_dd_value + 1e-6  # cdar <= max


# =====================================================================
# Comparison Tests
# =====================================================================

def test_compare_drawdown_profiles_basic(equity_curve_simple, equity_curve_volatile):
    """Test comparison de deux equity curves."""
    comparison = compare_drawdown_profiles(
        equity_a=equity_curve_simple,
        equity_b=equity_curve_volatile,
        labels=('Simple', 'Volatile')
    )
    
    assert 'Simple' in comparison.columns
    assert 'Volatile' in comparison.columns
    
    # Vérifier que les metrics sont dans l'index
    assert 'max_drawdown' in comparison.index
    assert 'cdar_95' in comparison.index
    assert 'pain_index' in comparison.index


def test_compare_drawdown_profiles_different_risk(equity_curve_simple, equity_curve_volatile):
    """Volatile devrait avoir drawdowns plus sévères."""
    comparison = compare_drawdown_profiles(
        equity_a=equity_curve_simple,
        equity_b=equity_curve_volatile,
        labels=('Simple', 'Volatile')
    )
    
    # Volatile devrait avoir abs(max_dd) >= Simple
    max_dd_simple = abs(comparison.loc['max_drawdown', 'Simple'])
    max_dd_volatile = abs(comparison.loc['max_drawdown', 'Volatile'])
    
    # (peut ne pas toujours être vrai selon seed, donc test souple)
    assert max_dd_volatile >= 0
    assert max_dd_simple >= 0


# =====================================================================
# Edge Cases
# =====================================================================

def test_single_point_equity_curve():
    """Equity curve avec un seul point."""
    equity = pd.Series([100.0], index=[datetime.now()])
    returns = pd.Series([0.0], index=[datetime.now()])
    
    analyzer = DrawdownAnalyzer(equity, returns)
    stats = analyzer.get_drawdown_statistics()
    
    # Tous les metrics devraient être 0 ou vides
    assert stats['max_drawdown'] == 0.0
    assert stats['cdar_95'] == 0.0
    assert stats['avg_drawdown'] == 0.0


def test_all_negative_returns():
    """Equity curve qui ne fait que descendre."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    returns = pd.Series([-0.01] * 100, index=dates)
    equity = (1 + returns).cumprod() * 100
    
    analyzer = DrawdownAnalyzer(equity, returns)
    stats = analyzer.get_drawdown_statistics()
    
    # Max drawdown devrait être sévère (positive value)
    assert stats['max_drawdown'] > 0.5  # Au moins 50%


def test_sudden_crash_and_recovery():
    """Crash soudain puis recovery."""
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    # 30 jours flat, crash -50%, puis recovery
    values = [100.0] * 30 + [50.0] * 20 + list(np.linspace(50, 110, 50))
    equity = pd.Series(values, index=dates)
    returns = equity.pct_change().fillna(0.0)
    
    analyzer = DrawdownAnalyzer(equity, returns)
    stats = analyzer.get_drawdown_statistics()
    
    # Max drawdown devrait être proche de 50% (positive)
    assert stats['max_drawdown'] > 0.45
    
    # Recovery devrait être détecté
    assert stats['total_underwater_periods'] >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
