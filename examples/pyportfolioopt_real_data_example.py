"""
PyPortfolioOpt Integration Example with Real Market Data.

Demonstrates:
- Using FinanceDatabase to fetch 100+ real tickers
- Basic max Sharpe optimization on large universe
- Min volatility optimization
- Black-Litterman with views
- Efficient frontier calculation
- Discrete allocation
- Constraint integration with sectors
- Performance comparison: 10 vs 50 vs 100+ assets
"""

import sys
import numpy as np
import pandas as pd
from typing import List, Dict

from financial_analyzer.portfolio_optimization import PyPortfolioOptOptimizer
from financial_analyzer.portfolio.constraints import PortfolioConstraints

# ======================== Fetch Real Market Data ========================

def fetch_real_tickers(max_tickers: int = 100, sector: str = "Technology") -> List[str]:
    """
    Fetch real tickers from FinanceDatabase.
    
    Parameters
    ----------
    max_tickers : int
        Maximum number of tickers to fetch.
    sector : str
        Sector filter (Technology, Healthcare, Finance, etc.)
    
    Returns
    -------
    List[str]
        List of ticker symbols.
    """
    try:
        from financedatabase import Equities
        
        print(f"🔍 Fetching {sector} tickers from FinanceDatabase...")
        equities = Equities()
        
        # Search for US equities in specified sector
        result = equities.search(
            country="United States",
            sector=sector,
        )
        
        if result.empty:
            print(f"⚠️  No tickers found for {sector}, using synthetic data")
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        
        tickers = list(result.index[:max_tickers])
        print(f"✅ Found {len(tickers)} tickers in {sector} sector")
        
        return tickers
        
    except ImportError:
        print("⚠️  FinanceDatabase not available, using synthetic data")
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    except Exception as e:
        print(f"⚠️  Error fetching tickers: {e}, using synthetic data")
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]


def fetch_market_data(tickers: List[str], use_real_data: bool = False) -> pd.DataFrame:
    """
    Fetch historical price data for tickers.
    
    Parameters
    ----------
    tickers : List[str]
        List of ticker symbols.
    use_real_data : bool
        If True, fetch from yfinance. If False, generate synthetic data.
    
    Returns
    -------
    pd.DataFrame
        Historical prices with DatetimeIndex.
    """
    if use_real_data:
        try:
            import yfinance as yf
            
            print(f"📊 Fetching real market data for {len(tickers)} tickers...")
            data = yf.download(
                tickers,
                period="1y",
                interval="1d",
                progress=False,
                group_by='ticker',
            )
            
            if len(tickers) == 1:
                prices = data['Close'].to_frame(tickers[0])
            else:
                prices = data['Close'] if 'Close' in data.columns else pd.DataFrame()
            
            # Drop tickers with insufficient data
            prices = prices.dropna(axis=1, thresh=len(prices) * 0.8)
            
            if prices.empty or len(prices.columns) < 5:
                print(f"⚠️  Insufficient real data, using synthetic data")
                return generate_synthetic_prices(tickers[:10])
            
            print(f"✅ Fetched {len(prices.columns)} tickers with {len(prices)} days")
            return prices
            
        except Exception as e:
            print(f"⚠️  Error fetching real data: {e}, using synthetic data")
            return generate_synthetic_prices(tickers[:10])
    else:
        return generate_synthetic_prices(tickers)


def generate_synthetic_prices(tickers: List[str], n_days: int = 252) -> pd.DataFrame:
    """Generate synthetic price data for tickers."""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=n_days, freq="D")
    n_assets = len(tickers)
    
    # Generate correlated returns with sector structure
    # Create block correlation for sector effects
    cov = np.eye(n_assets) * 0.0004
    
    # Add correlation within blocks of 10 assets (simulating sectors)
    block_size = 10
    for i in range(0, n_assets, block_size):
        block_end = min(i + block_size, n_assets)
        for j in range(i, block_end):
            for k in range(i, block_end):
                if j != k:
                    cov[j, k] = 0.0001
    
    returns = np.random.multivariate_normal(
        mean=[0.0008] * n_assets,
        cov=cov,
        size=n_days,
    )
    
    prices = pd.DataFrame(
        (1 + returns).cumprod(axis=0) * 100,
        index=dates,
        columns=tickers,
    )
    
    return prices


