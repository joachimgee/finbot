import pytest
from datetime import datetime

from financial_analyzer.analysis.master_orchestrator import MasterOrchestrator, MasterAnalysisResult

@pytest.mark.parametrize("symbols", [["AAPL","MSFT"],["GOOGL","AMZN","TSLA"]])
def test_master_orchestrator_dry_run(symbols):
    orc = MasterOrchestrator(symbols=symbols, mode='paper', analysis_csv_path='professional_daily_global.csv')
    result: MasterAnalysisResult = orc.run_complete_analysis(
        start_date='2025-01-01',
        end_date='2025-11-21',
        dry_run=True,
        skip_if_no_drift=False,
        use_rl_signals=False,
        use_ml_signals=False,
        use_sentiment=False,
    )
    # Always returns pre_analysis object (even on failure)
    assert result.pre_analysis is not None
    assert hasattr(result.pre_analysis, 'drift_detected')
    assert result.timestamp <= datetime.now()
    # Dry-run may skip execution; ensure structure
    if result.execution:
        assert result.execution.risk_score is not None
        assert isinstance(result.execution.orders_submitted, list)

def test_master_orchestrator_failure_resilience(monkeypatch):
    # Force exception in pre-analysis by monkeypatching module import
    def boom(*args, **kwargs):
        raise RuntimeError("forced error")
    from financial_analyzer.preanalysis import daily_preanalysis
    monkeypatch.setattr(daily_preanalysis, 'run_daily_preanalysis', boom)
    orc = MasterOrchestrator(symbols=["AAPL"], mode='paper')
    res = orc.run_complete_analysis(start_date='2025-01-01', end_date='2025-11-21', dry_run=True)
    assert res.status == 'failed'
    assert res.pre_analysis is not None
    assert res.pre_analysis.drift_detected is False
