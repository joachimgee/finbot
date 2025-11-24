"""Ensemble RL Agent combining multiple algorithms for robust predictions.

Implements weighted voting and meta-learning strategies to combine:
    - PPO (Proximal Policy Optimization)
    - A2C (Advantage Actor-Critic)
    - DDPG (Deep Deterministic Policy Gradient)

Architecture:
    1. Train individual agents independently
    2. Evaluate recent performance (Sharpe, Win Rate)
    3. Weight predictions by performance metrics
    4. Combine via weighted average or majority vote

References:
    - Yang et al. (2020): FinRL ICAIF paper (ensemble strategies)
    - Breiman (1996): Bagging predictors
    - Wolpert (1992): Stacked generalization

Example:
    >>> from financial_analyzer.rl.ensemble import EnsembleAgent
    >>> ensemble = EnsembleAgent(
    ...     env=trading_env,
    ...     agent_types=['ppo', 'a2c', 'ddpg'],
    ...     weights='adaptive'
    ... )
    >>> ensemble.train(total_timesteps=50_000)
    >>> action = ensemble.predict(obs)
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.rl.agents import PPOAgent, A2CAgent, DDPGAgent

logger = get_logger(__name__)


@dataclass
class AgentPerformance:
    """Track individual agent performance metrics."""
    agent_type: str
    sharpe_ratio: float = 0.0
    win_rate: float = 0.5
    mean_reward: float = 0.0
    std_reward: float = 1.0
    episode_count: int = 0


class EnsembleAgent:
    """Ensemble combining multiple RL agents with adaptive weighting.
    
    Strategies:
        - equal: Equal weights (1/N per agent)
        - adaptive: Weight by recent Sharpe ratio
        - best: Use only best-performing agent
        - vote: Majority voting (discrete actions)
    
    Attributes:
        agents: Dictionary of individual RL agents
        agent_types: List of algorithm names
        weighting_strategy: How to combine predictions
        performance_window: Episodes for performance calculation
    """
    
    AGENT_CLASSES = {
        'ppo': PPOAgent,
        'a2c': A2CAgent,
        'ddpg': DDPGAgent,
    }
    
    def __init__(
        self,
        env: Any,
        agent_types: List[str] = ['ppo', 'a2c', 'ddpg'],
        weighting_strategy: str = 'adaptive',
        performance_window: int = 10,
        agent_kwargs: Optional[Dict[str, Any]] = None,
    ):
        """Initialize ensemble with multiple agents.
        
        Args:
            env: Trading environment
            agent_types: List of algorithms ('ppo', 'a2c', 'ddpg')
            weighting_strategy: 'equal', 'adaptive', 'best', 'vote'
            performance_window: Episodes for performance evaluation
            agent_kwargs: Optional kwargs for agent initialization
        """
        self.env = env
        self.agent_types = agent_types
        self.weighting_strategy = weighting_strategy
        self.performance_window = performance_window
        self.agent_kwargs = agent_kwargs or {}
        
        # Initialize agents
        self.agents: Dict[str, Any] = {}
        self.performance: Dict[str, AgentPerformance] = {}
        
        for agent_type in agent_types:
            if agent_type not in self.AGENT_CLASSES:
                raise ValueError(f"Unknown agent type: {agent_type}")
            
            agent_class = self.AGENT_CLASSES[agent_type]
            self.agents[agent_type] = agent_class(
                env=env,
                verbose=0,
                **self.agent_kwargs
            )
            self.performance[agent_type] = AgentPerformance(agent_type=agent_type)
        
        logger.info(
            f"EnsembleAgent initialized: {len(self.agents)} agents "
            f"({', '.join(agent_types)}), strategy={weighting_strategy}"
        )
    
    def train(
        self,
        total_timesteps: int = 100_000,
        eval_env: Optional[Any] = None,
        eval_freq: int = 5_000,
        n_eval_episodes: int = 5,
        **kwargs: Any,
    ) -> EnsembleAgent:
        """Train all agents independently.
        
        Args:
            total_timesteps: Total training timesteps per agent
            eval_env: Optional evaluation environment
            eval_freq: Evaluation frequency
            n_eval_episodes: Episodes per evaluation
            **kwargs: Additional training arguments
            
        Returns:
            self: Trained ensemble
        """
        logger.info(f"Training ensemble: {total_timesteps} timesteps per agent")
        
        for agent_type, agent in self.agents.items():
            logger.info(f"Training {agent_type.upper()}...")
            agent.train(
                total_timesteps=total_timesteps,
                eval_env=eval_env,
                eval_freq=eval_freq,
                n_eval_episodes=n_eval_episodes,
                **kwargs
            )
            
            # Evaluate and update performance
            if eval_env is not None:
                metrics = agent.evaluate(
                    eval_env=eval_env,
                    n_eval_episodes=n_eval_episodes
                )
                self._update_performance(agent_type, metrics)
        
        logger.info("Ensemble training complete")
        return self
    
    def predict(
        self,
        observation: np.ndarray,
        deterministic: bool = True,
    ) -> Tuple[np.ndarray, Optional[Any]]:
        """Predict action using ensemble strategy.
        
        Args:
            observation: Current state
            deterministic: Use deterministic predictions
            
        Returns:
            action: Combined action vector
            states: Recurrent states (None for ensemble)
        """
        # Collect predictions from all agents
        actions = []
        for agent_type, agent in self.agents.items():
            action, _ = agent.predict(observation, deterministic=deterministic)
            # Ensure action is 1D array matching env action space
            action = np.atleast_1d(action).flatten()
            actions.append(action)
        
        # Stack actions (N_agents x action_dim)
        try:
            actions_array = np.vstack(actions)
        except ValueError:
            # Fallback: pad or truncate to common shape
            max_len = max(len(a) for a in actions)
            actions_padded = [
                np.pad(a, (0, max_len - len(a)), mode='constant') if len(a) < max_len else a[:max_len]
                for a in actions
            ]
            actions_array = np.vstack(actions_padded)
        
        # Combine based on strategy
        if self.weighting_strategy == 'equal':
            combined_action = np.mean(actions_array, axis=0)
        
        elif self.weighting_strategy == 'adaptive':
            weights = self._compute_adaptive_weights()
            combined_action = np.average(actions_array, axis=0, weights=weights)
        
        elif self.weighting_strategy == 'best':
            best_agent = self._get_best_agent()
            combined_action, _ = self.agents[best_agent].predict(
                observation, deterministic
            )
        
        elif self.weighting_strategy == 'vote':
            # Discretize actions to {-1, 0, 1} then vote
            discrete_actions = np.sign(actions_array)
            # Majority vote per dimension
            combined_action = np.array([
                np.bincount(discrete_actions[:, i].astype(int) + 1).argmax() - 1
                for i in range(discrete_actions.shape[1])
            ], dtype=np.float32)
        
        else:
            raise ValueError(f"Unknown strategy: {self.weighting_strategy}")
        
        return combined_action, None
    
    def evaluate(
        self,
        eval_env: Any,
        n_eval_episodes: int = 10,
        deterministic: bool = True,
    ) -> Dict[str, float]:
        """Evaluate ensemble performance.
        
        Args:
            eval_env: Evaluation environment
            n_eval_episodes: Number of episodes
            deterministic: Use deterministic predictions
            
        Returns:
            metrics: Mean reward, std, length, per-agent breakdown
        """
        logger.info(f"Evaluating ensemble: {n_eval_episodes} episodes")
        
        episode_rewards = []
        episode_lengths = []
        
        for episode in range(n_eval_episodes):
            obs, _ = eval_env.reset()
            done = False
            ep_reward = 0.0
            ep_length = 0
            
            while not done:
                action, _ = self.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, _ = eval_env.step(action)
                done = terminated or truncated
                ep_reward += reward
                ep_length += 1
            
            episode_rewards.append(ep_reward)
            episode_lengths.append(ep_length)
        
        # Aggregate metrics
        metrics = {
            'mean_reward': float(np.mean(episode_rewards)),
            'std_reward': float(np.std(episode_rewards)),
            'mean_length': float(np.mean(episode_lengths)),
            'std_length': float(np.std(episode_lengths)),
        }
        
        # Add per-agent metrics
        for agent_type, perf in self.performance.items():
            metrics[f'{agent_type}_sharpe'] = perf.sharpe_ratio
            metrics[f'{agent_type}_weight'] = self._compute_adaptive_weights()[
                self.agent_types.index(agent_type)
            ]
        
        logger.info(
            f"Ensemble evaluation: mean_reward={metrics['mean_reward']:.4f}, "
            f"strategy={self.weighting_strategy}"
        )
        
        return metrics
    
    def save(self, path: str) -> None:
        """Save all agents and ensemble metadata.
        
        Args:
            path: Directory path for ensemble
        """
        ensemble_dir = Path(path)
        ensemble_dir.mkdir(parents=True, exist_ok=True)
        
        # Save individual agents
        for agent_type, agent in self.agents.items():
            agent_path = ensemble_dir / f"{agent_type}_model.zip"
            agent.save(str(agent_path))
        
        # Save performance metadata
        import json
        perf_data = {
            agent_type: {
                'sharpe_ratio': perf.sharpe_ratio,
                'win_rate': perf.win_rate,
                'mean_reward': perf.mean_reward,
                'std_reward': perf.std_reward,
                'episode_count': perf.episode_count,
            }
            for agent_type, perf in self.performance.items()
        }
        perf_path = ensemble_dir / "performance.json"
        perf_path.write_text(json.dumps(perf_data, indent=2))
        
        logger.info(f"Ensemble saved to {ensemble_dir}")
    
    @classmethod
    def load(
        cls,
        path: str,
        env: Any,
        agent_types: Optional[List[str]] = None,
    ) -> EnsembleAgent:
        """Load ensemble from directory.
        
        Args:
            path: Directory containing ensemble
            env: Trading environment
            agent_types: Optional list of agents to load
            
        Returns:
            Loaded ensemble agent
        """
        ensemble_dir = Path(path)
        if not ensemble_dir.exists():
            raise FileNotFoundError(f"Ensemble not found: {ensemble_dir}")
        
        # Discover agent types if not provided
        if agent_types is None:
            agent_types = [
                p.stem.replace('_model', '')
                for p in ensemble_dir.glob('*_model.zip')
            ]
        
        # Create ensemble
        ensemble = cls(env=env, agent_types=agent_types)
        
        # Load agents
        for agent_type in agent_types:
            agent_path = ensemble_dir / f"{agent_type}_model.zip"
            agent_class = cls.AGENT_CLASSES[agent_type]
            ensemble.agents[agent_type] = agent_class.load(str(agent_path), env=env)
        
        # Load performance metadata
        import json
        perf_path = ensemble_dir / "performance.json"
        if perf_path.exists():
            perf_data = json.loads(perf_path.read_text())
            for agent_type, data in perf_data.items():
                if agent_type in ensemble.performance:
                    perf = ensemble.performance[agent_type]
                    perf.sharpe_ratio = data.get('sharpe_ratio', 0.0)
                    perf.win_rate = data.get('win_rate', 0.5)
                    perf.mean_reward = data.get('mean_reward', 0.0)
                    perf.std_reward = data.get('std_reward', 1.0)
                    perf.episode_count = data.get('episode_count', 0)
        
        logger.info(f"Ensemble loaded from {ensemble_dir}")
        return ensemble
    
    def _update_performance(
        self,
        agent_type: str,
        metrics: Dict[str, float]
    ) -> None:
        """Update agent performance metrics."""
        perf = self.performance[agent_type]
        
        mean_reward = metrics.get('mean_reward', 0.0)
        std_reward = metrics.get('std_reward', 1.0)
        
        # Calculate Sharpe ratio (annualized)
        if std_reward > 1e-8:
            sharpe = (mean_reward * 252 - 0.02) / (std_reward * np.sqrt(252))
        else:
            sharpe = 0.0
        
        perf.sharpe_ratio = sharpe
        perf.mean_reward = mean_reward
        perf.std_reward = std_reward
        perf.episode_count += metrics.get('mean_length', 1)
        
        # Estimate win rate (rough approximation)
        if mean_reward > 0:
            perf.win_rate = min(0.5 + mean_reward * 10, 0.95)
        else:
            perf.win_rate = max(0.05, 0.5 + mean_reward * 10)
    
    def _compute_adaptive_weights(self) -> np.ndarray:
        """Compute adaptive weights based on recent performance.
        
        Returns:
            weights: Normalized weights for each agent
        """
        # Use Sharpe ratio as performance metric
        sharpe_values = np.array([
            max(self.performance[agent_type].sharpe_ratio, 0.0)
            for agent_type in self.agent_types
        ])
        
        # Softmax for numerical stability
        if sharpe_values.sum() < 1e-8:
            return np.ones(len(self.agent_types)) / len(self.agent_types)
        
        exp_sharpe = np.exp(sharpe_values - sharpe_values.max())
        weights = exp_sharpe / exp_sharpe.sum()
        
        return weights
    
    def _get_best_agent(self) -> str:
        """Get agent type with best recent performance."""
        best_agent = max(
            self.agent_types,
            key=lambda t: self.performance[t].sharpe_ratio
        )
        return best_agent
    
    def get_weights(self) -> Dict[str, float]:
        """Get current agent weights.
        
        Returns:
            Dictionary mapping agent type to weight
        """
        if self.weighting_strategy == 'equal':
            weight = 1.0 / len(self.agent_types)
            return {agent_type: weight for agent_type in self.agent_types}
        
        elif self.weighting_strategy == 'adaptive':
            weights = self._compute_adaptive_weights()
            return {
                agent_type: float(weights[i])
                for i, agent_type in enumerate(self.agent_types)
            }
        
        elif self.weighting_strategy == 'best':
            best = self._get_best_agent()
            return {
                agent_type: 1.0 if agent_type == best else 0.0
                for agent_type in self.agent_types
            }
        
        else:
            return {agent_type: 1.0 / len(self.agent_types) for agent_type in self.agent_types}
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"EnsembleAgent(agents={self.agent_types}, "
            f"strategy={self.weighting_strategy})"
        )


__all__ = ['EnsembleAgent', 'AgentPerformance']
