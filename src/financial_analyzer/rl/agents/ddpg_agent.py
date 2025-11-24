"""DDPGAgent wrapper using BaseRLAgent abstraction."""
from __future__ import annotations
from typing import Any
from stable_baselines3 import DDPG
from ..base_agent import BaseRLAgent

class DDPGAgent(BaseRLAgent):
    def _init_model(self, env: Any, **kwargs: Any) -> None:
        self.model = DDPG("MlpPolicy", env, **kwargs)

__all__ = ["DDPGAgent"]
