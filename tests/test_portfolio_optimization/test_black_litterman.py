"""Tests for BlackLittermanModel."""

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.portfolio import BlackLittermanModel


@pytest.fixture
def bl_inputs():
    assets = ["A", "B", "C"]
    cov = pd.DataFrame(
        [[0.04, 0.01, 0.0], [0.01, 0.09, 0.02], [0.0, 0.02, 0.16]],
        index=assets,
        columns=assets,
    )
    mcap = pd.Series([100, 300, 600], index=assets)
    return cov, mcap


def test_init(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap)
    assert (bl.cov.values == cov.values).all()
    assert abs(bl.market_weights.sum() - 1.0) < 1e-9


def test_equilibrium_no_views(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap, risk_free_rate=0.01)
    posterior = bl.get_posterior_returns()
    assert isinstance(posterior, pd.Series)
    assert set(posterior.index) == set(cov.columns)
    # Verify equals rf + cov @ market_weights (delta=1 convention here)
    w_mkt = mcap / mcap.sum()
    expected = 0.01 + cov.values @ w_mkt.values
    assert np.allclose(posterior.values, expected, atol=1e-12)


def test_add_absolute_view(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap)
    bl.add_absolute_view("A", 0.15, confidence=0.8)
    posterior = bl.get_posterior_returns()
    assert "A" in posterior.index


def test_add_relative_view(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap)
    bl.add_relative_view("A", "B", 0.05, confidence=0.9)
    posterior = bl.get_posterior_returns()
    assert len(posterior) == 3


def test_multiple_views_shape(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap)
    bl.add_absolute_view("A", 0.12, confidence=1.0)
    bl.add_relative_view("B", "C", 0.03, confidence=0.5)
    posterior = bl.get_posterior_returns()
    assert posterior.shape[0] == 3


def test_confidence_impact(bl_inputs):
    cov, mcap = bl_inputs
    bl_high = BlackLittermanModel(cov, mcap)
    bl_low = BlackLittermanModel(cov, mcap)
    # Same view different confidence
    bl_high.add_absolute_view("A", 0.20, confidence=1.0)
    bl_low.add_absolute_view("A", 0.20, confidence=0.1)
    post_high = bl_high.get_posterior_returns()
    post_low = bl_low.get_posterior_returns()
    # High confidence should push A further from rf baseline than low confidence
    assert abs(post_high["A"] - bl_high.rf) >= abs(post_low["A"] - bl_low.rf)


def test_invalid_asset_absolute(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap)
    with pytest.raises(ValueError):
        bl.add_absolute_view("Z", 0.1)


def test_invalid_asset_relative(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap)
    with pytest.raises(ValueError):
        bl.add_relative_view("A", "Z", 0.05)


def test_confidence_bounds(bl_inputs):
    cov, mcap = bl_inputs
    bl = BlackLittermanModel(cov, mcap)
    bl.add_absolute_view("A", 0.10, confidence=0)  # clipped to >0
    posterior = bl.get_posterior_returns()
    assert "A" in posterior.index


def test_market_caps_zero_fallback():
    assets = ["A", "B", "C"]
    cov = pd.DataFrame(
        [[0.01, 0.0, 0.0], [0.0, 0.02, 0.0], [0.0, 0.0, 0.03]],
        index=assets,
        columns=assets,
    )
    mcap = pd.Series([0.0, 0.0, 0.0], index=assets)
    bl = BlackLittermanModel(cov, mcap, risk_free_rate=0.0)
    posterior = bl.get_posterior_returns()
    assert not posterior.isna().any()
    assert len(posterior) == 3
