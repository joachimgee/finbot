"""
Reinforcement Learning Trainer for Trading Strategies.

Orchestrates complete RL training pipeline with:
    - Walk-forward analysis (train/validation/test splits)
    - Multiple agent types (PPO, DQN, DDPG, A2C)
    - Hyperparameter optimization (Optuna)
    - Baseline comparisons (Buy&Hold, Equal Weight, PyPortfolioOpt)
    - TensorBoard logging
    - Model checkpointing

Integration:
    - financial_analyzer.rl.environments.TradingEnvironment
    - financial_analyzer.rl.agents (PPO, DQN, DDPG, A2C)
    - financial_analyzer.backtest.validation.walk_forward.WalkForwardAnalyzer
    - financial_analyzer.portfolio_optimization (PyPortfolioOpt baselines)

Architecture:
    1. Data split (walk-forward windows)
    2. For each window:
        a. Train agent on training data
        b. Validate on validation data
        c. Save best checkpoint
    3. Final test on holdout data
    4. Compare vs baselines

References:
    - Yang et al. (2020): FinRL framework
    - Pardo (2008): Walk-forward analysis
    - Stable-Baselines3: RL training best practices

Example:
    >>> from financial_analyzer.rl.trainers import RLTrainer
    >>> 
    >>> trainer = RLTrainer(
    ...     symbols=['AAPL', 'MSFT', 'GOOGL'],
    ...     start_date='2015-01-01',
    ...     end_date='2023-12-31'
    ... )
    >>> results = trainer.train_walk_forward(
    ...     agent_type='ppo',
    ...     total_timesteps=100_000
    ... )
    >>> trainer.compare_baselines(results)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

# Lazy imports for environments and agents
TradingEnvironment = None
PPOAgent = None
DQNAgent = None
A2CAgent = None
DDPGAgent = None


def _lazy_imports():
    """Lazy import modules to avoid circular dependencies."""
    global TradingEnvironment, PPOAgent, DQNAgent, A2CAgent, DDPGAgent

    if TradingEnvironment is None:
        try:
            from financial_analyzer.rl.environments import TradingEnvironment as TE
            TradingEnvironment = TE
        except ImportError:
            logger.warning("TradingEnvironment not available")

    # Agents
    try:
        from financial_analyzer.rl.agents import (
            PPOAgent as _PPO,
            DQNAgent as _DQN,
            A2CAgent as _A2C,
            DDPGAgent as _DDPG,
        )
        PPOAgent = PPOAgent or _PPO
        DQNAgent = DQNAgent or _DQN
        A2CAgent = A2CAgent or _A2C
        DDPGAgent = DDPGAgent or _DDPG
    except ImportError as e:
        logger.warning(f"Agent imports partial: {e}")


class RLTrainer:
    """
    RL training orchestrator with walk-forward analysis.
    
    Manages complete training pipeline:
        - Environment creation
        - Agent initialization
        - Walk-forward training/validation
        - Model checkpointing
        - Baseline comparisons
        - Performance reporting
    
    Attributes:
        symbols: List of stock tickers
        start_date: Training start date
        end_date: Training end date
        train_ratio: Proportion for training (0.7 = 70%)
        val_ratio: Proportion for validation (0.15 = 15%)
        test_ratio: Proportion for test (0.15 = 15%)
    """
    
    def __init__(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100_000.0,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        models_dir: str = "./models",
        logs_dir: str = "./logs",
    ):
        """
        Initialize RL Trainer.
        
        Args:
            symbols: List of stock ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Starting portfolio value
            train_ratio: Training data proportion (0.7 = 70%)
            val_ratio: Validation data proportion (0.15 = 15%)
            test_ratio: Test data proportion (0.15 = 15%)
            models_dir: Directory for saving models
            logs_dir: Directory for TensorBoard logs
        """
        _lazy_imports()
        
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        
        # Directories
        self.models_dir = Path(models_dir)
        self.logs_dir = Path(logs_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Results tracking
        self.training_results = {}
        
        logger.info(
            f"RLTrainer initialized: {len(symbols)} symbols, "
            f"{start_date} to {end_date}"
        )
    
    def train_walk_forward(
        self,
        agent_type: str = "ppo",
        total_timesteps: int = 100_000,
        eval_freq: int = 5_000,
        save_freq: int = 10_000,
        n_eval_episodes: int = 5,
        agent_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Train agent with walk-forward analysis.
        
        Splits data into train/val/test, trains on training data,
        validates during training, and evaluates on test data.
        
        Args:
            agent_type: Type of agent ("ppo", "dqn", "ddpg", "a2c")
            total_timesteps: Total training timesteps
            eval_freq: Evaluate every N timesteps
            save_freq: Save checkpoint every N timesteps
            n_eval_episodes: Number of validation episodes
            agent_kwargs: Additional agent initialization arguments
            
        Returns:
            results: Dictionary with training metrics, test results, baselines
        """
        logger.info(f"Starting walk-forward training: {agent_type.upper()}")
        
        # Split data into train/val/test
        train_start, train_end, val_start, val_end, test_start, test_end = (
            self._split_dates()
        )
        
        # Create environments
        train_env = self._create_environment(train_start, train_end)
        val_env = self._create_environment(val_start, val_end)
        test_env = self._create_environment(test_start, test_end)
        
        logger.info(
            f"Data splits: Train={train_start} to {train_end}, "
            f"Val={val_start} to {val_end}, Test={test_start} to {test_end}"
        )
        
        # Initialize agent
        agent = self._create_agent(
            agent_type=agent_type,
            env=train_env,
            agent_kwargs=agent_kwargs
        )
        
        # Train agent
        logger.info(f"Training {agent_type.upper()} for {total_timesteps} timesteps")
        
        agent.train(
            total_timesteps=total_timesteps,
            eval_env=val_env,
            eval_freq=eval_freq,
            n_eval_episodes=n_eval_episodes,
            save_freq=save_freq,
            save_path=str(self.models_dir / "checkpoints" / agent_type),
            best_model_save_path=str(self.models_dir / "best" / agent_type),
        )
        
        # Evaluate on test set
        logger.info("Evaluating on test set")
        test_metrics = agent.evaluate(
            eval_env=test_env,
            n_eval_episodes=10,
            deterministic=True
        )

        # If EvalCallback didn't produce a best model (e.g., eval_freq > total_timesteps),
        # save a final checkpoint so the run still produces an artifact.
        final_model_path = None
        try:
            # agent.best_model_path is either a Path or None
            if getattr(agent, "best_model_path", None) is not None and Path(agent.best_model_path).exists():
                final_model_path = Path(agent.best_model_path)
            else:
                # Save final model to a deterministic location
                fallback_dir = self.models_dir / "best" / agent_type
                fallback_dir.mkdir(parents=True, exist_ok=True)
                final_model_path = fallback_dir / "final_model.zip"
                try:
                    agent.save(str(final_model_path))
                    logger.info(f"Saved final model to {final_model_path}")
                except Exception:
                    logger.warning("Failed to save final model via agent.save()")
                    final_model_path = None
        except Exception:
            final_model_path = None

        # Store results
        results = {
            "agent_type": agent_type,
            "train_period": (train_start, train_end),
            "val_period": (val_start, val_end),
            "test_period": (test_start, test_end),
            "test_metrics": test_metrics,
            "model_path": str(final_model_path) if final_model_path is not None else None,
        }
        
        self.training_results[agent_type] = results
        
        logger.info(
            f"Training completed: {agent_type.upper()} "
            f"test_reward={test_metrics['mean_reward']:.4f}"
        )
        
        return results
    
    def _split_dates(self) -> Tuple[str, str, str, str, str, str]:
        """
        Split date range into train/val/test periods.
        
        Returns:
            (train_start, train_end, val_start, val_end, test_start, test_end)
        """
        # Convert to datetime
        start = pd.to_datetime(self.start_date)
        end = pd.to_datetime(self.end_date)
        total_days = (end - start).days
        
        # Calculate split points
        train_days = int(total_days * self.train_ratio)
        val_days = int(total_days * self.val_ratio)
        
        train_end = start + pd.Timedelta(days=train_days)
        val_end = train_end + pd.Timedelta(days=val_days)
        
        # Format as strings — les périodes sont disjointes : chaque split
        # démarre le lendemain de la fin du précédent (pas de chevauchement)
        train_start = start.strftime('%Y-%m-%d')
        train_end_str = train_end.strftime('%Y-%m-%d')
        val_start = (train_end + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        val_end_str = val_end.strftime('%Y-%m-%d')
        test_start = (val_end + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        test_end_str = end.strftime('%Y-%m-%d')
        
        return train_start, train_end_str, val_start, val_end_str, test_start, test_end_str
    
    def _create_environment(
        self,
        start_date: str,
        end_date: str
    ) -> Any:
        """Create TradingEnvironment for given date range."""
        if TradingEnvironment is None:
            raise ImportError("TradingEnvironment not available")
        
        env = TradingEnvironment(
            symbols=self.symbols,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            use_technical_indicators=True,
            use_sentiment=False,
            use_risk_metrics=True,
        )
        
        return env
    
    def _create_agent(
        self,
        agent_type: str,
        env: Any,
        agent_kwargs: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Factory method: instantiate RL agent wrapper.

        Supports: ppo, dqn, a2c, ddpg. Each wrapper implements a consistent
        interface (train, evaluate, predict, save, load) via BaseRLAgent or
        legacy PPOAgent class. Additional algorithms can be added here.

        Args:
            agent_type: Algorithm identifier.
            env: Initialized trading environment.
            agent_kwargs: Optional hyperparameter overrides.

        Returns:
            Instantiated agent object.
        """
        if agent_kwargs is None:
            agent_kwargs = {}

        algo = agent_type.lower()
        tensorboard_log = str(self.logs_dir / algo)
        agent_kwargs.setdefault("tensorboard_log", tensorboard_log)

        if algo == "ppo":
            if PPOAgent is None:
                raise ImportError("PPOAgent not available")
            return PPOAgent(env=env, **agent_kwargs)
        if algo == "dqn":
            if DQNAgent is None:
                raise ImportError("DQNAgent not available")
            return DQNAgent(env=env, **agent_kwargs)
        if algo == "a2c":
            if A2CAgent is None:
                raise ImportError("A2CAgent not available")
            return A2CAgent(env=env, **agent_kwargs)
        if algo == "ddpg":
            if DDPGAgent is None:
                raise ImportError("DDPGAgent not available")
            return DDPGAgent(env=env, **agent_kwargs)

        raise ValueError(
            f"Unsupported agent_type '{agent_type}'. Valid: ppo, dqn, a2c, ddpg"
        )
    
    def compare_baselines(
        self,
        results: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Compare RL agent vs baseline strategies.
        
        Baselines:
            - Buy & Hold (equal weight, rebalance never)
            - Equal Weight (rebalance monthly)
            - Minimum Variance (PyPortfolioOpt)
            - Max Sharpe (PyPortfolioOpt)
        
        Args:
            results: Training results (uses last results if None)
            
        Returns:
            comparison_df: DataFrame with metrics for all strategies
        """
        if results is None:
            if not self.training_results:
                logger.warning("No training results available")
                return pd.DataFrame()
            results = list(self.training_results.values())[0]
        
        logger.info("Comparing against baseline strategies")
        
        # Extract test period
        test_start, test_end = results["test_period"]
        
        # RL agent metrics
        rl_metrics = results["test_metrics"]
        
        # Placeholder for baselines (would need actual implementation)
        baselines = {
            "RL Agent": {
                "mean_reward": rl_metrics["mean_reward"],
                "std_reward": rl_metrics["std_reward"],
            },
            "Buy & Hold": {
                "mean_reward": 0.0,  # Placeholder
                "std_reward": 0.0,
            },
            "Equal Weight": {
                "mean_reward": 0.0,  # Placeholder
                "std_reward": 0.0,
            },
            "Min Variance": {
                "mean_reward": 0.0,  # Placeholder
                "std_reward": 0.0,
            },
            "Max Sharpe": {
                "mean_reward": 0.0,  # Placeholder
                "std_reward": 0.0,
            },
        }
        
        # Convert to DataFrame
        comparison_df = pd.DataFrame(baselines).T
        comparison_df = comparison_df.sort_values("mean_reward", ascending=False)
        
        logger.info(f"\n{comparison_df.to_string()}")
        
        return comparison_df
    
    def save_results(
        self,
        filename: Optional[str] = None
    ) -> None:
        """
        Save training results to disk.
        
        Args:
            filename: Output filename (default: rl_results_YYYYMMDD.json)
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rl_results_{timestamp}.json"
        
        output_path = self.models_dir / filename
        
        # Convert results to serializable format
        serializable_results = {}
        for agent_type, results in self.training_results.items():
            serializable_results[agent_type] = {
                "agent_type": results["agent_type"],
                "train_period": results["train_period"],
                "val_period": results["val_period"],
                "test_period": results["test_period"],
                "test_metrics": results["test_metrics"],
                "model_path": str(results["model_path"]) if results["model_path"] else None,
            }
        
        # Save to JSON
        import json
        with open(output_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        logger.info(f"Results saved to {output_path}")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RLTrainer(symbols={len(self.symbols)}, "
            f"period={self.start_date} to {self.end_date})"
        )


__all__ = ['RLTrainer']
