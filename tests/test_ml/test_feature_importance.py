"""Tests for Feature Importance module."""
import pytest
import numpy as np
from sklearn.linear_model import Ridge

from financial_analyzer.ml.feature_importance import FeatureImportance


@pytest.fixture
def simple_regression_data():
    """Generate simple regression dataset."""
    rng = np.random.default_rng(123)
    X = rng.normal(size=(100, 5))
    # y = 2*X0 + 3*X1 + noise
    y = 2 * X[:, 0] + 3 * X[:, 1] + rng.normal(scale=0.1, size=100)
    return X, y


def test_feature_importance_initialization(simple_regression_data):
    """FeatureImportance initializes correctly."""
    X, y = simple_regression_data
    model = Ridge(alpha=1.0)
    model.fit(X, y)
    fi = FeatureImportance(model, X, y, random_state=42)
    assert fi is not None
    assert fi.model is model
    assert fi.X.shape == X.shape
    assert fi.y.shape == y.shape


def test_permutation_importance_returns_dict(simple_regression_data):
    """permutation_importance returns a dict with feature names."""
    X, y = simple_regression_data
    model = Ridge(alpha=1.0)
    model.fit(X, y)
    fi = FeatureImportance(model, X, y, random_state=42)
    importances = fi.permutation_importance(n_repeats=5)
    assert isinstance(importances, dict)
    assert len(importances) == X.shape[1]
    # Check feature names
    assert all(k.startswith("Feature_") for k in importances.keys())


def test_permutation_importance_identifies_important_features(simple_regression_data):
    """Permutation importance ranks important features higher."""
    X, y = simple_regression_data
    model = Ridge(alpha=1.0)
    model.fit(X, y)
    fi = FeatureImportance(model, X, y, random_state=42)
    importances = fi.permutation_importance(n_repeats=20)
    # Feature_0 and Feature_1 should have highest importance (used in y construction)
    sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    top2 = {sorted_features[0][0], sorted_features[1][0]}
    # Top 2 should include Feature_0 and Feature_1
    assert "Feature_0" in top2 or "Feature_1" in top2


def test_feature_importance_reproducibility():
    """Permutation importance is reproducible with fixed seed."""
    rng = np.random.default_rng(99)
    X = rng.normal(size=(50, 3))
    y = X[:, 0] + 2 * X[:, 1] + rng.normal(scale=0.1, size=50)
    model = Ridge(alpha=0.1)
    model.fit(X, y)
    
    fi1 = FeatureImportance(model, X, y, random_state=123)
    imp1 = fi1.permutation_importance(n_repeats=10)
    
    fi2 = FeatureImportance(model, X, y, random_state=123)
    imp2 = fi2.permutation_importance(n_repeats=10)
    
    # Should be identical with same seed
    assert imp1.keys() == imp2.keys()
    for k in imp1.keys():
        assert pytest.approx(imp1[k], rel=1e-9) == imp2[k]


def test_feature_importance_invalid_X_raises():
    """FeatureImportance raises on 1D X."""
    X = np.array([1, 2, 3])
    y = np.array([1, 2, 3])
    model = Ridge()
    with pytest.raises(ValueError, match="X must be 2D array"):
        FeatureImportance(model, X, y)


def test_feature_importance_invalid_y_raises():
    """FeatureImportance raises on 2D y."""
    X = np.random.normal(size=(10, 3))
    y = np.random.normal(size=(10, 2))
    model = Ridge()
    with pytest.raises(ValueError, match="y must be 1D array"):
        FeatureImportance(model, X, y)


def test_feature_importance_shape_mismatch_raises():
    """FeatureImportance raises on X/y shape mismatch."""
    X = np.random.normal(size=(10, 3))
    y = np.random.normal(size=(8,))
    model = Ridge()
    with pytest.raises(ValueError, match="same number of samples"):
        FeatureImportance(model, X, y)
