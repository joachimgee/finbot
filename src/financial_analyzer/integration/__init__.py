"""Integration layer modules.

This package connects ML & sentiment signals to portfolio optimization,
backtesting workflows, and performance attribution.
"""

from financial_analyzer.integration.performance_attribution import (
    PerformanceAttributor,
    AttributionResult,
    AttributionMethod
)

__all__ = [
    'PerformanceAttributor',
    'AttributionResult',
    'AttributionMethod'
]
