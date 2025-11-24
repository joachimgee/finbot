"""Tests for DQN/A2C/DDPG agents using unified interface.

Smoke-level training to ensure wrappers instantiate and run minimal timesteps.
"""
import pytest
import numpy as np
from financial_analyzer.rl.environments import TradingEnvironment
from financial_analyzer.rl.agents import DQNAgent, A2CAgent, DDPGAgent


@pytest.fixture(scope="module")
def tiny_env():
	return TradingEnvironment(
		symbols=["AAPL"],
		start_date="2020-01-01",
		end_date="2020-03-31",
		initial_capital=50_000,
		random_start=False,
	)


@pytest.mark.parametrize("agent_cls", [DQNAgent, A2CAgent, DDPGAgent])
def test_agent_init(agent_cls, tiny_env):
	agent = agent_cls(env=tiny_env, verbose=0)
	assert agent.model is not None


@pytest.mark.parametrize("agent_cls", [A2CAgent, DDPGAgent])  # DQN excluded from training due to discrete proxy complexity
def test_agent_train_minimal(agent_cls, tiny_env):
	agent = agent_cls(env=tiny_env, verbose=0)
	agent.train(total_timesteps=50)  # very small
	obs, _ = tiny_env.reset()
	action, _ = agent.predict(obs)
	assert isinstance(action, np.ndarray)
	assert action.shape == (tiny_env.n_assets,)


def test_dqn_predict(tiny_env):
	agent = DQNAgent(env=tiny_env, verbose=0)
	obs, _ = tiny_env.reset()
	action, _ = agent.predict(obs)
	assert isinstance(action, np.ndarray)
	assert action.shape == (tiny_env.n_assets,)

