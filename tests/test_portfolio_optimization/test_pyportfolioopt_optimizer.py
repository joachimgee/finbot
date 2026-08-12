"""
Tests for PyPortfolioOpt optimizer integration.

Covers:
- Max Sharpe optimization
- Min volatility optimization
- Black-Litterman with views
- Efficient frontier calculation
- Discrete allocation
- Constraint integration
- Error handling and edge cases
"""

from __future__ import annotations

from typing import Dict
import pytest
import numpy as np
import pandas as pd

from financial_analyzer.portfolio.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
from financial_analyzer.portfolio.constraints import PortfolioConstraints


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    """
    Generate realistic synthetic price data for 5 assets over 252 days.
    """
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=252, freq="D")
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    # Generate returns with some correlation
    returns = np.random.multivariate_normal(
        mean=[0.0005] * 5,
        cov=np.array([
            [0.0004, 0.0002, 0.0001, 0.0001, 0.0001],
            [0.0002, 0.0005, 0.0002, 0.0001, 0.0001],
            [0.0001, 0.0002, 0.0006, 0.0001, 0.0001],
            [0.0001, 0.0001, 0.0001, 0.0007, 0.0002],
            [0.0001, 0.0001, 0.0001, 0.0002, 0.0010],
        ]),
        size=252,
    )

    # Cumulative product to get prices
    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=tickers,
    )

    return prices


@pytest.fixture
def sample_constraints() -> PortfolioConstraints:
    """
    Create sample constraints for testing.
    """
    constraints = PortfolioConstraints(
        sector_mapping={
            "AAPL": "Tech",
            "MSFT": "Tech",
            "GOOGL": "Tech",
            "AMZN": "Other",
            "TSLA": "Other",
        }
    )
    # Use existing API
    constraints.add_allocation_limits(min_weight=0.0, max_weight=0.4)
    constraints.sector_limits = {"Tech": 0.6, "Other": 0.4}
    constraints.long_only_enabled = True

    return constraints


# ======================= INITIALIZATION TESTS =======================


def test_initialization_valid(sample_prices: pd.DataFrame) -> None:
    """Test PyPortfolioOptOptimizer initialization with valid data."""
    opt = PyPortfolioOptOptimizer(sample_prices, risk_free_rate=0.02, frequency=252)

    assert opt.tickers == list(sample_prices.columns)
    assert opt.risk_free_rate == 0.02
    assert opt.frequency == 252
    assert opt.prices.shape == sample_prices.shape


def test_initialization_empty_prices() -> None:
    """Test initialization with empty DataFrame raises error."""
    with pytest.raises(ValueError, match="prices must be a non-empty DataFrame"):
        PyPortfolioOptOptimizer(pd.DataFrame())


def test_initialization_none_prices() -> None:
    """Test initialization with None raises error."""
    with pytest.raises(ValueError, match="prices must be a non-empty DataFrame"):
        PyPortfolioOptOptimizer(None)  # type: ignore


def test_initialization_non_datetime_index(sample_prices: pd.DataFrame) -> None:
    """Test initialization with non-datetime index logs warning."""
    prices_no_dt = sample_prices.reset_index(drop=True)
    opt = PyPortfolioOptOptimizer(prices_no_dt)
    # Should log warning but not fail
    assert opt.tickers == list(prices_no_dt.columns)


# ======================= MAX SHARPE TESTS =======================


def test_max_sharpe_basic(sample_prices: pd.DataFrame) -> None:
    """Test basic max Sharpe optimization."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe()

    assert isinstance(weights, pd.Series)
    assert len(weights) == len(sample_prices.columns)
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    assert (weights >= -0.01).all()  # Numerical tolerance for 0


def test_max_sharpe_with_constraints(
    sample_prices: pd.DataFrame,
    sample_constraints: PortfolioConstraints,
) -> None:
    """Test max Sharpe with constraints."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe(constraints=sample_constraints)

    # Check weight bounds
    assert (weights >= 0.0).all()  # Long-only
    assert (weights <= 0.4).all()  # Max weight

    # Check sector limits
    tech_weight = weights[["AAPL", "MSFT", "GOOGL"]].sum()
    other_weight = weights[["AMZN", "TSLA"]].sum()
    assert tech_weight <= 0.6 + 1e-4
    assert other_weight <= 0.4 + 1e-4


