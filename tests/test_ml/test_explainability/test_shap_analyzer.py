"""Tests for SHAP Analyzer explainability module."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from financial_analyzer.ml.explainability import SHAPAnalyzer
from financial_analyzer.ml.explainability.shap_analyzer import SHAPResult


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def classification_data():
    """Generate synthetic classification dataset."""
    X, y = make_classification(
        n_samples=200,
        n_features=10,
        n_informative=7,
        n_redundant=2,
        n_repeated=0,
        n_classes=2,
        random_state=42,
    )
    feature_names = [f"feature_{i}" for i in range(X.shape[1])]

    # Split train/test
    split_idx = 150
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "feature_names": feature_names,
    }


@pytest.fixture
def trained_rf_model(classification_data):
    """Train a Random Forest model."""
    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    model.fit(classification_data["X_train"], classification_data["y_train"])
    return model


@pytest.fixture
def trained_logistic_model(classification_data):
    """Train a Logistic Regression model."""
    model = LogisticRegression(max_iter=500, random_state=42)
    model.fit(classification_data["X_train"], classification_data["y_train"])
    return model


@pytest.fixture
def trained_tree_model(classification_data):
    """Train a Decision Tree model."""
    model = DecisionTreeClassifier(max_depth=5, random_state=42)
    model.fit(classification_data["X_train"], classification_data["y_train"])
    return model


@pytest.fixture
def shap_analyzer_rf(trained_rf_model, classification_data):
    """Create SHAP analyzer for Random Forest."""
    return SHAPAnalyzer(
        model=trained_rf_model,
        feature_names=classification_data["feature_names"],
        model_type="tree",
    )


@pytest.fixture
def shap_analyzer_logistic(trained_logistic_model, classification_data):
    """Create SHAP analyzer for Logistic Regression."""
    return SHAPAnalyzer(
        model=trained_logistic_model,
        feature_names=classification_data["feature_names"],
        model_type="linear",
        background_data=classification_data["X_train"][:50],
    )


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


def test_shap_analyzer_init_tree(trained_rf_model, classification_data):
    """Test SHAPAnalyzer initialization with tree model."""
    analyzer = SHAPAnalyzer(
        model=trained_rf_model,
        feature_names=classification_data["feature_names"],
        model_type="tree",
    )

    assert analyzer.model is trained_rf_model
    assert analyzer.feature_names == classification_data["feature_names"]
    assert analyzer.model_type == "tree"
    assert analyzer.explainer is not None
    assert isinstance(analyzer._shap_cache, dict)
    assert len(analyzer._shap_cache) == 0


def test_shap_analyzer_init_linear(trained_logistic_model, classification_data):
    """Test SHAPAnalyzer initialization with linear model."""
    analyzer = SHAPAnalyzer(
        model=trained_logistic_model,
        feature_names=classification_data["feature_names"],
        model_type="linear",
        background_data=classification_data["X_train"][:50],
    )

    assert analyzer.model is trained_logistic_model
    assert analyzer.model_type == "linear"
    assert analyzer.background_data is not None
    assert analyzer.explainer is not None


def test_shap_analyzer_init_auto_detect_tree(trained_rf_model, classification_data):
    """Test auto-detection of tree model type."""
    analyzer = SHAPAnalyzer(
        model=trained_rf_model,
        feature_names=classification_data["feature_names"],
        model_type="auto",
    )

    # Should detect as tree model
    assert analyzer.explainer is not None


def test_shap_analyzer_init_auto_detect_linear(trained_logistic_model, classification_data):
    """Test auto-detection of linear model type."""
    analyzer = SHAPAnalyzer(
        model=trained_logistic_model,
        feature_names=classification_data["feature_names"],
        model_type="auto",
        background_data=classification_data["X_train"][:50],
    )

    assert analyzer.explainer is not None


def test_shap_analyzer_init_invalid_model_type(trained_rf_model, classification_data):
    """Test error on invalid model type."""
    with pytest.raises(ValueError, match="Unsupported model_type"):
        SHAPAnalyzer(
            model=trained_rf_model,
            feature_names=classification_data["feature_names"],
            model_type="invalid_type",
        )


def test_shap_analyzer_init_missing_background_data(trained_logistic_model, classification_data):
    """Test error when background data missing for linear model."""
    # Linear models now use KernelExplainer which requires background data
    # We check that ValueError is raised regardless of exact message
    with pytest.raises(ValueError):
        SHAPAnalyzer(
            model=trained_logistic_model,
            feature_names=classification_data["feature_names"],
            model_type="linear",
            background_data=None,
        )


# ============================================================================
# SHAP VALUE COMPUTATION TESTS
# ============================================================================


def test_compute_shap_values_basic(shap_analyzer_rf, classification_data):
    """Test basic SHAP value computation."""
    X_test = classification_data["X_test"][:20]

    result = shap_analyzer_rf.compute_shap_values(X_test)

    assert isinstance(result, SHAPResult)
    assert result.shap_values.shape == (20, 10)
    assert len(result.feature_names) == 10
    assert isinstance(result.base_value, (float, np.floating))
    assert len(result.feature_importance) == 10
    assert result.data is not None
    assert np.array_equal(result.data, X_test)


def test_compute_shap_values_with_dataframe(shap_analyzer_rf, classification_data):
    """Test SHAP computation with pandas DataFrame input."""
    X_test = classification_data["X_test"][:20]
    X_test_df = pd.DataFrame(X_test, columns=classification_data["feature_names"])

    result = shap_analyzer_rf.compute_shap_values(X_test_df)

    assert result.shap_values.shape == (20, 10)
    assert isinstance(result.data, np.ndarray)


def test_compute_shap_values_caching(shap_analyzer_rf, classification_data):
    """Test SHAP value caching."""
    X_test = classification_data["X_test"][:20]

    # First computation
    result1 = shap_analyzer_rf.compute_shap_values(X_test, cache_key="test_cache")
    assert len(shap_analyzer_rf._shap_cache) == 1

    # Second computation (should use cache)
    result2 = shap_analyzer_rf.compute_shap_values(X_test, cache_key="test_cache")
    assert result1 is result2  # Same object from cache


def test_compute_shap_values_no_caching(shap_analyzer_rf, classification_data):
    """Test disabling SHAP caching."""
    analyzer = SHAPAnalyzer(
        model=shap_analyzer_rf.model,
        feature_names=classification_data["feature_names"],
        model_type="tree",
        cache_shap_values=False,
    )

    X_test = classification_data["X_test"][:20]
    analyzer.compute_shap_values(X_test, cache_key="test")

    assert len(analyzer._shap_cache) == 0


def test_compute_shap_values_invalid_shape(shap_analyzer_rf, classification_data):
    """Test error on invalid input shape."""
    X_invalid = np.random.rand(10, 5)  # Wrong number of features

    with pytest.raises(ValueError, match="Input has 5 features but expected 10"):
        shap_analyzer_rf.compute_shap_values(X_invalid)


def test_compute_shap_values_linear_model(shap_analyzer_logistic, classification_data):
    """Test SHAP computation for linear model."""
    X_test = classification_data["X_test"][:20]

    result = shap_analyzer_logistic.compute_shap_values(X_test)

    assert result.shap_values.shape == (20, 10)
    assert len(result.feature_importance) == 10


# ============================================================================
# FEATURE IMPORTANCE TESTS
# ============================================================================


def test_get_feature_importance(shap_analyzer_rf, classification_data):
    """Test feature importance extraction."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    importance = shap_analyzer_rf.get_feature_importance(result)

    assert len(importance) == 10
    assert all(isinstance(v, float) for v in importance.values())
    assert all(v >= 0 for v in importance.values())

    # Check sorted descending
    values = list(importance.values())
    assert values == sorted(values, reverse=True)


