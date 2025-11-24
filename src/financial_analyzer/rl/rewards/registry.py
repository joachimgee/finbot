"""Reward registry for RL training.

Provides a lightweight plugin system to register reward functions by name.
Usage:
    from financial_analyzer.rl.rewards.registry import register_reward, get_reward

    @register_reward("sharpe")
    def calculate_sharpe(...):
        ...

    reward_fn = get_reward("sharpe")
    value = reward_fn(returns)
"""
from __future__ import annotations
from typing import Callable, Dict, Optional

_REWARD_REGISTRY: Dict[str, Callable] = {}

def register_reward(name: str) -> Callable:
    """Decorator to register a reward function.

    Args:
        name: Unique identifier (lowercase recommended).
    Returns:
        Wrapped function (unchanged) while storing in registry.
    """
    def decorator(func: Callable) -> Callable:
        key = name.lower()
        if key in _REWARD_REGISTRY:
            # Allow overwrite but warn
            import logging
            logging.getLogger(__name__).warning(f"Reward '{key}' overwritten in registry")
        _REWARD_REGISTRY[key] = func
        return func
    return decorator

def get_reward(name: str) -> Optional[Callable]:
    """Retrieve reward function by name."""
    return _REWARD_REGISTRY.get(name.lower())

def list_rewards() -> Dict[str, Callable]:
    """Return a copy of the registry."""
    return dict(_REWARD_REGISTRY)

__all__ = ["register_reward", "get_reward", "list_rewards"]
