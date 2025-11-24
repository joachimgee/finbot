"""
Greeks Calculator for Black-Scholes Options.

Computes first and second-order sensitivities of option prices to underlying parameters:
- Delta (Δ): Sensitivity to spot price changes
- Gamma (Γ): Rate of change of Delta (convexity)
- Vega (ν): Sensitivity to volatility changes
- Theta (Θ): Sensitivity to time decay
- Rho (ρ): Sensitivity to interest rate changes

All Greeks computed using analytical derivatives of Black-Scholes formula.

Example:
    >>> from financial_analyzer.derivatives.options import GreeksCalculator
    >>> 
    >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
    >>> greeks = calc.compute_all()
    >>> print(f"Call Delta: {greeks.delta_call:.4f}")
    >>> print(f"Gamma: {greeks.gamma:.4f}")
    >>> print(f"Vega: {greeks.vega:.4f}")
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.stats import norm

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class Greeks:
    """
    Container for all Greeks.
    
    Attributes:
        delta_call: Call delta (0 to 1)
        delta_put: Put delta (-1 to 0)
        gamma: Gamma (same for call and put)
        vega: Vega (same for call and put, % per 1% vol change)
        theta_call: Call theta (typically negative, $ per day)
        theta_put: Put theta (typically negative, $ per day)
        rho_call: Call rho ($ per 1% rate change)
        rho_put: Put rho ($ per 1% rate change)
        vanna: Second-order: ∂²V/∂S∂σ
        charm: Second-order: ∂²V/∂S∂t (delta decay)
        vomma: Second-order: ∂²V/∂σ² (vega convexity)
    """

    delta_call: float
    delta_put: float
    gamma: float
    vega: float
    theta_call: float
    theta_put: float
    rho_call: float
    rho_put: float
    vanna: float
    charm: float
    vomma: float


class GreeksCalculator:
    """
    Calculate Greeks for Black-Scholes options.
    
    All Greeks use analytical derivatives (no numerical approximation).
    
    Args:
        S: Current stock price (spot)
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate (annualized)
        sigma: Volatility (annualized)
        q: Dividend yield (continuous, default: 0.0)
    
    Example:
        >>> calc = GreeksCalculator(S=100, K=105, T=0.5, r=0.05, sigma=0.25)
        >>> delta_call = calc.delta(option_type='call')
        >>> gamma = calc.gamma()
        >>> print(f"Delta: {delta_call:.4f}, Gamma: {gamma:.4f}")
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
        """Initialize Greeks calculator."""
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

        # Compute d1, d2, and cached values
        self.d1, self.d2 = self._compute_d1_d2()
        self.n_d1 = norm.pdf(self.d1)  # Standard normal PDF at d1
        self.N_d1 = norm.cdf(self.d1)  # Standard normal CDF at d1
        self.N_d2 = norm.cdf(self.d2)  # Standard normal CDF at d2

        logger.debug(
            f"GreeksCalculator initialized: S={S}, K={K}, T={T:.3f}, "
            f"r={r:.3%}, sigma={sigma:.3%}, q={q:.3%}"
        )

    def _compute_d1_d2(self) -> tuple[float, float]:
        """
        Compute d1 and d2.
        
        Returns:
            Tuple of (d1, d2)
        """
        if self.T == 0:
            return (np.inf if self.S > self.K else -np.inf, 0.0)

        if self.sigma == 0:
            return (np.inf if self.S > self.K else -np.inf, 0.0)

        d1 = (
            np.log(self.S / self.K)
            + (self.r - self.q + 0.5 * self.sigma**2) * self.T
        ) / (self.sigma * np.sqrt(self.T))

        d2 = d1 - self.sigma * np.sqrt(self.T)

        return d1, d2

    def delta(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate option delta.
        
        Delta measures sensitivity to spot price changes:
        - Call delta: ∂C/∂S = e^(-q*T) * N(d1)
        - Put delta: ∂P/∂S = -e^(-q*T) * N(-d1) = e^(-q*T) * (N(d1) - 1)
        
        Args:
            option_type: 'call' or 'put'
        
        Returns:
            Delta (call: 0 to 1, put: -1 to 0)
        
        Example:
            >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> delta_call = calc.delta('call')
            >>> print(f"Call delta: {delta_call:.4f}")
        """
        if self.T == 0:
            # At expiration: delta = 1 if ITM, 0 if OTM
            if option_type == "call":
                return 1.0 if self.S > self.K else 0.0
            else:
                return -1.0 if self.K > self.S else 0.0

        if option_type == "call":
            delta = np.exp(-self.q * self.T) * self.N_d1
        else:
            delta = -np.exp(-self.q * self.T) * norm.cdf(-self.d1)

        return float(delta)

    def gamma(self) -> float:
        """
        Calculate gamma (same for call and put).
        
        Gamma measures convexity (rate of change of delta):
        Γ = ∂²V/∂S² = e^(-q*T) * n(d1) / (S * sigma * sqrt(T))
        
        Returns:
            Gamma (always non-negative)
        
        Example:
            >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> gamma = calc.gamma()
            >>> print(f"Gamma: {gamma:.6f}")
        """
        if self.T == 0 or self.sigma == 0:
            return 0.0

        gamma = (
            np.exp(-self.q * self.T) * self.n_d1 / (self.S * self.sigma * np.sqrt(self.T))
        )

        return float(gamma)

    def vega(self) -> float:
        """
        Calculate vega (same for call and put).
        
        Vega measures sensitivity to volatility changes:
        ν = ∂V/∂σ = S * e^(-q*T) * n(d1) * sqrt(T)
        
        Returns:
            Vega (price change per 1% volatility change)
        
        Note:
            Vega is NOT a Greek letter (it's Latin).
            Sometimes denoted as κ (kappa).
        
        Example:
            >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> vega = calc.vega()
            >>> print(f"Vega: ${vega:.2f} per 1% vol")
        """
        if self.T == 0:
            return 0.0

        # Vega per 1% volatility change (divide by 100)
        vega = self.S * np.exp(-self.q * self.T) * self.n_d1 * np.sqrt(self.T) / 100

        return float(vega)

    def theta(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate theta (time decay).
        
        Theta measures sensitivity to time passage:
        - Call theta: ∂C/∂t
        - Put theta: ∂P/∂t
        
        Typically negative (options lose value as expiration approaches).
        
        Args:
            option_type: 'call' or 'put'
        
        Returns:
            Theta (price change per day, typically negative)
        
        Example:
            >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> theta_call = calc.theta('call')
            >>> print(f"Call theta: ${theta_call:.4f}/day")
        """
        if self.T == 0:
            return 0.0

        # Common term
        term1 = -(
            self.S * np.exp(-self.q * self.T) * self.n_d1 * self.sigma
        ) / (2 * np.sqrt(self.T))

        if option_type == "call":
            term2 = self.q * self.S * np.exp(-self.q * self.T) * self.N_d1
            term3 = -self.r * self.K * np.exp(-self.r * self.T) * self.N_d2
            theta = term1 - term2 + term3
        else:
            term2 = -self.q * self.S * np.exp(-self.q * self.T) * norm.cdf(-self.d1)
            term3 = self.r * self.K * np.exp(-self.r * self.T) * norm.cdf(-self.d2)
            theta = term1 + term2 + term3

        # Convert to per-day (divide by 365)
        theta_per_day = theta / 365

        return float(theta_per_day)

    def rho(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate rho (interest rate sensitivity).
        
        Rho measures sensitivity to risk-free rate changes:
        - Call rho: ∂C/∂r = K * T * e^(-r*T) * N(d2)
        - Put rho: ∂P/∂r = -K * T * e^(-r*T) * N(-d2)
        
        Args:
            option_type: 'call' or 'put'
        
        Returns:
            Rho (price change per 1% rate change)
        
        Example:
            >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> rho_call = calc.rho('call')
            >>> print(f"Call rho: ${rho_call:.4f} per 1% rate")
        """
        if self.T == 0:
            return 0.0

        if option_type == "call":
            rho = self.K * self.T * np.exp(-self.r * self.T) * self.N_d2
        else:
            rho = -self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(-self.d2)

        # Rho per 1% rate change (divide by 100)
        rho_per_percent = rho / 100

        return float(rho_per_percent)

    def vanna(self) -> float:
        """
        Calculate vanna (second-order Greek).
        
        Vanna = ∂²V/∂S∂σ = ∂Δ/∂σ = ∂ν/∂S
        
        Measures how delta changes with volatility (or vega with spot).
        
        Returns:
            Vanna
        
        Example:
            >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> vanna = calc.vanna()
        """
        if self.T == 0 or self.sigma == 0:
            return 0.0

        vanna = (
            -np.exp(-self.q * self.T)
            * self.n_d1
            * self.d2
            / (self.sigma * 100)
        )

        return float(vanna)

    def charm(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate charm (delta decay).
        
        Charm = ∂²V/∂S∂t = ∂Δ/∂t
        
        Measures how delta changes as time passes.
        
        Args:
            option_type: 'call' or 'put'
        
        Returns:
            Charm (delta change per day)
        """
        if self.T == 0 or self.sigma == 0:
            return 0.0

        term1 = (
            self.q * np.exp(-self.q * self.T) * self.N_d1
        )

        term2 = (
            np.exp(-self.q * self.T)
            * self.n_d1
            * (2 * (self.r - self.q) * self.T - self.d2 * self.sigma * np.sqrt(self.T))
            / (2 * self.T * self.sigma * np.sqrt(self.T))
        )

        if option_type == "call":
            charm = -term1 - term2
        else:
            charm = term1 - term2

        # Convert to per-day
        charm_per_day = charm / 365

        return float(charm_per_day)

    def vomma(self) -> float:
        """
        Calculate vomma (vega convexity).
        
        Vomma = ∂²V/∂σ² = ∂ν/∂σ
        
        Measures how vega changes with volatility.
        Also called volga or vega convexity.
        
        Returns:
            Vomma
        """
        if self.T == 0 or self.sigma == 0:
            return 0.0

        vomma = (
            self.S
            * np.exp(-self.q * self.T)
            * self.n_d1
            * np.sqrt(self.T)
            * self.d1
            * self.d2
            / (self.sigma * 10000)
        )

        return float(vomma)

    def compute_all(self) -> Greeks:
        """
        Compute all Greeks at once.
        
        Returns:
            Greeks dataclass with all first and second-order Greeks
        
        Example:
            >>> calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            >>> greeks = calc.compute_all()
            >>> print(f"Delta call: {greeks.delta_call:.4f}")
            >>> print(f"Gamma: {greeks.gamma:.6f}")
            >>> print(f"Vega: ${greeks.vega:.4f}")
        """
        return Greeks(
            delta_call=self.delta("call"),
            delta_put=self.delta("put"),
            gamma=self.gamma(),
            vega=self.vega(),
            theta_call=self.theta("call"),
            theta_put=self.theta("put"),
            rho_call=self.rho("call"),
            rho_put=self.rho("put"),
            vanna=self.vanna(),
            charm=self.charm("call"),  # Same for call/put (approximately)
            vomma=self.vomma(),
        )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"GreeksCalculator(S={self.S:.2f}, K={self.K:.2f}, T={self.T:.3f}, "
            f"r={self.r:.3%}, sigma={self.sigma:.3%}, q={self.q:.3%})"
        )
