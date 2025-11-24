"""
Simple RL Trading Example.

Quick demonstration of basic RL trading workflow.

Usage:
    python examples/rl_example_simple.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
from financial_analyzer.rl import TradingEnvironment, PPOAgent


def main():
    """Simple PPO training example."""
    print("\n🤖 Simple RL Trading Example")
    print("=" * 60)
    
    # 1. Create environment
    print("\n1. Creating TradingEnvironment...")
    env = TradingEnvironment(
        symbols=['AAPL', 'MSFT'],
        start_date='2022-01-01',
        end_date='2022-12-31',
        initial_capital=100_000,
        commission=0.001,
        random_start=False,  # Disable for consistency
        use_technical_indicators=False,  # Faster
        use_sentiment=False,  # Faster
        use_risk_metrics=True,  # Keep risk
    )
    
    print(f"   ✅ Environment created")
    print(f"      - Assets: {env.n_assets}")
    print(f"      - State dimension: {env.observation_space.shape[0]}")
    print(f"      - Action dimension: {env.action_space.shape[0]}")
    print(f"      - Max steps: {env.max_steps}")
    
    # 2. Create agent
    print("\n2. Creating PPO Agent...")
    agent = PPOAgent(
        env=env,
        learning_rate=3e-4,
        n_steps=128,
        batch_size=64,
        verbose=0,  # Quiet mode
    )
    
    print(f"   ✅ Agent created: {agent}")
    
    # 3. Train (short demo)
    print("\n3. Training agent...")
    print("   (Using 500 timesteps for demo - use 100K+ for production)")
    
    agent.train(
        total_timesteps=500,
        log_interval=1
    )
    
    print("   ✅ Training completed!")
    
    # 4. Evaluate
    print("\n4. Evaluating agent...")
    metrics = agent.evaluate(
        eval_env=env,
        n_eval_episodes=5,
        deterministic=True
    )
    
    print(f"   ✅ Evaluation results:")
    print(f"      - Mean Reward: {metrics['mean_reward']:.4f}")
    print(f"      - Std Reward: {metrics['std_reward']:.4f}")
    
    # 5. Test inference
    print("\n5. Testing inference...")
    obs, info = env.reset()
    
    total_return = 0.0
    for step in range(min(20, env.max_steps)):
        action, _ = agent.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_return += reward
        
        if terminated or truncated:
            break
    
    print(f"   ✅ Inference test completed")
    print(f"      - Steps: {step + 1}")
    print(f"      - Total Reward: {total_return:.4f}")
    print(f"      - Final Portfolio Value: ${info.get('portfolio_value', 0):,.2f}")
    
    # 6. Save model
    print("\n6. Saving model...")
    save_path = "./models/rl_simple_demo"
    agent.save(save_path)
    print(f"   ✅ Model saved to {save_path}.zip")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 EXAMPLE COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Increase training timesteps (100K-1M)")
    print("2. Enable technical indicators & sentiment")
    print("3. Try walk-forward validation (RLTrainer)")
    print("4. Use RLTradingPipeline for full integration")
    print("\nSee docs/RL_INTEGRATION_SUMMARY.md for more details.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
