"""
Trading strategies module.

Contains ML/Sentiment-based trading strategies for backtesting engine integration.

Strategies:
- SentimentMomentumStrategy: Combine sentiment analysis with technical momentum
- FactorEnsembleStrategy: Multi-factor ensemble with IC-weighted composite scores (Phase 5.4 Module 4)

Audit references:
- AUDIT_BACKTESTING_PY.md pp. 5-12 (Strategy base class, vectorization)
- AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md pp. 10-15 (momentum strategies)
- AUDIT_ML4T_BOOK.md pp. 48-65 (factor models, IC-weighting)
"""

from financial_analyzer.strategies.sentiment_momentum_strategy import SentimentMomentumStrategy
from financial_analyzer.strategies.factor_ensemble_strategy import FactorEnsembleStrategy

__all__ = [
    'SentimentMomentumStrategy',
    'FactorEnsembleStrategy',
]
