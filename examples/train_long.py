"""
Long RL training runner.

Usage examples:

# Smoke (quick validation, overrides total_timesteps):
python examples/train_long.py --config config/rl_train_long.yaml --timesteps 2000

# Full production run (uses config default 1_000_000):
python examples/train_long.py --config config/rl_train_long.yaml

"""
import argparse
import yaml
import os
from pathlib import Path
import json
import logging

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from financial_analyzer.rl.trainers.rl_trainer import RLTrainer

logger = logging.getLogger("train_long")
logging.basicConfig(level=logging.INFO)


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def ensure_dirs(cfg: dict):
    p = Path(cfg.get("paths", {}).get("models_dir", "./models/rl_long"))
    l = Path(cfg.get("paths", {}).get("logs_dir", "./logs/rl_long"))
    p.mkdir(parents=True, exist_ok=True)
    l.mkdir(parents=True, exist_ok=True)


def run_training(cfg: dict, override_timesteps: int | None = None):
    env_cfg = cfg.get("environment", {})
    train_cfg = cfg.get("train", {})
    paths = cfg.get("paths", {})

    total_timesteps = override_timesteps if override_timesteps is not None else train_cfg.get("total_timesteps")

    # Create trainer
    trainer = RLTrainer(
        symbols=env_cfg.get("symbols", ["AAPL"]),
        start_date=env_cfg.get("start_date"),
        end_date=env_cfg.get("end_date"),
        initial_capital=env_cfg.get("initial_capital", 100000),
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15,
        models_dir=paths.get("models_dir"),
        logs_dir=paths.get("logs_dir"),
    )

    logger.info(f"Starting training: agent={train_cfg.get('agent_type')} timesteps={total_timesteps}")

    results = trainer.train_walk_forward(
        agent_type=train_cfg.get("agent_type", "ppo"),
        total_timesteps=int(total_timesteps),
        eval_freq=train_cfg.get("eval_freq", 10000),
        n_eval_episodes=train_cfg.get("n_eval_episodes", 10),
    )

    # Save results
    results_file = paths.get("results_file") or "./models/rl_long/rl_long_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Training finished. Results saved to {results_file}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--timesteps", type=int, default=None, help="Override total timesteps for smoke test")
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)

    results = run_training(cfg, override_timesteps=args.timesteps)
    print("Training run complete. Summary:")
    print(results)


if __name__ == "__main__":
    main()
