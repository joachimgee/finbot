"""Portfolio module public exports.

Provides unified access to optimization and constraint objects for Phase 4.

Example:
    >>> from financial_analyzer.portfolio import PortfolioOptimizer, ConstraintSet
    >>> optimizer = PortfolioOptimizer(returns)
    >>> constraints = ConstraintSet(max_weight=0.15, min_weight=0.0)
    >>> result = optimizer.optimize_min_variance()
    >>> result['weights'].head()
"""

from .optimizer import PortfolioOptimizer, OptimizationResult
from .constraints import ConstraintSet, ConstraintViolation

__all__ = [
    "PortfolioOptimizer",
    "OptimizationResult",
    "ConstraintSet",
    "ConstraintViolation",
]
