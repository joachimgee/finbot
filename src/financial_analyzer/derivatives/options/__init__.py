"""
Options Derivatives Module.

Provides options pricing, Greeks calculation, and strategy backtesting:
- BlackScholesModel: Analytical option pricing (call/put)
- BlackScholesResult: Pricing result container
- GreeksCalculator: Delta, Gamma, Vega, Theta, Rho
- Greeks: Greeks result container
- OptionsStrategy: Multi-leg strategies (straddle, butterfly, etc.)
- OptionLeg: Single option position
- OptionsBacktester: Strategy backtesting with P&L tracking (TODO)

Example:
    >>> from financial_analyzer.derivatives.options import BlackScholesModel, GreeksCalculator
    >>> 
    >>> # Price a call option
    >>> bs = BlackScholesModel(S=100, K=105, T=0.25, r=0.05, sigma=0.2)
    >>> call_price = bs.call_price()
    >>> print(f"Call price: ${call_price:.2f}")
    >>> 
    >>> # Compute Greeks
    >>> greeks = GreeksCalculator(S=100, K=105, T=0.25, r=0.05, sigma=0.2)
    >>> delta = greeks.delta('call')
    >>> print(f"Delta: {delta:.4f}")
"""

from .black_scholes import BlackScholesModel, BlackScholesResult
from .greeks import GreeksCalculator, Greeks
from .strategies import OptionsStrategy, OptionLeg

# OptionsBacktester not yet implemented
# from .backtest import OptionsBacktester

__all__ = [
    "BlackScholesModel",
    "BlackScholesResult",
    "GreeksCalculator",
    "Greeks",
    "OptionsStrategy",
    "OptionLeg",
    # "OptionsBacktester",
]

