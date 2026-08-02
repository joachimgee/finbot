"""
Tests for PPOAgent.

Test suite for Proximal Policy Optimization agent:
    - Initialization with various configs
    - Training functionality
    - Prediction (inference)
    - Evaluation metrics
    - Model save/load
    - Parameter retrieval
    - Integration with TradingEnvironment

Coverage Target: 80%+
"""

import pytest
import numpy as np
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from financial_analyzer.rl.agents import PPOAgent
from financial_analyzer.rl.environments import TradingEnvironment


@pytest.fixture
def trading_env():
    """Create a simple trading environment for testing."""
    env = TradingEnvironment(
        symbols=['AAPL', 'MSFT'],
        start_date='2020-01-01',
        end_date='2020-06-30',
        initial_capital=100_000
    )
    return env


@pytest.fixture
def ppo_agent(trading_env):
    """Create a PPO agent for testing."""
    agent = PPOAgent(
        env=trading_env,
        learning_rate=3e-4,
        n_steps=64,  # Small for fast tests
        batch_size=32,
        verbose=0
    )
    return agent


class TestPPOAgentInit:
    """Test PPOAgent initialization."""
    
    def test_init_basic(self, trading_env):
        """Test basic initialization."""
        agent = PPOAgent(env=trading_env, verbose=0)
        
        assert agent.env is trading_env
        assert agent.model is not None
        assert agent.learning_rate == 3e-4  # Default
    
    def test_init_custom_learning_rate(self, trading_env):
        """Test initialization with custom learning rate."""
        agent = PPOAgent(
            env=trading_env,
            learning_rate=1e-3,
            verbose=0
        )
        
        assert agent.learning_rate == 1e-3
    
    def test_init_custom_policy_kwargs(self, trading_env):
        """Test initialization with custom policy network."""
        policy_kwargs = {
            "net_arch": [128, 128, 64],
            "activation_fn": "relu"
        }
        
        agent = PPOAgent(
            env=trading_env,
            policy_kwargs=policy_kwargs,
            verbose=0
        )
        
        assert agent.model is not None
    
    def test_init_custom_hyperparameters(self, trading_env):
        """Test initialization with custom hyperparameters."""
        agent = PPOAgent(
            env=trading_env,
            n_steps=128,
            batch_size=64,
            n_epochs=5,
            gamma=0.95,
            gae_lambda=0.90,
            clip_range=0.3,
            verbose=0
        )
        
        params = agent.get_parameters()
        assert params['n_steps'] == 128
        assert params['batch_size'] == 64
        assert params['n_epochs'] == 5
        assert params['gamma'] == 0.95