def get_sector_mapping(tickers: List[str]) -> Dict[str, str]:
    """
    Create sector mapping for tickers.
    
    For synthetic data, assigns sectors in blocks.
    For real data, could fetch from FinanceDatabase.
    """
    sectors = ["Tech", "Healthcare", "Finance", "Energy", "Consumer", "Industrial"]
    sector_size = max(1, len(tickers) // len(sectors))
    
    mapping = {}
    for i, ticker in enumerate(tickers):
        sector_idx = min(i // sector_size, len(sectors) - 1)
        mapping[ticker] = sectors[sector_idx]
    
    return mapping


# ======================== Example 1: Large Universe (100+ tickers) ========================

def example_large_universe():
    """Max Sharpe optimization with 100+ tickers from FinanceDatabase."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Large Universe Optimization (100+ tickers)")
    print("=" * 70)
    
    # Fetch real tickers
    tickers = fetch_real_tickers(max_tickers=100, sector="Technology")
    
    # Generate data (use use_real_data=True to fetch from yfinance)
    prices = fetch_market_data(tickers, use_real_data=False)
    
    print(f"\n📊 Portfolio Universe: {len(prices.columns)} assets")
    print(f"📅 Historical Period: {len(prices)} days")
    
    # Optimize
    opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)
    weights = opt.optimize_max_sharpe()
    
    # Show top 10 holdings
    top_10 = weights.nlargest(10)
    
    print("\nTop 10 Holdings (Max Sharpe):")
    for ticker, weight in top_10.items():
        print(f"  {ticker:>10}: {weight:>7.2%}")
    
    print(f"\nTotal Weight (Top 10): {top_10.sum():.2%}")
    print(f"Number of Holdings:    {(weights > 0.001).sum()}")
    print(f"Portfolio Sum:         {weights.sum():.4f}")


# ======================== Example 2: Sector Constraints (50 tickers) ========================

def example_sector_constraints():
    """Optimization with sector constraints on 50 tickers."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Sector Constraints (50 tickers)")
    print("=" * 70)
    
    # Fetch multi-sector tickers
    tech_tickers = fetch_real_tickers(max_tickers=20, sector="Technology")
    health_tickers = fetch_real_tickers(max_tickers=15, sector="Healthcare")
    finance_tickers = fetch_real_tickers(max_tickers=15, sector="Finance")
    
    all_tickers = tech_tickers + health_tickers + finance_tickers
    prices = fetch_market_data(all_tickers, use_real_data=False)
    
    print(f"\n📊 Portfolio: {len(prices.columns)} assets across 3 sectors")
    
    # Create sector mapping
    sector_mapping = {}
    for t in prices.columns:
        if t in tech_tickers:
            sector_mapping[t] = "Tech"
        elif t in health_tickers:
            sector_mapping[t] = "Healthcare"
        else:
            sector_mapping[t] = "Finance"
    
    # Setup constraints
    # Setup constraints (relaxed to avoid infeasibility with synthetic data)
    constraints = PortfolioConstraints(sector_mapping=sector_mapping)
    constraints.add_allocation_limits(min_weight=0.0, max_weight=0.20)
    constraints.sector_limits = {
        "Tech": 0.60,
        "Healthcare": 0.40,
        "Finance": 0.40,
    }
    constraints.long_only_enabled = True
    
    # Optimize
    opt = PyPortfolioOptOptimizer(prices)
    weights = opt.optimize_max_sharpe(constraints=constraints)
    
    # Analyze by sector
    sector_weights = {}
    for sector in ["Tech", "Healthcare", "Finance"]:
        sector_tickers = [t for t, s in sector_mapping.items() if s == sector and t in weights.index]
        sector_weights[sector] = weights[sector_tickers].sum()
    
    print("\nSector Allocations:")
    for sector, weight in sector_weights.items():
        limit = constraints.sector_limits[sector]
        status = "✅" if weight <= limit + 1e-4 else "❌"
        print(f"  {sector:<12}: {weight:>6.2%} (limit: {limit:.0%}) {status}")
    
    print(f"\nNumber of Holdings: {(weights > 0.001).sum()}")
    print(f"Max Weight:         {weights.max():.2%}")


# ======================== Example 3: Performance Comparison ========================

def example_performance_comparison():
    """Compare optimization performance: 10 vs 50 vs 100 assets."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Performance Comparison (10 vs 50 vs 100 assets)")
    print("=" * 70)
    
    import time
    
    tickers_100 = fetch_real_tickers(max_tickers=100, sector="Technology")
    
    for n_assets in [10, 50, 100]:
        tickers = tickers_100[:n_assets]
        prices = generate_synthetic_prices(tickers)
        
        print(f"\n{'─' * 70}")
        print(f"🔬 Testing with {n_assets} assets:")
        
        opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)
        
        # Max Sharpe
        start = time.time()
        weights_sharpe = opt.optimize_max_sharpe()
        time_sharpe = time.time() - start
        
        # Min Vol
        start = time.time()
        weights_minvol = opt.optimize_min_volatility()
        time_minvol = time.time() - start
        
        print(f"  Max Sharpe:     {time_sharpe:.3f}s | {(weights_sharpe > 0.001).sum()} holdings")
        print(f"  Min Volatility: {time_minvol:.3f}s | {(weights_minvol > 0.001).sum()} holdings")


# ======================== Example 4: Efficient Frontier (30 tickers) ========================

def example_efficient_frontier():
    """Calculate efficient frontier for 30 tickers."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Efficient Frontier (30 tickers)")
    print("=" * 70)
    
    tickers = fetch_real_tickers(max_tickers=30, sector="Technology")
    prices = fetch_market_data(tickers, use_real_data=False)
    
    print(f"\n📊 Calculating frontier for {len(prices.columns)} assets...")
    
    opt = PyPortfolioOptOptimizer(prices)
    frontier = opt.calculate_efficient_frontier(num_portfolios=50)
    
    print(f"\n✅ Computed {len(frontier)} portfolios on efficient frontier")
    
    # Show frontier statistics
    print("\nFrontier Statistics:")
    print(f"  Min Return:       {frontier['return'].min():.2%}")
    print(f"  Max Return:       {frontier['return'].max():.2%}")
    print(f"  Min Volatility:   {frontier['volatility'].min():.2%}")
    print(f"  Max Volatility:   {frontier['volatility'].max():.2%}")
    print(f"  Max Sharpe Ratio: {frontier['sharpe'].max():.2f}")
    
    # Find optimal portfolios
    max_sharpe_idx = frontier['sharpe'].idxmax()
    min_vol_idx = frontier['volatility'].idxmin()
    
    print("\nOptimal Portfolios:")
    print(f"  Max Sharpe: Return={frontier.loc[max_sharpe_idx, 'return']:.2%}, "
          f"Vol={frontier.loc[max_sharpe_idx, 'volatility']:.2%}, "
          f"Sharpe={frontier.loc[max_sharpe_idx, 'sharpe']:.2f}")
    print(f"  Min Vol:    Return={frontier.loc[min_vol_idx, 'return']:.2%}, "
          f"Vol={frontier.loc[min_vol_idx, 'volatility']:.2%}, "
          f"Sharpe={frontier.loc[min_vol_idx, 'sharpe']:.2f}")