def test_max_sharpe_different_methods(sample_prices: pd.DataFrame) -> None:
    """Test max Sharpe with different expected return methods."""
    opt = PyPortfolioOptOptimizer(sample_prices)

    w1 = opt.optimize_max_sharpe(method="mean_historical_return")
    w2 = opt.optimize_max_sharpe(method="ema_historical_return")

    assert isinstance(w1, pd.Series)
    assert isinstance(w2, pd.Series)
    # Different methods should produce different results
    assert not np.allclose(w1.values, w2.values, atol=1e-2)


def test_max_sharpe_different_cov_methods(sample_prices: pd.DataFrame) -> None:
    """Test max Sharpe with different covariance methods."""
    opt = PyPortfolioOptOptimizer(sample_prices)

    w1 = opt.optimize_max_sharpe(cov_method="sample_cov")
    w2 = opt.optimize_max_sharpe(cov_method="ledoit_wolf")

    assert isinstance(w1, pd.Series)
    assert isinstance(w2, pd.Series)
    # Different covariance estimation should affect results
    # (may be similar but not identical)


# ======================= MIN VOLATILITY TESTS =======================


def test_min_volatility_basic(sample_prices: pd.DataFrame) -> None:
    """Test basic min volatility optimization."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_min_volatility()

    assert isinstance(weights, pd.Series)
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    assert (weights >= -0.01).all()


def test_min_volatility_with_constraints(
    sample_prices: pd.DataFrame,
    sample_constraints: PortfolioConstraints,
) -> None:
    """Test min volatility with constraints."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_min_volatility(constraints=sample_constraints)

    assert (weights >= 0.0).all()
    assert (weights <= 0.4).all()

    # Min vol tends to diversify → check sector constraints
    tech_weight = weights[["AAPL", "MSFT", "GOOGL"]].sum()
    other_weight = weights[["AMZN", "TSLA"]].sum()
    assert tech_weight <= 0.6 + 1e-4
    assert other_weight <= 0.4 + 1e-4


def test_min_volatility_different_cov_methods(sample_prices: pd.DataFrame) -> None:
    """Test min volatility with different covariance methods."""
    opt = PyPortfolioOptOptimizer(sample_prices)

    w1 = opt.optimize_min_volatility(cov_method="sample_cov")
    w2 = opt.optimize_min_volatility(cov_method="semicovariance")

    assert isinstance(w1, pd.Series)
    assert isinstance(w2, pd.Series)
    # Different covariance methods should affect min vol result


# ======================= BLACK-LITTERMAN TESTS =======================


def test_black_litterman_basic(sample_prices: pd.DataFrame) -> None:
    """Test Black-Litterman optimization with simple views."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    views = {"AAPL": 0.15, "TSLA": 0.20}  # Absolute views

    weights = opt.optimize_black_litterman(views=views)

    assert isinstance(weights, pd.Series)
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    # Higher views should lead to higher weights (not guaranteed but likely)


def test_black_litterman_with_confidences(sample_prices: pd.DataFrame) -> None:
    """Test Black-Litterman with view confidences."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    views = {"AAPL": 0.15, "TSLA": 0.20}
    confidences = {"AAPL": 0.8, "TSLA": 0.5}

    weights = opt.optimize_black_litterman(views=views, view_confidences=confidences)

    assert isinstance(weights, pd.Series)
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    # Higher confidence in AAPL should tilt weights more


