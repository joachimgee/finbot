"""Initialize ML module.

Exports:
    - AlphaFactorEngine: Compute 100+ alpha factors from OHLCV.
    - FactorAnalyzer: Information Coefficient analysis for factors.
    - FeatureImportance: Permutation importance utilities for trained models.
    - SHAPAnalyzer: SHAP-based model explainability (Priority 3).
"""
from .feature_engineering import AlphaFactorEngine, FactorResult
from .factor_selection import FactorAnalyzer
from .feature_importance import FeatureImportance
from .explainability import SHAPAnalyzer

__all__ = [
    "AlphaFactorEngine",
    "FactorAnalyzer",
    "FeatureImportance",
    "FactorResult",
    "SHAPAnalyzer",
]