# ======================== Example 5: Black-Litterman (20 tickers) ========================

def example_black_litterman():
    """Black-Litterman with views on 20 tech stocks."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Black-Litterman (20 tickers)")
    print("=" * 70)
    
    tickers = fetch_real_tickers(max_tickers=20, sector="Technology")
    prices = fetch_market_data(tickers, use_real_data=False)
    
    print(f"\n📊 Portfolio: {len(prices.columns)} tech stocks")
    
    # Select 3 tickers for views
    view_tickers = list(prices.columns[:3])
    views = {
        view_tickers[0]: 0.18,  # Bullish: 18% expected
        view_tickers[1]: 0.12,  # Moderate: 12% expected
        view_tickers[2]: 0.08,  # Conservative: 8% expected
    }
    
    confidences = {
        view_tickers[0]: 0.9,   # High confidence
        view_tickers[1]: 0.7,   # Medium confidence
        view_tickers[2]: 0.5,   # Low confidence
    }
    
    # Market caps (equal for synthetic data)
    market_caps = {t: 1e12 for t in prices.columns}
    
    opt = PyPortfolioOptOptimizer(prices, risk_free_rate=0.02)
    weights = opt.optimize_black_litterman(
        views=views,
        view_confidences=confidences,
        market_caps=market_caps,
        risk_aversion=1.0,
    )
    
    print("\nInvestor Views:")
    for ticker in view_tickers:
        print(f"  {ticker:>10}: {views[ticker]:.0%} return (confidence: {confidences[ticker]:.0%})")
    
    print("\nTop 10 Holdings (Black-Litterman):")
    top_10 = weights.nlargest(10)
    for ticker, weight in top_10.items():
        view_status = "📈" if ticker in views else "  "
        print(f"  {view_status} {ticker:>10}: {weight:>7.2%}")


# ======================== Example 6: Discrete Allocation (15 tickers) ========================

def example_discrete_allocation():
    """Discrete allocation with $500k capital."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Discrete Allocation ($500k capital)")
    print("=" * 70)
    
    tickers = fetch_real_tickers(max_tickers=15, sector="Technology")
    prices = fetch_market_data(tickers, use_real_data=False)
    
    print(f"\n📊 Portfolio: {len(prices.columns)} assets")
    
    opt = PyPortfolioOptOptimizer(prices)
    weights = opt.optimize_max_sharpe()
    
    # Discrete allocation
    total_value = 500_000.0
    allocation, leftover = opt.discrete_allocation(weights, total_portfolio_value=total_value)
    
    print(f"\nDiscrete Allocation (${total_value:,.0f}):")
    print(f"{'Ticker':<12} {'Shares':>8} {'Price':>10} {'Value':>12} {'Weight':>8}")
    print("─" * 60)
    
    latest_prices = prices.iloc[-1]
    for ticker in sorted(allocation.keys(), key=lambda t: allocation[t] * latest_prices[t], reverse=True):
        shares = allocation[ticker]
        price = latest_prices[ticker]
        value = shares * price
        weight = value / total_value
        print(f"{ticker:<12} {shares:>8}  ${price:>9.2f}  ${value:>11,.2f}  {weight:>7.2%}")
    
    allocated_value = sum(allocation[t] * latest_prices[t] for t in allocation)
    print("─" * 60)
    print(f"{'Total':<12} {sum(allocation.values()):>8}  {'':>10}  ${allocated_value:>11,.2f}  {allocated_value/total_value:>7.2%}")
    print(f"\nLeftover Cash:  ${leftover:>11,.2f}")
    print(f"Utilization:    {allocated_value / total_value:>12.2%}")


# ======================== Main ========================

def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("PyPortfolioOpt Integration Examples with Real Market Data")
    print("=" * 70)
    print("\nNote: Using synthetic data by default. Set use_real_data=True")
    print("      in fetch_market_data() to fetch from yfinance.")
    
    try:
        example_large_universe()
        example_sector_constraints()
        example_performance_comparison()
        example_efficient_frontier()
        example_black_litterman()
        example_discrete_allocation()
        
        print("\n" + "=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Examples interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
