"""Tests pour FeatureImportanceAnalyzer."""

import pytest
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from src.financial_analyzer.ml_features_advanced.feature_importance import FeatureImportanceAnalyzer, get_feature_importance

@pytest.fixture
def simple_dataset():
    np.random.seed(42)
    X = pd.DataFrame({
        'f1': np.random.rand(200),
        'f2': np.random.rand(200),
        'f3': np.random.rand(200)
    })
    y = (X['f1'] + X['f2'] > 1).astype(int)
    split = 150
    return X.iloc[:split], y.iloc[:split], X.iloc[split:], y.iloc[split:]

@pytest.fixture
def fitted_model(simple_dataset):
    X_train, y_train, X_test, y_test = simple_dataset
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X_train, y_train)
    return model, X_train, y_train, X_test, y_test

def test_fi_init(fitted_model):
    model, X_train, y_train, X_test, y_test = fitted_model
    fi = FeatureImportanceAnalyzer(model, X_train, y_train, X_test, y_test)
    assert fi.model is not None

def test_fi_get_mdi(fitted_model):
    model, X_train, y_train, X_test, y_test = fitted_model
    fi = FeatureImportanceAnalyzer(model, X_train, y_train, X_test, y_test)
    importance = fi.get_mdi_importance()
    assert isinstance(importance, pd.Series)
    assert len(importance) == X_train.shape[1]

def test_fi_get_mda(fitted_model):
    model, X_train, y_train, X_test, y_test = fitted_model
    fi = FeatureImportanceAnalyzer(model, X_train, y_train, X_test, y_test)
    importance = fi.get_mda_importance(n_repeats=5)
    assert isinstance(importance, pd.Series)
    assert len(importance) == X_train.shape[1]

def test_fi_convenience(fitted_model):
    model, X_train, y_train, X_test, y_test = fitted_model
    importance = get_feature_importance(model, X_train, y_train, X_test, y_test)
    assert isinstance(importance, pd.Series)
    assert len(importance) > 0
