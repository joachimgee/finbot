# PHASE 5.4 – ML Sentiment Backtesting Integration (Detailed Plan)

This document lays out the implementation plan for Phase 5.4: connecting features/sentiment to portfolio optimization and backtesting with full attribution and an E2E pipeline.

## Scope

- Module 1: integration/signal_portfolio_bridge.py (Day 1)
- Module 2: strategies/sentiment_momentum_strategy.py (Day 2)
- Module 3: strategies/factor_ensemble_strategy.py (Day 2)
- Module 4: integration/performance_attribution.py (Day 3)
- Module 5: integration/ml_trading_pipeline.py (Day 4)

## Objectives

- End-to-end pipeline: Features → Sentiment → Signals → Portfolio → Backtest → Attribution
- Use library capabilities directly: backtesting.py, Riskfolio-Lib, PyPortfolioOpt
- Strict validations, exhaustive logging, robust error handling with fallbacks
- High-quality tests built on mocks; zero external API calls

## Audit Mapping (references abbreviated)

- AUDIT_BACKTESTING_PY.md: Strategy base, Backtest.run/optimize, metrics (pp.5–12, 20–30)
- AUDIT_RISKFOLIO_LIB.md: NCO optimization, risk measures, risk contribution (pp.5–25)
- AUDIT_PYPORTFOLIOOPT.md: Efficient frontier, constraints (pp.8–15)
- AUDIT_ML4T_BOOK.md: Brinson attribution, factor models, walk-forward (pp.35–48)
- FINANCE PART 4/5: Strategy patterns, ML best practices

## Deliverables

- Source modules (5 files) with type hints and Google-style docstrings
- Tests (≈130 total): unit + integration (mocked)
- Coverage ≥ 90% on new modules
- Logging across critical paths

## Coding Guidelines

- Imports order: stdlib → data/num → finance libs → ML → project local
- Type hints on all params and returns; no unbounded Any
- Validation before use (types, NaNs, shapes, OHLCV columns)
- Logging: debug/info/warning/error, structured messages
- Error handling: try/except with library fallbacks
- Batch processing if signals > 50 tickers

## Module 1: SignalPortfolioBridge

Responsibilities:
- Validate inputs (signals dict, OHLCV DataFrame, UTC index)
- Filter assets by signal thresholds
- Compute expected returns from signal strength and historical IC (via sentiment/feature engines)
- Optimize portfolio with Riskfolio NCO; fallback to mean-variance/EfficientFrontier; fallback to equal-weight
- Enforce constraints (min/max weight) and normalize

Key methods:
- __init__(portfolio_optimizer, sentiment_engine, feature_selector, max_weight=0.20, min_weight=0.01)
- convert_signals_to_weights(signals, prices, lookback_days=252, risk_measure='CVaR') -> Dict[str, float]

Edge cases:
- Empty signals
- All zeros or all negatives
- NaNs in signals or prices
- Single-asset portfolios
- Highly correlated assets

Tests (30):
- 10 valid signal scenarios (long-only, long/short, normalization, constraints)
- 8 invalid inputs (types, ranges, empty, NaNs)
- 12 edge cases (single asset, perfect correlation, missing prices, high volatility)
- 1 mocked integration with backtesting Backtest input/output wiring

## Module 2: SentimentMomentumStrategy

Responsibilities:
- Combine sentiment (Phase 5.3) with momentum/technical filters (Phase 5.2)
- Use backtesting.py Strategy with vectorized indicators via self.I
- Position sizing proportional to signal strength up to max cap

Parameters (optimizable):
- sentiment_threshold, rsi_period, rsi_upper, volume_multiplier, max_position_size

Tests (20):
- Entry/exit rules correctness
- Handling of existing positions, stop/timeout
- End-to-end backtest smoke test (mocked)

## Module 3: FactorEnsembleStrategy

Responsibilities:
- Build composite signals from top-N factors by IC
- Long/short decisions based on ensemble score

Tests (15):
- Factor ranking and selection mock
- Ensemble weighting and thresholds
- Backtest smoke (mocked)

## Module 4: PerformanceAttributor

Responsibilities:
- Brinson-style attribution of PnL into sentiment, technicals, optimization, timing, residual

Tests (25):
- Component contribution sums and sign sanity
- Edge cases: zero trades, missing segments

## Module 5: MLTradingPipeline

Responsibilities:
- Orchestrate the full E2E flow
- Provide a simple run() returning MLPipelineResult

Tests (40):
- Happy path end-to-end (mocked submodules)
- Failure modes and retries

## Acceptance Criteria

- All new modules with 100% type hints and full docstrings
- Tests ≥ 130 with coverage ≥ 90%
- No external calls in tests; mocks for finance libs
- Logging present and informative
- Quality score target ≥ 9.8/10

## Execution Plan (Day by Day)

- Day 1: Implement SignalPortfolioBridge + 30 tests (mock optimizer and engines)
- Day 2: Implement strategies (2 files) + 35 tests
- Day 3: Implement PerformanceAttributor + 25 tests
- Day 4: Implement MLTradingPipeline + 40 tests

## Risks and Mitigations

- Finance libs presence: import guarded with try/except; fallback strategies
- Large test suite slow: rely on mocks and small synthetic datasets
- Tight validation: comprehensive fixtures and negative tests

## Done Definition

- Code compiles, tests pass, coverage target met, mypy clean
- Docstrings present with examples and audit references
- No duplicated logic; proper logging and error handling

## Appendix A: Data Shapes

- signals: Dict[str, float], values in [-2, 2]
- prices: DataFrame with columns ['Open', 'High', 'Low', 'Close', 'Volume'] and DatetimeIndex (UTC)
- weights: Dict[str, float], non-negative, sum ≈ 1.0

## Appendix B: Constraints

- max_weight default 20%, min_weight default 1%
- Long-only by default; negative signals may be ignored or down-weighted in bridge module (configurable later)

## Appendix C: Logging Keys

- event: 'optimize', 'fallback', 'validate', 'filter', 'normalize'
- tickers_count, selected_count, method, risk_measure

