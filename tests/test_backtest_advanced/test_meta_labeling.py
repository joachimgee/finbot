"""Tests pour MetaLabeler."""

import pytest
import numpy as np
import pandas as pd
from src.financial_analyzer.backtest_advanced.meta_labeling import MetaLabeler, create_meta_labels

@pytest.fixture
def simple_data():
    dates = pd.date_range('2020-01-01', periods=200, freq='D')
    returns = pd.Series(np.random.randn(200) * 0.01, index=dates)
    signals = pd.Series(np.random.choice([-1, 1], size=200), index=dates)
    features = pd.DataFrame({'f1': np.random.rand(200), 'f2': np.random.rand(200)}, index=dates)
    return returns, signals, features

def test_meta_labeler_init():
    ml = MetaLabeler()
    assert ml.side_threshold == 0.5
    assert ml.min_return_threshold == 0.0

def test_create_meta_labels_side(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    labels = ml.create_meta_labels_side(returns, signals, horizon=5)
    assert isinstance(labels, pd.Series)
    assert len(labels) > 0
    assert labels.isin([0, 1]).all()

def test_create_meta_labels_size(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    labels = ml.create_meta_labels_size(returns, signals, horizon=5, method='abs_return')
    assert isinstance(labels, pd.Series)
    assert len(labels) > 0

def test_fit_side(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    ml.fit_side(features, returns, signals, horizon=5)
    assert ml._is_fitted_side is True

def test_fit_size(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    ml.fit_size(features, returns, signals, horizon=5, method='abs_return')
    assert ml._is_fitted_size is True

def test_fit_unified(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    ml.fit(features, returns, signals, horizon=5, fit_size=True)
    assert ml._is_fitted_side is True
    assert ml._is_fitted_size is True

def test_predict_side(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    ml.fit_side(features, returns, signals, horizon=5)
    preds = ml.predict_side(features, signals)
    assert isinstance(preds, pd.Series)
    assert preds.isin([0, 1]).all()

def test_predict_size(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    ml.fit_size(features, returns, signals, horizon=5, method='abs_return')
    preds = ml.predict_size(features, signals)
    assert isinstance(preds, pd.Series)
    assert len(preds) > 0

def test_filter_signals(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    ml.fit_side(features, returns, signals, horizon=5)
    filtered = ml.filter_signals(features, signals)
    assert isinstance(filtered, pd.Series)
    assert len(filtered) <= len(signals)

def test_evaluate(simple_data):
    returns, signals, features = simple_data
    ml = MetaLabeler()
    ml.fit_side(features, returns, signals, horizon=5)
    metrics = ml.evaluate(features, returns, signals, horizon=5)
    assert 'accuracy' in metrics
    assert 'precision' in metrics
    assert 'recall' in metrics
    assert 'f1' in metrics

def test_create_meta_labels_convenience(simple_data):
    returns, signals, _ = simple_data
    labels = create_meta_labels(returns, signals, horizon=5)
    assert isinstance(labels, pd.Series)
    assert labels.isin([0, 1]).all()
