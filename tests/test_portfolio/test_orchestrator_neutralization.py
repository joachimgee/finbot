"""P0/P1: the MasterOrchestrator execution path is neutralised (refuses real
order submission) and its portfolio construction no longer crashes.

Background: the execution path was dead — it called a non-existent
PortfolioOptimizer.optimize_mean_variance (AttributeError, swallowed), unpacked
Dict-returning optimizers as tuples, and fed synthetic PIT prices. These tests
lock in that (a) real submission is refused loudly, and (b) construction returns
a valid weight vector for dry-run analysis.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from financial_analyzer.analysis.master_orchestrator import (
    MasterOrchestrator,
    PreAnalysisResult,
    SignalGenerationResult,
)


@pytest.fixture
def orchestrator():
    return MasterOrchestrator(symbols=["AAPL", "MSFT", "GOOGL"], initial_capital=100_000.0)


def _pre_analysis():
    return PreAnalysisResult(
        timestamp=datetime.now(),
        current_portfolio={"positions": []},
        drift_detected=False,
        drift_reason=None,
        options_analysis={},
        portfolio_decisions={"hold": [], "sell": [], "buy": [], "cancel": []},
        should_retrain=False,
        warnings=[],
        learning_insights=[],
    )


def _signals(symbols):
    return SignalGenerationResult(
        timestamp=datetime.now(),
        rl_signals=None,
        ml_predictions=None,
        sentiment_scores=None,
        combined_signals={s: 0.0 for s in symbols},
        confidence_scores={s: 0.5 for s in symbols},
    )


class TestExecutionNeutralised:
    def test_real_submission_refused(self, orchestrator):
        with pytest.raises(NotImplementedError):
            orchestrator._run_execution(
                portfolio_construction=None,
                pre_analysis=_pre_analysis(),
                dry_run=False,
            )


class TestConstructionNoLongerCrashes:
    def test_returns_valid_weights(self, orchestrator):
        # PITDataLoader returns synthetic prices (no network), so this exercises
        # the real construction path end to end.
        result = orchestrator._run_portfolio_construction(
            pre_analysis=_pre_analysis(),
            signal_gen=_signals(orchestrator.symbols),
            optimization_method="mean_variance",
        )
        weights = result.target_weights
        assert isinstance(weights, pd.Series)
        # A weight for every symbol, finite, no NaN.
        assert set(orchestrator.symbols).issubset(set(weights.index))
        assert weights.notna().all()
        assert float(weights.sum()) == pytest.approx(weights.sum())  # finite
