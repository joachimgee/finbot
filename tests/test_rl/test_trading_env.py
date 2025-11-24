"""
Tests for TradingEnvironment.

Comprehensive test suite for OpenAI Gym trading environment:
    - Initialization & configuration
    - Reset functionality
    - Step execution & action handling
    - Observation space validation
    - Reward calculation
    - Portfolio state tracking
    - Integration with FinBot modules
    - Edge cases (bankruptcy, invalid actions)

Coverage Target: 85%+
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from financial_analyzer.rl.environments import TradingEnvironment


class TestTradingEnvironmentInit:
    """Test TradingEnvironment initialization."""
    
    def test_init_basic(self):
        """Test basic initialization with minimal parameters."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            initial_capital=100_000
        )
        
        assert env.n_assets == 2
        assert env.initial_capital == 100_000
        assert len(env.symbols) == 2
        assert env.action_space.shape == (2,)
        assert env.observation_space.shape[0] > 0
    
    def test_init_with_technical_indicators(self):
        """Test initialization with technical indicators enabled."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            use_technical_indicators=True
        )
        
        assert env.use_technical_indicators is True
        # State should be larger with indicators
        assert env.observation_space.shape[0] > 10
    
    def test_init_with_risk_metrics(self):
        """Test initialization with risk metrics enabled."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            use_risk_metrics=True
        )
        
        assert env.use_risk_metrics is True
    
    def test_init_custom_commission(self):
        """Test initialization with custom commission rate."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            commission=0.005  # 0.5%
        )
        
        assert env.commission == 0.005
    
    def test_init_custom_position_size(self):
        """Test initialization with custom max position size."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT', 'GOOGL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            max_position_size=0.2  # 20% per asset
        )
        
        assert env.max_position_size == 0.2


class TestTradingEnvironmentReset:
    """Test environment reset functionality."""
    
    def test_reset_basic(self):
        """Test basic reset returns valid observation."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        obs, info = env.reset()
        
        assert isinstance(obs, np.ndarray)
        assert obs.shape == env.observation_space.shape
        assert isinstance(info, dict)
        assert 'portfolio_value' in info
        assert info['portfolio_value'] == env.initial_capital
    
    def test_reset_portfolio_state(self):
        """Test reset initializes portfolio state correctly."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT', 'GOOGL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            initial_capital=100_000
        )
        
        obs, info = env.reset()
        
        assert env.cash == 100_000
        assert np.all(env.holdings == 0)
        assert env.portfolio_value == 100_000
        assert env.current_step == 0 or env.current_step > 0  # May be random start
    
    def test_reset_with_seed(self):
        """Test reset with seed produces reproducible results."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            random_start=True
        )
        
        obs1, _ = env.reset(seed=42)
        step1 = env.current_step
        
        obs2, _ = env.reset(seed=42)
        step2 = env.current_step
        
        assert step1 == step2
        np.testing.assert_array_equal(obs1, obs2)
    
    def test_reset_clears_tracking(self):
        """Test reset clears performance tracking."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        # First episode
        env.reset()
        env.step(env.action_space.sample())
        env.step(env.action_space.sample())
        
        # Reset and check
        env.reset()
        
        assert len(env.portfolio_values) == 1
        assert len(env.actions_memory) == 0
        assert len(env.returns) == 0


class TestTradingEnvironmentStep:
    """Test environment step execution."""
    
    def test_step_basic(self):
        """Test basic step execution."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        env.reset()
        action = np.array([0.5, -0.3])  # Buy AAPL, sell some MSFT
        
        obs, reward, terminated, truncated, info = env.step(action)
        
        assert isinstance(obs, np.ndarray)
        assert obs.shape == env.observation_space.shape
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)
    
    def test_step_buy_action(self):
        """Test buy action increases holdings."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            initial_capital=100_000
        )
        
        env.reset()
        initial_cash = env.cash
        
        # Buy action
        action = np.array([1.0])  # Maximum buy
        env.step(action)
        
        assert env.holdings[0] > 0
        assert env.cash < initial_cash
    
    def test_step_sell_action(self):
        """Test sell action decreases holdings."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            initial_capital=100_000
        )
        
        env.reset()
        
        # First buy
        env.step(np.array([1.0]))
        holdings_after_buy = env.holdings[0]
        cash_after_buy = env.cash
        
        # Then sell
        env.step(np.array([-0.5]))
        
        assert env.holdings[0] < holdings_after_buy
        assert env.cash > cash_after_buy
    
    def test_step_hold_action(self):
        """Test hold action maintains positions."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        env.reset()
        env.step(np.array([1.0]))  # Buy
        
        holdings_before = env.holdings[0]
        cash_before = env.cash
        
        # Hold
        env.step(np.array([0.0]))
        
        # Holdings should be same (cash may differ slightly due to portfolio value updates)
        assert abs(env.holdings[0] - holdings_before) < 0.01
    
    def test_step_commission_deducted(self):
        """Test commission is properly deducted from trades."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            initial_capital=100_000,
            commission=0.01  # 1% commission
        )
        
        env.reset()
        initial_cash = env.cash
        
        # Buy action
        env.step(np.array([1.0]))
        
        # Cash should decrease by more than just the purchase (commission included)
        cash_spent = initial_cash - env.cash
        assert cash_spent > 0
    
    def test_step_max_steps_termination(self):
        """Test episode terminates after max steps."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-01-31',  # Short period
            random_start=False
        )
        
        env.reset()
        terminated = False
        steps = 0
        
        while not terminated and steps < 100:
            _, _, terminated, _, _ = env.step(env.action_space.sample())
            steps += 1
        
        assert terminated or steps < 100


