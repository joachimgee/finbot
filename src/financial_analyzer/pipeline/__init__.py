"""
ML Trading Pipeline module.

Orchestrates complete ML trading system end-to-end:
- Walk-forward validation
- Feature engineering (Phase 5.2)
- Signal generation (Phase 5.3)
- Portfolio optimization (Phase 5.1)
- Multi-strategy backtesting (Phase 5.4)
- Performance attribution

Example:
    >>> from financial_analyzer.pipeline import MLTradingPipeline
    >>> pipeline = MLTradingPipeline(universe_size=50)
    >>> result = pipeline.run_walk_forward(prices_data, n_windows=10)
"""

from financial_analyzer.pipeline.ml_trading_pipeline import (
    MLTradingPipeline,
    PipelineResult
)

__all__ = [
    'MLTradingPipeline',
    'PipelineResult',
]
