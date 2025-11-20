"""
Combinatorial Purged CV - déjà inclus dans purged_cv.py.

Ce fichier sert de point d'entrée pour compatibilité avec l'import.
"""

from financial_analyzer.backtest_advanced.purged_cv import (
    CombinatorialPurgedCV,
    generate_backtest_paths
)

__all__ = ['CombinatorialPurgedCV', 'generate_backtest_paths']
