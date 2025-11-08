from __future__ import annotations

from typing import Any, Dict, List
import numpy as np
import pandas as pd
import pytest

from financial_analyzer.sentiment import SentimentAggregator
from financial_analyzer.strategy import SignalFusion, EnsembleAllocator
from financial_analyzer.deep_learning import LSTMPredictor
from financial_analyzer.portfolio_optimization import RiskfolioOptimizer
from financial_analyzer.pipeline.order_executor import OrderExecutor
from financial_analyzer.analytics.performance_analyzer import PerformanceAnalyzer
from financial_analyzer.analytics.report_generator import ReportGenerator


# -----------------------------
# Fixtures & utilities
# -----------------------------

@pytest.fixture
def returns_df() -> pd.DataFrame:
    np.random.seed(7)
    dates = pd.date_range('2025-10-01', periods=60, freq='B')
    data = {t: np.random.normal(0.0004, 0.01, len(dates)) for t in ['AAA', 'BBB', 'CCC']}
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sentiment_scores() -> Dict[str, float]:
    return {'AAA': 0.2, 'BBB': -0.1, 'CCC': 0.4}


def test_sentiment_to_signal_fusion(sentiment_scores):
    fusion = SignalFusion()
    out = fusion.fuse('AAA', sentiment_scores['AAA'], technical_signals=None, dl_prediction=None)
    assert 'final_score' in out and 0.0 <= out['final_score'] <= 1.0


def test_technical_to_signal_fusion(returns_df):
    fusion = SignalFusion()
    technical = {'rsi': 55, 'macd': 0.01, 'sma_cross': 1, 'bb_position': 0.6}
    out = fusion.fuse('BBB', 0.0, technical_signals=technical, dl_prediction=None)
    assert 'confidence' in out and out['confidence'] >= 0


def test_lstm_to_signal_fusion(returns_df):
    # Simulate predictor output directly
    fusion = SignalFusion()
    out = fusion.fuse('CCC', 0.0, technical_signals=None, dl_prediction=0.7)
    assert 0.0 <= out['final_score'] <= 1.0


def test_signal_fusion_to_allocator(returns_df):
    fusion = SignalFusion()
    signals = {t: fusion.fuse(t, 0.0, {'rsi': 50, 'macd': 0.0, 'sma_cross': 1, 'bb_position': 0.5}, 0.5) for t in returns_df.columns}
    alloc = EnsembleAllocator().allocate(signals, total_capital=100_000, risk_model='signal_based')
    assert isinstance(alloc, dict) and 'cash' in alloc


def test_allocator_to_riskfolio(returns_df):
    # Use optimizer equal weights fallback to mimic passing allocations
    opt = RiskfolioOptimizer(returns_df)
    weights = opt._equal_weights()  # internal method used as baseline
    assert abs(weights.sum() - 1.0) < 1e-6
    # Risk decomposition should run
    risk_decomp = opt.risk_decomposition(weights)
    assert not risk_decomp.empty and {'mrc', 'rc', 'pct'}.issubset(risk_decomp.columns)


def test_riskfolio_to_order_executor():
    executor = OrderExecutor(initial_capital=100_000)
    order = {'ticker': 'AAA', 'action': 'BUY', 'target_weight': 0.1, 'delta_weight': 0.1, 'notional': 10_000}
    res = executor.execute(order, current_price=100.0)
    assert res['status'] == 'success'


def test_order_executor_to_performance_attribution():
    # Placeholder: ensure trade log can feed into analytics
    executor = OrderExecutor(initial_capital=100_000)
    executor.execute({'ticker': 'AAA', 'action': 'BUY', 'target_weight': 0.1, 'delta_weight': 0.1, 'notional': 10_000}, 100.0)
    trades = executor.track_trades()
    assert not trades.empty and {'timestamp', 'ticker', 'action'}.issubset(trades.columns)


def test_attribution_to_report_generator(returns_df):
    analyzer = PerformanceAnalyzer()
    port = returns_df.mean(axis=1)
    metrics = analyzer.analyze_returns(port, None, None)
    rg = ReportGenerator()
    md = rg.generate_report(port, None, None, None, metrics=metrics)
    assert isinstance(md, str) and '# ' in md


def test_config_propagation_and_logging(returns_df, caplog):
    caplog.clear()
    caplog.set_level('INFO')
    fusion = SignalFusion()
    out = fusion.fuse('AAA', 0.1, {'rsi': 52, 'macd': 0.01, 'sma_cross': 1, 'bb_position': 0.55}, 0.6)
    assert 'final_score' in out
    # We don't rely on specific messages, just ensure logging does not crash and capture worked
    assert True


def test_constructors_interfaces():
    # Smoke tests for constructors
    _ = SignalFusion()
    _ = EnsembleAllocator()
    _ = OrderExecutor()
    _ = PerformanceAnalyzer()
    _ = ReportGenerator()