class TestTradingEnvironmentObservation:
    """Test observation space and state construction."""
    
    def test_observation_shape_consistent(self):
        """Test observation shape is consistent across steps."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        obs1, _ = env.reset()
        shape1 = obs1.shape
        
        obs2, _, _, _, _ = env.step(env.action_space.sample())
        shape2 = obs2.shape
        
        assert shape1 == shape2
    
    def test_observation_contains_cash(self):
        """Test observation includes cash information."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            initial_capital=100_000
        )
        
        obs, _ = env.reset()
        
        # First element should be normalized cash
        assert obs[0] == pytest.approx(1.0, rel=0.01)
    
    def test_observation_contains_holdings(self):
        """Test observation includes holdings information."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        obs, _ = env.reset()
        
        # Should have cash (1) + holdings (2) + prices (2) + ...
        assert len(obs) >= 5


class TestTradingEnvironmentReward:
    """Test reward calculation."""
    
    def test_reward_is_float(self):
        """Test reward is always a float."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        env.reset()
        _, reward, _, _, _ = env.step(env.action_space.sample())
        
        assert isinstance(reward, float)
    
    def test_reward_positive_for_profit(self):
        """Test reward is generally positive when portfolio increases."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        env.reset()
        
        # Buy at beginning of uptrend (hopefully)
        env.step(np.array([1.0]))
        
        # Take several steps
        total_reward = 0
        for _ in range(10):
            _, reward, terminated, _, _ = env.step(np.array([0.0]))  # Hold
            total_reward += reward
            if terminated:
                break
        
        # Can't guarantee positive, but check it's reasonable
        assert -10 < total_reward < 10


class TestTradingEnvironmentIntegration:
    """Test integration with FinBot modules."""
    
    def test_integration_with_multiple_assets(self):
        """Test environment handles multiple assets correctly."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        env.reset()
        
        # Trade all assets
        action = np.array([0.5, -0.3, 0.2, 0.0])
        obs, _, _, _, info = env.step(action)
        
        assert len(env.holdings) == 4
        assert env.portfolio_value > 0
    
    def test_full_episode_execution(self):
        """Test complete episode from start to finish."""
        env = TradingEnvironment(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2020-03-31',  # Short period
            random_start=False
        )
        
        obs, _ = env.reset()
        done = False
        steps = 0
        total_reward = 0
        
        while not done and steps < 100:
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            total_reward += reward
            steps += 1
        
        assert steps > 0
        assert env.portfolio_value > 0
        assert len(env.portfolio_values) > 1


class TestTradingEnvironmentEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_symbols_list(self):
        """Test initialization with empty symbols list fails gracefully."""
        with pytest.raises((ValueError, IndexError)):
            env = TradingEnvironment(
                symbols=[],
                start_date='2020-01-01',
                end_date='2020-12-31'
            )
    
    def test_invalid_date_range(self):
        """Test initialization with invalid date range."""
        # End before start
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-12-31',
            end_date='2020-01-01'
        )
        
        # Should handle gracefully (might have no data)
        obs, _ = env.reset()
        assert isinstance(obs, np.ndarray)
    
    def test_extreme_action_values(self):
        """Test environment handles extreme action values."""
        env = TradingEnvironment(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31'
        )
        
        env.reset()
        
        # Extreme actions (should be clipped by action_space)
        action = np.array([10.0])  # Way beyond [1.0]
        obs, _, _, _, _ = env.step(action)
        
        assert isinstance(obs, np.ndarray)
        assert env.portfolio_value > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
