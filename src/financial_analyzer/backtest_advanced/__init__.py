"""
Advanced Backtesting Module.

Modules avancés pour backtesting robuste :
- Walk-forward analysis (rolling/expanding windows)
- Purged K-Fold cross-validation (time-series aware)
- Combinatorial purged CV (path-dependent testing)
- Meta-labeling (ML on signals, bet sizing)
"""

from financial_analyzer.backtest_advanced.walk_forward import (
    WalkForwardAnalyzer,
    walk_forward_optimize
)
from financial_analyzer.backtest_advanced.purged_cv import (
    PurgedKFold,
    purged_kfold_split
)
from financial_analyzer.backtest_advanced.combinatorial_cv import (
    CombinatorialPurgedCV,
    generate_backtest_paths
)
from financial_analyzer.backtest_advanced.meta_labeling import (
    MetaLabeler,
    create_meta_labels
)

__all__ = [
    # Walk-forward
    'WalkForwardAnalyzer',
    'walk_forward_optimize',
    
    # Purged K-Fold
    'PurgedKFold',
    'purged_kfold_split',
    
    # Combinatorial CV
    'CombinatorialPurgedCV',
    'generate_backtest_paths',
    
    # Meta-labeling
    'MetaLabeler',
    'create_meta_labels',
]
