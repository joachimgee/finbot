"""Initialize ML module.

Exports:
    - AlphaFactorEngine: Compute 100+ alpha factors from OHLCV.
    - FactorAnalyzer: Information Coefficient analysis for factors.
    - FeatureImportance: Permutation importance utilities for trained models.
"""
from .feature_engineering import AlphaFactorEngine, FactorResult
from .factor_selection import FactorAnalyzer
from .feature_importance import FeatureImportance

__all__ = [
    "AlphaFactorEngine",
    "FactorAnalyzer",
    "FeatureImportance",
    "FactorResult",
]
