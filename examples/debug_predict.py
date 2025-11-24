"""Debug predict() return shape."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from financial_analyzer.rl import TradingEnvironment, PPOAgent

# Create env
env = TradingEnvironment(
    symbols=['AAPL', 'MSFT'],
    start_date='2022-01-01',
    end_date='2022-12-31',
    initial_capital=100_000,
    random_start=False,
    use_technical_indicators=False,
    use_sentiment=False,
    use_risk_metrics=True,
)

# Create agent
agent = PPOAgent(env=env, verbose=0)

# Train minimal
agent.train(total_timesteps=100)

# Reset and predict
obs, info = env.reset()
print(f"Observation shape: {obs.shape}")
print(f"Observation: {obs}")

action, _ = agent.model.predict(obs, deterministic=True)
print(f"\nRaw action shape: {action.shape if hasattr(action, 'shape') else type(action)}")
print(f"Raw action: {action}")

# Via agent.predict()
action2 = agent.predict(obs, deterministic=True)
print(f"\nAgent.predict() shape: {action2.shape if hasattr(action2, 'shape') else type(action2)}")
print(f"Agent.predict() action: {action2}")
