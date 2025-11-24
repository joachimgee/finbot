"""Tests for EnsembleAgent."""
import pytest
import numpy as np
from financial_analyzer.rl.environments import TradingEnvironment
from financial_analyzer.rl.ensemble import EnsembleAgent


@pytest.fixture
def tiny_env():
    return TradingEnvironment(
        symbols=["AAPL"],
        start_date="2020-01-01",
        end_date="2020-03-31",
        initial_capital=50_000,
        random_start=False,
    )


def test_ensemble_init(tiny_env):
    """Test ensemble initialization."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo', 'a2c'],
        weighting_strategy='equal'
    )
    assert len(ensemble.agents) == 2
    assert 'ppo' in ensemble.agents
    assert 'a2c' in ensemble.agents


def test_ensemble_predict_equal(tiny_env):
    """Test prediction with equal weighting."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo', 'a2c'],
        weighting_strategy='equal'
    )
    obs, _ = tiny_env.reset()
    action, _ = ensemble.predict(obs)
    assert isinstance(action, np.ndarray)
    assert action.shape == (tiny_env.n_assets,)


def test_ensemble_predict_adaptive(tiny_env):
    """Test prediction with adaptive weighting."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo', 'a2c'],
        weighting_strategy='adaptive'
    )
    # Set different sharpe ratios
    ensemble.performance['ppo'].sharpe_ratio = 2.0
    ensemble.performance['a2c'].sharpe_ratio = 0.5
    
    obs, _ = tiny_env.reset()
    action, _ = ensemble.predict(obs)
    assert isinstance(action, np.ndarray)
    
    # Check weights favor PPO
    weights = ensemble.get_weights()
    assert weights['ppo'] > weights['a2c']


def test_ensemble_predict_best(tiny_env):
    """Test prediction with best agent only."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo', 'a2c'],
        weighting_strategy='best'
    )
    ensemble.performance['a2c'].sharpe_ratio = 3.0
    ensemble.performance['ppo'].sharpe_ratio = 1.0
    
    obs, _ = tiny_env.reset()
    action, _ = ensemble.predict(obs)
    assert isinstance(action, np.ndarray)
    
    weights = ensemble.get_weights()
    assert weights['a2c'] == 1.0
    assert weights['ppo'] == 0.0


@pytest.mark.slow
def test_ensemble_train_minimal(tiny_env):
    """Test minimal ensemble training."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['a2c'],  # Single agent for speed
        weighting_strategy='equal'
    )
    ensemble.train(total_timesteps=100)
    obs, _ = tiny_env.reset()
    action, _ = ensemble.predict(obs)
    assert isinstance(action, np.ndarray)


def test_ensemble_evaluate(tiny_env):
    """Test ensemble evaluation."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo', 'a2c'],
        weighting_strategy='equal'
    )
    metrics = ensemble.evaluate(eval_env=tiny_env, n_eval_episodes=2)
    assert 'mean_reward' in metrics
    assert 'std_reward' in metrics
    assert 'ppo_sharpe' in metrics
    assert 'a2c_sharpe' in metrics


def test_get_weights_equal(tiny_env):
    """Test equal weight calculation."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo', 'a2c', 'ddpg'],
        weighting_strategy='equal'
    )
    weights = ensemble.get_weights()
    assert len(weights) == 3
    assert all(abs(w - 1/3) < 1e-6 for w in weights.values())


def test_get_weights_adaptive(tiny_env):
    """Test adaptive weight calculation."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo', 'a2c'],
        weighting_strategy='adaptive'
    )
    ensemble.performance['ppo'].sharpe_ratio = 2.0
    ensemble.performance['a2c'].sharpe_ratio = 1.0
    
    weights = ensemble.get_weights()
    assert weights['ppo'] > weights['a2c']
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_invalid_agent_type(tiny_env):
    """Test error on invalid agent type."""
    with pytest.raises(ValueError, match="Unknown agent type"):
        EnsembleAgent(
            env=tiny_env,
            agent_types=['invalid_agent']
        )


def test_invalid_strategy(tiny_env):
    """Test error on invalid weighting strategy."""
    ensemble = EnsembleAgent(
        env=tiny_env,
        agent_types=['ppo'],
        weighting_strategy='invalid_strategy'
    )
    obs, _ = tiny_env.reset()
    with pytest.raises(ValueError, match="Unknown strategy"):
        ensemble.predict(obs)
