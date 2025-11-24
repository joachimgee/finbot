"""Execute multi-agent RL pipeline demo.

Runs A2C training with enhanced tearsheet generation.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from financial_analyzer.rl.rl_trading_pipeline import run_rl_pipeline
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

if __name__ == "__main__":
    logger.info("Starting multi-agent RL pipeline demo")
    results = run_rl_pipeline(
        symbols=["AAPL", "MSFT"],
        start_date="2020-01-01",
        end_date="2020-06-30",
        agent_type="a2c",
        total_timesteps=5_000,
        output_dir="./models/rl_demo",
    )
    logger.info("Pipeline complete.")
    logger.info(f"Test metrics: {results['test_metrics']}")
    logger.info(f"Tearsheet: {results['tearsheet']}")
    print("\n✅ Pipeline executed successfully!")
    print(f"📊 Tearsheet: {results['tearsheet']}")
    print(f"🎯 Mean Reward: {results['test_metrics']['mean_reward']:.4f}")
