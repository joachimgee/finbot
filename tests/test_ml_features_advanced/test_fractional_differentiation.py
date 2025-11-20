"""Tests pour FractionalDifferentiator."""

import pytest
import numpy as np
import pandas as pd
from src.financial_analyzer.ml_features_advanced.fractional_differentiation import FractionalDifferentiator, frac_diff

@pytest.fixture
def price_series():
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=200, freq='D')
    prices = 100 * np.exp(np.cumsum(np.random.randn(200) * 0.01))
    return pd.Series(prices, index=dates)

def test_fd_init():
    fd = FractionalDifferentiator()
    assert fd.min_weight == 1e-5
    assert fd.threshold == 1e-5

def test_fd_get_weights():
    fd = FractionalDifferentiator()
    weights = fd._get_weights(d=0.5, size=10)
    assert len(weights) == 10
    assert weights.sum() < 1.0

def test_fd_transform_basic(price_series):
    fd = FractionalDifferentiator()
    transformed = fd.transform(price_series, d=0.5)
    assert isinstance(transformed, pd.Series)
    assert len(transformed) <= len(price_series)

def test_fd_transform_d_zero(price_series):
    fd = FractionalDifferentiator()
    transformed = fd.transform(price_series, d=0.0)
    np.testing.assert_array_almost_equal(transformed.values, price_series.iloc[:len(transformed)].values)

def test_fd_transform_d_one(price_series):
    fd = FractionalDifferentiator()
    transformed = fd.transform(price_series, d=1.0)
    returns = price_series.diff().dropna()
    assert len(transformed) > 0

def test_fd_inverse_transform(price_series):
    fd = FractionalDifferentiator()
    d = 0.3
    transformed = fd.transform(price_series, d=d)
    reconstructed = fd.inverse_transform(transformed, d=d, initial_values=price_series.iloc[:10])
    assert isinstance(reconstructed, pd.Series)

def test_fd_frac_diff_convenience(price_series):
    diff_series = frac_diff(price_series, d=0.5)
    assert isinstance(diff_series, pd.Series)
    assert len(diff_series) <= len(price_series)

def test_fd_invalid_d(price_series):
    fd = FractionalDifferentiator()
    with pytest.raises(ValueError):
        fd.transform(price_series, d=1.5)

def test_fd_ffd_transform(price_series):
    fd = FractionalDifferentiator()
    transformed = fd.transform(price_series, d=0.5, use_ffd=True)
    assert isinstance(transformed, pd.Series)
    assert len(transformed) > 0
