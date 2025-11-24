"""
ML Explainability Module.

Provides SHAP-based model explanations for ML predictions:
- SHAPAnalyzer: SHAP value computation for feature importance
- Feature importance ranking
- Visualization (bar, waterfall, dependence plots)

Example:
    >>> from financial_analyzer.ml.explainability import SHAPAnalyzer
    >>> from financial_analyzer.ml.predictors import LSTMPredictor
    >>> 
    >>> # Train a model
    >>> model = LSTMPredictor(input_dim=20, hidden_dim=128)
    >>> model.train(X_train, y_train)
    >>> 
    >>> # Explain predictions
    >>> analyzer = SHAPAnalyzer(model=model, feature_names=feature_names)
    >>> shap_values = analyzer.compute_shap_values(X_test[:100])
    >>> importance = analyzer.get_feature_importance(shap_values)
    >>> 
    >>> # Visualize
    >>> analyzer.plot_feature_importance(shap_values, save_path="importance.png")
    >>> analyzer.plot_waterfall(shap_values, idx=0, save_path="waterfall.png")
"""

from .shap_analyzer import SHAPAnalyzer

__all__ = ["SHAPAnalyzer"]
