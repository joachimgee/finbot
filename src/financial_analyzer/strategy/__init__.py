"""
Strategy package for signal fusion and ensemble allocation.

This package provides tools for combining multiple signals (sentiment, technical,
deep learning) into unified trading decisions and converting them into portfolio
allocations with proper risk management.
"""

from financial_analyzer.strategy.signal_fusion import SignalFusion
from financial_analyzer.strategy.ensemble_allocator import EnsembleAllocator

__all__ = ["SignalFusion", "EnsembleAllocator"]
