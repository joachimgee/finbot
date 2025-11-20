"""
PyPortfolioOpt Integration Example.

Demonstrates:
- Basic max Sharpe optimization
- Min volatility optimization
- Black-Litterman with views
- Efficient frontier calculation
- Discrete allocation
- Constraint integration
"""

import numpy as np
import pandas as pd

from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
from financial_analyzer.portfolio.constraints import PortfolioConstraints

# ======================== Generate Sample Data ========================

def generate_sample_prices(n_assets: int = 5, n_days: int = 252) -> pd.DataFrame:
    """Generate synthetic price data."""
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=n_days, freq="D")
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"][:n_assets]

    # Generate correlated returns
    returns = np.random.multivariate_normal(
        mean=[0.0005] * n_assets,
        cov=np.eye(n_assets) * 0.0004 + 0.0001,
        size=n_days,
    )

    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=tickers,
    )

    return prices


# ======================== Example 1: Basic Max Sharpe ========================

def example_max_sharpe():
    """Basic max Sharpe optimization."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Max Sharpe Optimization")
    print("=" * 60)

    prices = generate_sample_prices()
    opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)

    weights = opt.optimize_max_sharpe()

    print("\nOptimal Weights (Max Sharpe):")
    for ticker, weight in weights.items():
        print(f"  {ticker}: {weight:.2%}")

    print(f"\nTotal: {weights.sum():.2%}")


# ======================== Example 2: Min Volatility ========================

def example_min_volatility():
    """Min volatility optimization."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Min Volatility Optimization")
    print("=" * 60)

    prices = generate_sample_prices()
    opt = PyPortfolioOptOptimizer(prices)

    weights = opt.optimize_min_volatility()

    print("\nOptimal Weights (Min Vol):")
    for ticker, weight in weights.items():
        print(f"  {ticker}: {weight:.2%}")


# ======================== Example 3: With Constraints ========================

def example_with_constraints():
    """Optimization with portfolio constraints."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Optimization with Constraints")
    print("=" * 60)

    prices = generate_sample_prices()
    opt = PyPortfolioOptOptimizer(prices)

    # Setup constraints
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
    constraints.long_only_enabled = True

    weights = opt.optimize_max_sharpe(constraints=constraints)

    print("\nOptimal Weights (With Constraints):")
    for ticker, weight in weights.items():
        print(f"  {ticker}: {weight:.2%}")

    # Verify sector limits
    tech_weight = weights[["AAPL", "MSFT", "GOOGL"]].sum()
    retail_weight = weights["AMZN"]
    auto_weight = weights["TSLA"]

    print("\nSector Allocations:")
    print(f"  Tech:   {tech_weight:.2%} (limit: 60%)")
    print(f"  Retail: {retail_weight:.2%} (limit: 25%)")
    print(f"  Auto:   {auto_weight:.2%} (limit: 15%)")


# ======================== Example 4: Black-Litterman ========================

def example_black_litterman():
    """Black-Litterman optimization with views."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Black-Litterman with Views")
    print("=" * 60)

    prices = generate_sample_prices()
    opt = PyPortfolioOptOptimizer(prices)

    # Define views
    views = {
        "AAPL": 0.15,  # Bullish on AAPL: 15% expected return
        "TSLA": 0.20,  # Very bullish on TSLA: 20% expected return
    }

    confidences = {
        "AAPL": 0.8,  # High confidence
        "TSLA": 0.5,  # Medium confidence
    }

    market_caps = {
        "AAPL": 3e12,
        "MSFT": 2.5e12,
        "GOOGL": 1.8e12,
        "AMZN": 1.5e12,
        "TSLA": 0.8e12,
    }

    weights = opt.optimize_black_litterman(
        views=views,
        view_confidences=confidences,
        market_caps=market_caps,
        risk_aversion=1.0,
    )

    print("\nViews:")
    for ticker, ret in views.items():
        conf = confidences.get(ticker, 1.0)
        print(f"  {ticker}: {ret:.2%} (confidence: {conf:.0%})")

    print("\nOptimal Weights (Black-Litterman):")
    for ticker, weight in weights.items():
        print(f"  {ticker}: {weight:.2%}")


