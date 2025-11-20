"""
Feature engineering module.

Ce module contient les classes pour calculer les features techniques
et fondamentales à partir de données de marché.

Convention de nommage: **snake_case strict** pour toutes les features.

Author: FinBot Team
Date: 2025-11-12
Version: 2.1.0
"""

from financial_analyzer.features.fundamental import FundamentalFeatureEngine
from financial_analyzer.features.pipeline import FeaturePipeline
from financial_analyzer.features.technical import (
    FEATURE_NAMES,
    TechnicalFeatureEngine,
    validate_feature_columns,
)

__all__ = [
    'TechnicalFeatureEngine',
    'FundamentalFeatureEngine',
    'FeaturePipeline',
    'FEATURE_NAMES',
    'validate_feature_columns',
]
