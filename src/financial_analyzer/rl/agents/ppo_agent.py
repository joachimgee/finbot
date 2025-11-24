"""
Proximal Policy Optimization (PPO) Agent for Trading.

PPO is the most stable and widely-used deep RL algorithm for continuous
action spaces. It's particularly well-suited for portfolio management due to:
    - Policy gradient with clipped objective (stable training)
    - Sample efficient (on-policy with multiple epochs)
    - Robust hyperparameters across different environments

Architecture:
    - Policy Network: Actor outputs mean/std for Gaussian distribution
    - Value Network: Critic estimates state value function
    - Advantage: GAE (Generalized Advantage Estimation)
    - Optimization: Clipped surrogate objective

Integration:
    - Stable-Baselines3 PPO implementation
    - TradingEnvironment (gym.Env)
    - TensorBoard logging
    - Model checkpointing

References:
    - Schulman et al. (2017): "Proximal Policy Optimization Algorithms"
    - Stable-Baselines3: https://stable-baselines3.readthedocs.io/
    - FinRL (Yang et al. 2020): PPO for trading

Example:
    >>> from financial_analyzer.rl.agents import PPOAgent
    >>> from financial_analyzer.rl.environments import TradingEnvironment
    >>> 
    >>> env = TradingEnvironment(symbols=['AAPL', 'MSFT'], ...)
    >>> agent = PPOAgent(env, learning_rate=3e-4)
    >>> agent.train(total_timesteps=100_000)
    >>> agent.save("models/ppo_trading_agent")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CallbackList,
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class PPOAgent:
    """
    Proximal Policy Optimization agent for stock trading.
    
    Wraps Stable-Baselines3 PPO with trading-specific configurations:
        - MlpPolicy with [256, 256] hidden layers
        - Learning rate: 3e-4 (standard for PPO)
        - Batch size: 64 (for stable gradients)
        - n_steps: 2048 (rollout buffer size)
        - GAE lambda: 0.95 (advantage estimation)
        - Clip range: 0.2 (policy clipping)
        - Entropy coefficient: 0.01 (exploration)
    
    Attributes:
        env: Trading environment (gym.Env)
        model: PPO model from Stable-Baselines3
        tensorboard_log: Path to TensorBoard logs
        best_model_path: Path to best model checkpoint
    """
    
    def __init__(
        self,
        env: Any,  # gym.Env or VecEnv
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_range: float = 0.2,
        ent_coef: float = 0.01,
        vf_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        policy_kwargs: Optional[Dict[str, Any]] = None,
        tensorboard_log: Optional[str] = "./logs/rl_training",
        verbose: int = 1,
        device: str = "auto",
    ):
        """
        Initialize PPO agent.
        
        Args:
            env: Trading environment (TradingEnvironment)
            learning_rate: Learning rate for Adam optimizer
            n_steps: Number of steps per rollout (buffer size)
            batch_size: Minibatch size for SGD
            n_epochs: Number of epochs for policy update
            gamma: Discount factor
            gae_lambda: GAE lambda parameter
            clip_range: Clipping parameter for PPO objective
            ent_coef: Entropy coefficient (exploration)
            vf_coef: Value function coefficient
            max_grad_norm: Gradient clipping threshold
            policy_kwargs: Additional policy network arguments
            tensorboard_log: Path to TensorBoard log directory
            verbose: Verbosity level (0: none, 1: info, 2: debug)
            device: Device for training ("cpu", "cuda", "auto")
        """
        self.env = env
        self.learning_rate = learning_rate
        self.tensorboard_log = tensorboard_log
        self.verbose = verbose
        
        # Default policy kwargs (2-layer MLP with 256 units)
        if policy_kwargs is None:
            import torch.nn as nn
            policy_kwargs = {
                "net_arch": [256, 256],
                "activation_fn": nn.Tanh,  # Must be class, not string
            }
        
        # Initialize PPO model
        self.model = PPO(
            policy="MlpPolicy",
            env=env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            ent_coef=ent_coef,
            vf_coef=vf_coef,
            max_grad_norm=max_grad_norm,
            policy_kwargs=policy_kwargs,
            tensorboard_log=tensorboard_log,
            verbose=verbose,
            device=device,
        )
        
        self.best_model_path = None
        
        logger.info(
            f"PPOAgent initialized: lr={learning_rate}, "
            f"n_steps={n_steps}, batch_size={batch_size}, "
            f"device={self.model.device}"
        )
    
    def train(
        self,
        total_timesteps: int = 100_000,
        callback: Optional[Union[BaseCallback, list]] = None,
        log_interval: int = 10,
        eval_env: Optional[Any] = None,
        eval_freq: int = 5_000,
        n_eval_episodes: int = 5,
        save_freq: int = 10_000,
        save_path: Optional[str] = "./models/checkpoints",
        best_model_save_path: Optional[str] = "./models/best",
    ) -> PPOAgent:
        """
        Train PPO agent.
        
        Args:
            total_timesteps: Total number of training timesteps
            callback: Custom callback(s) for training
            log_interval: Log training info every N episodes
            eval_env: Separate environment for evaluation
            eval_freq: Evaluate every N timesteps
            n_eval_episodes: Number of episodes for evaluation
            save_freq: Save checkpoint every N timesteps
            save_path: Path for regular checkpoints
            best_model_save_path: Path for best model (based on eval)
            
        Returns:
            self: Trained agent
        """
        logger.info(f"Starting PPO training: {total_timesteps} timesteps")
        
        # Setup callbacks
        callbacks = []
        
        # Checkpoint callback
        if save_path is not None:
            Path(save_path).mkdir(parents=True, exist_ok=True)
            checkpoint_callback = CheckpointCallback(
                save_freq=save_freq,
                save_path=save_path,
                name_prefix="ppo_trading",
                verbose=1,
            )
            callbacks.append(checkpoint_callback)
        
        # Evaluation callback
        if eval_env is not None:
            Path(best_model_save_path).mkdir(parents=True, exist_ok=True)
            eval_callback = EvalCallback(
                eval_env=eval_env,
                eval_freq=eval_freq,
                n_eval_episodes=n_eval_episodes,
                best_model_save_path=best_model_save_path,
                log_path=best_model_save_path,
                deterministic=True,
                render=False,
                verbose=1,
            )
            callbacks.append(eval_callback)
            self.best_model_path = Path(best_model_save_path) / "best_model.zip"
        
        # Custom callbacks
        if callback is not None:
            if isinstance(callback, list):
                callbacks.extend(callback)
            else:
                callbacks.append(callback)
        
        # Combine callbacks
        callback_list = CallbackList(callbacks) if callbacks else None
        
        # Train model
        try:
            self.model.learn(
                total_timesteps=total_timesteps,
                callback=callback_list,
                log_interval=log_interval,
                progress_bar=True,
            )
            logger.info("Training completed successfully")
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
        
        return self
    
    def predict(
        self,
        observation: np.ndarray,
        deterministic: bool = True,
    ) -> np.ndarray:
        """
        Predict action for given observation.
        
        Args:
            observation: Current state observation
            deterministic: If True, use mean action (no sampling)
            
        Returns:
            action: Predicted action vector
            states: Recurrent states (None for MLP policies)
        """
        action, _states = self.model.predict(
            observation,
            deterministic=deterministic
        )
        # Ensure action is 1D (squeeze if batched)
        return np.squeeze(action), _states
    
    def evaluate(
        self,
        eval_env: Any,
        n_eval_episodes: int = 10,
        deterministic: bool = True,
    ) -> Dict[str, float]:
        """
        Evaluate agent performance.
        
        Args:
            eval_env: Environment for evaluation
            n_eval_episodes: Number of evaluation episodes
            deterministic: Use deterministic actions
            
        Returns:
            metrics: Dictionary with mean reward, std, episode lengths
        """
        logger.info(f"Evaluating agent for {n_eval_episodes} episodes")
        
        episode_rewards = []
        episode_lengths = []
        
        for episode in range(n_eval_episodes):
            obs, info = eval_env.reset()
            done = False
            episode_reward = 0.0
            episode_length = 0
            
            while not done:
                action, _ = self.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, info = eval_env.step(action)
                done = terminated or truncated
                episode_reward += reward
                episode_length += 1
            
            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
            
            logger.debug(
                f"Eval episode {episode + 1}/{n_eval_episodes}: "
                f"reward={episode_reward:.4f}, length={episode_length}"
            )
        
        metrics = {
            "mean_reward": np.mean(episode_rewards),
            "std_reward": np.std(episode_rewards),
            "mean_length": np.mean(episode_lengths),
            "std_length": np.std(episode_lengths),
        }
        
        logger.info(
            f"Evaluation results: mean_reward={metrics['mean_reward']:.4f} "
            f"± {metrics['std_reward']:.4f}"
        )
        
        return metrics
    
    def save(self, path: str) -> None:
        """
        Save model to disk.
        
        Args:
            path: Path to save model (without extension)
        """
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add .zip extension if not present
        if save_path.suffix != ".zip":
            save_path = save_path.with_suffix(".zip")
        
        self.model.save(str(save_path))
        logger.info(f"Model saved to {save_path}")
    
    @classmethod
    def load(
        cls,
        path: str,
        env: Optional[Any] = None,
        device: str = "auto",
    ) -> PPOAgent:
        """
        Load model from disk.
        
        Args:
            path: Path to saved model
            env: Environment for loaded model (optional)
            device: Device for model ("cpu", "cuda", "auto")
            
        Returns:
            agent: Loaded PPO agent
        """
        load_path = Path(path)
        if load_path.suffix != ".zip":
            load_path = load_path.with_suffix(".zip")
        
        if not load_path.exists():
            raise FileNotFoundError(f"Model not found: {load_path}")
        
        logger.info(f"Loading model from {load_path}")
        
        # Load PPO model
        model = PPO.load(str(load_path), env=env, device=device)
        
        # Create agent instance
        agent = cls.__new__(cls)
        agent.model = model
        agent.env = env if env is not None else model.get_env()
        agent.learning_rate = model.learning_rate
        agent.tensorboard_log = None
        agent.verbose = 1
        agent.best_model_path = None
        
        logger.info("Model loaded successfully")
        
        return agent
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get model hyperparameters."""
        return {
            "learning_rate": self.model.learning_rate,
            "n_steps": self.model.n_steps,
            "batch_size": self.model.batch_size,
            "n_epochs": self.model.n_epochs,
            "gamma": self.model.gamma,
            "gae_lambda": self.model.gae_lambda,
            "clip_range": self.model.clip_range,
            "ent_coef": self.model.ent_coef,
            "vf_coef": self.model.vf_coef,
            "max_grad_norm": self.model.max_grad_norm,
        }
    
    def __repr__(self) -> str:
        """String representation."""
        params = self.get_parameters()
        return (
            f"PPOAgent(lr={params['learning_rate']}, "
            f"n_steps={params['n_steps']}, "
            f"batch_size={params['batch_size']})"
        )


__all__ = ['PPOAgent']
