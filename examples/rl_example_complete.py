"""
RL Trading Example - Complete Usage.

Demonstrates complete RL trading workflow:
1. Environment creation
2. Agent training
3. Evaluation
4. Comparison with baselines

Usage:
    python examples/rl_example_complete.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
from financial_analyzer.rl import TradingEnvironment, PPOAgent, RLTrainer
from financial_analyzer.rl.rewards import (
    calculate_sharpe_reward,
    calculate_sortino_reward,
    calculate_calmar_reward,
)
from financial_analyzer.pipeline import RLTradingPipeline


def example_1_simple_training():
    """Example 1: Simple PPO training."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Simple PPO Training")
    print("=" * 60)
    
    # Create environment
    print("\n1. Creating TradingEnvironment...")
    env = TradingEnvironment(
        symbols=['AAPL', 'MSFT'],
        start_date='2020-01-01',
        end_date='2020-06-30',  # Short period for demo
        initial_capital=100_000,
        use_technical_indicators=True,
        use_sentiment=False,
        use_risk_metrics=True,
    )
    
    print(f"   ✅ Environment created: {env.n_assets} assets")
    print(f"   ✅ State dimension: {env.observation_space.shape[0]}")
    print(f"   ✅ Action dimension: {env.action_space.shape[0]}")
    
    # Create agent
    print("\n2. Creating PPO Agent...")
    agent = PPOAgent(
        env=env,
        learning_rate=3e-4,
        n_steps=64,  # Small for demo
        batch_size=32,
        verbose=0
    )
    
    print(f"   ✅ Agent created: {agent}")
    
    # Train
    print("\n3. Training agent (100 timesteps - DEMO ONLY)...")
    agent.train(
        total_timesteps=100,  # Very short for demo
        log_interval=10
    )
    
    print("   ✅ Training completed!")
    
    # Evaluate
    print("\n4. Evaluating agent...")
    metrics = agent.evaluate(
        eval_env=env,
        n_eval_episodes=2,
        deterministic=True
    )
    
    print(f"   ✅ Mean Reward: {metrics['mean_reward']:.4f}")
    print(f"   ✅ Std Reward: {metrics['std_reward']:.4f}")
    
    # Save
    print("\n5. Saving model...")
    agent.save("./models/example_ppo_simple")
    print("   ✅ Model saved to ./models/example_ppo_simple.zip")
    
    return agent


