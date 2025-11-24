"""A2CAgent wrapper using BaseRLAgent abstraction."""
from __future__ import annotations
from typing import Any
from stable_baselines3 import A2C
from ..base_agent import BaseRLAgent

class A2CAgent(BaseRLAgent):
    def _init_model(self, env: Any, **kwargs: Any) -> None:
        self.model = A2C("MlpPolicy", env, **kwargs)

__all__ = ["A2CAgent"]
