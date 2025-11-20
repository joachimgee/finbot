"""Tests pour AutocorrelationFeatures."""

import pytest
import numpy as np
import pandas as pd
from src.financial_analyzer.ml_features_advanced.autocorrelation_features import AutocorrelationFeatures, compute_hurst

@pytest.fixture
def returns_series():
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=250, freq='D')
    returns = pd.Series(np.random.randn(250) * 0.01, index=dates)
    return returns

def test_acf_init():
    acf = AutocorrelationFeatures(max_lags=20)
    assert acf.max_lags == 20
    assert acf.alpha == 0.05

def test_acf_invalid_init():
    with pytest.raises(ValueError):
        AutocorrelationFeatures(max_lags=0)

def test_acf_compute_acf(returns_series):
    acf = AutocorrelationFeatures()
    acf_vals, conf = acf.compute_acf(returns_series)
    assert len(acf_vals) > 0
    assert conf > 0

def test_acf_compute_pacf(returns_series):
    acf = AutocorrelationFeatures()
    pacf_vals, conf = acf.compute_pacf(returns_series)
    assert len(pacf_vals) > 0
    assert conf > 0

def test_acf_compute_hurst(returns_series):
    acf = AutocorrelationFeatures()
    hurst = acf.compute_hurst_exponent(returns_series)
    assert 0 <= hurst <= 1

def test_acf_hurst_convenience(returns_series):
    hurst = compute_hurst(returns_series)
    assert 0 <= hurst <= 1

def test_acf_detect_seasonality(returns_series):
    acf = AutocorrelationFeatures()
    decomp = acf.detect_seasonality(returns_series, period=7)
    assert 'seasonality_strength' in decomp
    assert 0 <= decomp['seasonality_strength'] <= 1
