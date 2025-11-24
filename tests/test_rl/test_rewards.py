"""
Tests for Reward Functions.

Test suite for risk-adjusted reward calculations:
    - Sharpe ratio
    - Sortino ratio  
    - Calmar ratio
    - Profit factor
    - Combined risk-adjusted reward

Coverage Target: 95%+
"""

import pytest
import numpy as np

from financial_analyzer.rl.rewards import (
    calculate_sharpe_reward,
    calculate_sortino_reward,
    calculate_calmar_reward,
    calculate_profit_factor_reward,
    calculate_risk_adjusted_reward,
)


class TestSharpeReward:
    """Test Sharpe ratio reward calculation."""
    
    def test_sharpe_basic(self):
        """Test basic Sharpe calculation."""
        returns = np.array([0.01, 0.02, -0.005, 0.015, 0.01])
        sharpe = calculate_sharpe_reward(returns, rf_rate=0.02)
        
        assert isinstance(sharpe, float)
        assert -10 < sharpe < 30  # Reasonable range (can be high for short series)
    
    def test_sharpe_positive_returns(self):
        """Test Sharpe with all positive returns."""
        returns = np.array([0.01, 0.02, 0.015, 0.02, 0.01])
        sharpe = calculate_sharpe_reward(returns, rf_rate=0.0)
        
        assert sharpe > 0
    
    def test_sharpe_negative_returns(self):
        """Test Sharpe with all negative returns."""
        returns = np.array([-0.01, -0.02, -0.015, -0.02, -0.01])
        sharpe = calculate_sharpe_reward(returns, rf_rate=0.0)
        
        assert sharpe < 0
    
    def test_sharpe_zero_volatility(self):
        """Test Sharpe with zero volatility."""
        returns = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        sharpe = calculate_sharpe_reward(returns, rf_rate=0.0)
        
        assert sharpe == 0.0
    
    def test_sharpe_single_return(self):
        """Test Sharpe with single return."""
        returns = np.array([0.01])
        sharpe = calculate_sharpe_reward(returns)
        
        assert sharpe == 0.0
    
    def test_sharpe_empty_array(self):
        """Test Sharpe with empty array."""
        returns = np.array([])
        sharpe = calculate_sharpe_reward(returns)
        
        assert sharpe == 0.0
    
    def test_sharpe_custom_rf_rate(self):
        """Test Sharpe with custom risk-free rate."""
        returns = np.array([0.01, 0.02, 0.015, 0.02, 0.01])
        
        sharpe_low_rf = calculate_sharpe_reward(returns, rf_rate=0.01)
        sharpe_high_rf = calculate_sharpe_reward(returns, rf_rate=0.10)
        
        assert sharpe_low_rf > sharpe_high_rf


class TestSortinoReward:
    """Test Sortino ratio reward calculation."""
    
    def test_sortino_basic(self):
        """Test basic Sortino calculation."""
        returns = np.array([0.01, 0.02, -0.005, 0.015, -0.01])
        sortino = calculate_sortino_reward(returns, rf_rate=0.02)
        
        assert isinstance(sortino, float)
        assert -10 < sortino < 30  # Reasonable range (can be high for short series)
    
    def test_sortino_no_downside(self):
        """Test Sortino with no downside returns."""
        returns = np.array([0.01, 0.02, 0.015, 0.02, 0.01])
        sortino = calculate_sortino_reward(returns, rf_rate=0.0)
        
        assert sortino > 0
    
    def test_sortino_all_downside(self):
        """Test Sortino with all downside returns."""
        returns = np.array([-0.01, -0.02, -0.015, -0.02, -0.01])
        sortino = calculate_sortino_reward(returns, rf_rate=0.0)
        
        assert sortino < 0
    
    def test_sortino_vs_sharpe(self):
        """Test Sortino typically higher than Sharpe for asymmetric returns."""
        # More upside than downside
        returns = np.array([0.03, 0.04, -0.005, 0.02, -0.003, 0.025])
        
        sharpe = calculate_sharpe_reward(returns, rf_rate=0.0)
        sortino = calculate_sortino_reward(returns, rf_rate=0.0)
        
        # Sortino should be higher (less penalty for upside volatility)
        assert sortino >= sharpe
    
    def test_sortino_custom_target(self):
        """Test Sortino with custom target return."""
        returns = np.array([0.01, 0.02, -0.005, 0.015, 0.01])
        
        sortino_low = calculate_sortino_reward(returns, target_return=0.0)
        sortino_high = calculate_sortino_reward(returns, target_return=0.02 / 252)
        
        assert isinstance(sortino_low, float)
        assert isinstance(sortino_high, float)


