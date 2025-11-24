"""
Black-Scholes Option Pricing Model.

Implements analytical formulas for European call and put options:
- Closed-form solutions (no Monte Carlo needed)
- Dividend support (continuous yield)
- Implied volatility calculation via Newton-Raphson
- Put-call parity validation

Model assumptions:
- European exercise (exercise only at expiration)
- No transaction costs or taxes
- Continuous trading
- Log-normal price distribution
- Constant volatility and risk-free rate

References:
    Black, F., & Scholes, M. (1973). The Pricing of Options and Corporate Liabilities.
    Journal of Political Economy, 81(3), 637-654.

Example:
    >>> from financial_analyzer.derivatives.options import BlackScholesModel
    >>> 
    >>> # ATM call option, 3 months to expiration
    >>> bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
    >>> call_price = bs.call_price()
    >>> put_price = bs.put_price()
    >>> 
    >>> print(f"Call: ${call_price:.2f}, Put: ${put_price:.2f}")
    >>> 
    >>> # With dividends
    >>> bs_div = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2, q=0.02)
    >>> call_div = bs_div.call_price()
"""

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from scipy.stats import norm
from scipy.optimize import newton

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class BlackScholesResult:
    """
    Result container for Black-Scholes pricing.
    
    Attributes:
        call_price: Call option price
        put_price: Put option price
        intrinsic_call: Intrinsic value of call (max(S-K, 0))
        intrinsic_put: Intrinsic value of put (max(K-S, 0))
        time_value_call: Time value of call (price - intrinsic)
        time_value_put: Time value of put (price - intrinsic)
        d1: Intermediate calculation d1
        d2: Intermediate calculation d2
    """

    call_price: float
    put_price: float
    intrinsic_call: float
    intrinsic_put: float
    time_value_call: float
    time_value_put: float
    d1: float
    d2: float


