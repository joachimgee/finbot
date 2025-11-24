"""Integration layer modules.

This package connects ML & sentiment signals to portfolio optimization,
backtesting workflows, and performance attribution.

Includes SignalFusionEngine for multi-source signal aggregation.
"""

from financial_analyzer.integration.performance_attribution import (
    PerformanceAttributor,
    AttributionResult,
    AttributionMethod
)
from financial_analyzer.integration.signal_fusion_engine import (
    SignalFusionEngine,
    SignalComponent,
    FusedSignal
)

__all__ = [
    'PerformanceAttributor',
    'AttributionResult',
    'AttributionMethod',
    'SignalFusionEngine',
    'SignalComponent',
    'FusedSignal',
]