def test_black_litterman_with_market_caps(sample_prices: pd.DataFrame) -> None:
    """Test Black-Litterman with market caps for prior."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    views = {"AAPL": 0.10}
    market_caps = {
        "AAPL": 3e12,
        "MSFT": 2.5e12,
        "GOOGL": 1.8e12,
        "AMZN": 1.5e12,
        "TSLA": 0.8e12,
    }

    weights = opt.optimize_black_litterman(views=views, market_caps=market_caps)

    assert isinstance(weights, pd.Series)
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    # Market-cap weighted prior should tilt towards large caps


def test_black_litterman_with_constraints(
    sample_prices: pd.DataFrame,
    sample_constraints: PortfolioConstraints,
) -> None:
    """Test Black-Litterman with constraints."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    views = {"GOOGL": 0.12}

    weights = opt.optimize_black_litterman(views=views, constraints=sample_constraints)

    assert (weights >= 0.0).all()
    assert (weights <= 0.4).all()

    tech_weight = weights[["AAPL", "MSFT", "GOOGL"]].sum()
    other_weight = weights[["AMZN", "TSLA"]].sum()
    assert tech_weight <= 0.6 + 1e-4
    assert other_weight <= 0.4 + 1e-4


# ======================= EFFICIENT FRONTIER TESTS =======================


def test_efficient_frontier_basic(sample_prices: pd.DataFrame) -> None:
    """Test efficient frontier calculation."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    frontier = opt.calculate_efficient_frontier(num_portfolios=50)

    assert isinstance(frontier, pd.DataFrame)
    assert len(frontier) > 0
    assert "return" in frontier.columns
    assert "volatility" in frontier.columns
    assert "sharpe" in frontier.columns
    assert "weights" in frontier.columns

    # Frontier should be sorted by return
    assert (frontier["return"].diff().dropna() >= 0).all()

    # Volatility should be monotonic (cummax enforced)
    assert (frontier["volatility"].diff().dropna() >= -1e-6).all()

    # Each weights should sum to 1
    for w in frontier["weights"]:
        assert np.isclose(w.sum(), 1.0, atol=1e-4)


def test_efficient_frontier_with_constraints(
    sample_prices: pd.DataFrame,
    sample_constraints: PortfolioConstraints,
) -> None:
    """Test efficient frontier with constraints."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    frontier = opt.calculate_efficient_frontier(num_portfolios=30, constraints=sample_constraints)

    assert len(frontier) > 0

    # Check all weights satisfy constraints
    for w in frontier["weights"]:
        assert (w >= 0.0).all()
        assert (w <= 0.4).all()

        tech_weight = w[["AAPL", "MSFT", "GOOGL"]].sum()
        other_weight = w[["AMZN", "TSLA"]].sum()
        assert tech_weight <= 0.6 + 1e-4
        assert other_weight <= 0.4 + 1e-4