# ======================== Example 5: Efficient Frontier ========================

def example_efficient_frontier():
    """Calculate and display efficient frontier."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Efficient Frontier")
    print("=" * 60)

    prices = generate_sample_prices()
    opt = PyPortfolioOptOptimizer(prices)

    frontier = opt.calculate_efficient_frontier(num_portfolios=20)

    print("\nEfficient Frontier (sample portfolios):")
    print(f"{'Return':<10} {'Volatility':<12} {'Sharpe':<8}")
    print("-" * 30)

    for _, row in frontier.head(10).iterrows():
        print(f"{row['return']:>8.2%}   {row['volatility']:>10.2%}   {row['sharpe']:>6.2f}")

    print(f"\nTotal portfolios on frontier: {len(frontier)}")

    # Find max Sharpe portfolio
    max_sharpe_idx = frontier['sharpe'].idxmax()
    max_sharpe_portfolio = frontier.loc[max_sharpe_idx]

    print("\nMax Sharpe Portfolio:")
    print(f"  Return: {max_sharpe_portfolio['return']:.2%}")
    print(f"  Volatility: {max_sharpe_portfolio['volatility']:.2%}")
    print(f"  Sharpe: {max_sharpe_portfolio['sharpe']:.2f}")


# ======================== Example 6: Discrete Allocation ========================

def example_discrete_allocation():
    """Convert continuous weights to discrete shares."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Discrete Allocation")
    print("=" * 60)

    prices = generate_sample_prices()
    opt = PyPortfolioOptOptimizer(prices)

    # Optimize
    weights = opt.optimize_max_sharpe()

    print("\nContinuous Weights:")
    for ticker, weight in weights.items():
        print(f"  {ticker}: {weight:.2%}")

    # Discrete allocation with $100k
    total_value = 100_000.0
    allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=total_value)

    print(f"\nDiscrete Allocation (${total_value:,.0f}):")
    latest_prices = prices.iloc[-1]

    for ticker, shares in allocation.items():
        price = latest_prices[ticker]
        value = shares * price
        print(f"  {ticker}: {shares:>4} shares @ ${price:>6.2f} = ${value:>10,.2f}")

    allocated_value = sum(allocation[t] * latest_prices[t] for t in allocation)
    print(f"\nTotal Allocated: ${allocated_value:,.2f}")
    print(f"Leftover Cash:   ${leftover:,.2f}")
    print(f"Utilization:     {allocated_value / total_value:.2%}")


# ======================== Example 7: Covariance Methods ========================

def example_covariance_methods():
    """Compare different covariance estimation methods."""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Covariance Methods Comparison")
    print("=" * 60)

    prices = generate_sample_prices()
    opt = PyPortfolioOptOptimizer(prices)

    methods = ['sample_cov', 'ledoit_wolf', 'exp_cov']

    print("\nOptimal Weights by Covariance Method:")
    print(f"{'Ticker':<8}", end="")
    for method in methods:
        print(f"{method:<18}", end="")
    print()

    print("-" * 60)

    results = {}
    for method in methods:
        weights = opt.optimize_max_sharpe(cov_method=method)
        results[method] = weights

    for ticker in prices.columns:
        print(f"{ticker:<8}", end="")
        for method in methods:
            weight = results[method][ticker]
            print(f"{weight:>16.2%}  ", end="")
        print()


# ======================== Main ========================

def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("PyPortfolioOpt Integration Examples")
    print("=" * 60)

    example_max_sharpe()
    example_min_volatility()
    example_with_constraints()
    example_black_litterman()
    example_efficient_frontier()
    example_discrete_allocation()
    example_covariance_methods()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
