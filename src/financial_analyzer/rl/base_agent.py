"""BaseRLAgent abstraction for FinBot RL models.

Provides a unified interface so RLTrainer and pipelines can interact
with different Stable-Baselines3 algorithms (PPO, DQN, A2C, DDPG, etc.).

All concrete agents must implement:
    - _init_model()
    - underlying SB3 model stored in self.model

Common methods supplied:
    - train()
    - predict()
    - evaluate()
    - save()
    - load() (classmethod)

NOTE: Keep this lightweight to avoid heavy coupling. The environment is
assumed to follow Gymnasium API returning (obs, info) on reset.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np

class BaseRLAgent:
    """Abstract base wrapper around a Stable-Baselines3 model.

    Attributes:
        env: Environment instance
        model: Underlying Stable-Baselines3 algorithm instance
        best_model_path: Optional path to a best checkpoint
    """
    def __init__(self, env: Any, **kwargs: Any) -> None:
        self.env = env
        self.model = None  # set by _init_model
        self.best_model_path: Optional[Path] = None
        self._init_model(env, **kwargs)

    # --- Must be implemented by subclass ---
    def _init_model(self, env: Any, **kwargs: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    # --- Training ---
    def train(
        self,
        total_timesteps: int,
        eval_env: Optional[Any] = None,
        eval_freq: int = 0,
        n_eval_episodes: int = 5,
        save_freq: int = 0,
        save_path: Optional[str] = None,
        best_model_save_path: Optional[str] = None,
        log_interval: int = 10,
    ) -> BaseRLAgent:
        """Train agent; supports optional evaluation & checkpointing.

        Arguments mirror PPOAgent for consistency.
        """
        from stable_baselines3.common.callbacks import (
            CallbackList,
            EvalCallback,
            CheckpointCallback,
        )
        callbacks = []
        if save_freq > 0 and save_path:
            Path(save_path).mkdir(parents=True, exist_ok=True)
            callbacks.append(
                CheckpointCallback(
                    save_freq=save_freq,
                    save_path=save_path,
                    name_prefix=self.__class__.__name__.lower(),
                    verbose=0,
                )
            )
        if eval_env is not None and eval_freq > 0:
            Path(best_model_save_path or "./models/best").mkdir(parents=True, exist_ok=True)
            eval_cb = EvalCallback(
                eval_env=eval_env,
                eval_freq=eval_freq,
                n_eval_episodes=n_eval_episodes,
                best_model_save_path=best_model_save_path,
                log_path=best_model_save_path,
                deterministic=True,
                render=False,
                verbose=0,
            )
            callbacks.append(eval_cb)
            if best_model_save_path:
                self.best_model_path = Path(best_model_save_path) / "best_model.zip"
        callback_list = CallbackList(callbacks) if callbacks else None
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callback_list,
            log_interval=log_interval,
            progress_bar=True,
        )
        return self

    # --- Prediction ---
    def predict(self, observation: np.ndarray, deterministic: bool = True) -> Tuple[np.ndarray, Any]:
        action, state = self.model.predict(observation, deterministic=deterministic)
        # Ensure 1D action matches environment action space shape
        import numpy as np
        if hasattr(self.env, "action_space") and hasattr(self.env.action_space, "shape") and self.env.action_space.shape is not None:
            desired_shape = self.env.action_space.shape
            action = np.array(action, dtype=np.float32).reshape(desired_shape)
        else:
            action = np.array(action, dtype=np.float32).ravel()
        return action, state

    # --- Evaluation ---
    def evaluate(self, eval_env: Any, n_eval_episodes: int = 10, deterministic: bool = True) -> Dict[str, float]:
        rewards = []
        lengths = []
        for _ in range(n_eval_episodes):
            obs, info = eval_env.reset()
            done = False
            ep_reward = 0.0
            ep_length = 0
            while not done:
                action, _ = self.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, info = eval_env.step(action)
                done = terminated or truncated
                ep_reward += reward
                ep_length += 1
            rewards.append(ep_reward)
            lengths.append(ep_length)
        import numpy as np
        return {
            "mean_reward": float(np.mean(rewards)),
            "std_reward": float(np.std(rewards)),
            "mean_length": float(np.mean(lengths)),
            "std_length": float(np.std(lengths)),
        }

    # --- Persistence ---
    def save(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix != ".zip":
            p = p.with_suffix(".zip")
        self.model.save(str(p))

    @classmethod
    def load(cls, path: str, env: Optional[Any] = None, **kwargs: Any) -> BaseRLAgent:
        from stable_baselines3.common.base_class import BaseAlgorithm
        p = Path(path)
        if p.suffix != ".zip":
            p = p.with_suffix(".zip")
        if not p.exists():
            raise FileNotFoundError(f"Model not found: {p}")
        # Instantiate empty then load
        dummy = cls.__new__(cls)
        dummy.env = env
        dummy.best_model_path = None
        dummy.model = BaseAlgorithm.load(str(p), env=env)  # type: ignore
        return dummy

__all__ = ["BaseRLAgent"]
