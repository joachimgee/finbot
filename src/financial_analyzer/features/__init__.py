"""
Feature engineering module.

Ce module contient les classes pour calculer les features techniques
et fondamentales à partir de données de marché.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from financial_analyzer.features.fundamental import FundamentalFeatureEngine
from financial_analyzer.features.pipeline import FeaturePipeline
from financial_analyzer.features.technical import TechnicalFeatureEngine

__all__ = ['TechnicalFeatureEngine', 'FundamentalFeatureEngine', 'FeaturePipeline']
