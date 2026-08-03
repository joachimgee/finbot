"""
DiscreteAllocation: Convert continuous portfolio weights to discrete shares.

Wraps PyPortfolioOpt's DiscreteAllocation for converting theoretical continuous
weights (e.g., 0.25) into executable integer share quantities (e.g., 42 shares).

Methods:
    - Greedy: Iteratively allocate remaining cash to assets with highest deficit
    - Linear Programming: Optimal integer allocation minimizing deviation from target weights

Author: FinBot
License: MIT
"""

import sys
import collections
from pathlib import Path
from typing import Dict, Optional, Tuple
from warnings import warn

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def _ensure_vendor_pypfopt_on_path() -> None:
    """Add vendor/PyPortfolioOpt to sys.path if not already present."""
    vendor_path = Path(__file__).parents[3] / "vendor" / "PyPortfolioOpt"
    if vendor_path.exists() and str(vendor_path) not in sys.path:
        sys.path.insert(0, str(vendor_path))
        logger.debug(f"Added {vendor_path} to sys.path for PyPortfolioOpt vendored import")


def get_latest_prices(
    prices: pd.DataFrame,
    tickers: Optional[list] = None
) -> pd.Series:
    """
    Extract latest prices from a DataFrame of price series.
    
    Args:
        prices: DataFrame with datetime index and ticker columns (Close prices)
        tickers: Optional list of tickers to filter. If None, use all columns
    
    Returns:
        Series mapping ticker → latest price
    
    Raises:
        ValueError: If prices DataFrame is empty or invalid
    
    Example:
        >>> prices = pd.DataFrame({
        ...     'AAPL': [150.0, 151.0, 152.0],
        ...     'MSFT': [300.0, 302.0, 305.0]
        ... })
        >>> latest = get_latest_prices(prices)
        >>> latest['AAPL']
        152.0
    """
    if prices.empty:
        raise ValueError("Prices DataFrame is empty")
    
    if tickers is not None:
        missing = set(tickers) - set(prices.columns)
        if missing:
            raise ValueError(f"Tickers not found in prices: {missing}")
        prices = prices[tickers]
    
    latest = prices.iloc[-1]
    
    # Validate no NaN prices
    if latest.isna().any():
        nan_tickers = latest[latest.isna()].index.tolist()
        raise ValueError(f"NaN prices for tickers: {nan_tickers}")
    
    return latest


