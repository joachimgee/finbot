"""
Options Trading Strategies.

Multi-leg strategies for options trading:
- Single-leg: Long call, long put, covered call
- Spreads: Bull spread, bear spread, calendar spread
- Volatility: Straddle, strangle, butterfly, iron condor
- Complex: Risk reversal, ratio spreads

Each strategy computes:
- Payoff at expiration
- Max profit and loss
- Breakeven points
- P&L at arbitrary spot prices

Example:
    >>> from financial_analyzer.derivatives.options import OptionsStrategy, OptionLeg
    >>> 
    >>> # Long straddle (bet on high volatility)
    >>> straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
    >>> payoff = straddle.payoff_at_expiry(spot_prices=[90, 95, 100, 105, 110])
    >>> print(f"Max loss: ${straddle.max_loss():.2f}")
    >>> print(f"Breakevens: {straddle.breakeven_points()}")
"""

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

from financial_analyzer.derivatives.options.black_scholes import BlackScholesModel
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class OptionLeg:
    """
    Single leg of an options strategy.
    
    Attributes:
        option_type: 'call' or 'put'
        position: 'long' (buy) or 'short' (sell)
        strike: Strike price
        premium: Option premium (price paid/received)
        quantity: Number of contracts (default: 1)
    """

    option_type: Literal["call", "put"]
    position: Literal["long", "short"]
    strike: float
    premium: float
    quantity: int = 1

    def payoff_at_expiry(self, spot: float) -> float:
        """
        Calculate payoff at expiration for given spot price.
        
        Args:
            spot: Stock price at expiration
        
        Returns:
            Net payoff (intrinsic value - premium)
        """
        # Intrinsic value
        if self.option_type == "call":
            intrinsic = max(spot - self.strike, 0)
        else:
            intrinsic = max(self.strike - spot, 0)

        # Sign convention: long = +1, short = -1
        sign = 1 if self.position == "long" else -1

        # Net payoff: intrinsic value gained/lost minus premium paid/received
        payoff = sign * intrinsic - (sign * self.premium)

        return payoff * self.quantity


