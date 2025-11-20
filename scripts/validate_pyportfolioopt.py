#!/usr/bin/env python3
"""
Quick validation script for PyPortfolioOpt backend integration.

Validates:
1. Module imports correctly
2. Basic max Sharpe works
3. Min volatility works
4. Constraints are respected
5. Black-Litterman works
6. Discrete allocation works

Exit code 0 if all pass, 1 otherwise.
"""

import sys
import numpy as np
import pandas as pd

def generate_test_prices() -> pd.DataFrame:
    """Generate test price data."""
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=252, freq="D")
    returns = np.random.multivariate_normal(
        mean=[0.001] * 5,
        cov=np.eye(5) * 0.0004 + 0.0001,
        size=252,
    )
    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    )
    return prices


def validate_import():
    """Validate module imports."""
    print("🔍 Validation 1: Module Import")
    try:
        from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
        print("   ✅ PyPortfolioOptOptimizer imported successfully")
        return True
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False


def validate_max_sharpe():
    """Validate max Sharpe optimization."""
    print("\n🔍 Validation 2: Max Sharpe Optimization")
    try:
        from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
        
        prices = generate_test_prices()
        opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.01)
        weights = opt.optimize_max_sharpe()
        
        # Check weights sum to 1
        assert np.isclose(weights.sum(), 1.0, atol=1e-4), f"Weights sum = {weights.sum()}, expected 1.0"
        
        # Check all weights >= 0 (long-only default)
        assert (weights >= -0.01).all(), "Found negative weights in long-only"
        
        print(f"   ✅ Max Sharpe works (sum={weights.sum():.4f})")
        return True
    except Exception as e:
        print(f"   ❌ Max Sharpe failed: {e}")
        return False


def validate_min_volatility():
    """Validate min volatility optimization."""
    print("\n🔍 Validation 3: Min Volatility Optimization")
    try:
        from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
        
        prices = generate_test_prices()
        opt = PyPortfolioOptOptimizer(prices)
        weights = opt.optimize_min_volatility()
        
        assert np.isclose(weights.sum(), 1.0, atol=1e-4), f"Weights sum = {weights.sum()}, expected 1.0"
        assert (weights >= -0.01).all(), "Found negative weights in long-only"
        
        print(f"   ✅ Min Volatility works (sum={weights.sum():.4f})")
        return True
    except Exception as e:
        print(f"   ❌ Min Volatility failed: {e}")
        return False


def validate_constraints():
    """Validate constraints are respected."""
    print("\n🔍 Validation 4: Constraints Respect")
    try:
        from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
        from financial_analyzer.portfolio.constraints import PortfolioConstraints
        
        prices = generate_test_prices()
        opt = PyPortfolioOptOptimizer(prices)
        
        constraints = PortfolioConstraints(
            sector_mapping={
                "AAPL": "Tech",
                "MSFT": "Tech",
                "GOOGL": "Tech",
                "AMZN": "Retail",
                "TSLA": "Auto",
            }
        )
        constraints.add_allocation_limits(min_weight=0.0, max_weight=0.3)
        constraints.sector_limits = {"Tech": 0.6, "Retail": 0.25, "Auto": 0.15}
        
        weights = opt.optimize_max_sharpe(constraints=constraints)
        
        # Check max weight
        assert (weights <= 0.3 + 1e-4).all(), f"Max weight constraint violated: {weights.max():.4f}"
        
        # Check sector limits
        tech_weight = weights[["AAPL", "MSFT", "GOOGL"]].sum()
        retail_weight = weights["AMZN"]
        auto_weight = weights["TSLA"]
        
        assert tech_weight <= 0.6 + 1e-4, f"Tech limit violated: {tech_weight:.4f}"
        assert retail_weight <= 0.25 + 1e-4, f"Retail limit violated: {retail_weight:.4f}"
        assert auto_weight <= 0.15 + 1e-4, f"Auto limit violated: {auto_weight:.4f}"
        
        print(f"   ✅ Constraints respected (max={weights.max():.2%}, Tech={tech_weight:.2%})")
        return True
    except Exception as e:
        print(f"   ❌ Constraints validation failed: {e}")
        return False


def validate_black_litterman():
    """Validate Black-Litterman optimization."""
    print("\n🔍 Validation 5: Black-Litterman Optimization")
    try:
        from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
        
        prices = generate_test_prices()
        opt = PyPortfolioOptOptimizer(prices)
        
        views = {"AAPL": 0.15, "TSLA": 0.20}
        market_caps = {t: 1e12 for t in prices.columns}
        
        weights = opt.optimize_black_litterman(views=views, market_caps=market_caps)
        
        assert np.isclose(weights.sum(), 1.0, atol=1e-4), f"Weights sum = {weights.sum()}, expected 1.0"
        
        print(f"   ✅ Black-Litterman works (sum={weights.sum():.4f})")
        return True
    except Exception as e:
        print(f"   ❌ Black-Litterman failed: {e}")
        return False


def validate_discrete_allocation():
    """Validate discrete allocation."""
    print("\n🔍 Validation 6: Discrete Allocation")
    try:
        from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
        
        prices = generate_test_prices()
        opt = PyPortfolioOptOptimizer(prices)
        
        weights = opt.optimize_max_sharpe()
        allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=100_000)
        
        assert isinstance(allocation, dict), "Allocation should be dict"
        assert isinstance(leftover, float), "Leftover should be float"
        assert leftover >= 0.0, f"Leftover should be >= 0, got {leftover}"
        
        # Check that allocated value + leftover <= total
        latest_prices = prices.iloc[-1]
        allocated_value = sum(allocation[t] * latest_prices[t] for t in allocation)
        assert allocated_value + leftover <= 100_000 + 1.0, "Allocation exceeds capital"
        
        print(f"   ✅ Discrete allocation works (allocated=${allocated_value:,.0f}, leftover=${leftover:.2f})")
        return True
    except Exception as e:
        print(f"   ❌ Discrete allocation failed: {e}")
        return False


def main():
    """Run all validations."""
    print("=" * 70)
    print("PyPortfolioOpt Backend - Quick Validation")
    print("=" * 70)
    
    results = [
        validate_import(),
        validate_max_sharpe(),
        validate_min_volatility(),
        validate_constraints(),
        validate_black_litterman(),
        validate_discrete_allocation(),
    ]
    
    print("\n" + "=" * 70)
    if all(results):
        print("✅ ALL VALIDATIONS PASSED - PyPortfolioOpt backend is working! 🚀")
        print("=" * 70)
        return 0
    else:
        failed = sum(1 for r in results if not r)
        print(f"❌ {failed}/{len(results)} VALIDATIONS FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
