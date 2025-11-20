"""
Tests for DiscreteAllocation module.

Tests:
- get_latest_prices() helper
- DiscreteAllocation initialization and validation
- greedy_portfolio() long-only allocation
- greedy_portfolio() long-short allocation
- lp_portfolio() optimal integer allocation
- RMSE error calculation
- Cash constraints and leftover validation
- Convenience function allocate_discrete_portfolio()

Author: FinBot
License: MIT
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

from financial_analyzer.portfolio.discrete_allocation import (
    DiscreteAllocation,
    get_latest_prices,
    allocate_discrete_portfolio
)


class TestGetLatestPrices:
    """Tests for get_latest_prices helper."""
    
    def test_get_latest_prices_basic(self):
        """Test extracting latest prices from DataFrame."""
        dates = pd.date_range('2023-01-01', periods=5, freq='D')
        prices = pd.DataFrame({
            'AAPL': [150.0, 151.0, 152.0, 153.0, 154.0],
            'MSFT': [300.0, 302.0, 304.0, 306.0, 308.0],
            'GOOGL': [2800.0, 2810.0, 2820.0, 2830.0, 2840.0]
        }, index=dates)
        
        latest = get_latest_prices(prices)
        
        assert latest['AAPL'] == 154.0
        assert latest['MSFT'] == 308.0
        assert latest['GOOGL'] == 2840.0
        assert len(latest) == 3
    
    def test_get_latest_prices_with_tickers(self):
        """Test filtering by ticker list."""
        dates = pd.date_range('2023-01-01', periods=5, freq='D')
        prices = pd.DataFrame({
            'AAPL': [150.0, 151.0, 152.0, 153.0, 154.0],
            'MSFT': [300.0, 302.0, 304.0, 306.0, 308.0],
            'GOOGL': [2800.0, 2810.0, 2820.0, 2830.0, 2840.0]
        }, index=dates)
        
        latest = get_latest_prices(prices, tickers=['AAPL', 'GOOGL'])
        
        assert latest['AAPL'] == 154.0
        assert latest['GOOGL'] == 2840.0
        assert 'MSFT' not in latest
        assert len(latest) == 2
    
    def test_get_latest_prices_empty_dataframe(self):
        """Test error on empty DataFrame."""
        prices = pd.DataFrame()
        
        with pytest.raises(ValueError, match="Prices DataFrame is empty"):
            get_latest_prices(prices)
    
    def test_get_latest_prices_missing_tickers(self):
        """Test error on missing tickers."""
        dates = pd.date_range('2023-01-01', periods=5, freq='D')
        prices = pd.DataFrame({
            'AAPL': [150.0, 151.0, 152.0, 153.0, 154.0]
        }, index=dates)
        
        with pytest.raises(ValueError, match="Tickers not found in prices"):
            get_latest_prices(prices, tickers=['AAPL', 'MISSING'])
    
    def test_get_latest_prices_nan_values(self):
        """Test error on NaN prices."""
        dates = pd.date_range('2023-01-01', periods=5, freq='D')
        prices = pd.DataFrame({
            'AAPL': [150.0, 151.0, 152.0, 153.0, np.nan],
            'MSFT': [300.0, 302.0, 304.0, 306.0, 308.0]
        }, index=dates)
        
        with pytest.raises(ValueError, match="NaN prices for tickers"):
            get_latest_prices(prices)


class TestDiscreteAllocationInit:
    """Tests for DiscreteAllocation initialization."""
    
    def test_init_valid(self):
        """Test valid initialization."""
        weights = {'AAPL': 0.5, 'MSFT': 0.3, 'GOOGL': 0.2}
        prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0, 'GOOGL': 2800.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=100000)
        
        assert da.total_portfolio_value == 100000
        assert da.short_ratio == 0.3
        assert da.allocation is None
        assert len(da.weights) == 3
    
    def test_init_normalize_weights(self):
        """Test automatic weight normalization."""
        weights = {'AAPL': 0.5, 'MSFT': 0.3}  # sum = 0.8
        prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=100000)
        
        # Weights should be normalized to sum to 1.0
        weight_sum = sum([w for _, w in da.weights])
        assert np.isclose(weight_sum, 1.0, atol=1e-6)
    
    def test_init_empty_weights(self):
        """Test error on empty weights."""
        with pytest.raises(ValueError, match="Weights dict is empty"):
            DiscreteAllocation({}, pd.Series(), total_portfolio_value=100000)
    
    def test_init_negative_portfolio_value(self):
        """Test error on negative total_portfolio_value."""
        weights = {'AAPL': 1.0}
        prices = pd.Series({'AAPL': 150.0})
        
        with pytest.raises(ValueError, match="Total portfolio value must be > 0"):
            DiscreteAllocation(weights, prices, total_portfolio_value=-1000)
    
    def test_init_invalid_short_ratio(self):
        """Test error on invalid short_ratio."""
        weights = {'AAPL': 1.0}
        prices = pd.Series({'AAPL': 150.0})
        
        with pytest.raises(ValueError, match="Short ratio must be in"):
            DiscreteAllocation(weights, prices, total_portfolio_value=100000, short_ratio=1.5)
    
    def test_init_missing_prices(self):
        """Test error on missing prices."""
        weights = {'AAPL': 0.5, 'MSFT': 0.5}
        prices = pd.Series({'AAPL': 150.0})  # MSFT missing
        
        with pytest.raises(ValueError, match="Missing prices for tickers"):
            DiscreteAllocation(weights, prices, total_portfolio_value=100000)


class TestGreedyPortfolio:
    """Tests for greedy_portfolio allocation."""
    
    def test_greedy_long_only_basic(self):
        """Test basic long-only greedy allocation."""
        weights = {'AAPL': 0.5, 'MSFT': 0.3, 'GOOGL': 0.2}
        prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0, 'GOOGL': 2800.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=100000)
        allocation, leftover = da.greedy_portfolio()
        
        # Validate allocation
        assert isinstance(allocation, dict)
        assert all(isinstance(v, int) for v in allocation.values())
        
        # Validate cash constraint: sum(shares * prices) <= total_value
        total_cost = sum(allocation[t] * prices[t] for t in allocation)
        assert total_cost <= 100000
        
        # Validate leftover is positive
        assert leftover >= 0
        assert leftover < max(prices.to_numpy())  # leftover < most expensive share
    
    def test_greedy_long_only_weights_respected(self):
        """Test greedy allocation respects target weights approximately."""
        weights = {'AAPL': 0.6, 'MSFT': 0.4}
        prices = pd.Series({'AAPL': 100.0, 'MSFT': 200.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=50000)
        allocation, leftover = da.greedy_portfolio()
        
        # Calculate actual weights
        total_value = sum(allocation[t] * prices[t] for t in allocation)
        actual_weights = {t: (allocation[t] * prices[t]) / total_value for t in allocation}
        
        # Should be close to target weights (allow 10% deviation)
        assert abs(actual_weights['AAPL'] - 0.6) < 0.1
        assert abs(actual_weights['MSFT'] - 0.4) < 0.1
    
    def test_greedy_long_short(self):
        """Test greedy allocation with long-short portfolio."""
        weights = {'AAPL': 0.6, 'MSFT': 0.4, 'GOOGL': -0.3, 'TSLA': -0.2}
        prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0, 'GOOGL': 2800.0, 'TSLA': 700.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=100000, short_ratio=0.3)
        allocation, leftover = da.greedy_portfolio()
        
        # Validate long and short positions
        long_positions = {t: v for t, v in allocation.items() if v > 0}
        short_positions = {t: v for t, v in allocation.items() if v < 0}
        
        assert len(long_positions) >= 1
        assert len(short_positions) >= 1
        
        # Validate short positions are negative
        assert all(v < 0 for v in short_positions.values())
    
    def test_greedy_verbose_output(self, capsys):
        """Test verbose output prints allocation details."""
        weights = {'AAPL': 0.7, 'MSFT': 0.3}
        prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=50000)
        allocation, leftover = da.greedy_portfolio(verbose=True)
        
        captured = capsys.readouterr()
        assert "Funds remaining:" in captured.out
        assert "RMSE" in captured.out


class TestLpPortfolio:
    """Tests for lp_portfolio optimal allocation."""
    
    def test_lp_long_only_basic(self):
        """Test basic long-only LP allocation."""
        pytest.importorskip("cvxpy", reason="cvxpy required for LP tests")
        
        weights = {'AAPL': 0.5, 'MSFT': 0.3, 'GOOGL': 0.2}
        prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0, 'GOOGL': 2800.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=100000)
        allocation, leftover = da.lp_portfolio()
        
        # Validate allocation
        assert isinstance(allocation, dict)
        assert all(isinstance(v, int) for v in allocation.values())
        
        # Validate cash constraint
        total_cost = sum(allocation[t] * prices[t] for t in allocation)
        assert total_cost <= 100000
        
        # Validate leftover
        assert leftover >= 0
    
    def test_lp_vs_greedy_rmse(self):
        """Test LP allocation has lower or equal RMSE than greedy."""
        pytest.importorskip("cvxpy", reason="cvxpy required for LP tests")
        
        weights = {'AAPL': 0.6, 'MSFT': 0.4}
        prices = pd.Series({'AAPL': 100.0, 'MSFT': 200.0})
        
        # Greedy
        da_greedy = DiscreteAllocation(weights, prices, total_portfolio_value=50000)
        da_greedy.greedy_portfolio()
        rmse_greedy = da_greedy._allocation_rmse_error()
        
        # LP
        da_lp = DiscreteAllocation(weights, prices, total_portfolio_value=50000)
        da_lp.lp_portfolio()
        rmse_lp = da_lp._allocation_rmse_error()
        
        # LP should be optimal (lower or equal RMSE)
        assert rmse_lp <= rmse_greedy + 0.01  # allow small numerical tolerance
    
    def test_lp_long_short(self):
        """Test LP allocation with long-short portfolio."""
        pytest.importorskip("cvxpy", reason="cvxpy required for LP tests")
        
        weights = {'AAPL': 0.6, 'MSFT': 0.4, 'GOOGL': -0.3, 'TSLA': -0.2}
        prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0, 'GOOGL': 2800.0, 'TSLA': 700.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=100000, short_ratio=0.3)
        allocation, leftover = da.lp_portfolio()
        
        # Validate long and short positions
        long_positions = {t: v for t, v in allocation.items() if v > 0}
        short_positions = {t: v for t, v in allocation.items() if v < 0}
        
        assert len(long_positions) >= 1
        assert len(short_positions) >= 1


class TestRmseError:
    """Tests for RMSE error calculation."""
    
    def test_rmse_error_perfect_allocation(self):
        """Test RMSE with perfect allocation (weights match exactly)."""
        # Perfect allocation: 1 share @ $100 each, weights 0.5/0.5
        weights = {'A': 0.5, 'B': 0.5}
        prices = pd.Series({'A': 100.0, 'B': 100.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=200)
        da.greedy_portfolio()
        rmse = da._allocation_rmse_error()
        
        # RMSE should be very small (near 0)
        assert rmse < 0.01
    
    def test_rmse_error_before_allocation(self):
        """Test error if RMSE called before allocation."""
        weights = {'A': 1.0}
        prices = pd.Series({'A': 100.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=1000)
        
        with pytest.raises(ValueError, match="Must call greedy_portfolio"):
            da._allocation_rmse_error()


class TestAllocateDiscretePortfolio:
    """Tests for convenience function allocate_discrete_portfolio."""
    
    def test_convenience_function_greedy(self):
        """Test convenience function with greedy method."""
        weights = {'AAPL': 0.6, 'MSFT': 0.4}
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        prices = pd.DataFrame({
            'AAPL': np.linspace(145, 155, 10),
            'MSFT': np.linspace(295, 305, 10)
        }, index=dates)
        
        allocation, leftover = allocate_discrete_portfolio(
            weights=weights,
            prices=prices,
            total_cash=50000,
            method='greedy'
        )
        
        assert isinstance(allocation, dict)
        assert 'AAPL' in allocation
        assert 'MSFT' in allocation
        assert leftover >= 0
    
    def test_convenience_function_lp(self):
        """Test convenience function with LP method."""
        pytest.importorskip("cvxpy", reason="cvxpy required for LP tests")
        
        weights = {'AAPL': 0.6, 'MSFT': 0.4}
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        prices = pd.DataFrame({
            'AAPL': np.linspace(145, 155, 10),
            'MSFT': np.linspace(295, 305, 10)
        }, index=dates)
        
        allocation, leftover = allocate_discrete_portfolio(
            weights=weights,
            prices=prices,
            total_cash=50000,
            method='lp'
        )
        
        assert isinstance(allocation, dict)
        assert 'AAPL' in allocation
        assert 'MSFT' in allocation
        assert leftover >= 0
    
    def test_convenience_function_invalid_method(self):
        """Test error on invalid method."""
        weights = {'AAPL': 1.0}
        prices = pd.DataFrame({'AAPL': [150.0]})
        
        with pytest.raises(ValueError, match="Method must be"):
            allocate_discrete_portfolio(weights, prices, 10000, method='invalid')


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_very_small_portfolio(self):
        """Test allocation with very small portfolio value."""
        weights = {'AAPL': 1.0}
        prices = pd.Series({'AAPL': 150.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=100)
        allocation, leftover = da.greedy_portfolio()
        
        # Can't afford even 1 share
        assert len(allocation) == 0 or allocation.get('AAPL', 0) == 0
        assert leftover == 100  # all cash leftover
    
    def test_single_asset(self):
        """Test allocation with single asset."""
        weights = {'AAPL': 1.0}
        prices = pd.Series({'AAPL': 150.0})
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=10000)
        allocation, leftover = da.greedy_portfolio()
        
        # Should buy floor(10000 / 150) = 66 shares
        assert allocation['AAPL'] == 66
        assert leftover == 10000 - (66 * 150)
    
    def test_remove_zero_positions(self):
        """Test zero positions are removed from allocation."""
        weights = {'AAPL': 0.99, 'MSFT': 0.01}
        prices = pd.Series({'AAPL': 100.0, 'MSFT': 10000.0})  # MSFT too expensive
        
        da = DiscreteAllocation(weights, prices, total_portfolio_value=10000)
        allocation, leftover = da.greedy_portfolio()
        
        # MSFT should not appear (0 shares affordable)
        assert 'MSFT' not in allocation or allocation['MSFT'] > 0