class DiscreteAllocation:
    """
    Convert continuous portfolio weights into discrete share allocations.
    
    Supports both greedy (fast, approximate) and LP (optimal, slower) methods.
    Handles long-only and long-short portfolios.
    
    Attributes:
        weights: Dict mapping ticker → continuous weight (0.0 to 1.0)
        latest_prices: Series mapping ticker → latest price
        total_portfolio_value: Total cash available for allocation
        short_ratio: Fraction of portfolio for short positions (default 0.3)
        allocation: Dict mapping ticker → integer shares (set after calling greedy/lp)
    
    Example:
        >>> weights = {'AAPL': 0.5, 'MSFT': 0.3, 'GOOGL': 0.2}
        >>> prices = pd.Series({'AAPL': 150.0, 'MSFT': 300.0, 'GOOGL': 2800.0})
        >>> da = DiscreteAllocation(weights, prices, total_portfolio_value=100000)
        >>> allocation, leftover = da.greedy_portfolio()
        >>> allocation
        {'AAPL': 333, 'MSFT': 100, 'GOOGL': 7}
    """
    
    def __init__(
        self,
        weights: Dict[str, float],
        latest_prices: pd.Series,
        total_portfolio_value: float,
        short_ratio: float = 0.3
    ):
        """
        Initialize DiscreteAllocation.
        
        Args:
            weights: Dict mapping ticker → continuous weight (must sum to 1.0)
            latest_prices: Series mapping ticker → latest price
            total_portfolio_value: Total cash available
            short_ratio: Fraction of portfolio for shorts (0.0 to 1.0)
        
        Raises:
            ValueError: If weights invalid, prices missing, or total_value <= 0
        """
        if not weights:
            raise ValueError("Weights dict is empty")
        
        if total_portfolio_value <= 0:
            raise ValueError(f"Total portfolio value must be > 0, got {total_portfolio_value}")
        
        if not 0 <= short_ratio <= 1:
            raise ValueError(f"Short ratio must be in [0, 1], got {short_ratio}")
        
        # Validate all tickers have prices
        missing_prices = set(weights.keys()) - set(latest_prices.index)
        if missing_prices:
            raise ValueError(f"Missing prices for tickers: {missing_prices}")
        
        # Validate weights sum approximately to 1.0 (allow 1e-4 tolerance)
        weight_sum = sum(weights.values())
        if not np.isclose(weight_sum, 1.0, atol=1e-4):
            logger.warning(f"Weights sum to {weight_sum:.6f}, not 1.0. Normalizing.")
            weights = {t: w / weight_sum for t, w in weights.items()}
        
        self.weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        self.latest_prices = latest_prices
        self.total_portfolio_value = total_portfolio_value
        self.short_ratio = short_ratio
        self.allocation: Optional[Dict[str, int]] = None
    
    def _remove_zero_positions(self, allocation: Dict[str, int]) -> Dict[str, int]:
        """Remove tickers with zero shares from allocation."""
        return {t: shares for t, shares in allocation.items() if shares != 0}
    
    def _allocation_rmse_error(self, verbose: bool = False) -> float:
        """
        Calculate RMSE between actual allocation and target weights.
        
        Args:
            verbose: Print RMSE if True
        
        Returns:
            RMSE value (lower is better)
        """
        if self.allocation is None:
            raise ValueError("Must call greedy_portfolio() or lp_portfolio() first")
        
        # Calculate actual weights from allocation
        actual_values = {
            t: shares * self.latest_prices[t]
            for t, shares in self.allocation.items()
        }
        total_value = sum(actual_values.values())
        
        if total_value == 0:
            logger.warning("Total allocated value is 0, RMSE undefined")
            return np.inf
        
        actual_weights = {t: val / total_value for t, val in actual_values.items()}
        
        # Compare to target weights
        target_weights = dict(self.weights)
        all_tickers = set(target_weights.keys()) | set(actual_weights.keys())
        
        squared_errors = []
        for ticker in all_tickers:
            target = target_weights.get(ticker, 0.0)
            actual = actual_weights.get(ticker, 0.0)
            squared_errors.append((target - actual) ** 2)
        
        rmse = np.sqrt(np.mean(squared_errors))
        
        if verbose:
            print(f"RMSE between target and actual weights: {rmse:.6f}")
        
        return rmse
    
    def greedy_portfolio(
        self,
        reinvest: bool = False,
        verbose: bool = False
    ) -> Tuple[Dict[str, int], float]:
        """
        Greedy discrete allocation: iteratively buy shares with highest deficit.
        
        Two-round algorithm:
        1. First round: Buy floor(weight * portfolio_value / price) shares per asset
        2. Second round: Iteratively buy 1 share of asset with highest weight deficit
        
        Args:
            reinvest: If True, reinvest cash from shorts into longs
            verbose: Print allocation details
        
        Returns:
            Tuple of (allocation dict, leftover cash)
        
        Example:
            >>> da = DiscreteAllocation(weights, prices, 100000)
            >>> allocation, leftover = da.greedy_portfolio(verbose=True)
            Funds remaining: 234.56
            RMSE between target and actual weights: 0.002134
        """
        # Handle long-short portfolios recursively
        if any([w < 0 for _, w in self.weights]):
            longs = {t: w for t, w in self.weights if w >= 0}
            shorts = {t: -w for t, w in self.weights if w < 0}
            
            # Normalize to sum = 1.0
            long_total = sum(longs.values())
            short_total = sum(shorts.values())
            
            if long_total > 0:
                longs = {t: w / long_total for t, w in longs.items()}
            if short_total > 0:
                shorts = {t: w / short_total for t, w in shorts.items()}
            
            # Allocate sub-portfolios
            short_val = self.total_portfolio_value * self.short_ratio
            long_val = self.total_portfolio_value
            if reinvest:
                long_val += short_val
            
            if verbose:
                print("\nAllocating long sub-portfolio:")
            
            long_alloc, long_leftover = {}, 0.0
            if longs:
                da_long = DiscreteAllocation(
                    longs,
                    self.latest_prices[list(longs.keys())],
                    total_portfolio_value=long_val
                )
                long_alloc, long_leftover = da_long.greedy_portfolio(verbose=verbose)
            
            if verbose:
                print("\nAllocating short sub-portfolio:")
            
            short_alloc, short_leftover = {}, 0.0
            if shorts:
                da_short = DiscreteAllocation(
                    shorts,
                    self.latest_prices[list(shorts.keys())],
                    total_portfolio_value=short_val
                )
                short_alloc, short_leftover = da_short.greedy_portfolio(verbose=verbose)
                short_alloc = {t: -shares for t, shares in short_alloc.items()}
            
            # Combine
            self.allocation = long_alloc.copy()
            self.allocation.update(short_alloc)
            self.allocation = self._remove_zero_positions(self.allocation)
            
            return self.allocation, long_leftover + short_leftover
        
        # Long-only portfolio: two-round greedy allocation
        available_funds = self.total_portfolio_value
        shares_bought = []
        buy_prices = []
        
        # First round: buy floor(weight * value / price) shares
        for ticker, weight in self.weights:
            price = self.latest_prices[ticker]
            n_shares = int(weight * self.total_portfolio_value / price)
            cost = n_shares * price
            
            # Weights are all > 0, so rounding down ensures cost <= allocated funds
            assert cost <= available_funds, "Unexpectedly insufficient funds"
            
            available_funds -= cost
            shares_bought.append(n_shares)
            buy_prices.append(price)
        
        # Second round: iteratively buy 1 share of most deficient asset
        while available_funds > 0:
            # Current allocation weights
            current_values = np.array(buy_prices) * np.array(shares_bought)
            current_weights = current_values / current_values.sum() if current_values.sum() > 0 else np.zeros_like(current_values)
            
            # Target weights
            ideal_weights = np.array([w for _, w in self.weights])
            
            # Deficit (positive = under-allocated)
            deficit = ideal_weights - current_weights
            
            # Try to buy asset with highest deficit
            idx = np.argmax(deficit)
            ticker, weight = self.weights[idx]
            price = self.latest_prices[ticker]
            
            # If can't afford, find next affordable asset
            counter = 0
            while price > available_funds:
                deficit[idx] = 0  # exclude this asset
                idx = np.argmax(deficit)
                
                # Break if no assets affordable or max retries
                if deficit[idx] <= 0 or counter >= 10:
                    break
                
                ticker, weight = self.weights[idx]
                price = self.latest_prices[ticker]
                counter += 1
            
            # Exit if no affordable assets
            if deficit[idx] <= 0 or counter >= 10:
                break
            
            # Buy 1 share
            shares_bought[idx] += 1
            available_funds -= price
        
        # Build final allocation
        self.allocation = self._remove_zero_positions(
            collections.OrderedDict(zip([t for t, _ in self.weights], shares_bought))
        )
        
        if verbose:
            print(f"Funds remaining: {available_funds:.2f}")
            self._allocation_rmse_error(verbose=True)
        
        return self.allocation, available_funds
    
    def lp_portfolio(
        self,
        reinvest: bool = False,
        verbose: bool = False,
        solver: Optional[str] = None
    ) -> Tuple[Dict[str, int], float]:
        """
        Linear programming discrete allocation: optimal integer allocation.
        
        Formulates as MILP:
            minimize: sum(|w_i * V - x_i * p_i|) + leftover_cash
            subject to: x_i >= 0 (integer), sum(x_i * p_i) <= V
        
        Requires cvxpy with MIP solver (ECOS_BB, GLPK_MI, CBC, SCIP).
        
        Args:
            reinvest: If True, reinvest cash from shorts into longs
            verbose: Print allocation details
            solver: CVXPY solver name (default None uses cvxpy default)
        
        Returns:
            Tuple of (allocation dict, leftover cash)
        
        Raises:
            ImportError: If cvxpy not installed
            OptimizationError: If solver fails
        
        Example:
            >>> da = DiscreteAllocation(weights, prices, 100000)
            >>> allocation, leftover = da.lp_portfolio(solver='ECOS_BB')
        """
        # Import cvxpy (not in vendored PyPortfolioOpt, user must pip install)
        try:
            import cvxpy as cp
        except ImportError:
            raise ImportError(
                "cvxpy required for lp_portfolio(). Install with: pip install cvxpy"
            )
        
        # Check ECOS availability for default solver (backward compat)
        if solver is None:
            try:
                import ecos
                solver = "ECOS_BB"
                warn(
                    "Using ECOS_BB as default solver. In future versions, "
                    "cvxpy default will be used. Set solver='ECOS_BB' explicitly "
                    "to silence this warning.",
                    FutureWarning
                )
            except ImportError:
                pass  # Use cvxpy default (usually GLPK_MI or CBC)
        
        # Handle long-short portfolios recursively
        if any([w < 0 for _, w in self.weights]):
            longs = {t: w for t, w in self.weights if w >= 0}
            shorts = {t: -w for t, w in self.weights if w < 0}
            
            # Normalize
            long_total = sum(longs.values())
            short_total = sum(shorts.values())
            
            if long_total > 0:
                longs = {t: w / long_total for t, w in longs.items()}
            if short_total > 0:
                shorts = {t: w / short_total for t, w in shorts.items()}
            
            # Allocate sub-portfolios
            short_val = self.total_portfolio_value * self.short_ratio
            long_val = self.total_portfolio_value
            if reinvest:
                long_val += short_val
            
            if verbose:
                print("\nAllocating long sub-portfolio:")
            
            long_alloc, long_leftover = {}, 0.0
            if longs:
                da_long = DiscreteAllocation(
                    longs,
                    self.latest_prices[list(longs.keys())],
                    total_portfolio_value=long_val
                )
                long_alloc, long_leftover = da_long.lp_portfolio(solver=solver, verbose=verbose)
            
            if verbose:
                print("\nAllocating short sub-portfolio:")
            
            short_alloc, short_leftover = {}, 0.0
            if shorts:
                da_short = DiscreteAllocation(
                    shorts,
                    self.latest_prices[list(shorts.keys())],
                    total_portfolio_value=short_val
                )
                short_alloc, short_leftover = da_short.lp_portfolio(solver=solver, verbose=verbose)
                short_alloc = {t: -shares for t, shares in short_alloc.items()}
            
            # Combine
            self.allocation = long_alloc.copy()
            self.allocation.update(short_alloc)
            self.allocation = self._remove_zero_positions(self.allocation)
            
            return self.allocation, long_leftover + short_leftover
        
        # Long-only portfolio: MILP formulation
        tickers = [t for t, _ in self.weights]
        prices = np.array([self.latest_prices[t] for t in tickers])
        weights = np.array([w for _, w in self.weights])
        
        n = len(tickers)
        
        # Decision variables
        x = cp.Variable(n, integer=True)  # shares bought
        r = self.total_portfolio_value - prices.T @ x  # remaining cash
        
        # Deviation from target weights: |w_i * V - x_i * p_i|
        eta = weights * self.total_portfolio_value - cp.multiply(x, prices)
        u = cp.Variable(n)  # auxiliary for absolute value
        
        # Constraints
        constraints = [
            eta <= u,           # upper bound for abs value
            eta >= -u,          # lower bound for abs value
            x >= 0,             # no negative shares
            r >= 0              # no negative cash
        ]
        
        # Objective: minimize total deviation + leftover cash
        objective = cp.sum(u) + r
        
        # Solve
        problem = cp.Problem(cp.Minimize(objective), constraints)
        
        try:
            problem.solve(solver=solver)
        except Exception as e:
            logger.error(f"LP solver failed: {e}")
            raise ValueError(
                f"LP solver '{solver}' failed. Try greedy_portfolio() instead or "
                f"install a different solver (GLPK_MI, CBC, SCIP)."
            ) from e
        
        if problem.status not in {"optimal", "optimal_inaccurate"}:
            raise ValueError(
                f"LP optimization failed with status: {problem.status}. "
                f"Try greedy_portfolio() instead."
            )
        
        # Extract integer solution
        shares = np.rint(x.value).astype(int)
        # max(0, ...) : le solveur peut renvoyer un reliquat infinitésimalement
        # négatif (~-1e-11) par imprécision flottante, ce qui n'a pas de sens
        leftover = max(0.0, float(r.value))
        
        self.allocation = self._remove_zero_positions(
            collections.OrderedDict(zip(tickers, [int(s) for s in shares]))
        )
        
        if verbose:
            print(f"Funds remaining: {leftover:.2f}")
            self._allocation_rmse_error(verbose=True)
        
        return self.allocation, leftover


