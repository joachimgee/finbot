"""
Tests pour financial_analyzer.trading.bet_sizing

Tests des fonctions de bet sizing:
- kelly_criterion: Kelly optimal
- bet_size_from_probability: AFML Snippet 10.1
- bet_size_budget: AFML Section 10.2
- bet_size_dynamic: AFML Snippet 10.4
- calculate_bet_sizes: Interface unifiée
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from financial_analyzer.trading.bet_sizing import (
    kelly_criterion,
    bet_size_from_probability,
    bet_size_budget,
    bet_size_dynamic,
    calculate_bet_sizes
)


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def sample_weights():
    """Poids de portfolio pour tests."""
    return pd.Series({
        'AAPL': 0.25,
        'MSFT': 0.20,
        'GOOGL': 0.15,
        'AMZN': 0.15,
        'NVDA': 0.10,
        'TSLA': 0.08,
        'META': 0.07
    })


@pytest.fixture
def sample_ml_confidence():
    """Confiances ML pour tests."""
    return pd.Series({
        'AAPL': 0.85,
        'MSFT': 0.75,
        'GOOGL': 0.65,
        'AMZN': 0.60,
        'NVDA': 0.55,
        'TSLA': 0.50,
        'META': 0.45
    })


@pytest.fixture
def sample_events_t1():
    """Événements avec label end times pour budget method."""
    # RNG local : le RNG global np.random dépend de l'ordre d'exécution des
    # autres fichiers de tests, ce qui rendait les durées d'événements (donc
    # les recouvrements long/short, donc les signes des bet sizes) non
    # déterministes en suite complète.
    rng = np.random.default_rng(0)
    start_dates = pd.date_range('2023-01-01', periods=100, freq='D')
    end_dates = start_dates + pd.Series([timedelta(days=int(rng.integers(1, 10))) for _ in range(100)])
    return pd.Series(end_dates.values, index=start_dates)


@pytest.fixture
def sample_sides():
    """Sides (1 = long, -1 = short) pour events."""
    rng = np.random.default_rng(0)
    start_dates = pd.date_range('2023-01-01', periods=100, freq='D')
    return pd.Series(rng.choice([1, -1], size=100), index=start_dates)


# ==============================
# Tests kelly_criterion
# ==============================

def test_kelly_criterion_basic():
    """Kelly criterion avec paramètres valides."""
    # p = 0.6, b = 2.0 → f* = (0.6*2 - 0.4) / 2 = 0.4
    kelly_frac = kelly_criterion(win_prob=0.6, win_loss_ratio=2.0, kelly_fraction=1.0)
    expected = (0.6 * 2.0 - 0.4) / 2.0
    assert abs(kelly_frac - expected) < 1e-10


def test_kelly_criterion_fifty_fifty():
    """Kelly criterion avec p = 0.5 (no edge) → 0."""
    kelly_frac = kelly_criterion(win_prob=0.5, win_loss_ratio=1.0, kelly_fraction=1.0)
    assert abs(kelly_frac) < 1e-10


def test_kelly_criterion_negative():
    """Kelly criterion avec negative edge → 0 (clamped)."""
    # p = 0.4, b = 1.0 → negative Kelly
    kelly_frac = kelly_criterion(win_prob=0.4, win_loss_ratio=1.0, kelly_fraction=1.0)
    assert kelly_frac == 0.0


def test_kelly_criterion_fractional():
    """Kelly criterion avec fractional Kelly (quarter Kelly)."""
    # p = 0.6, b = 2.0, fraction = 0.25
    kelly_full = kelly_criterion(win_prob=0.6, win_loss_ratio=2.0, kelly_fraction=1.0)
    kelly_quarter = kelly_criterion(win_prob=0.6, win_loss_ratio=2.0, kelly_fraction=0.25)
    assert abs(kelly_quarter - kelly_full * 0.25) < 1e-10


def test_kelly_criterion_max_leverage():
    """Kelly criterion avec max_leverage cap."""
    # p = 0.9, b = 5.0 → très grand Kelly, mais capped à max_leverage
    kelly_frac = kelly_criterion(win_prob=0.9, win_loss_ratio=5.0, max_leverage=1.0)
    assert kelly_frac <= 1.0


def test_kelly_criterion_edge_cases():
    """Kelly criterion edge cases (p = 0, p = 1)."""
    # p = 0 → 0
    assert kelly_criterion(win_prob=0.0, win_loss_ratio=1.0) == 0.0
    
    # p = 1 → max possible (capped by max_leverage)
    kelly_frac = kelly_criterion(win_prob=1.0, win_loss_ratio=1.0, max_leverage=2.0)
    assert kelly_frac <= 2.0


# ==============================
# Tests bet_size_from_probability
# ==============================

def test_bet_size_from_probability_binary_long():
    """bet_size_from_probability avec 2 classes, side = 1 (long)."""
    # prob = 0.7, num_classes = 2 → signal = (0.7 - 0.5) / 0.5 = 0.4
    # size = 0.4 * 0.25 = 0.1
    size = bet_size_from_probability(prob=0.7, num_classes=2, side=1, kelly_fraction=0.25)
    signal = (0.7 - 0.5) / 0.5
    expected = signal * 0.25
    assert abs(size - expected) < 1e-10


def test_bet_size_from_probability_binary_short():
    """bet_size_from_probability avec 2 classes, side = -1 (short)."""
    # prob = 0.3, num_classes = 2 → signal = (0.3 - 0.5) / 0.5 = -0.4
    # size = |-0.4| * 0.25 * (-1) = -0.1
    size = bet_size_from_probability(prob=0.3, num_classes=2, side=-1, kelly_fraction=0.25)
    signal = (0.3 - 0.5) / 0.5
    expected = abs(signal) * 0.25 * (-1)
    assert abs(size - expected) < 1e-10


def test_bet_size_from_probability_three_classes():
    """bet_size_from_probability avec 3 classes."""
    # prob = 0.6, num_classes = 3 → signal = (0.6 - 1/3) / (1 - 1/3) = 0.4
    # size = 0.4 * 0.25 = 0.1
    size = bet_size_from_probability(prob=0.6, num_classes=3, side=1, kelly_fraction=0.25)
    signal = (0.6 - 1/3) / (2/3)
    expected = signal * 0.25
    assert abs(size - expected) < 1e-10


def test_bet_size_from_probability_no_confidence():
    """bet_size_from_probability avec prob = 1/n_classes (no confidence) → 0."""
    size = bet_size_from_probability(prob=0.5, num_classes=2, side=1)
    assert abs(size) < 1e-10


def test_bet_size_from_probability_full_confidence():
    """bet_size_from_probability avec prob = 1.0 (full confidence)."""
    # prob = 1.0, num_classes = 2 → signal = (1.0 - 0.5) / 0.5 = 1.0
    # size = 1.0 * 0.25 = 0.25
    size = bet_size_from_probability(prob=1.0, num_classes=2, side=1, kelly_fraction=0.25)
    assert abs(size - 0.25) < 1e-10


def test_bet_size_from_probability_capped():
    """bet_size_from_probability avec max_position_size cap."""
    # prob très élevée → size serait > 0.1, mais capped
    size = bet_size_from_probability(
        prob=0.95, num_classes=2, side=1, 
        kelly_fraction=1.0, max_position_size=0.1
    )
    assert size <= 0.1


# ==============================
# Tests bet_size_budget
# ==============================

def test_bet_size_budget_basic(sample_events_t1, sample_sides):
    """bet_size_budget calcule avg concurrent bets."""
    sizes = bet_size_budget(events_t1=sample_events_t1, sides=sample_sides)
    
    assert isinstance(sizes, pd.Series)
    assert len(sizes) == len(sample_events_t1)
    assert (sizes != 0).any()  # Au moins quelques non-zero


def test_bet_size_budget_all_long(sample_events_t1):
    """bet_size_budget avec tous long (side = 1)."""
    sides_long = pd.Series([1] * len(sample_events_t1), index=sample_events_t1.index)
    sizes = bet_size_budget(events_t1=sample_events_t1, sides=sides_long)
    
    # Tous positifs
    assert (sizes > 0).all()


def test_bet_size_budget_all_short(sample_events_t1):
    """bet_size_budget avec tous short (side = -1)."""
    sides_short = pd.Series([-1] * len(sample_events_t1), index=sample_events_t1.index)
    sizes = bet_size_budget(events_t1=sample_events_t1, sides=sides_short)
    
    # Tous négatifs
    assert (sizes < 0).all()


def test_bet_size_budget_mixed(sample_events_t1):
    """bet_size_budget avec mix long/short."""
    sides_mixed = pd.Series([1, -1, 1, -1] * 25, index=sample_events_t1.index)
    sizes = bet_size_budget(events_t1=sample_events_t1, sides=sides_mixed)
    
    # Mix de positifs et négatifs
    assert (sizes > 0).any()
    assert (sizes < 0).any()


def test_bet_size_budget_no_overlap():
    """bet_size_budget avec events non-overlapping → size = 1.0 ou -1.0."""
    # 5 events séquentiels sans overlap (start day X, end day X+1)
    start_dates = [datetime(2023, 1, i) for i in [1, 3, 5, 7, 9]]
    end_dates = [datetime(2023, 1, i) for i in [2, 4, 6, 8, 10]]
    
    events_t1 = pd.Series(end_dates, index=start_dates)
    sides = pd.Series([1, 1, 1, 1, 1], index=start_dates)
    
    sizes = bet_size_budget(events_t1=events_t1, sides=sides)
    
    # Pas d'overlap → avg_concurrent = 1 → size = 1.0
    assert (abs(sizes - 1.0) < 1e-10).all()


# ==============================
# Tests bet_size_dynamic
# ==============================

def test_bet_size_dynamic_sigmoid_scalar():
    """bet_size_dynamic avec sigmoid, scalar inputs."""
    size = bet_size_dynamic(
        current_positions=0.05,
        max_position_size=0.10,
        current_price=100.0,
        forecast_price=110.0,
        w_param=5.0,
        func='sigmoid'
    )
    
    assert isinstance(size, float)
    assert 0.0 <= size <= 0.10


def test_bet_size_dynamic_power_scalar():
    """bet_size_dynamic avec power, scalar inputs."""
    size = bet_size_dynamic(
        current_positions=0.05,
        max_position_size=0.10,
        current_price=100.0,
        forecast_price=110.0,
        w_param=2.0,
        func='power'
    )
    
    assert isinstance(size, float)
    assert 0.0 <= size <= 0.10


def test_bet_size_dynamic_series():
    """bet_size_dynamic avec Series inputs."""
    current_positions = pd.Series([0.02, 0.05, 0.08], index=['AAPL', 'MSFT', 'GOOGL'])
    max_position_size = pd.Series([0.10, 0.10, 0.10], index=['AAPL', 'MSFT', 'GOOGL'])
    current_price = pd.Series([100.0, 200.0, 150.0], index=['AAPL', 'MSFT', 'GOOGL'])
    forecast_price = pd.Series([110.0, 190.0, 160.0], index=['AAPL', 'MSFT', 'GOOGL'])
    
    sizes = bet_size_dynamic(
        current_positions=current_positions,
        max_position_size=max_position_size,
        current_price=current_price,
        forecast_price=forecast_price,
        w_param=5.0,
        func='sigmoid'
    )
    
    assert isinstance(sizes, pd.Series)
    assert len(sizes) == 3
    assert (sizes <= 0.10).all()


def test_bet_size_dynamic_no_divergence():
    """bet_size_dynamic avec current_price = forecast_price → size = current."""
    size = bet_size_dynamic(
        current_positions=0.05,
        max_position_size=0.10,
        current_price=100.0,
        forecast_price=100.0,
        w_param=5.0,
        func='sigmoid'
    )
    
    # Pas de divergence → sigmoid(0) = 0.5 → target = 0.5 * 0.10 = 0.05
    # size = 0.05 - 0.05 = 0
    assert abs(size) < 1e-5


def test_bet_size_dynamic_large_divergence():
    """bet_size_dynamic avec large price divergence → size proche de max."""
    size = bet_size_dynamic(
        current_positions=0.0,
        max_position_size=0.10,
        current_price=100.0,
        forecast_price=200.0,  # +100%
        w_param=5.0,
        func='sigmoid'
    )
    
    # Large divergence positive → sigmoid(large) → 1.0 → target = 0.10
    # size = 0.10 - 0.0 = 0.10
    assert abs(size - 0.10) < 0.01


# ==============================
# Tests calculate_bet_sizes
# ==============================

def test_calculate_bet_sizes_proportional(sample_weights):
    """calculate_bet_sizes avec method='proportional' (passthrough)."""
    sizes = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='proportional'
    )
    
    # Proportional → sizes = weights * equity
    expected = sample_weights * 100000
    pd.testing.assert_series_equal(sizes, expected)


def test_calculate_bet_sizes_kelly(sample_weights):
    """calculate_bet_sizes avec method='kelly'."""
    kelly_params = {
        'win_prob': 0.6,
        'win_loss_ratio': 2.0,
        'kelly_fraction': 0.25
    }
    
    sizes = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='kelly',
        kelly_params=kelly_params
    )
    
    # Kelly fraction appliqué → sizes = weights * equity * kelly_frac
    kelly_frac = kelly_criterion(**kelly_params)
    expected = sample_weights * 100000 * kelly_frac
    pd.testing.assert_series_equal(sizes, expected)


def test_calculate_bet_sizes_confidence(sample_weights, sample_ml_confidence):
    """calculate_bet_sizes avec method='confidence'."""
    sizes = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='confidence',
        ml_confidence=sample_ml_confidence,
        num_classes=2
    )
    
    assert isinstance(sizes, pd.Series)
    assert len(sizes) == len(sample_weights)
    
    # Confiances plus élevées → sizes plus grandes (relative)
    # AAPL (0.85) devrait avoir size > META (0.45)
    assert sizes['AAPL'] > sizes['META']


def test_calculate_bet_sizes_confidence_missing():
    """calculate_bet_sizes avec method='confidence' mais ml_confidence None → ValueError."""
    weights = pd.Series({'AAPL': 0.5, 'MSFT': 0.5})
    
    with pytest.raises(ValueError, match="ml_confidence requis"):
        calculate_bet_sizes(
            weights=weights,
            equity=100000,
            method='confidence',
            ml_confidence=None
        )


def test_calculate_bet_sizes_kelly_missing_params():
    """calculate_bet_sizes avec method='kelly' mais kelly_params None → ValueError."""
    weights = pd.Series({'AAPL': 0.5, 'MSFT': 0.5})
    
    with pytest.raises(ValueError, match="kelly_params requis"):
        calculate_bet_sizes(
            weights=weights,
            equity=100000,
            method='kelly',
            kelly_params=None
        )


def test_calculate_bet_sizes_max_position_size(sample_weights):
    """calculate_bet_sizes avec max_position_size cap."""
    sizes = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='proportional',
        max_position_size=0.15  # Cap à 15%
    )
    
    # Toutes les positions doivent être <= 15% de equity
    max_size = 0.15 * 100000
    assert (sizes <= max_size).all()


def test_calculate_bet_sizes_empty_weights():
    """calculate_bet_sizes avec weights vide → Series vide."""
    weights = pd.Series(dtype=float)
    
    sizes = calculate_bet_sizes(
        weights=weights,
        equity=100000,
        method='proportional'
    )
    
    assert len(sizes) == 0


def test_calculate_bet_sizes_zero_equity():
    """calculate_bet_sizes avec equity=0 → ValueError."""
    weights = pd.Series({'AAPL': 0.5, 'MSFT': 0.5})
    
    with pytest.raises(ValueError, match="equity doit être > 0"):
        calculate_bet_sizes(
            weights=weights,
            equity=0.0,
            method='proportional'
        )


def test_calculate_bet_sizes_negative_weights():
    """calculate_bet_sizes avec negative weights (short) supporté."""
    weights = pd.Series({'AAPL': 0.5, 'MSFT': -0.3})
    
    sizes = calculate_bet_sizes(
        weights=weights,
        equity=100000,
        method='proportional'
    )
    
    # AAPL positif, MSFT négatif
    assert sizes['AAPL'] > 0
    assert sizes['MSFT'] < 0


def test_calculate_bet_sizes_confidence_partial_coverage(sample_weights):
    """calculate_bet_sizes avec ml_confidence ne couvrant que partie de weights."""
    # ml_confidence pour seulement AAPL, MSFT
    ml_confidence = pd.Series({'AAPL': 0.8, 'MSFT': 0.7})
    
    sizes = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='confidence',
        ml_confidence=ml_confidence,
        num_classes=2
    )
    
    # Weights sans ml_confidence devraient avoir size = 0 ou baseline
    # (baseline = 0.5 utilisé dans bet_size_from_probability)
    assert isinstance(sizes, pd.Series)


# ==============================
# Tests d'intégration
# ==============================

def test_integration_kelly_with_confidence(sample_weights, sample_ml_confidence):
    """Integration: Kelly criterion ET ML confidence combinés."""
    kelly_params = {
        'win_prob': 0.6,
        'win_loss_ratio': 1.5,
        'kelly_fraction': 0.25
    }
    
    # Kelly sizes
    sizes_kelly = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='kelly',
        kelly_params=kelly_params
    )
    
    # Confidence sizes
    sizes_conf = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='confidence',
        ml_confidence=sample_ml_confidence,
        num_classes=2
    )
    
    # Les deux devraient réduire les positions par rapport à proportional
    sizes_prop = calculate_bet_sizes(
        weights=sample_weights,
        equity=100000,
        method='proportional'
    )
    
    assert sizes_kelly.sum() <= sizes_prop.sum()
    # (confidence peut être > proportional si confiances élevées)


def test_integration_pipeline_full(sample_weights, sample_ml_confidence):
    """Integration: Full pipeline proportional → kelly → confidence → discrete."""
    equity = 100000
    
    # 1. Proportional
    sizes_prop = calculate_bet_sizes(
        weights=sample_weights,
        equity=equity,
        method='proportional'
    )
    
    # 2. Kelly
    sizes_kelly = calculate_bet_sizes(
        weights=sample_weights,
        equity=equity,
        method='kelly',
        kelly_params={'win_prob': 0.55, 'win_loss_ratio': 1.5, 'kelly_fraction': 0.25}
    )
    
    # 3. Confidence
    sizes_conf = calculate_bet_sizes(
        weights=sample_weights,
        equity=equity,
        method='confidence',
        ml_confidence=sample_ml_confidence,
        num_classes=2,
        max_position_size=0.20
    )
    
    # Tous devraient être Series with same tickers
    assert set(sizes_prop.index) == set(sample_weights.index)
    assert set(sizes_kelly.index) == set(sample_weights.index)
    assert set(sizes_conf.index) == set(sample_weights.index)
    
    # Confidence avec max_position_size devrait avoir cap
    max_size = 0.20 * equity
    assert (sizes_conf <= max_size).all()