class TestCalmarReward:
    """Test Calmar ratio reward calculation."""
    
    def test_calmar_basic(self):
        """Test basic Calmar calculation."""
        returns = np.array([0.01, 0.02, -0.01, 0.015, -0.005])
        calmar = calculate_calmar_reward(returns)
        
        assert isinstance(calmar, float)
    
    def test_calmar_positive_trend(self):
        """Test Calmar with positive trend."""
        returns = np.array([0.01, 0.02, 0.015, -0.005, 0.02])
        calmar = calculate_calmar_reward(returns)
        
        assert calmar > 0
    
    def test_calmar_negative_trend(self):
        """Test Calmar with negative trend."""
        returns = np.array([-0.01, -0.02, -0.015, 0.005, -0.02])
        calmar = calculate_calmar_reward(returns)
        
        assert calmar < 0
    
    def test_calmar_no_drawdown(self):
        """Test Calmar with no drawdown (monotonic increase)."""
        returns = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        calmar = calculate_calmar_reward(returns)
        
        # Should be zero (no drawdown)
        assert calmar == 0.0
    
    def test_calmar_single_return(self):
        """Test Calmar with single return."""
        returns = np.array([0.01])
        calmar = calculate_calmar_reward(returns)
        
        assert calmar == 0.0


class TestProfitFactorReward:
    """Test profit factor reward calculation."""
    
    def test_profit_factor_basic(self):
        """Test basic profit factor calculation."""
        returns = np.array([0.02, -0.01, 0.03, -0.005, 0.015])
        pf = calculate_profit_factor_reward(returns)
        
        assert isinstance(pf, float)
        assert pf > 0
    
    def test_profit_factor_all_wins(self):
        """Test profit factor with all winning trades."""
        returns = np.array([0.01, 0.02, 0.015, 0.02, 0.01])
        pf = calculate_profit_factor_reward(returns)
        
        assert pf == 10.0  # Maximum
    
    def test_profit_factor_all_losses(self):
        """Test profit factor with all losing trades."""
        returns = np.array([-0.01, -0.02, -0.015, -0.02, -0.01])
        pf = calculate_profit_factor_reward(returns)
        
        assert pf == pytest.approx(0.0, abs=0.1)  # No wins = 0 profit factor
    
    def test_profit_factor_balanced(self):
        """Test profit factor with balanced wins/losses."""
        returns = np.array([0.01, -0.01, 0.01, -0.01])
        pf = calculate_profit_factor_reward(returns)
        
        assert pf == pytest.approx(1.0, rel=0.01)
    
    def test_profit_factor_greater_than_one(self):
        """Test profit factor > 1 for profitable strategy."""
        returns = np.array([0.03, -0.01, 0.02, -0.005])
        pf = calculate_profit_factor_reward(returns)
        
        assert pf > 1.0
    
    def test_profit_factor_less_than_one(self):
        """Test profit factor < 1 for losing strategy."""
        returns = np.array([0.01, -0.03, 0.005, -0.02])
        pf = calculate_profit_factor_reward(returns)
        
        assert pf < 1.0