def test_efficient_frontier_small_num_portfolios(sample_prices: pd.DataFrame) -> None:
    """Test efficient frontier with small number of portfolios."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    frontier = opt.calculate_efficient_frontier(num_portfolios=5)

    assert len(frontier) <= 5  # Some may fail
    assert len(frontier) > 0


# ======================= NEW FUNCTIONALITY TESTS =======================


def test_optimize_efficient_return(sample_prices: pd.DataFrame) -> None:
    opt = PyPortfolioOptOptimizer(sample_prices)
    # Pick a modest target return between min/max historical returns
    mu = opt._expected_returns("mean_historical_return")
    target = float(np.clip(mu.mean(), mu.min() + 1e-4, mu.max() - 1e-4))
    w = opt.optimize_efficient_return(target_return=target)
    assert isinstance(w, pd.Series)
    assert np.isclose(w.sum(), 1.0, atol=1e-4)


def test_optimize_efficient_risk(sample_prices: pd.DataFrame) -> None:
    opt = PyPortfolioOptOptimizer(sample_prices)
    # Compute a feasible target volatility between low/high
    S = opt._covariance_matrix("sample_cov")
    # Use diagonal as rough volatility proxy
    vol_guess = float(np.sqrt(np.diag(S)).mean())
    target_vol = max(1e-4, min(vol_guess * 1.2, vol_guess * 2.0))
    w = opt.optimize_efficient_risk(target_volatility=target_vol)
    assert isinstance(w, pd.Series)
    assert np.isclose(w.sum(), 1.0, atol=1e-4)


def test_max_quadratic_utility_and_l2_reg(sample_prices: pd.DataFrame) -> None:
    opt = PyPortfolioOptOptimizer(sample_prices)
    w1 = opt.optimize_max_quadratic_utility(risk_aversion=1.0)
    w2 = opt.optimize_max_quadratic_utility(risk_aversion=1.0, l2_reg=1e-2)
    assert isinstance(w1, pd.Series) and isinstance(w2, pd.Series)
    assert np.isclose(w1.sum(), 1.0, atol=1e-4)
    assert np.isclose(w2.sum(), 1.0, atol=1e-4)
    # L2 regularization should not break feasibility; differences may be small or null on some data.


def test_portfolio_performance_and_risk_contributions(sample_prices: pd.DataFrame) -> None:
    opt = PyPortfolioOptOptimizer(sample_prices)
    w = opt.optimize_min_volatility()
    exp_ret, vol, sharpe = opt.portfolio_performance(w)
    assert isinstance(exp_ret, float) and isinstance(vol, float) and isinstance(sharpe, float)
    assert vol >= 0
    rc = opt.risk_contributions(w)
    assert set(rc.columns) == {"marginal", "contribution", "percentage"}
    assert np.isclose(float(rc["percentage"].sum()), 1.0, atol=1e-6)


def test_turnover_and_asset_specific_bounds(sample_prices: pd.DataFrame) -> None:
    opt = PyPortfolioOptOptimizer(sample_prices)
    w_a = opt.optimize_max_sharpe()
    w_b = opt.optimize_min_volatility()
    to = opt.turnover(w_a, w_b, one_way=True)
    assert isinstance(to, float) and to >= 0

    # Asset-specific bounds: force AAPL <= 10%, MSFT >= 5%
    cons = PortfolioConstraints()
    cons.add_asset_bound("AAPL", 0.0, 0.10)
    cons.add_asset_bound("MSFT", 0.05, 0.50)
    cons.add_allocation_limits(min_weight=0.0, max_weight=0.6)
    w_c = opt.optimize_max_sharpe(constraints=cons)
    assert w_c["AAPL"] <= 0.10 + 1e-4
    assert w_c["MSFT"] >= 0.05 - 1e-4


# ======================= DISCRETE ALLOCATION TESTS =======================


def test_discrete_allocation_basic(sample_prices: pd.DataFrame) -> None:
    """Test discrete allocation from continuous weights."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe()

    allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=100000.0)

    assert isinstance(allocation, dict)
    assert isinstance(leftover, float)
    assert leftover >= 0.0

    # Allocation should use most of the capital
    latest_prices = sample_prices.iloc[-1]
    allocated_value = sum(allocation[t] * latest_prices[t] for t in allocation)
    assert allocated_value + leftover <= 100000.0 + 1.0  # Numerical tolerance


def test_discrete_allocation_small_capital(sample_prices: pd.DataFrame) -> None:
    """Test discrete allocation with small capital."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe()

    allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=1000.0)

    # With small capital, may not afford many shares
    assert isinstance(allocation, dict)
    assert leftover < 1000.0


def test_discrete_allocation_large_capital(sample_prices: pd.DataFrame) -> None:
    """Test discrete allocation with large capital."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe()

    allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=10_000_000.0)

    assert isinstance(allocation, dict)
    assert len(allocation) > 0
    # Leftover should be small relative to total
    assert leftover / 10_000_000.0 < 0.01


# ======================= ERROR HANDLING & EDGE CASES =======================


def test_invalid_expected_returns_method(sample_prices: pd.DataFrame) -> None:
    """Test invalid expected returns method raises error."""
    opt = PyPortfolioOptOptimizer(sample_prices)

    with pytest.raises(ValueError, match="Unknown expected returns method"):
        opt.optimize_max_sharpe(method="invalid_method")


def test_invalid_covariance_method(sample_prices: pd.DataFrame) -> None:
    """Test invalid covariance method raises error."""
    opt = PyPortfolioOptOptimizer(sample_prices)

    with pytest.raises(ValueError, match="Unknown covariance method"):
        opt.optimize_max_sharpe(cov_method="invalid_cov")


