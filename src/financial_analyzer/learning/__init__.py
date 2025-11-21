"""
Learning Module - Apprentissage continu du portfolio.

Composants:
- PortfolioLearner: Analyse matinale pré-analyse
- Calcul métriques professionnelles (Sharpe, Sortino, Calmar, etc.)
- Détection patterns d'erreurs
- Ajustement automatique paramètres
"""

from financial_analyzer.learning.portfolio_learner import (
    PortfolioLearner,
    PortfolioSnapshot,
    PerformanceInsight,
    LearningResult
)

__all__ = [
    'PortfolioLearner',
    'PortfolioSnapshot',
    'PerformanceInsight',
    'LearningResult'
]
