"""RL Trading Pipeline integrating preanalysis and training.

High-level convenience function to:
    1. Run daily preanalysis (PIT data + reward registry)
    2. Instantiate RLTrainer
    3. Train chosen agent type
    4. Generate tearsheet
"""
from __future__ import annotations
from typing import List, Dict, Any
from financial_analyzer.preanalysis.daily_preanalysis import run_daily_preanalysis
from financial_analyzer.rl.trainers import RLTrainer
from financial_analyzer.reports.generate_tearsheet import generate_tearsheet
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

def run_rl_pipeline(
    symbols: List[str],
    start_date: str,
    end_date: str,
    agent_type: str = "ppo",
    total_timesteps: int = 50_000,
    output_dir: str = "./models/rl_runs",
    trainer_kwargs: Dict[str, Any] | None = None,
    agent_kwargs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    pre = run_daily_preanalysis(symbols, start_date, end_date)
    trainer = RLTrainer(symbols=symbols, start_date=start_date, end_date=end_date, models_dir=output_dir)
    results = trainer.train_walk_forward(
        agent_type=agent_type,
        total_timesteps=total_timesteps,
        agent_kwargs=agent_kwargs,
    )
    # Generate tearsheet from test metrics (enhanced)
    test_metrics = results["test_metrics"]
    mean_reward = test_metrics.get("mean_reward", 0.0)
    std_reward = test_metrics.get("std_reward", 0.1)
    n_steps = test_metrics.get("mean_length", 50)
    # Synthetic equity curve simulation
    import numpy as np
    rng = np.random.default_rng(42)
    returns = rng.normal(mean_reward / n_steps, std_reward / np.sqrt(n_steps), int(n_steps))
    portfolio_values = 100_000 * np.exp(np.cumsum(returns))
    tearsheet_path = generate_tearsheet(
        portfolio_values=portfolio_values,
        returns=returns,
        metrics=test_metrics,
        output_path=f"{output_dir}/tearsheets/{agent_type}_latest.html"
    )
    results["tearsheet"] = tearsheet_path
    logger.info(f"Pipeline complete. Tearsheet: {tearsheet_path}")
    return results

__all__ = ["run_rl_pipeline"]
