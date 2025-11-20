"""Tests pour MicrostructureFeatures."""

import pytest
import numpy as np
import pandas as pd
from src.financial_analyzer.ml_features_advanced.microstructure_features import MicrostructureFeatures, compute_vwap

@pytest.fixture
def ohlcv_data():
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=200, freq='D')
    data = pd.DataFrame({
        'open': 100 + np.random.randn(200),
        'high': 102 + np.random.randn(200),
        'low': 98 + np.random.randn(200),
        'close': 100 + np.random.randn(200),
        'volume': 1e6 + np.random.rand(200) * 1e5
    }, index=dates)
    return data

def test_micro_init():
    micro = MicrostructureFeatures(window=20)
    assert micro.window == 20

def test_micro_invalid_init():
    with pytest.raises(ValueError):
        MicrostructureFeatures(window=0)

def test_micro_compute_vwap(ohlcv_data):
    micro = MicrostructureFeatures()
    vwap = micro.compute_vwap(ohlcv_data)
    assert isinstance(vwap, pd.Series)
    assert len(vwap) == len(ohlcv_data)

def test_micro_order_flow_imbalance(ohlcv_data):
    micro = MicrostructureFeatures()
    ofi = micro.compute_order_flow_imbalance(ohlcv_data)
    assert isinstance(ofi, pd.Series)
    assert ofi.abs().max() <= 1.0

def test_micro_bid_ask_spread_roll(ohlcv_data):
    micro = MicrostructureFeatures()
    spread = micro.compute_bid_ask_spread(ohlcv_data, method='roll')
    assert isinstance(spread, pd.Series)

def test_micro_bid_ask_spread_hl(ohlcv_data):
    micro = MicrostructureFeatures()
    spread = micro.compute_bid_ask_spread(ohlcv_data, method='high_low')
    assert isinstance(spread, pd.Series)

def test_micro_amihud_illiquidity(ohlcv_data):
    micro = MicrostructureFeatures()
    illiq = micro.compute_amihud_illiquidity(ohlcv_data)
    assert isinstance(illiq, pd.Series)

def test_micro_kyles_lambda(ohlcv_data):
    micro = MicrostructureFeatures()
    lambda_k = micro.compute_kyles_lambda(ohlcv_data)
    assert isinstance(lambda_k, float)

def test_micro_effective_spread(ohlcv_data):
    micro = MicrostructureFeatures()
    eff_spread = micro.compute_effective_spread(ohlcv_data)
    assert isinstance(eff_spread, pd.Series)

def test_micro_volume_concentration(ohlcv_data):
    micro = MicrostructureFeatures()
    conc = micro.compute_volume_concentration(ohlcv_data)
    assert isinstance(conc, pd.Series)

def test_micro_price_impact(ohlcv_data):
    micro = MicrostructureFeatures()
    impact = micro.compute_price_impact(ohlcv_data)
    assert isinstance(impact, pd.Series)

def test_micro_compute_all(ohlcv_data):
    micro = MicrostructureFeatures()
    features = micro.compute_all(ohlcv_data)
    assert 'vwap' in features
    assert 'order_flow_imbalance' in features
    assert 'kyles_lambda' in features

def test_micro_vwap_convenience(ohlcv_data):
    vwap = compute_vwap(ohlcv_data, window=20)
    assert isinstance(vwap, pd.Series)
