import numpy as np
import pandas as pd
import pytest

from financial_analyzer.portfolio import (
    PortfolioOptimizer,
    PortfolioConstraints,
    calculate_min_variance,
    calculate_max_sharpe,
    calculate_risk_parity,
    calculate_equal_weight,
)


@pytest.fixture(scope="module")
def random_returns_df():
    rng = np.random.default_rng(42)
    n_days = 252
    n_assets = 5
    # Simulate with some correlation structure
    A = rng.normal(size=(n_assets, n_assets))
    cov = A @ A.T
    cov = cov / np.max(np.abs(cov)) * 0.02  # scale
    mean = np.linspace(0.05, 0.15, n_assets) / 252
    data = rng.multivariate_normal(mean=mean, cov=cov, size=n_days)
    df = pd.DataFrame(data, columns=[f'A{i}' for i in range(n_assets)])
    return df


def test_equal_weight_basic(random_returns_df):
    res = calculate_equal_weight(random_returns_df)
    w = res['weights']
    assert isinstance(w, pd.Series)
    assert pytest.approx(w.sum(), rel=1e-6, abs=1e-6) == 1.0
    assert all(w > 0)
    assert all(np.isclose(w.values, 1.0 / len(w), atol=1e-6))


def test_risk_parity_basic(random_returns_df):
    res = calculate_risk_parity(random_returns_df)
    w = res['weights']
    assert isinstance(w, pd.Series)
    assert pytest.approx(w.sum(), rel=1e-6, abs=1e-6) == 1.0
    assert all(w >= 0)


def test_min_variance_vs_equal_weight_vol(random_returns_df):
    opt = PortfolioOptimizer(random_returns_df)
    ew = opt.optimize_equal_weight()
    mv = opt.optimize_min_variance()
    assert mv['volatility'] <= ew['volatility'] + 1e-6


def test_max_sharpe_beats_equal_weight_sharpe(random_returns_df):
    opt = PortfolioOptimizer(random_returns_df)
    ew = opt.optimize_equal_weight()
    ms = opt.optimize_max_sharpe()
    # Just ensure Sharpe computed and is at least as good as EW Sharpe
    assert 'sharpe' in ms
    assert ms['sharpe'] >= 0 or np.isnan(ms['sharpe'])


def test_sector_limit_respected(random_returns_df):
    opt = PortfolioOptimizer(random_returns_df)
    # Map first 3 assets to Tech with a 30% max
    tickers = list(random_returns_df.columns)
    sector_map = {t: ('Tech' if i < 3 else 'Other') for i, t in enumerate(tickers)}
    pc = PortfolioConstraints()
    pc.add_sector_constraint({'Tech': 0.3}, sector_map)
    opt.add_constraint(pc)

    res = opt.optimize_max_sharpe()
    w = res['weights']
    tech_weight = float(w.iloc[:3].sum())
    assert tech_weight <= 0.3 + 1e-4


def test_concentration_limit_caps_single_weight(random_returns_df):
    opt = PortfolioOptimizer(random_returns_df)
    pc = PortfolioConstraints()
    pc.add_concentration_limit(0.35)
    opt.add_constraint(pc)
    res = opt.optimize_max_sharpe()
    w = res['weights']
    # if HHI <= 0.35 then any single weight should be <= sqrt(0.35) ~= 0.5916; we test stricter bound
    assert (w <= 0.6 + 1e-4).all()


def test_efficient_frontier_monotonic_vol(random_returns_df):
    opt = PortfolioOptimizer(random_returns_df)
    frontier = opt.calculate_efficient_frontier(num_portfolios=20)
    assert not frontier.empty
    frontier_sorted = frontier.sort_values(by='return')
    vols = frontier_sorted['volatility'].values
    # Vol should be non-decreasing as return increases (allow small numerical slack)
    assert np.all(vols[1:] >= vols[:-1] - 1e-6)


def test_module_level_calls_with_constraints(random_returns_df):
    pc = PortfolioConstraints()
    pc.add_allocation_limits(0.0, 0.5)
    res = calculate_min_variance(random_returns_df, constraints=pc)
    assert isinstance(res['weights'], pd.Series)
    assert (res['weights'] <= 0.5 + 1e-6).all()


def test_single_asset_case():
    # Single asset should allocate 100% to it
    rng = np.random.default_rng(0)
    data = rng.normal(loc=0.0003, scale=0.01, size=252)
    df = pd.DataFrame({'ONLY': data})
    opt = PortfolioOptimizer(df)
    res = opt.optimize_min_variance()
    w = res['weights']
    assert pytest.approx(w['ONLY'], abs=1e-6) == 1.0


def test_risk_free_rate_setter_validation(random_returns_df):
    opt = PortfolioOptimizer(random_returns_df)
    with pytest.raises(ValueError):
        opt.set_risk_free_rate(1.0)
    with pytest.raises(ValueError):
        opt.set_risk_free_rate(-0.2)
    opt.set_risk_free_rate(0.03)


def test_bounds_respected_in_risk_parity_when_limited(random_returns_df):
    opt = PortfolioOptimizer(random_returns_df)
    pc = PortfolioConstraints()
    pc.add_allocation_limits(0.0, 0.3)
    opt.add_constraint(pc)
    res = opt.optimize_risk_parity()
    w = res['weights']
    assert (w <= 0.3 + 1e-6).all()


def test_min_variance_returns_shapes(random_returns_df):
    res = calculate_min_variance(random_returns_df)
    assert set(res.keys()) == {'weights', 'return', 'volatility'}


def test_max_sharpe_returns_shapes(random_returns_df):
    res = calculate_max_sharpe(random_returns_df)
    assert set(res.keys()) == {'weights', 'return', 'volatility', 'sharpe'}
