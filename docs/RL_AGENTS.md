# RL Agents Overview

This document summarizes the reinforcement learning agents integrated into FinBot Phase 4.

## Supported Algorithms

| Agent | Type | Action Space | Stability | Sample Efficiency | Notes |
|-------|------|--------------|-----------|-------------------|-------|
| PPO | On-Policy | Continuous | High | Moderate | Baseline default |
| DQN | Off-Policy | Discrete (proxy) | Medium | High | Uses discrete wrapper mapping {-1,0,1} to vector actions |
| A2C | On-Policy | Continuous | Medium | Lower | Simpler than PPO |
| DDPG | Off-Policy | Continuous | Medium | High | Deterministic policy gradient |

## Unified Interface
All agents (except legacy `PPOAgent`) inherit from `BaseRLAgent` exposing:

```python
agent.train(total_timesteps=10000)
metrics = agent.evaluate(eval_env, n_eval_episodes=5)
action, _ = agent.predict(obs)
agent.save("models/best/my_agent")
```

## Factory Usage
Use `RLTrainer._create_agent(agent_type, env, agent_kwargs)` where `agent_type` in `{"ppo","dqn","a2c","ddpg"}`.

## When to Choose Each
- PPO: Default choice; robust and widely validated in trading literature.
- DQN: Useful for simplified discrete decision regimes (e.g., buy/hold/sell). Proxy layer abstracts continuous environment.
- A2C: Lightweight baseline for quick experimentation; fewer hyperparameters.
- DDPG: Suitable for continuous fine-grained allocation; can be extended toward SAC/TD3 later.

## Extensibility Roadmap
Planned additions: SAC (entropy-regularized), TD3 (twin critics), multi-agent coordination layer.

## Reward Integration
Reward functions auto-register via decorators in `rl/rewards/registry.py`. Query available rewards:
```python
from financial_analyzer.rl.rewards.registry import list_rewards
print(list_rewards().keys())
```

## Point-In-Time Data
`PITDataLoader` ensures future enhancements (corporate actions, delistings) to reduce bias. Current implementation returns synthetic data; replace with vendor ingestion pipeline in Phase 4.2.

## Tearsheets
`generate_tearsheet` produces HTML summaries. Future upgrade: integrate real equity curve & advanced analytics (rolling Sharpe, drawdown paths).

## Example Full Pipeline
```python
from financial_analyzer.rl.rl_trading_pipeline import run_rl_pipeline
results = run_rl_pipeline(
    symbols=["AAPL","MSFT"],
    start_date="2020-01-01",
    end_date="2020-06-30",
    agent_type="a2c",
    total_timesteps=25_000,
)
print(results["test_metrics"])  # {'mean_reward': ..., ...}
print("Tearsheet:", results["tearsheet"])  # Path to HTML
```

## Known Limitations
- DQN discrete proxy collapses per-asset nuance; extend to multi-discrete mapping.
- Synthetic PIT loader; integrate real-time ingestion next iteration.
- Reward scaling/clipping heuristic (range [-3,5])—consider adaptive normalization.

## Next Steps
1. Implement SAC/TD3 wrappers.
2. Add episodic curriculum (volatility regimes).
3. Introduce factor risk constraints in environment action post-processing.
4. Integrate evaluation tearsheet with performance metrics and benchmark overlays.

## References
- Stable-Baselines3 Documentation
- Yang et al., FinRL (2020)
- Schulman et al., PPO (2017)