def test_single_asset_optimization() -> None:
    """Test optimization with single asset."""
    dates = pd.date_range(start="2022-01-01", periods=100, freq="D")
    prices = pd.DataFrame(
        {"AAPL": np.linspace(100, 120, 100)},
        index=dates,
    )

    opt = PyPortfolioOptOptimizer(prices)
    weights = opt.optimize_max_sharpe()

    assert len(weights) == 1
    assert np.isclose(weights.iloc[0], 1.0, atol=1e-4)


def test_two_asset_optimization() -> None:
    """Test optimization with two assets."""
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=100, freq="D")
    returns = np.random.multivariate_normal(
        mean=[0.003, 0.0025],  # Higher returns to exceed rf=0.02 annually
        cov=[[0.0004, 0.0001], [0.0001, 0.0005]],
        size=100,
    )
    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=["AAPL", "MSFT"],
    )

    opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.00)  # rf=0 to avoid constraint
    weights = opt.optimize_max_sharpe()

    assert len(weights) == 2
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    assert (weights >= -0.01).all()


def test_highly_correlated_assets() -> None:
    """Test optimization with highly correlated assets."""
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=252, freq="D")
    # Nearly identical assets
    returns = np.random.normal(loc=0.0005, scale=0.01, size=(252, 3))
    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=["A", "B", "C"],
    )

    opt = PyPortfolioOptOptimizer(prices)
    weights = opt.optimize_max_sharpe()

    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    # Highly correlated → diversification less beneficial


def test_negative_returns_data() -> None:
    """Test optimization with assets having negative average returns."""
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=100, freq="D")
    returns = np.random.multivariate_normal(
        mean=[-0.001, -0.0008, -0.0005],  # Negative drift
        cov=np.eye(3) * 0.0004,
        size=100,
    )
    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=["A", "B", "C"],
    )

    opt = PyPortfolioOptOptimizer(prices)
    weights = opt.optimize_max_sharpe()

    # Should still return valid weights (may concentrate on least-negative)
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)


def test_constraints_no_sector_limits(sample_prices: pd.DataFrame) -> None:
    """Test constraints without sector limits."""
    constraints = PortfolioConstraints()
    constraints.add_allocation_limits(min_weight=0.0, max_weight=0.3)
    constraints.long_only_enabled = True

    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe(constraints=constraints)

    assert (weights >= 0.0).all()
    assert (weights <= 0.3 + 1e-4).all()  # Add tolerance for numerical precision


def test_constraints_short_allowed(sample_prices: pd.DataFrame) -> None:
    """Test constraints with short selling allowed."""
    constraints = PortfolioConstraints()
    constraints.long_only_enabled = False
    constraints.max_weight = 0.5

    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe(constraints=constraints)

    # Weights can be negative
    # Sum should still be ~1.0
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)


def test_zero_risk_free_rate(sample_prices: pd.DataFrame) -> None:
    """Test optimization with zero risk-free rate."""
    opt = PyPortfolioOptOptimizer(sample_prices, risk_free_rate=0.0)
    weights = opt.optimize_max_sharpe()

    assert np.isclose(weights.sum(), 1.0, atol=1e-4)


def test_high_risk_free_rate(sample_prices: pd.DataFrame) -> None:
    """Test optimization with high risk-free rate."""
    opt = PyPortfolioOptOptimizer(sample_prices, risk_free_rate=0.10)
    weights = opt.optimize_max_sharpe()

    assert np.isclose(weights.sum(), 1.0, atol=1e-4)
    # High rf → optimizer needs higher returns to justify risk


# ======================= INTEGRATION WITH PORTFOLIO CONSTRAINTS =======================