def example_2_walk_forward():
    """Example 2: Walk-forward training with RLTrainer."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Walk-Forward Training")
    print("=" * 60)
    
    # Create trainer
    print("\n1. Creating RLTrainer...")
    trainer = RLTrainer(
        symbols=['AAPL', 'MSFT', 'GOOGL'],
        start_date='2020-01-01',
        end_date='2020-06-30',  # Short period for demo
        initial_capital=100_000,
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15,
        models_dir="./models/rl_trainer",
        logs_dir="./logs/rl_trainer"
    )
    
    print(f"   ✅ Trainer created: {len(trainer.symbols)} assets")
    
    # Train with walk-forward
    print("\n2. Training with walk-forward validation...")
    results = trainer.train_walk_forward(
        agent_type='ppo',
        total_timesteps=100,  # Very short for demo
        eval_freq=50,
        n_eval_episodes=2
    )
    
    print(f"   ✅ Training completed!")
    print(f"   ✅ Test Reward: {results['test_metrics']['mean_reward']:.4f}")
    
    # Compare baselines
    print("\n3. Comparing with baselines...")
    comparison = trainer.compare_baselines(results)
    print(f"\n{comparison.to_string()}")
    
    # Save results
    print("\n4. Saving results...")
    trainer.save_results("rl_trainer_results.json")
    print("   ✅ Results saved to ./models/rl_trainer/rl_trainer_results.json")
    
    return results


def example_3_pipeline_integration():
    """Example 3: Complete pipeline integration."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Pipeline Integration")
    print("=" * 60)
    
    # Create pipeline
    print("\n1. Creating RLTradingPipeline...")
    pipeline = RLTradingPipeline(
        symbols=['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
        start_date='2020-01-01',
        end_date='2020-06-30',  # Short period for demo
        initial_capital=100_000,
        use_technical_indicators=True,
        use_sentiment=False,
        use_risk_metrics=True,
        models_dir="./models/rl_pipeline",
        logs_dir="./logs/rl_pipeline"
    )
    
    print(f"   ✅ Pipeline created: {len(pipeline.symbols)} assets")
    
    # Train RL agent
    print("\n2. Training RL agent...")
    result = pipeline.run_rl_training(
        agent_type='ppo',
        total_timesteps=100,  # Very short for demo
        eval_freq=50,
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15
    )
    
    print(f"   ✅ Training completed!")
    print(f"   ✅ Total Return: {result.total_return_pct:.2f}%")
    print(f"   ✅ Sharpe Ratio: {result.sharpe_ratio:.4f}")
    
    # Compare with traditional
    print("\n3. Comparing with traditional strategies...")
    comparison = pipeline.compare_with_traditional()
    print(f"\n{comparison.to_string()}")
    
    # Save results
    print("\n4. Saving pipeline results...")
    pipeline.save_results("rl_pipeline_results.json")
    print("   ✅ Results saved!")
    
    return result


def example_4_reward_functions():
    """Example 4: Reward functions demonstration."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Reward Functions")
    print("=" * 60)
    
    # Sample returns
    returns = np.array([0.02, -0.01, 0.03, 0.01, -0.005, 0.015, 0.02, -0.008])
    
    print("\n1. Sample returns:")
    print(f"   {returns}")
    
    # Calculate rewards
    print("\n2. Calculating reward metrics...")
    
    sharpe = calculate_sharpe_reward(returns, rf_rate=0.02)
    print(f"   ✅ Sharpe Ratio: {sharpe:.4f}")
    
    sortino = calculate_sortino_reward(returns, rf_rate=0.02)
    print(f"   ✅ Sortino Ratio: {sortino:.4f}")
    
    calmar = calculate_calmar_reward(returns)
    print(f"   ✅ Calmar Ratio: {calmar:.4f}")
    
    # Performance summary
    print("\n3. Performance Summary:")
    print(f"   Mean Return: {np.mean(returns):.4f}")
    print(f"   Volatility: {np.std(returns):.4f}")
    print(f"   Max Return: {np.max(returns):.4f}")
    print(f"   Min Return: {np.min(returns):.4f}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("🤖 RL TRADING EXAMPLES - COMPLETE DEMONSTRATION")
    print("=" * 60)
    print("\nThis demo shows 4 complete RL trading workflows:")
    print("1. Simple PPO Training")
    print("2. Walk-Forward Training")
    print("3. Pipeline Integration")
    print("4. Reward Functions")
    print("\nNote: Using short training periods (100 timesteps) for demo speed.")
    print("For production, use 100K-1M timesteps.")
    
    try:
        # Example 1: Simple training
        agent = example_1_simple_training()
        
        # Example 2: Walk-forward
        results = example_2_walk_forward()
        
        # Example 3: Pipeline
        pipeline_result = example_3_pipeline_integration()
        
        # Example 4: Rewards
        example_4_reward_functions()
        
        # Final summary
        print("\n" + "=" * 60)
        print("🎉 ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nNext Steps:")
        print("1. Increase training timesteps (100K-1M)")
        print("2. Add more assets to universe")
        print("3. Enable technical indicators & sentiment")
        print("4. Run walk-forward on longer periods")
        print("5. Compare with Portfolio Learning system")
        print("\nSee docs/RL_INTEGRATION_SUMMARY.md for more details.")
        
    except Exception as e:
        print(f"\n❌ Error during examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
