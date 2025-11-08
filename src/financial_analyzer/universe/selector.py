"""
Universe module public API for selectors.

This small adapter preserves backward compatibility while exposing
`UniverseSelector` under the universe package namespace.

Source implementation currently resides in
`financial_analyzer.data.universe`.
"""

from __future__ import annotations

from financial_analyzer.data.universe import UniverseSelector

__all__ = ["UniverseSelector"]