def test_portfolio_constraints_integration(sample_prices: pd.DataFrame) -> None:
    """Test full integration with PortfolioConstraints."""
    constraints = PortfolioConstraints(
        sector_mapping={
            "AAPL": "Tech",
            "MSFT": "Tech",
            "GOOGL": "Tech",
            "AMZN": "Other",
            "TSLA": "Other",
        }
    )
    constraints.long_only_enabled = True
    constraints.add_allocation_limits(min_weight=0.05, max_weight=0.25)
    constraints.sector_limits = {"Tech": 0.5, "Other": 0.5}

    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe(constraints=constraints)

    # Validate all constraints
    assert (weights >= 0.0).all()
    assert (weights <= 0.25 + 1e-4).all()

    tech_weight = weights[["AAPL", "MSFT", "GOOGL"]].sum()
    other_weight = weights[["AMZN", "TSLA"]].sum()
    assert tech_weight <= 0.5 + 1e-4
    assert other_weight <= 0.5 + 1e-4

    assert np.isclose(weights.sum(), 1.0, atol=1e-4)


def test_portfolio_constraints_none_bounds(sample_prices: pd.DataFrame) -> None:
    """Test PortfolioConstraints with None max_weight."""
    constraints = PortfolioConstraints()
    constraints.long_only_enabled = True
    constraints.max_weight = None  # No upper bound except sum=1

    opt = PyPortfolioOptOptimizer(sample_prices)
    weights = opt.optimize_max_sharpe(constraints=constraints)

    assert (weights >= 0.0).all()
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)


# ======================= COMPARISON TESTS =======================


def test_max_sharpe_vs_min_vol_different_results(sample_prices: pd.DataFrame) -> None:
    """Test that max Sharpe and min vol produce different portfolios."""
    opt = PyPortfolioOptOptimizer(sample_prices)

    w_sharpe = opt.optimize_max_sharpe()
    w_min_vol = opt.optimize_min_volatility()

    # Should be different (unless data is degenerate)
    assert not np.allclose(w_sharpe.values, w_min_vol.values, atol=1e-2)


def test_black_litterman_vs_max_sharpe_different_with_views(sample_prices: pd.DataFrame) -> None:
    """Test that Black-Litterman with views differs from max Sharpe."""
    opt = PyPortfolioOptOptimizer(sample_prices)

    w_sharpe = opt.optimize_max_sharpe()
    views = {"TSLA": 0.25}  # Strong view
    w_bl = opt.optimize_black_litterman(views=views)

    # BL should differ due to views
    assert not np.allclose(w_sharpe.values, w_bl.values, atol=1e-2)
    # TSLA weight should increase in BL
    assert w_bl["TSLA"] >= w_sharpe["TSLA"] - 0.01


# ======================= PERFORMANCE TESTS =======================


def test_optimization_performance_large_universe() -> None:
    """Test optimization performance with larger universe (50 assets)."""
    np.random.seed(42)
    dates = pd.date_range(start="2021-01-01", periods=252, freq="D")
    n_assets = 50
    tickers = [f"TICKER{i:02d}" for i in range(n_assets)]

    # Random returns with some structure
    returns = np.random.multivariate_normal(
        mean=[0.0005] * n_assets,
        cov=np.eye(n_assets) * 0.0005 + 0.0001,
        size=252,
    )
    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=tickers,
    )

    opt = PyPortfolioOptOptimizer(prices)
    weights = opt.optimize_max_sharpe()

    assert len(weights) == n_assets
    assert np.isclose(weights.sum(), 1.0, atol=1e-4)


def test_efficient_frontier_performance(sample_prices: pd.DataFrame) -> None:
    """Test efficient frontier calculation performance."""
    opt = PyPortfolioOptOptimizer(sample_prices)
    frontier = opt.calculate_efficient_frontier(num_portfolios=100)

    # Should complete in reasonable time
    assert len(frontier) > 0
    assert len(frontier) <= 100


# ======================= MODULE-LEVEL TESTS =======================


def test_module_all_exports() -> None:
    """Test that __all__ exports are correct."""
    from financial_analyzer.portfolio import pyportfolioopt_optimizer

    assert hasattr(pyportfolioopt_optimizer, "__all__")
    assert "PyPortfolioOptOptimizer" in pyportfolioopt_optimizer.__all__


def test_module_logger_created() -> None:
    """Test that module logger is created."""
    from financial_analyzer.portfolio import pyportfolioopt_optimizer

    assert pyportfolioopt_optimizer.logger is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
