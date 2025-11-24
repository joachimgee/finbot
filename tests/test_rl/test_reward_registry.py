"""Tests for reward registry system."""
import pytest
from financial_analyzer.rl.rewards.registry import get_reward, list_rewards


def test_registry_contains_core_rewards():
    rewards = list_rewards()
    for name in ["sharpe", "sortino", "calmar", "profit_factor", "risk_adjusted"]:
        assert name in rewards
        assert callable(rewards[name])


def test_get_reward_functionality():
    sharpe_fn = get_reward("sharpe")
    assert sharpe_fn is not None
    # Simple call
    import numpy as np
    val = sharpe_fn(np.array([0.01, 0.02, -0.01]))
    assert isinstance(val, float)


def test_unknown_reward_returns_none():
    assert get_reward("nonexistent_reward") is None


def test_registry_is_copy():
    rewards = list_rewards()
    rewards["sharpe"] = None
    # Original should remain intact
    assert callable(get_reward("sharpe"))
