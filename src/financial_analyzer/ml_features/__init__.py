"""
ML Features Engineering Module.

Provides production-grade feature engineering with 114 ML factors:
- Momentum (18 factors)
- Mean-reversion (18 factors)
- Volatility (18 factors)
- Quality/Fundamental (18 factors)
- Technical (18 factors)
- Volume (18 factors)
- Custom/Hybrid (6 factors)

Features:
- Cross-sectional Z-score normalization
- IC (Information Coefficient) validation
- Robust NaN handling
- Comprehensive logging

Audit references:
- AUDIT_FINANCE_PARTIE_5_ML.md (feature patterns)
- AUDIT_RISKFOLIO_LIB.md (factor models)
- AUDIT_FINANCE_PARTIE_3_TECHNICALS.md (technical indicators)
"""

from financial_analyzer.ml_features.feature_engineer import (
    FeatureEngineer,
    FactorMetadata
)

__all__ = [
    'FeatureEngineer',
    'FactorMetadata'
]
