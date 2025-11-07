"""
Portfolio Optimization module.

Fournit des outils pour optimisation de portefeuille :

- Mean-Variance optimization (Efficient Frontier)
- Risk constraints
- Rebalancing strategies
- Portfolio metrics
"""

from financial_analyzer.portfolio.optimizer import (
    PortfolioOptimizer,
    calculate_efficient_frontier,
    calculate_min_variance,
    calculate_max_sharpe,
    calculate_risk_parity,
    calculate_equal_weight,
)
from financial_analyzer.portfolio.constraints import (
    PortfolioConstraints,
    add_sector_constraint,
    add_allocation_limits,
    add_concentration_limit,
)
from financial_analyzer.portfolio.rebalancer import (
    PortfolioRebalancer,
    rebalance_periodic,
    rebalance_threshold,
    rebalance_calendar,
)
from financial_analyzer.portfolio.metrics import (
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
    'calculate_efficient_frontier',
    'calculate_min_variance',
    'calculate_max_sharpe',
    'calculate_risk_parity',
    'calculate_equal_weight',
    'PortfolioConstraints',
    'add_sector_constraint',
    'add_allocation_limits',
    'add_concentration_limit',
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
