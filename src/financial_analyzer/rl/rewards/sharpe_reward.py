"""
Reward Functions for Reinforcement Learning Trading.

Collection of reward functions for RL agents, focusing on risk-adjusted
performance metrics used in quantitative finance:

1. Sharpe Ratio Reward (Sharpe 1966)
   - Risk-adjusted return: (mean - rf) / std
   - Most widely used in academic literature
   
2. Sortino Ratio Reward (Sortino 1991)
   - Downside risk only: (mean - rf) / downside_std
   - Better for asymmetric return distributions
   
3. Calmar Ratio Reward
   - Return vs max drawdown: annualized_return / max_dd
   - Focuses on worst-case scenario

Integration:
    - financial_analyzer.risk.risk_metrics (for advanced metrics)
    - financial_analyzer.backtest.metrics (for backtesting)

References:
    - Sharpe (1966): "Mutual Fund Performance"
    - Sortino (1991): "Downside Risk"
    - FinRL (Yang et al. 2020): Reward shaping for trading

Example:
    >>> from financial_analyzer.rl.rewards import calculate_sharpe_reward
    >>> returns = np.array([0.01, -0.005, 0.02, 0.015, -0.01])
    >>> reward = calculate_sharpe_reward(returns, rf_rate=0.02)
"""

from __future__ import annotations

from typing import Optional

from .registry import register_reward

import numpy as np


@register_reward("sharpe")
def calculate_sharpe_reward(
    returns: np.ndarray,
    rf_rate: float = 0.02,
    annualization_factor: int = 252,
) -> float:
    """
    Calculate Sharpe ratio reward.
    
    Sharpe ratio measures risk-adjusted returns by comparing excess return
    to volatility. Higher values indicate better risk-adjusted performance.
    
    Formula:
        Sharpe = (mean_return - rf_rate) / std_return
        Annualized: Sharpe * sqrt(252) for daily returns
    
    Args:
        returns: Array of portfolio returns
        rf_rate: Risk-free rate (annualized, default 2%)
        annualization_factor: 252 for daily, 52 for weekly, 12 for monthly
        
    Returns:
        sharpe_ratio: Annualized Sharpe ratio
        
    Example:
        >>> returns = np.array([0.01, -0.005, 0.02, 0.015, -0.01])
        >>> sharpe = calculate_sharpe_reward(returns)
        >>> print(f"Sharpe: {sharpe:.4f}")
    """
    if len(returns) < 2:
        return 0.0
    
    # Convert to numpy array
    returns = np.asarray(returns, dtype=np.float64)
    
    # Calculate mean and std
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)
    
    if std_return < 1e-8:
        return 0.0
    
    # Annualize
    annualized_mean = mean_return * annualization_factor
    annualized_std = std_return * np.sqrt(annualization_factor)
    
    # Sharpe ratio
    sharpe = (annualized_mean - rf_rate) / annualized_std
    
    return float(sharpe)


@register_reward("sortino")
def calculate_sortino_reward(
    returns: np.ndarray,
    rf_rate: float = 0.02,
    annualization_factor: int = 252,
    target_return: Optional[float] = None,
) -> float:
    """
    Calculate Sortino ratio reward.
    
    Sortino ratio is similar to Sharpe but only considers downside volatility,
    making it more appropriate for strategies with asymmetric returns.
    
    Formula:
        Sortino = (mean_return - target) / downside_std
        where downside_std = std(returns[returns < target])
    
    Args:
        returns: Array of portfolio returns
        rf_rate: Risk-free rate (annualized, default 2%)
        annualization_factor: 252 for daily, 52 for weekly, 12 for monthly
        target_return: Target return threshold (default: rf_rate)
        
    Returns:
        sortino_ratio: Annualized Sortino ratio
        
    Example:
        >>> returns = np.array([0.01, -0.005, 0.02, 0.015, -0.01])
        >>> sortino = calculate_sortino_reward(returns)
        >>> print(f"Sortino: {sortino:.4f}")
    """
    if len(returns) < 2:
        return 0.0
    
    # Convert to numpy array
    returns = np.asarray(returns, dtype=np.float64)
    
    # Target return (use rf_rate if not specified)
    if target_return is None:
        target_return = rf_rate / annualization_factor
    
    # Calculate mean return
    mean_return = np.mean(returns)
    
    # Downside returns (below target)
    downside_returns = returns[returns < target_return]
    
    if len(downside_returns) < 2:
        # No downside risk, use Sharpe-like calculation
        std_return = np.std(returns, ddof=1)
        if std_return < 1e-8:
            return 0.0
        annualized_mean = mean_return * annualization_factor
        annualized_std = std_return * np.sqrt(annualization_factor)
        return float((annualized_mean - rf_rate) / annualized_std)
    
    # Downside deviation
    downside_std = np.std(downside_returns, ddof=1)
    
    if downside_std < 1e-8:
        return 0.0
    
    # Annualize
    annualized_mean = mean_return * annualization_factor
    annualized_downside_std = downside_std * np.sqrt(annualization_factor)
    
    # Sortino ratio
    sortino = (annualized_mean - rf_rate) / annualized_downside_std
    
    return float(sortino)