class BlackScholesModel:
    """
    Black-Scholes option pricing model.
    
    Computes European call and put option prices using closed-form formulas.
    Supports continuous dividend yield.
    
    Args:
        S: Current stock price (spot)
        K: Strike price
        T: Time to expiration (years, e.g., 0.25 = 3 months)
        r: Risk-free rate (annualized, e.g., 0.05 = 5%)
        sigma: Volatility (annualized, e.g., 0.2 = 20%)
        q: Dividend yield (continuous, default: 0.0)
    
    Raises:
        ValueError: If parameters are invalid (negative prices, time, volatility)
    
    Example:
        >>> bs = BlackScholesModel(S=100, K=105, T=0.5, r=0.05, sigma=0.25)
        >>> call = bs.call_price()
        >>> put = bs.put_price()
        >>> print(f"Call: ${call:.2f}, Put: ${put:.2f}")
        >>> 
        >>> # Compute both at once
        >>> result = bs.price()
        >>> print(f"Call intrinsic: ${result.intrinsic_call:.2f}")
    """

    def __init__(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float = 0.0,
    ):
        """Initialize Black-Scholes model with option parameters."""
        # Validate inputs
        if S <= 0:
            raise ValueError(f"Stock price must be positive, got S={S}")
        if K <= 0:
            raise ValueError(f"Strike price must be positive, got K={K}")
        if T < 0:
            raise ValueError(f"Time to expiration must be non-negative, got T={T}")
        if sigma < 0:
            raise ValueError(f"Volatility must be non-negative, got sigma={sigma}")

        self.S = S
        self.K = K
        self.T = T
        self.r = r
        self.sigma = sigma
        self.q = q

        # Compute d1 and d2
        self.d1, self.d2 = self._compute_d1_d2()

        logger.debug(
            f"BlackScholes initialized: S={S}, K={K}, T={T:.3f}, r={r:.3%}, "
            f"sigma={sigma:.3%}, q={q:.3%}"
        )

    def _compute_d1_d2(self) -> tuple[float, float]:
        """
        Compute intermediate values d1 and d2.
        
        d1 = [ln(S/K) + (r - q + sigma²/2) * T] / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
        
        Returns:
            Tuple of (d1, d2)
        """
        if self.T == 0:
            # At expiration, option is either ITM or OTM
            # d1, d2 not used directly, but return sensible values
            return (np.inf if self.S > self.K else -np.inf, 0.0)

        if self.sigma == 0:
            # Zero volatility: option value is intrinsic value
            return (np.inf if self.S > self.K else -np.inf, 0.0)

        d1 = (
            np.log(self.S / self.K)
            + (self.r - self.q + 0.5 * self.sigma**2) * self.T
        ) / (self.sigma * np.sqrt(self.T))

        d2 = d1 - self.sigma * np.sqrt(self.T)

        return d1, d2

    def call_price(self) -> float:
        """
        Calculate European call option price.
        
        C = S * e^(-q*T) * N(d1) - K * e^(-r*T) * N(d2)
        
        Returns:
            Call option price
        
        Example:
            >>> bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> call = bs.call_price()
            >>> print(f"${call:.2f}")
        """
        if self.T == 0:
            # At expiration: intrinsic value
            return max(self.S - self.K, 0.0)

        call = self.S * np.exp(-self.q * self.T) * norm.cdf(self.d1) - self.K * np.exp(
            -self.r * self.T
        ) * norm.cdf(self.d2)

        return float(call)

    def put_price(self) -> float:
        """
        Calculate European put option price.
        
        P = K * e^(-r*T) * N(-d2) - S * e^(-q*T) * N(-d1)
        
        Returns:
            Put option price
        
        Example:
            >>> bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> put = bs.put_price()
            >>> print(f"${put:.2f}")
        """
        if self.T == 0:
            # At expiration: intrinsic value
            return max(self.K - self.S, 0.0)

        put = self.K * np.exp(-self.r * self.T) * norm.cdf(-self.d2) - self.S * np.exp(
            -self.q * self.T
        ) * norm.cdf(-self.d1)

        return float(put)

    def price(self) -> BlackScholesResult:
        """
        Calculate both call and put prices with additional metrics.
        
        Returns:
            BlackScholesResult with call/put prices, intrinsic values, time values
        
        Example:
            >>> bs = BlackScholesModel(S=100, K=105, T=0.25, r=0.05, sigma=0.2)
            >>> result = bs.price()
            >>> print(f"Call: ${result.call_price:.2f}")
            >>> print(f"Call time value: ${result.time_value_call:.2f}")
        """
        call = self.call_price()
        put = self.put_price()

        # Intrinsic values
        intrinsic_call = max(self.S - self.K, 0.0)
        intrinsic_put = max(self.K - self.S, 0.0)

        # Time values (extrinsic value)
        time_value_call = call - intrinsic_call
        time_value_put = put - intrinsic_put

        return BlackScholesResult(
            call_price=call,
            put_price=put,
            intrinsic_call=intrinsic_call,
            intrinsic_put=intrinsic_put,
            time_value_call=time_value_call,
            time_value_put=time_value_put,
            d1=self.d1,
            d2=self.d2,
        )

    def verify_put_call_parity(self, tolerance: float = 1e-6) -> bool:
        """
        Verify put-call parity holds.
        
        Put-call parity: C - P = S * e^(-q*T) - K * e^(-r*T)
        
        Args:
            tolerance: Acceptable deviation (default: 1e-6)
        
        Returns:
            True if parity holds within tolerance
        
        Example:
            >>> bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> assert bs.verify_put_call_parity()
        """
        call = self.call_price()
        put = self.put_price()

        lhs = call - put
        rhs = self.S * np.exp(-self.q * self.T) - self.K * np.exp(-self.r * self.T)

        diff = abs(lhs - rhs)
        parity_holds = diff < tolerance

        if not parity_holds:
            logger.warning(
                f"Put-call parity violated: |{lhs:.6f} - {rhs:.6f}| = {diff:.6f} > {tolerance}"
            )

        return parity_holds

    def implied_volatility(
        self,
        market_price: float,
        option_type: Literal["call", "put"] = "call",
        initial_guess: float = 0.3,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> Optional[float]:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Finds volatility that makes model price equal to market price.
        
        Args:
            market_price: Observed market price of option
            option_type: 'call' or 'put'
            initial_guess: Starting volatility guess (default: 0.3 = 30%)
            max_iterations: Maximum Newton-Raphson iterations
            tolerance: Convergence tolerance
        
        Returns:
            Implied volatility (annualized), or None if convergence fails
        
        Example:
            >>> bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> market_call = 5.5
            >>> iv = bs.implied_volatility(market_call, option_type='call')
            >>> print(f"Implied vol: {iv:.2%}")
        """
        if market_price <= 0:
            logger.warning(f"Market price must be positive: {market_price}")
            return None

        # Check if market price is arbitrage-free
        intrinsic = max(self.S - self.K, 0.0) if option_type == "call" else max(self.K - self.S, 0.0)
        if market_price < intrinsic:
            logger.warning(
                f"Market price {market_price:.4f} < intrinsic {intrinsic:.4f} (arbitrage)"
            )
            return None

        def objective(sigma_trial: float) -> float:
            """Difference between model price and market price."""
            try:
                bs_trial = BlackScholesModel(
                    S=self.S, K=self.K, T=self.T, r=self.r, sigma=sigma_trial, q=self.q
                )
                model_price = (
                    bs_trial.call_price() if option_type == "call" else bs_trial.put_price()
                )
                return model_price - market_price
            except Exception:
                return np.inf

        try:
            implied_vol = newton(
                objective,
                x0=initial_guess,
                maxiter=max_iterations,
                tol=tolerance,
            )

            # Validate result
            if implied_vol < 0 or implied_vol > 5.0:  # Sanity check (>500% vol is unrealistic)
                logger.warning(f"Implied vol {implied_vol:.2%} outside reasonable range")
                return None

            logger.debug(f"Implied volatility converged: {implied_vol:.4%}")
            return float(implied_vol)

        except Exception as e:
            logger.warning(f"Implied volatility failed to converge: {e}")
            return None

    def moneyness(self) -> float:
        """
        Calculate option moneyness.
        
        Moneyness = S / K
        - > 1.0: In-the-money (ITM) for call, OTM for put
        - = 1.0: At-the-money (ATM)
        - < 1.0: Out-of-the-money (OTM) for call, ITM for put
        
        Returns:
            Moneyness ratio
        
        Example:
            >>> bs = BlackScholesModel(S=105, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> m = bs.moneyness()
            >>> print(f"Moneyness: {m:.2f} (5% ITM call)")
        """
        return self.S / self.K

    def is_itm(self, option_type: Literal["call", "put"]) -> bool:
        """
        Check if option is in-the-money.
        
        Args:
            option_type: 'call' or 'put'
        
        Returns:
            True if ITM
        """
        if option_type == "call":
            return self.S > self.K
        else:
            return self.K > self.S

    def is_atm(self, tolerance: float = 0.01) -> bool:
        """
        Check if option is at-the-money.
        
        Args:
            tolerance: Percentage tolerance (default: 0.01 = 1%)
        
        Returns:
            True if ATM within tolerance
        """
        return abs(self.S - self.K) / self.K < tolerance

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"BlackScholesModel(S={self.S:.2f}, K={self.K:.2f}, T={self.T:.3f}, "
            f"r={self.r:.3%}, sigma={self.sigma:.3%}, q={self.q:.3%})"
        )