class TestRiskAdjustedReward:
    """Test combined risk-adjusted reward."""
    
    def test_risk_adjusted_basic(self):
        """Test basic combined reward calculation."""
        returns = np.array([0.01, 0.02, -0.005, 0.015, 0.01])
        reward = calculate_risk_adjusted_reward(returns)
        
        assert isinstance(reward, float)
        assert -10 < reward < 10
    
    def test_risk_adjusted_custom_weights(self):
        """Test combined reward with custom weights."""
        returns = np.array([0.01, 0.02, -0.005, 0.015, 0.01])
        
        reward = calculate_risk_adjusted_reward(
            returns,
            sharpe_weight=0.6,
            sortino_weight=0.3,
            calmar_weight=0.1
        )
        
        assert isinstance(reward, float)
    
    def test_risk_adjusted_positive_returns(self):
        """Test combined reward with positive returns."""
        returns = np.array([0.02, 0.03, 0.01, 0.025, 0.02])
        reward = calculate_risk_adjusted_reward(returns, rf_rate=0.0)
        
        assert reward > 0
    
    def test_risk_adjusted_negative_returns(self):
        """Test combined reward with negative returns."""
        returns = np.array([-0.02, -0.03, -0.01, -0.025, -0.02])
        reward = calculate_risk_adjusted_reward(returns, rf_rate=0.0)
        
        assert reward < 0
    
    def test_risk_adjusted_clipping(self):
        """Test combined reward clips extreme values."""
        # Create extreme returns
        returns = np.array([0.5, -0.4, 0.6, -0.3, 0.5])
        reward = calculate_risk_adjusted_reward(returns)
        
        # Should be clipped to reasonable range
        assert -10 < reward < 10


class TestRewardEdgeCases:
    """Test edge cases for all reward functions."""
    
    def test_all_rewards_with_empty_array(self):
        """Test all reward functions with empty array."""
        returns = np.array([])
        
        assert calculate_sharpe_reward(returns) == 0.0
        assert calculate_sortino_reward(returns) == 0.0
        assert calculate_calmar_reward(returns) == 0.0
        assert calculate_profit_factor_reward(returns) == 1.0
        assert calculate_risk_adjusted_reward(returns) == 0.0
    
    def test_all_rewards_with_single_value(self):
        """Test all reward functions with single value."""
        returns = np.array([0.01])
        
        assert calculate_sharpe_reward(returns) == 0.0
        assert calculate_sortino_reward(returns) == 0.0
        assert calculate_calmar_reward(returns) == 0.0
        # Profit factor should handle single value
        pf = calculate_profit_factor_reward(returns)
        assert pf > 0
    
    def test_all_rewards_with_zeros(self):
        """Test all reward functions with zero returns."""
        returns = np.array([0.0, 0.0, 0.0, 0.0])
        
        assert calculate_sharpe_reward(returns) == 0.0
        # Others may vary
        sortino = calculate_sortino_reward(returns)
        assert isinstance(sortino, float)
    
    def test_rewards_with_large_values(self):
        """Test reward functions with large values."""
        returns = np.array([1.0, 0.9, 1.1, 0.95])  # 100% returns
        
        sharpe = calculate_sharpe_reward(returns)
        sortino = calculate_sortino_reward(returns)
        calmar = calculate_calmar_reward(returns)
        
        assert all(isinstance(r, float) for r in [sharpe, sortino, calmar])
    
    def test_rewards_with_small_values(self):
        """Test reward functions with very small values."""
        returns = np.array([1e-6, -5e-7, 2e-6, -1e-7])
        
        sharpe = calculate_sharpe_reward(returns)
        sortino = calculate_sortino_reward(returns)
        
        assert isinstance(sharpe, float)
        assert isinstance(sortino, float)


class TestRewardConsistency:
    """Test consistency across reward functions."""
    
    def test_rewards_consistent_signs(self):
        """Test all rewards have consistent signs for same data."""
        # Positive trend
        positive_returns = np.array([0.01, 0.02, 0.015, 0.02, 0.01])
        
        sharpe_pos = calculate_sharpe_reward(positive_returns, rf_rate=0.0)
        sortino_pos = calculate_sortino_reward(positive_returns, rf_rate=0.0)
        calmar_pos = calculate_calmar_reward(positive_returns)
        
        assert sharpe_pos > 0
        assert sortino_pos > 0
        assert calmar_pos >= 0  # May be 0 if no drawdown
        
        # Negative trend
        negative_returns = np.array([-0.01, -0.02, -0.015, -0.02, -0.01])
        
        sharpe_neg = calculate_sharpe_reward(negative_returns, rf_rate=0.0)
        sortino_neg = calculate_sortino_reward(negative_returns, rf_rate=0.0)
        calmar_neg = calculate_calmar_reward(negative_returns)
        
        assert sharpe_neg < 0
        assert sortino_neg < 0
        assert calmar_neg <= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
