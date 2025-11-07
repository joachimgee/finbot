import numpy as np
import pandas as pd

from financial_analyzer.portfolio.metrics import (
    calculate_portfolio_return,
    calculate_portfolio_volatility,
    calculate_portfolio_sharpe,
    calculate_correlation_matrix,
    calculate_var,
    calculate_cvar,
    calculate_diversification_ratio,
    calculate_herfindahl_index,
)


def test_basic_portfolio_metrics():
    mean_returns = pd.Series({'A': 0.10, 'B': 0.05})
    cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.01]], index=['A', 'B'], columns=['A', 'B'])
    w = pd.Series({'A': 0.6, 'B': 0.4})

    port_ret = calculate_portfolio_return(w, mean_returns)
    assert np.isclose(port_ret, 0.6 * 0.10 + 0.4 * 0.05)

    port_vol = calculate_portfolio_volatility(w, cov)
    expected_vol = np.sqrt(0.6**2 * 0.04 + 0.4**2 * 0.01)
    assert np.isclose(port_vol, expected_vol)

    sharpe = calculate_portfolio_sharpe(w, mean_returns, cov, risk_free_rate=0.02)
    assert np.isfinite(sharpe)


def test_correlation_var_cvar():
    rng = np.random.default_rng(0)
    data = rng.normal(loc=0.001, scale=0.01, size=(252, 3))
    df = pd.DataFrame(data, columns=['A', 'B', 'C'])
    corr = calculate_correlation_matrix(df)
    assert corr.shape == (3, 3)

    # VaR/CVaR on a single series
    s = df['A']
    var95 = calculate_var(s, confidence=0.95)
    cvar95 = calculate_cvar(s, confidence=0.95)
    assert var95 >= 0
    assert cvar95 >= var95


def test_diversification_and_hhi():
    vols = pd.Series({'A': 0.2, 'B': 0.1, 'C': 0.15})
    w = pd.Series({'A': 1/3, 'B': 1/3, 'C': 1/3})
    cov = pd.DataFrame(np.diag(vols.values**2), index=vols.index, columns=vols.index)
    pvol = calculate_portfolio_volatility(w, cov)
    dr = calculate_diversification_ratio(w, vols, pvol)
    assert dr >= 1.0

    hhi = calculate_herfindahl_index(w)
    assert np.isclose(hhi, 3 * (1/3)**2)