def allocate_discrete_portfolio(
    weights: Dict[str, float],
    prices: pd.DataFrame,
    total_cash: float,
    method: str = "greedy",
    short_ratio: float = 0.3,
    verbose: bool = False,
    **kwargs
) -> Tuple[Dict[str, int], float]:
    """
    Convenience function for discrete allocation.
    
    Args:
        weights: Dict mapping ticker → continuous weight
        prices: DataFrame with datetime index and ticker columns (Close prices)
        total_cash: Total cash available for allocation
        method: 'greedy' (fast) or 'lp' (optimal, requires cvxpy)
        short_ratio: Fraction of portfolio for shorts (0.0 to 1.0)
        verbose: Print allocation details
        **kwargs: Additional arguments for lp_portfolio (e.g., solver='ECOS_BB')
    
    Returns:
        Tuple of (allocation dict, leftover cash)
    
    Raises:
        ValueError: If method invalid or inputs malformed
        ImportError: If method='lp' and cvxpy not installed
    
    Example:
        >>> weights = {'AAPL': 0.5, 'MSFT': 0.5}
        >>> prices = pd.DataFrame({'AAPL': [150, 152], 'MSFT': [300, 305]})
        >>> allocation, leftover = allocate_discrete_portfolio(
        ...     weights, prices, total_cash=10000, method='greedy'
        ... )
        >>> allocation
        {'AAPL': 33, 'MSFT': 16}
    """
    if method not in ["greedy", "lp"]:
        raise ValueError(f"Method must be 'greedy' or 'lp', got '{method}'")
    
    # Extract latest prices
    latest_prices = get_latest_prices(prices, tickers=list(weights.keys()))
    
    # Create allocator
    da = DiscreteAllocation(
        weights=weights,
        latest_prices=latest_prices,
        total_portfolio_value=total_cash,
        short_ratio=short_ratio
    )
    
    # Allocate
    if method == "greedy":
        return da.greedy_portfolio(verbose=verbose)
    else:  # method == "lp"
        return da.lp_portfolio(verbose=verbose, **kwargs)
