"""DQNAgent wrapper using BaseRLAgent abstraction."""
from __future__ import annotations
from typing import Any
from stable_baselines3 import DQN
from ..base_agent import BaseRLAgent

class DQNAgent(BaseRLAgent):
    def _init_model(self, env: Any, **kwargs: Any) -> None:
        # DQN is for discrete action spaces; our trading env is continuous.
        # For now we approximate by discretizing each action into {-1,0,1} applied independently
        # which explodes action space if multi-asset. Simplify: single aggregated action controlling all.
        # Placeholder minimal discrete wrapper:
        from gymnasium import spaces
        import gymnasium as gym
        import numpy as np
        if not isinstance(env.action_space, spaces.Discrete):
            # Build a proxy Env translating discrete {-1,0,1} to continuous vector.
            base_env = env
            class DiscreteProxyEnv(gym.Env):  # type: ignore
                metadata = {"render_modes": []}
                def __init__(self):
                    self.action_space = spaces.Discrete(3)
                    self.observation_space = base_env.observation_space
                def reset(self, *, seed: int | None = None, options: dict | None = None):
                    return base_env.reset(seed=seed)
                def step(self, action: int):
                    if action == 0:
                        vec = np.zeros(base_env.action_space.shape, dtype=np.float32)
                    elif action == 1:
                        vec = np.ones(base_env.action_space.shape, dtype=np.float32)
                    else:  # action == 2 mapped to sell
                        vec = -np.ones(base_env.action_space.shape, dtype=np.float32)
                    return base_env.step(vec)
                def render(self):
                    return None
                def close(self):
                    return None
            env = DiscreteProxyEnv()
        self.model = DQN("MlpPolicy", env, **kwargs)

__all__ = ["DQNAgent"]
