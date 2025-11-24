"""
ML Trading Pipeline module.

Orchestrates complete ML trading system end-to-end:
- Walk-forward validation
- Feature engineering (Phase 5.2)
- Signal generation (Phase 5.3)
- Portfolio optimization (Phase 5.1)
- Multi-strategy backtesting (Phase 5.4)
- Performance attribution
- Reinforcement Learning (Phase 6: Deep RL integration)

Example:
    >>> from financial_analyzer.pipeline import MLTradingPipeline
    >>> pipeline = MLTradingPipeline(universe_size=50)
    >>> result = pipeline.run_walk_forward(prices_data, n_windows=10)
    
    >>> # RL Pipeline
    >>> from financial_analyzer.pipeline import RLTradingPipeline
    >>> rl_pipeline = RLTradingPipeline(symbols=['AAPL', 'MSFT', 'GOOGL'])
    >>> rl_result = rl_pipeline.run_rl_training(agent_type='ppo', total_timesteps=100_000)
"""

from financial_analyzer.pipeline.ml_trading_pipeline import (
    MLTradingPipeline,
    PipelineResult
)

from financial_analyzer.pipeline.rl_trading_pipeline import (
    RLTradingPipeline,
    RLPipelineResult
)

__all__ = [
    'MLTradingPipeline',
    'PipelineResult',
    'RLTradingPipeline',
    'RLPipelineResult',
]