@register_reward("calmar")
def calculate_calmar_reward(
    returns: np.ndarray,
    annualization_factor: int = 252,
) -> float:
    """
    Calculate Calmar ratio reward.
    
    Calmar ratio measures return relative to maximum drawdown, focusing
    on the worst-case scenario rather than volatility.
    
    Formula:
        Calmar = annualized_return / abs(max_drawdown)
    
    Args:
        returns: Array of portfolio returns
        annualization_factor: 252 for daily, 52 for weekly, 12 for monthly
        
    Returns:
        calmar_ratio: Calmar ratio
        
    Example:
        >>> returns = np.array([0.01, -0.005, 0.02, 0.015, -0.01])
        >>> calmar = calculate_calmar_reward(returns)
        >>> print(f"Calmar: {calmar:.4f}")
    """
    if len(returns) < 2:
        return 0.0
    
    # Convert to numpy array
    returns = np.asarray(returns, dtype=np.float64)
    
    # Annualized return
    mean_return = np.mean(returns)
    annualized_return = mean_return * annualization_factor
    
    # Calculate maximum drawdown
    cumulative = np.exp(np.cumsum(returns))
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / (running_max + 1e-8)
    max_drawdown = np.min(drawdown)
    
    if abs(max_drawdown) < 1e-8:
        return 0.0
    
    # Calmar ratio
    calmar = annualized_return / abs(max_drawdown)
    
    return float(calmar)


@register_reward("profit_factor")
def calculate_profit_factor_reward(
    returns: np.ndarray,
) -> float:
    """
    Calculate profit factor reward.
    
    Profit factor is the ratio of gross profit to gross loss,
    commonly used in systematic trading strategies.
    
    Formula:
        Profit Factor = sum(winning_returns) / abs(sum(losing_returns))
        If no losses, returns 10.0 (capped)
        If no wins, returns 0.0
    
    Args:
        returns: Array of portfolio returns
        
    Returns:
        profit_factor: Ratio of wins to losses (>1 is profitable, 0 = no wins)
        
    Example:
        >>> returns = np.array([0.01, -0.005, 0.02, 0.015, -0.01])
        >>> pf = calculate_profit_factor_reward(returns)
        >>> print(f"Profit Factor: {pf:.4f}")
    """
    if len(returns) < 2:
        return 1.0
    
    # Convert to numpy array
    returns = np.asarray(returns, dtype=np.float64)
    
    # Separate wins and losses
    winning_returns = returns[returns > 0]
    losing_returns = returns[returns < 0]
    
    # Calculate sums
    gross_profit = np.sum(winning_returns) if len(winning_returns) > 0 else 0.0
    gross_loss = np.abs(np.sum(losing_returns)) if len(losing_returns) > 0 else 0.0
    
    if gross_loss < 1e-8:
        # No losses, perfect strategy
        return 10.0 if gross_profit > 0 else 1.0
    
    if gross_profit < 1e-8:
        # No wins, losing strategy
        return 0.0
    
    profit_factor = gross_profit / gross_loss
    
    return float(profit_factor)


@register_reward("risk_adjusted")
def calculate_risk_adjusted_reward(
    returns: np.ndarray,
    rf_rate: float = 0.02,
    annualization_factor: int = 252,
    sharpe_weight: float = 0.5,
    sortino_weight: float = 0.3,
    calmar_weight: float = 0.2,
) -> float:
    """
    Calculate combined risk-adjusted reward.
    
    Weighted combination of multiple risk-adjusted metrics to provide
    a more robust reward signal that balances different risk perspectives.
    
    Formula:
        Combined = w1*Sharpe + w2*Sortino + w3*Calmar
    
    Args:
        returns: Array of portfolio returns
        rf_rate: Risk-free rate (annualized)
        annualization_factor: 252 for daily, 52 for weekly, 12 for monthly
        sharpe_weight: Weight for Sharpe ratio (default 0.5)
        sortino_weight: Weight for Sortino ratio (default 0.3)
        calmar_weight: Weight for Calmar ratio (default 0.2)
        
    Returns:
        combined_reward: Weighted combination of risk-adjusted metrics
        
    Example:
        >>> returns = np.array([0.01, -0.005, 0.02, 0.015, -0.01])
        >>> reward = calculate_risk_adjusted_reward(returns)
        >>> print(f"Combined Reward: {reward:.4f}")
    """
    if len(returns) < 2:
        return 0.0
    
    # Normalize weights
    total_weight = sharpe_weight + sortino_weight + calmar_weight
    sharpe_weight /= total_weight
    sortino_weight /= total_weight
    calmar_weight /= total_weight
    
    # Calculate individual metrics
    sharpe = calculate_sharpe_reward(returns, rf_rate, annualization_factor)
    sortino = calculate_sortino_reward(returns, rf_rate, annualization_factor)
    calmar = calculate_calmar_reward(returns, annualization_factor)
    
    # Normalize metrics to similar scale (clip extreme values)
    sharpe_clipped = np.clip(sharpe, -3.0, 5.0)
    sortino_clipped = np.clip(sortino, -3.0, 5.0)
    calmar_clipped = np.clip(calmar, -3.0, 5.0)
    
    # Weighted combination
    combined = (
        sharpe_weight * sharpe_clipped +
        sortino_weight * sortino_clipped +
        calmar_weight * calmar_clipped
    )
    
    return float(combined)


__all__ = [
    'calculate_sharpe_reward',
    'calculate_sortino_reward',
    'calculate_calmar_reward',
    'calculate_profit_factor_reward',
    'calculate_risk_adjusted_reward',
]