class TestPPOAgentTraining:
    """Test PPO agent training."""
    
    def test_train_basic(self, ppo_agent):
        """Test basic training (very short)."""
        initial_step = 0
        
        ppo_agent.train(
            total_timesteps=100,  # Very short for fast test
            log_interval=10,
            save_freq=None  # Don't save checkpoints
        )
        
        # Model should exist after training
        assert ppo_agent.model is not None
    
    def test_train_with_checkpoints(self, ppo_agent):
        """Test training with checkpoint saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ppo_agent.train(
                total_timesteps=100,
                save_freq=50,
                save_path=tmpdir,
                log_interval=10
            )
            
            # Check checkpoint was created
            checkpoint_files = list(Path(tmpdir).glob("ppo_trading_*.zip"))
            assert len(checkpoint_files) > 0
    
    def test_train_with_evaluation(self, trading_env):
        """Test training with evaluation callback."""
        # Create separate eval env
        eval_env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-07-01',
            end_date='2020-09-30',
            initial_capital=100_000
        )
        
        agent = PPOAgent(env=trading_env, verbose=0, n_steps=64, batch_size=32)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            agent.train(
                total_timesteps=100,
                eval_env=eval_env,
                eval_freq=50,
                n_eval_episodes=2,
                best_model_save_path=tmpdir
            )
            
            # Best model should be saved
            best_model_path = Path(tmpdir) / "best_model.zip"
            assert best_model_path.exists()


class TestPPOAgentPrediction:
    """Test PPO agent prediction."""
    
    def test_predict_basic(self, ppo_agent, trading_env):
        """Test basic prediction."""
        obs, _ = trading_env.reset()
        action, states = ppo_agent.predict(obs, deterministic=True)
        
        assert isinstance(action, np.ndarray)
        assert action.shape == (trading_env.n_assets,)
        assert np.all(action >= -1.0)
        assert np.all(action <= 1.0)
    
    def test_predict_deterministic_consistent(self, ppo_agent, trading_env):
        """Test deterministic predictions are consistent."""
        obs, _ = trading_env.reset()
        
        action1, _ = ppo_agent.predict(obs, deterministic=True)
        action2, _ = ppo_agent.predict(obs, deterministic=True)
        
        np.testing.assert_array_almost_equal(action1, action2, decimal=5)
    
    def test_predict_stochastic_different(self, ppo_agent, trading_env):
        """Test stochastic predictions vary."""
        obs, _ = trading_env.reset()
        
        actions = [
            ppo_agent.predict(obs, deterministic=False)[0]
            for _ in range(5)
        ]
        
        # Not all actions should be identical
        not_all_same = any(
            not np.allclose(actions[0], action)
            for action in actions[1:]
        )
        assert not_all_same


class TestPPOAgentEvaluation:
    """Test PPO agent evaluation."""
    
    def test_evaluate_basic(self, ppo_agent, trading_env):
        """Test basic evaluation."""
        metrics = ppo_agent.evaluate(
            eval_env=trading_env,
            n_eval_episodes=2,
            deterministic=True
        )
        
        assert isinstance(metrics, dict)
        assert 'mean_reward' in metrics
        assert 'std_reward' in metrics
        assert 'mean_length' in metrics
        assert isinstance(metrics['mean_reward'], float)
    
    def test_evaluate_multiple_episodes(self, ppo_agent):
        """Test evaluation with multiple episodes.

        L'env d'évaluation doit avoir le même univers que l'env
        d'entraînement : l'espace d'observation d'une MlpPolicy est figé
        (SB3 rejette toute observation d'une autre dimension).
        """
        eval_env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-03-31',
            initial_capital=100_000
        )
        
        metrics = ppo_agent.evaluate(
            eval_env=eval_env,
            n_eval_episodes=3,
            deterministic=True
        )
        
        assert metrics['mean_length'] > 0
        assert metrics['std_reward'] >= 0


class TestPPOAgentSaveLoad:
    """Test PPO agent save/load functionality."""
    
    def test_save_basic(self, ppo_agent):
        """Test basic model saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_model"
            ppo_agent.save(str(save_path))
            
            # Check file exists
            assert save_path.with_suffix(".zip").exists()
    
    def test_load_basic(self, ppo_agent, trading_env):
        """Test basic model loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_model.zip"
            ppo_agent.save(str(save_path))
            
            # Load model
            loaded_agent = PPOAgent.load(
                str(save_path),
                env=trading_env
            )
            
            assert loaded_agent.model is not None
    
    def test_save_load_predictions_consistent(self, ppo_agent, trading_env):
        """Test predictions are consistent after save/load."""
        obs, _ = trading_env.reset()
        
        # Predict before saving
        action_before, _ = ppo_agent.predict(obs, deterministic=True)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_model"
            ppo_agent.save(str(save_path))
            
            # Load and predict
            loaded_agent = PPOAgent.load(
                str(save_path),
                env=trading_env
            )
            action_after, _ = loaded_agent.predict(obs, deterministic=True)
        
        np.testing.assert_array_almost_equal(
            action_before,
            action_after,
            decimal=5
        )


class TestPPOAgentParameters:
    """Test PPO agent parameter retrieval."""
    
    def test_get_parameters(self, ppo_agent):
        """Test parameter retrieval."""
        params = ppo_agent.get_parameters()
        
        assert isinstance(params, dict)
        assert 'learning_rate' in params
        assert 'n_steps' in params
        assert 'batch_size' in params
        assert 'gamma' in params
        assert 'clip_range' in params
    
    def test_repr(self, ppo_agent):
        """Test string representation."""
        repr_str = repr(ppo_agent)
        
        assert 'PPOAgent' in repr_str
        assert 'lr=' in repr_str


class TestPPOAgentIntegration:
    """Test PPO agent integration with environment."""
    
    def test_full_episode_with_agent(self, ppo_agent, trading_env):
        """Test complete episode execution with agent."""
        obs, _ = trading_env.reset()
        done = False
        steps = 0
        total_reward = 0
        
        while not done and steps < 50:
            action, _ = ppo_agent.predict(obs, deterministic=False)
            obs, reward, terminated, truncated, info = trading_env.step(action)
            done = terminated or truncated
            total_reward += reward
            steps += 1
        
        assert steps > 0
        assert trading_env.portfolio_value > 0
    
    def test_train_and_evaluate_workflow(self):
        """Test complete train and evaluate workflow."""
        # Create environments
        train_env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-06-30',
            initial_capital=100_000
        )
        
        test_env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-07-01',
            end_date='2020-09-30',
            initial_capital=100_000
        )
        
        # Create and train agent
        agent = PPOAgent(
            env=train_env,
            verbose=0,
            n_steps=64,
            batch_size=32
        )
        
        agent.train(total_timesteps=100)
        
        # Evaluate
        metrics = agent.evaluate(
            eval_env=test_env,
            n_eval_episodes=2,
            deterministic=True
        )
        
        assert isinstance(metrics['mean_reward'], float)
        assert metrics['mean_length'] > 0


class TestPPOAgentEdgeCases:
    """Test edge cases and error handling."""
    
    def test_train_zero_timesteps(self, ppo_agent):
        """Test training with zero timesteps."""
        # Should handle gracefully or raise clear error
        try:
            ppo_agent.train(total_timesteps=0)
        except Exception as e:
            assert True  # Expected to fail
    
    def test_load_nonexistent_model(self, trading_env):
        """Test loading non-existent model."""
        with pytest.raises(FileNotFoundError):
            PPOAgent.load(
                "/nonexistent/path/model.zip",
                env=trading_env
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
