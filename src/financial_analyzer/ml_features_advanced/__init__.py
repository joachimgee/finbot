"""
ML Features Advanced Module - Phase F.

Features ML avancés pour trading quantitatif :
- Fractional Differentiation : stationnarité + mémoire
- Feature Importance : SHAP, MDI, MDA
- Autocorrelation Features : ACF, PACF, Hurst
- Microstructure Features : VWAP, order flow, spreads
"""

from financial_analyzer.ml_features_advanced.fractional_differentiation import FractionalDifferentiator, frac_diff
from financial_analyzer.ml_features_advanced.feature_importance import FeatureImportanceAnalyzer, get_feature_importance
from financial_analyzer.ml_features_advanced.autocorrelation_features import AutocorrelationFeatures, compute_hurst
from financial_analyzer.ml_features_advanced.microstructure_features import MicrostructureFeatures, compute_vwap

__all__ = [
    'FractionalDifferentiator',
    'frac_diff',
    'FeatureImportanceAnalyzer',
    'get_feature_importance',
    'AutocorrelationFeatures',
    'compute_hurst',
    'MicrostructureFeatures',
    'compute_vwap',
]
