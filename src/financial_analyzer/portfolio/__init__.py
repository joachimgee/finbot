"""
Portfolio Optimization module.

Fournit des outils pour optimisation de portefeuille :

- Mean-Variance optimization (Efficient Frontier)
- Monte Carlo optimizer (compatibilité tests internes)
- Risk constraints
- Rebalancing strategies
- Portfolio metrics
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
    PortfolioConstraints,
    add_sector_constraint,
    add_allocation_limits,
    add_concentration_limit,
    WeightBounds,
    MaxPositionsConstraint,
    GroupConstraint,
    MaxTurnoverConstraint,
    LeverageConstraint,
    RiskBudgetConstraint,
    Constraints,
)
from .rebalancer import (
    PortfolioRebalancer,
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
    'PortfolioOptimizer',
    'OptimizationResult',
    'calculate_efficient_frontier',
    'calculate_min_variance',
    'calculate_max_sharpe',
    'calculate_risk_parity',
    'calculate_equal_weight',
    'PortfolioConstraints',
    'add_sector_constraint',
    'add_allocation_limits',
    'add_concentration_limit',
    'WeightBounds',
    'MaxPositionsConstraint',
    'GroupConstraint',
    'MaxTurnoverConstraint',
    'LeverageConstraint',
    'RiskBudgetConstraint',
    'Constraints',
    'PortfolioRebalancer',
    'rebalance_periodic',
    'rebalance_threshold',
    'rebalance_calendar',
    'calculate_portfolio_return',
    'calculate_portfolio_volatility',
    'calculate_portfolio_sharpe',
    'calculate_correlation_matrix',
    'calculate_var',
    'calculate_cvar',
    'calculate_diversification_ratio',
    'calculate_herfindahl_index',
]