def test_get_feature_importance_top_k(shap_analyzer_rf, classification_data):
    """Test top-k feature importance."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    importance = shap_analyzer_rf.get_feature_importance(result, top_k=5)

    assert len(importance) == 5


def test_get_feature_importance_no_result(shap_analyzer_rf, classification_data):
    """Test error when no SHAP values computed."""
    with pytest.raises(ValueError, match="No SHAP values available"):
        shap_analyzer_rf.get_feature_importance()


def test_get_feature_importance_from_cache(shap_analyzer_rf, classification_data):
    """Test getting importance from cached result."""
    X_test = classification_data["X_test"][:20]
    shap_analyzer_rf.compute_shap_values(X_test, cache_key="test")

    # Get importance without passing result (uses cache)
    importance = shap_analyzer_rf.get_feature_importance()

    assert len(importance) == 10


# ============================================================================
# TOP FEATURES FOR SAMPLE TESTS
# ============================================================================


def test_get_top_features_for_sample(shap_analyzer_rf, classification_data):
    """Test getting top features for single sample."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    top_features = shap_analyzer_rf.get_top_features_for_sample(result, idx=0, top_k=3)

    assert len(top_features) == 3
    assert all(isinstance(v, float) for v in top_features.values())

    # Check sorted by absolute value
    abs_values = [abs(v) for v in top_features.values()]
    assert abs_values == sorted(abs_values, reverse=True)