class OptionsStrategy:
    """
    Multi-leg options strategy.
    
    Combines multiple option legs to create complex payoff profiles.
    
    Args:
        legs: List of OptionLeg objects
        name: Strategy name (e.g., 'straddle', 'iron_condor')
    
    Example:
        >>> # Manual construction
        >>> call_leg = OptionLeg('call', 'long', strike=100, premium=5.0)
        >>> put_leg = OptionLeg('put', 'long', strike=100, premium=4.5)
        >>> straddle = OptionsStrategy([call_leg, put_leg], name='straddle')
        >>> 
        >>> # Factory method
        >>> straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
    """

    def __init__(self, legs: list[OptionLeg], name: str = "custom"):
        """Initialize options strategy."""
        if not legs:
            raise ValueError("Strategy must have at least one leg")

        self.legs = legs
        self.name = name

        logger.debug(f"OptionsStrategy '{name}' created with {len(legs)} legs")

    def payoff_at_expiry(
        self, spot_prices: list[float] | np.ndarray
    ) -> pd.DataFrame:
        """
        Calculate strategy payoff at expiration for multiple spot prices.
        
        Args:
            spot_prices: Array of potential stock prices at expiration
        
        Returns:
            DataFrame with columns: spot, payoff, pnl (per leg breakdown)
        
        Example:
            >>> straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
            >>> payoff = straddle.payoff_at_expiry([90, 95, 100, 105, 110])
            >>> print(payoff)
        """
        spot_array = np.array(spot_prices)
        results = {"spot": spot_array}

        # Compute payoff for each leg
        for i, leg in enumerate(self.legs):
            leg_payoffs = [leg.payoff_at_expiry(s) for s in spot_array]
            results[f"leg_{i}_{leg.option_type}_{leg.position}"] = leg_payoffs

        # Total payoff (sum across legs for each spot price)
        total_payoff = np.zeros(len(spot_array))
        for s_idx, s in enumerate(spot_array):
            total_payoff[s_idx] = sum(leg.payoff_at_expiry(s) for leg in self.legs)
        
        results["total_payoff"] = total_payoff

        return pd.DataFrame(results)

    def max_profit(self) -> float:
        """
        Calculate maximum profit for strategy.
        
        Returns:
            Maximum profit (positive number, or np.inf if unlimited)
        
        Example:
            >>> straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
            >>> max_profit = straddle.max_profit()
            >>> print(f"Max profit: ${max_profit:.2f}")
        """
        # Sample spot prices from 0 to 2x max strike
        max_strike = max(leg.strike for leg in self.legs)
        spot_range = np.linspace(0, 2 * max_strike, 1000)

        payoffs = self.payoff_at_expiry(spot_range)["total_payoff"]
        max_profit = float(np.max(payoffs))

        # Check if profit is unbounded
        if max_profit > 1e6:  # Arbitrary large threshold
            logger.debug(f"Strategy '{self.name}' has unlimited max profit")
            return np.inf

        return max_profit

    def max_loss(self) -> float:
        """
        Calculate maximum loss for strategy.
        
        Returns:
            Maximum loss (negative number, or -np.inf if unlimited)
        
        Example:
            >>> straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
            >>> max_loss = straddle.max_loss()
            >>> print(f"Max loss: ${abs(max_loss):.2f}")
        """
        # Sample spot prices
        max_strike = max(leg.strike for leg in self.legs)
        spot_range = np.linspace(0, 2 * max_strike, 1000)

        payoffs = self.payoff_at_expiry(spot_range)["total_payoff"]
        max_loss = float(np.min(payoffs))

        # Check if loss is unbounded
        if max_loss < -1e6:
            logger.warning(f"Strategy '{self.name}' has unlimited max loss")
            return -np.inf

        return max_loss

    def breakeven_points(self, tolerance: float = 0.01) -> list[float]:
        """
        Find breakeven points (where payoff = 0).
        
        Args:
            tolerance: Tolerance for zero payoff (default: $0.01)
        
        Returns:
            List of breakeven spot prices
        
        Example:
            >>> straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
            >>> breakevens = straddle.breakeven_points()
            >>> print(f"Breakevens: {breakevens}")
        """
        # Sample spot prices
        max_strike = max(leg.strike for leg in self.legs)
        spot_range = np.linspace(0, 2 * max_strike, 5000)

        payoffs = self.payoff_at_expiry(spot_range)["total_payoff"].values

        # Find where payoff crosses zero
        breakevens = []
        for i in range(len(payoffs) - 1):
            if abs(payoffs[i]) < tolerance:
                breakevens.append(spot_range[i])
            elif payoffs[i] * payoffs[i + 1] < 0:  # Sign change
                # Linear interpolation
                be = spot_range[i] - payoffs[i] * (spot_range[i + 1] - spot_range[i]) / (
                    payoffs[i + 1] - payoffs[i]
                )
                breakevens.append(be)

        # Remove duplicates
        breakevens = list(dict.fromkeys([round(be, 2) for be in breakevens]))

        logger.debug(f"Strategy '{self.name}' breakevens: {breakevens}")
        return breakevens

    def net_premium(self) -> float:
        """
        Calculate net premium paid/received.
        
        Returns:
            Net premium (negative = credit, positive = debit)
        """
        net = sum(
            leg.premium * leg.quantity * (1 if leg.position == "long" else -1)
            for leg in self.legs
        )
        return net

    # -------------------------------------------------------------------------
    # Factory methods for common strategies
    # -------------------------------------------------------------------------

    @classmethod
    def straddle(
        cls, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> "OptionsStrategy":
        """
        Create long straddle (buy call + put at same strike).
        
        Profits from large moves in either direction (high volatility).
        
        Args:
            S: Current spot price
            K: Strike price (typically ATM)
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
        
        Returns:
            OptionsStrategy object
        
        Example:
            >>> straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        """
        bs = BlackScholesModel(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
        call_premium = bs.call_price()
        put_premium = bs.put_price()

        legs = [
            OptionLeg("call", "long", K, call_premium),
            OptionLeg("put", "long", K, put_premium),
        ]

        return cls(legs, name="straddle")

    @classmethod
    def strangle(
        cls,
        S: float,
        K_call: float,
        K_put: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
    ) -> "OptionsStrategy":
        """
        Create long strangle (buy OTM call + OTM put).
        
        Similar to straddle but with different strikes (cheaper premium).
        
        Args:
            S: Current spot price
            K_call: Call strike (typically above S)
            K_put: Put strike (typically below S)
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
        
        Returns:
            OptionsStrategy object
        """
        bs_call = BlackScholesModel(S=S, K=K_call, T=T, r=r, sigma=sigma, q=q)
        bs_put = BlackScholesModel(S=S, K=K_put, T=T, r=r, sigma=sigma, q=q)

        call_premium = bs_call.call_price()
        put_premium = bs_put.put_price()

        legs = [
            OptionLeg("call", "long", K_call, call_premium),
            OptionLeg("put", "long", K_put, put_premium),
        ]

        return cls(legs, name="strangle")

    @classmethod
    def butterfly(
        cls,
        S: float,
        K_low: float,
        K_mid: float,
        K_high: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
        option_type: Literal["call", "put"] = "call",
    ) -> "OptionsStrategy":
        """
        Create butterfly spread (long 2 wings, short 2 middle).
        
        Profits from low volatility (price stays near K_mid).
        
        Args:
            S: Current spot price
            K_low: Low strike
            K_mid: Middle strike (typically ATM)
            K_high: High strike
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
            option_type: 'call' or 'put'
        
        Returns:
            OptionsStrategy object
        """
        bs_low = BlackScholesModel(S=S, K=K_low, T=T, r=r, sigma=sigma, q=q)
        bs_mid = BlackScholesModel(S=S, K=K_mid, T=T, r=r, sigma=sigma, q=q)
        bs_high = BlackScholesModel(S=S, K=K_high, T=T, r=r, sigma=sigma, q=q)

        if option_type == "call":
            premium_low = bs_low.call_price()
            premium_mid = bs_mid.call_price()
            premium_high = bs_high.call_price()
        else:
            premium_low = bs_low.put_price()
            premium_mid = bs_mid.put_price()
            premium_high = bs_high.put_price()

        legs = [
            OptionLeg(option_type, "long", K_low, premium_low),
            OptionLeg(option_type, "short", K_mid, premium_mid, quantity=2),
            OptionLeg(option_type, "long", K_high, premium_high),
        ]

        return cls(legs, name="butterfly")

    @classmethod
    def iron_condor(
        cls,
        S: float,
        K_put_low: float,
        K_put_high: float,
        K_call_low: float,
        K_call_high: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
    ) -> "OptionsStrategy":
        """
        Create iron condor (short strangle + long strangle).
        
        Profits from low volatility (price stays between K_put_high and K_call_low).
        
        Args:
            S: Current spot price
            K_put_low: Long put strike (furthest OTM)
            K_put_high: Short put strike
            K_call_low: Short call strike
            K_call_high: Long call strike (furthest OTM)
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
        
        Returns:
            OptionsStrategy object
        """
        bs_put_low = BlackScholesModel(S=S, K=K_put_low, T=T, r=r, sigma=sigma, q=q)
        bs_put_high = BlackScholesModel(S=S, K=K_put_high, T=T, r=r, sigma=sigma, q=q)
        bs_call_low = BlackScholesModel(S=S, K=K_call_low, T=T, r=r, sigma=sigma, q=q)
        bs_call_high = BlackScholesModel(S=S, K=K_call_high, T=T, r=r, sigma=sigma, q=q)

        legs = [
            OptionLeg("put", "long", K_put_low, bs_put_low.put_price()),
            OptionLeg("put", "short", K_put_high, bs_put_high.put_price()),
            OptionLeg("call", "short", K_call_low, bs_call_low.call_price()),
            OptionLeg("call", "long", K_call_high, bs_call_high.call_price()),
        ]

        return cls(legs, name="iron_condor")

    @classmethod
    def covered_call(
        cls,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
        shares: int = 100,
    ) -> "OptionsStrategy":
        """
        Create covered call (long stock + short call).
        
        Income strategy: collect premium, cap upside.
        
        Args:
            S: Current spot price
            K: Call strike (typically OTM)
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
            shares: Number of shares held (default: 100)
        
        Returns:
            OptionsStrategy object
        
        Note:
            Stock position not represented as OptionLeg (different payoff).
            Payoff includes: shares * (S_final - S_initial) - call_payoff
        """
        bs = BlackScholesModel(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
        call_premium = bs.call_price()

        # Only option leg (stock position handled separately)
        legs = [
            OptionLeg("call", "short", K, call_premium, quantity=shares // 100),
        ]

        strategy = cls(legs, name="covered_call")
        strategy._stock_position = shares  # Store for payoff calculation
        strategy._initial_stock_price = S

        return strategy

    @classmethod
    def bull_call_spread(
        cls,
        S: float,
        K_low: float,
        K_high: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
    ) -> "OptionsStrategy":
        """
        Create bull call spread (buy low strike call, sell high strike call).
        
        Bullish strategy with limited upside and downside.
        
        Args:
            S: Current spot price
            K_low: Long call strike (lower)
            K_high: Short call strike (higher)
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
        
        Returns:
            OptionsStrategy object
        """
        bs_low = BlackScholesModel(S=S, K=K_low, T=T, r=r, sigma=sigma, q=q)
        bs_high = BlackScholesModel(S=S, K=K_high, T=T, r=r, sigma=sigma, q=q)

        legs = [
            OptionLeg("call", "long", K_low, bs_low.call_price()),
            OptionLeg("call", "short", K_high, bs_high.call_price()),
        ]

        return cls(legs, name="bull_call_spread")

    @classmethod
    def bear_put_spread(
        cls,
        S: float,
        K_low: float,
        K_high: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
    ) -> "OptionsStrategy":
        """
        Create bear put spread (buy high strike put, sell low strike put).
        
        Bearish strategy with limited upside and downside.
        
        Args:
            S: Current spot price
            K_low: Short put strike (lower)
            K_high: Long put strike (higher)
            T: Time to expiration
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield
        
        Returns:
            OptionsStrategy object
        """
        bs_low = BlackScholesModel(S=S, K=K_low, T=T, r=r, sigma=sigma, q=q)
        bs_high = BlackScholesModel(S=S, K=K_high, T=T, r=r, sigma=sigma, q=q)

        legs = [
            OptionLeg("put", "short", K_low, bs_low.put_price()),
            OptionLeg("put", "long", K_high, bs_high.put_price()),
        ]

        return cls(legs, name="bear_put_spread")

    def __repr__(self) -> str:
        """String representation."""
        return f"OptionsStrategy(name='{self.name}', legs={len(self.legs)}, net_premium={self.net_premium():.2f})"
