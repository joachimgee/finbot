"""Portfolio module public exports.

Provides unified access to optimization, constraints, rebalancing and
portfolio metrics for Phase 4.

Example:
    >>> from financial_analyzer.portfolio import PortfolioOptimizer, ConstraintSet
    >>> optimizer = PortfolioOptimizer(returns)
    >>> constraints = ConstraintSet(max_weight=0.15, min_weight=0.0)
    >>> result = optimizer.optimize_min_variance()
    >>> result['weights'].head()
"""

from .optimizer import (
    PortfolioOptimizer,
    OptimizationResult,
    calculate_efficient_frontier,
    calculate_min_variance,
    calculate_max_sharpe,
    calculate_risk_parity,
    calculate_equal_weight,
)
from .constraints import (
    ConstraintSet,
    ConstraintViolation,
    PortfolioConstraints,
)
from .rebalancer import (
    PortfolioRebalancer,
    RebalanceResult,
    rebalance_periodic,
    rebalance_threshold,
    rebalance_calendar,
)
from .metrics import (
    calculate_portfolio_return,
    calculate_portfolio_volatility,
    calculate_portfolio_sharpe,
    calculate_correlation_matrix,
    calculate_var,
    calculate_cvar,
    calculate_diversification_ratio,
    calculate_herfindahl_index,
)

__all__ = [
    # Optimizer
    "PortfolioOptimizer",
    "OptimizationResult",
    "calculate_efficient_frontier",
    "calculate_min_variance",
    "calculate_max_sharpe",
    "calculate_risk_parity",
    "calculate_equal_weight",
    # Constraints
    "ConstraintSet",
    "ConstraintViolation",
    "PortfolioConstraints",
    # Rebalancer
    "PortfolioRebalancer",
    "RebalanceResult",
    "rebalance_periodic",
    "rebalance_threshold",
    "rebalance_calendar",
    # Metrics
    "calculate_portfolio_return",
    "calculate_portfolio_volatility",
    "calculate_portfolio_sharpe",
    "calculate_correlation_matrix",
    "calculate_var",
    "calculate_cvar",
    "calculate_diversification_ratio",
    "calculate_herfindahl_index",
]
