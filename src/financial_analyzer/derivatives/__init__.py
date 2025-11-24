"""
Derivatives module.

Exports options pricing and trading functionality.
"""

from financial_analyzer.derivatives.options import (
    BlackScholesModel,
    BlackScholesResult,
    GreeksCalculator,
    Greeks,
    OptionsStrategy,
    OptionLeg,
)

__all__ = [
    "BlackScholesModel",
    "BlackScholesResult",
    "GreeksCalculator",
    "Greeks",
    "OptionsStrategy",
    "OptionLeg",
]
