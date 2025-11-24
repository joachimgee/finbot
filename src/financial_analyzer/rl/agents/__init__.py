"""RL Agents package exposing multiple algorithms.

Exports:
	PPOAgent: Proximal Policy Optimization agent.
	DQNAgent: Deep Q-Network agent (with discrete proxy wrapper if needed).
	A2CAgent: Advantage Actor-Critic agent.
	DDPGAgent: Deep Deterministic Policy Gradient agent.
"""

from .ppo_agent import PPOAgent
from .dqn_agent import DQNAgent
from .a2c_agent import A2CAgent
from .ddpg_agent import DDPGAgent

__all__ = ["PPOAgent", "DQNAgent", "A2CAgent", "DDPGAgent"]

from financial_analyzer.rl.agents.ppo_agent import PPOAgent

__all__ = ['PPOAgent']
