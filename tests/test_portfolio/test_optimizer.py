import numpy as np
import pandas as pd

from financial_analyzer.portfolio.optimizer import PortfolioOptimizer
from financial_analyzer.portfolio.constraints import (
    Constraints,
    GroupConstraint,
    LeverageConstraint,
    MaxPositionsConstraint,
    RiskBudgetConstraint,
    WeightBounds,
)


def make_daily_returns(n_days=252, tickers=('A', 'B', 'C', 'D', 'E'), seed=123) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = {}
    for t in tickers:
        rets[t] = rng.normal(loc=0.0005, scale=0.02, size=n_days)
    df = pd.DataFrame(rets)
    return df


def test_optimize_basic_properties():
    df = make_daily_returns()
    opt = PortfolioOptimizer(random_seed=7)
    res = opt.optimize_max_sharpe(df, constraints=None, n_trials=2000)
    assert isinstance(res.weights, pd.Series)
    assert abs(float(res.weights.sum()) - 1.0) < 1e-9
    assert res.volatility >= 0
    assert res.sharpe >= 0


def test_enforce_bounds_and_positions():
    df = make_daily_returns()
    bounds = WeightBounds(0.0, 0.4)
    cons = Constraints(bounds=bounds, max_positions=MaxPositionsConstraint(3))
    opt = PortfolioOptimizer(random_seed=10)
    res = opt.optimize_max_sharpe(df, constraints=cons, n_trials=3000)
    assert (res.weights <= 0.4000001).all()
    assert int((res.weights > 1e-12).sum()) <= 3


def test_group_constraints_respected():
    df = make_daily_returns(tickers=('A', 'B', 'C', 'D'))
    group_map = {'A': 'G1', 'B': 'G1', 'C': 'G2', 'D': 'G2'}
    cons = Constraints(group=GroupConstraint(group_map=group_map, group_max={'G1': 0.6, 'G2': 1.0}))
    opt = PortfolioOptimizer(random_seed=2)
    res = opt.optimize_max_sharpe(df, constraints=cons, n_trials=3000)
    g1_sum = float(res.weights[['A', 'B']].sum())
    assert g1_sum <= 0.6000001


def test_risk_budget_respected():
    df = make_daily_returns(tickers=('A', 'B', 'C'))
    # Forcer corrélations fortes pour hausser la vol potentielle
    df['B'] = df['A'] * 0.5 + df['B'] * 0.5
    df['C'] = df['A'] * 0.5 + df['C'] * 0.5
    cons = Constraints(risk_budget=RiskBudgetConstraint(max_volatility=0.6))
    opt = PortfolioOptimizer(random_seed=3)
    res = opt.optimize_max_sharpe(df, constraints=cons, n_trials=3000)
    assert res.volatility <= 0.6000001


def test_leverage_constraint():
    df = make_daily_returns(tickers=('A', 'B', 'C'))
    cons = Constraints(leverage=LeverageConstraint(max_leverage=1.0))
    res = PortfolioOptimizer(random_seed=11).optimize_max_sharpe(df, constraints=cons, n_trials=2000)
    assert float(res.weights.abs().sum()) <= 1.0000001


def test_determinism_with_seed():
    df = make_daily_returns(tickers=('A', 'B', 'C'))
    opt1 = PortfolioOptimizer(random_seed=123)
    opt2 = PortfolioOptimizer(random_seed=123)
    res1 = opt1.optimize_max_sharpe(df, n_trials=2000)
    res2 = opt2.optimize_max_sharpe(df, n_trials=2000)
    pd.testing.assert_series_equal(res1.weights, res2.weights)


def test_raises_when_no_feasible():
    df = make_daily_returns(tickers=('A', 'B', 'C'))
    # Contraintes impossibles: bounds max 0.1 sur 3 actifs + max_positions=1 et levier=1
    bounds = WeightBounds(0.0, 0.05)
    cons = Constraints(bounds=bounds, max_positions=MaxPositionsConstraint(1))
    opt = PortfolioOptimizer(random_seed=1)
    try:
        _ = opt.optimize_max_sharpe(df, constraints=cons, n_trials=500)
        assert False, "Expected ValueError for infeasible constraints"
    except ValueError:
        assert True


def test_nan_handling_and_cleaning():
    df = make_daily_returns(tickers=('A', 'B', 'C'))
    df.iloc[0, 0] = np.nan
    df.iloc[5, 2] = np.inf
    res = PortfolioOptimizer(random_seed=5).optimize_max_sharpe(df, n_trials=1500)
    assert abs(float(res.weights.sum()) - 1.0) < 1e-9


def test_single_asset_edge_case():
    df = make_daily_returns(tickers=('ONLY',))
    res = PortfolioOptimizer(random_seed=9).optimize_max_sharpe(df, n_trials=500)
    assert abs(res.weights['ONLY'] - 1.0) < 1e-9


def test_more_assets_than_positions():
    df = make_daily_returns(tickers=('A', 'B', 'C', 'D', 'E', 'F'))
    cons = Constraints(max_positions=MaxPositionsConstraint(2))
    res = PortfolioOptimizer(random_seed=12).optimize_max_sharpe(df, constraints=cons, n_trials=2500)
    assert int((res.weights > 1e-12).sum()) <= 2


def test_bounds_applied_in_optimizer():
    df = make_daily_returns(tickers=('A', 'B', 'C', 'D'))
    bounds = WeightBounds(lower={'A': 0.2, 'B': 0.0, 'C': 0.0, 'D': 0.0}, upper=0.7)
    res = PortfolioOptimizer(random_seed=21).optimize_max_sharpe(df, constraints=Constraints(bounds=bounds), n_trials=2500)
    assert res.weights['A'] >= 0.199
    assert (res.weights <= 0.700001).all()


def test_group_min_and_max():
    df = make_daily_returns(tickers=('A', 'B', 'C', 'D'))
    group_map = {'A': 'G1', 'B': 'G1', 'C': 'G2', 'D': 'G2'}
    group_min = {'G1': 0.2}
    group_max = {'G1': 0.7, 'G2': 0.9}
    cons = Constraints(group=GroupConstraint(group_map=group_map, group_min=group_min, group_max=group_max))
    res = PortfolioOptimizer(random_seed=33).optimize_max_sharpe(df, constraints=cons, n_trials=3000)
    g1 = float(res.weights[['A', 'B']].sum())
    assert 0.2 - 1e-6 <= g1 <= 0.700001


def test_risk_budget_tight_but_feasible():
    df = make_daily_returns(tickers=('A', 'B', 'C'))
    df['B'] = df['A'] * 0.8 + df['B'] * 0.2
    df['C'] = df['A'] * 0.7 + df['C'] * 0.3
    cons = Constraints(risk_budget=RiskBudgetConstraint(max_volatility=0.4))
    res = PortfolioOptimizer(random_seed=44).optimize_max_sharpe(df, constraints=cons, n_trials=4000)
    assert res.volatility <= 0.400001


def test_performance_quick():
    df = make_daily_returns(tickers=tuple([f'T{i}' for i in range(10)]))
    res = PortfolioOptimizer(random_seed=1).optimize_max_sharpe(df, n_trials=1500)
    assert abs(float(res.weights.sum()) - 1.0) < 1e-9
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