def test_get_top_features_for_sample_all_features(shap_analyzer_rf, classification_data):
    """Test getting all features for sample."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    top_features = shap_analyzer_rf.get_top_features_for_sample(result, idx=0, top_k=100)

    assert len(top_features) == 10  # All features


# ============================================================================
# VISUALIZATION TESTS
# ============================================================================


def test_plot_feature_importance(shap_analyzer_rf, classification_data):
    """Test feature importance plot."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "importance.png"
        fig = shap_analyzer_rf.plot_feature_importance(result, save_path=save_path)

        assert fig is not None
        assert save_path.exists()


def test_plot_feature_importance_top_k(shap_analyzer_rf, classification_data):
    """Test feature importance plot with top_k."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    fig = shap_analyzer_rf.plot_feature_importance(result, top_k=5)

    assert fig is not None


def test_plot_waterfall(shap_analyzer_rf, classification_data):
    """Test waterfall plot for single prediction."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "waterfall.png"
        fig = shap_analyzer_rf.plot_waterfall(result, idx=0, save_path=save_path)

        assert fig is not None
        assert save_path.exists()


def test_plot_dependence(shap_analyzer_rf, classification_data):
    """Test dependence plot."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "dependence.png"
        fig = shap_analyzer_rf.plot_dependence(
            result, feature_name="feature_0", save_path=save_path
        )

        assert fig is not None
        assert save_path.exists()


def test_plot_dependence_with_interaction(shap_analyzer_rf, classification_data):
    """Test dependence plot with interaction feature."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    fig = shap_analyzer_rf.plot_dependence(
        result, feature_name="feature_0", interaction_feature="feature_1"
    )

    assert fig is not None


def test_plot_dependence_invalid_feature(shap_analyzer_rf, classification_data):
    """Test error on invalid feature name."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    with pytest.raises(ValueError, match="Feature 'invalid_feature' not in feature_names"):
        shap_analyzer_rf.plot_dependence(result, feature_name="invalid_feature")


def test_plot_summary_dot(shap_analyzer_rf, classification_data):
    """Test summary plot (dot/beeswarm)."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    with TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "summary_dot.png"
        fig = shap_analyzer_rf.plot_summary(
            result, plot_type="dot", save_path=save_path
        )

        assert fig is not None
        assert save_path.exists()


def test_plot_summary_bar(shap_analyzer_rf, classification_data):
    """Test summary plot (bar)."""
    X_test = classification_data["X_test"][:20]
    result = shap_analyzer_rf.compute_shap_values(X_test)

    fig = shap_analyzer_rf.plot_summary(result, plot_type="bar")

    assert fig is not None


# ============================================================================
# CACHE MANAGEMENT TESTS
# ============================================================================


def test_clear_cache(shap_analyzer_rf, classification_data):
    """Test clearing SHAP cache."""
    X_test = classification_data["X_test"][:20]

    # Compute and cache
    shap_analyzer_rf.compute_shap_values(X_test, cache_key="test1")
    shap_analyzer_rf.compute_shap_values(X_test, cache_key="test2")
    assert len(shap_analyzer_rf._shap_cache) == 2

    # Clear cache
    shap_analyzer_rf.clear_cache()
    assert len(shap_analyzer_rf._shap_cache) == 0


# ============================================================================
# EDGE CASES
# ============================================================================


def test_single_sample_shap_computation(shap_analyzer_rf, classification_data):
    """Test SHAP computation for single sample."""
    X_single = classification_data["X_test"][:1]

    result = shap_analyzer_rf.compute_shap_values(X_single)

    assert result.shap_values.shape == (1, 10)
    assert len(result.feature_importance) == 10


def test_large_batch_shap_computation(shap_analyzer_rf, classification_data):
    """Test SHAP computation for large batch."""
    X_large = classification_data["X_test"]

    result = shap_analyzer_rf.compute_shap_values(X_large)

    assert result.shap_values.shape[0] == len(X_large)
    assert result.shap_values.shape[1] == 10


