"""Tests for RiskfolioOptimizer.

All tests mock riskfolio Portfolio/HCPortfolio to avoid heavy computations.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from financial_analyzer.portfolio_optimization import RiskfolioOptimizer


@pytest.fixture
def returns_df():
    np.random.seed(0)
    data = np.random.randn(100, 4) / 100.0
    return pd.DataFrame(data, columns=["A", "B", "C", "D"])


def test_init_with_data(returns_df, caplog):
    with caplog.at_level("INFO"):
        opt = RiskfolioOptimizer(returns_df)
    assert opt.returns.shape == (100, 4)
    assert "initialized" in caplog.text.lower()


def test_init_empty(caplog):
    with caplog.at_level("WARNING"):
        opt = RiskfolioOptimizer(pd.DataFrame())
    assert opt.returns.empty
    assert "empty returns" in caplog.text.lower()


@patch("financial_analyzer.portfolio_optimization.riskfolio_optimizer.Portfolio")
def test_optimize_mean_cvar_basic(mock_portfolio, returns_df):
    mock_inst = MagicMock()
    mock_portfolio.return_value = mock_inst
    mock_inst.optimization.return_value = pd.Series([0.2, 0.3, 0.1, 0.4], index=returns_df.columns)
    opt = RiskfolioOptimizer(returns_df)
    w = opt.optimize_mean_cvar()
    assert pytest.approx(float(w.sum())) == 1.0
    assert all(a in w.index for a in returns_df.columns)


@patch("financial_analyzer.portfolio_optimization.riskfolio_optimizer.Portfolio")
def test_optimize_mean_cdar_basic(mock_portfolio, returns_df):
    mock_inst = MagicMock()
    mock_portfolio.return_value = mock_inst
    mock_inst.optimization.return_value = pd.Series([0.25, 0.25, 0.25, 0.25], index=returns_df.columns)
    opt = RiskfolioOptimizer(returns_df)
    w = opt.optimize_mean_cdar()
    assert pytest.approx(float(w.sum())) == 1.0


@patch("financial_analyzer.portfolio_optimization.riskfolio_optimizer.HCPortfolio")
def test_optimize_nco(mock_hc, returns_df):
    mock_inst = MagicMock()
    mock_hc.return_value = mock_inst
    mock_inst.optimization.return_value = pd.Series([0.3, 0.2, 0.2, 0.3], index=returns_df.columns)
    opt = RiskfolioOptimizer(returns_df)
    w = opt.optimize_nco(risk_measure='CVaR')
    assert pytest.approx(float(w.sum())) == 1.0


@patch("financial_analyzer.portfolio_optimization.riskfolio_optimizer.HCPortfolio")
def test_optimize_hrp(mock_hc, returns_df):
    mock_inst = MagicMock()
    mock_hc.return_value = mock_inst
    mock_inst.optimization.return_value = pd.Series([0.4, 0.3, 0.2, 0.1], index=returns_df.columns)
    opt = RiskfolioOptimizer(returns_df)
    w = opt.optimize_hrp()
    assert pytest.approx(float(w.sum())) == 1.0


def test_equal_weights_fallback(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    w = opt._equal_weights()
    assert pytest.approx(float(w.sum())) == 1.0
    assert len(w) == returns_df.shape[1]


def test_covariance_ledoit_wolf(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    cov = opt._estimate_covariance('ledoit_wolf')
    assert cov.shape == (4, 4)
    assert np.allclose(cov, cov.T)


def test_covariance_oracle(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    cov = opt._estimate_covariance('oracle')
    assert cov.shape == (4, 4)


def test_covariance_sample(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    cov = opt._estimate_covariance('sample')
    assert cov.shape == (4, 4)


def test_risk_decomposition(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    w = pd.Series([0.25, 0.25, 0.25, 0.25], index=returns_df.columns)
    rd = opt.risk_decomposition(w)
    assert set(rd.columns) == {'mrc', 'rc', 'pct'}
    assert pytest.approx(float(rd['pct'].sum())) == 1.0


def test_classic_optimization_error_fallback(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    # Force error: mock Portfolio to raise
    with patch("financial_analyzer.portfolio_optimization.riskfolio_optimizer.Portfolio", side_effect=Exception("fail")):
        w = opt.optimize_mean_cvar()
    assert pytest.approx(float(w.sum())) == 1.0  # equal weight fallback


def test_nco_error_fallback(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    with patch("financial_analyzer.portfolio_optimization.riskfolio_optimizer.HCPortfolio", side_effect=Exception("fail")):
        w = opt.optimize_nco()
    assert pytest.approx(float(w.sum())) == 1.0


def test_hrp_error_fallback(returns_df):
    opt = RiskfolioOptimizer(returns_df)
    with patch("financial_analyzer.portfolio_optimization.riskfolio_optimizer.HCPortfolio", side_effect=Exception("fail")):
        w = opt.optimize_hrp()
    assert pytest.approx(float(w.sum())) == 1.0


def test_empty_returns_behavior():
    opt = RiskfolioOptimizer(pd.DataFrame())
    w = opt.optimize_mean_cvar()
    assert w.empty