def test_multiple_model_types(classification_data):
    """Test SHAP analyzer with multiple model types."""
    # Random Forest
    rf_model = RandomForestClassifier(n_estimators=20, random_state=42)
    rf_model.fit(classification_data["X_train"], classification_data["y_train"])
    rf_analyzer = SHAPAnalyzer(
        model=rf_model,
        feature_names=classification_data["feature_names"],
        model_type="tree",
    )

    # Decision Tree
    tree_model = DecisionTreeClassifier(max_depth=5, random_state=42)
    tree_model.fit(classification_data["X_train"], classification_data["y_train"])
    tree_analyzer = SHAPAnalyzer(
        model=tree_model,
        feature_names=classification_data["feature_names"],
        model_type="tree",
    )

    X_test = classification_data["X_test"][:20]

    rf_result = rf_analyzer.compute_shap_values(X_test)
    tree_result = tree_analyzer.compute_shap_values(X_test)

    assert rf_result.shap_values.shape == tree_result.shap_values.shape
    # SHAP values should be different for different models
    assert not np.allclose(rf_result.shap_values, tree_result.shap_values)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.slow
def test_full_shap_workflow(trained_rf_model, classification_data):
    """Test complete SHAP analysis workflow."""
    # Initialize analyzer
    analyzer = SHAPAnalyzer(
        model=trained_rf_model,
        feature_names=classification_data["feature_names"],
        model_type="tree",
        max_display=10,
    )

    X_test = classification_data["X_test"]

    # Compute SHAP values
    result = analyzer.compute_shap_values(X_test, cache_key="full_test")

    # Get feature importance
    importance = analyzer.get_feature_importance(result, top_k=5)
    assert len(importance) == 5

    # Get top features for sample
    top_features = analyzer.get_top_features_for_sample(result, idx=0, top_k=3)
    assert len(top_features) == 3

    # Create all plots
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        fig1 = analyzer.plot_feature_importance(result, save_path=tmpdir / "importance.png")
        fig2 = analyzer.plot_waterfall(result, idx=0, save_path=tmpdir / "waterfall.png")
        fig3 = analyzer.plot_dependence(
            result, feature_name="feature_0", save_path=tmpdir / "dependence.png"
        )
        fig4 = analyzer.plot_summary(result, plot_type="bar", save_path=tmpdir / "summary.png")

        assert all(fig is not None for fig in [fig1, fig2, fig3, fig4])
        assert (tmpdir / "importance.png").exists()
        assert (tmpdir / "waterfall.png").exists()
        assert (tmpdir / "dependence.png").exists()
        assert (tmpdir / "summary.png").exists()

    # Clear cache
    analyzer.clear_cache()
    assert len(analyzer._shap_cache) == 0


@pytest.mark.slow
def test_comparison_tree_vs_linear_shap(classification_data):
    """Compare SHAP values from tree vs linear models."""
    # Train both models
    rf_model = RandomForestClassifier(n_estimators=50, random_state=42)
    rf_model.fit(classification_data["X_train"], classification_data["y_train"])

    lr_model = LogisticRegression(max_iter=500, random_state=42)
    lr_model.fit(classification_data["X_train"], classification_data["y_train"])

    # Create analyzers
    rf_analyzer = SHAPAnalyzer(
        model=rf_model,
        feature_names=classification_data["feature_names"],
        model_type="tree",
    )

    lr_analyzer = SHAPAnalyzer(
        model=lr_model,
        feature_names=classification_data["feature_names"],
        model_type="linear",
        background_data=classification_data["X_train"][:50],
    )

    X_test = classification_data["X_test"][:20]

    # Compute SHAP values
    rf_result = rf_analyzer.compute_shap_values(X_test)
    lr_result = lr_analyzer.compute_shap_values(X_test)

    # Both should have valid SHAP values
    assert rf_result.shap_values.shape == lr_result.shap_values.shape
    assert len(rf_result.feature_importance) == len(lr_result.feature_importance)

    # Feature importance rankings may differ
    rf_importance = rf_analyzer.get_feature_importance(rf_result)
    lr_importance = lr_analyzer.get_feature_importance(lr_result)

    rf_top_feature = list(rf_importance.keys())[0]
    lr_top_feature = list(lr_importance.keys())[0]

    # Not necessarily the same top feature (different model types)
    assert rf_top_feature in classification_data["feature_names"]
    assert lr_top_feature in classification_data["feature_names"]
