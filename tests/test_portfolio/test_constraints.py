import math
from typing import Dict

import numpy as np
import pandas as pd

from financial_analyzer.portfolio.constraints import (
    Constraints,
    GroupConstraint,
    LeverageConstraint,
    MaxPositionsConstraint,
    MaxTurnoverConstraint,
    RiskBudgetConstraint,
    WeightBounds,
)


def test_bounds_enforcement_global():
    w = pd.Series([0.5, 0.6, -0.1], index=['A', 'B', 'C'])
    cons = Constraints(bounds=WeightBounds(lower=0.0, upper=0.5))
    w2 = cons.enforce_bounds(w)
    assert (w2 >= -1e-12).all() and (w2 <= 0.5 + 1e-12).all()
    assert abs(float(w2.sum()) - 1.0) < 1e-9


def test_bounds_enforcement_per_asset():
    bounds = WeightBounds(lower={'A': 0.1, 'B': 0.0}, upper={'A': 0.2, 'B': 0.8, 'C': 0.5})
    w = pd.Series([0.05, 0.9, 0.2], index=['A', 'B', 'C'])
    w2 = Constraints(bounds=bounds).enforce_bounds(w)
    assert 0.099 <= w2['A'] <= 0.201
    assert w2['B'] <= 0.801
    assert w2['C'] <= 0.501
    assert abs(float(w2.sum()) - 1.0) < 1e-9


def test_max_positions_true():
    cons = Constraints(max_positions=MaxPositionsConstraint(max_positions=2))
    w = pd.Series([0.5, 0.5, 0.0], index=['A', 'B', 'C'])
    assert cons.check_max_positions(w)


def test_max_positions_false():
    cons = Constraints(max_positions=MaxPositionsConstraint(max_positions=2))
    w = pd.Series([0.4, 0.4, 0.2], index=['A', 'B', 'C'])
    assert not cons.check_max_positions(w)


def test_group_bounds_ok():
    group_map = {'A': 'Tech', 'B': 'Tech', 'C': 'Health'}
    cons = Constraints(group=GroupConstraint(group_map=group_map, group_max={'Tech': 0.9}))
    w = pd.Series([0.45, 0.45, 0.10], index=['A', 'B', 'C'])
    assert cons.check_group_bounds(w)


def test_group_bounds_violation():
    group_map = {'A': 'Tech', 'B': 'Tech', 'C': 'Health'}
    cons = Constraints(group=GroupConstraint(group_map=group_map, group_max={'Tech': 0.8}))
    w = pd.Series([0.45, 0.45, 0.10], index=['A', 'B', 'C'])
    assert not cons.check_group_bounds(w)


def test_turnover_ok():
    prev = {'A': 0.5, 'B': 0.3, 'C': 0.2}
    cons = Constraints(turnover=MaxTurnoverConstraint(previous_weights=prev, max_turnover=0.6))
    w = pd.Series([0.4, 0.4, 0.2], index=['A', 'B', 'C'])
    assert cons.check_turnover(w)


def test_turnover_violation():
    prev = {'A': 0.5, 'B': 0.3, 'C': 0.2}
    cons = Constraints(turnover=MaxTurnoverConstraint(previous_weights=prev, max_turnover=0.1))
    w = pd.Series([0.4, 0.4, 0.2], index=['A', 'B', 'C'])
    assert not cons.check_turnover(w)


def test_leverage_ok():
    cons = Constraints(leverage=LeverageConstraint(max_leverage=1.0))
    w = pd.Series([0.4, 0.3, 0.3], index=['A', 'B', 'C'])
    assert cons.check_leverage(w)


def test_leverage_violation():
    cons = Constraints(leverage=LeverageConstraint(max_leverage=0.9))
    w = pd.Series([0.4, 0.3, 0.3], index=['A', 'B', 'C'])
    assert not cons.check_leverage(w)


def test_risk_budget_ok():
    cons = Constraints(risk_budget=RiskBudgetConstraint(max_volatility=0.5))
    w = pd.Series([0.5, 0.5], index=['A', 'B'])
    cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.04]], index=['A', 'B'], columns=['A', 'B'])
    assert cons.check_risk_budget(w, cov)


def test_risk_budget_violation():
    cons = Constraints(risk_budget=RiskBudgetConstraint(max_volatility=0.1))
    w = pd.Series([0.5, 0.5], index=['A', 'B'])
    cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.04]], index=['A', 'B'], columns=['A', 'B'])
    assert not cons.check_risk_budget(w, cov)


def test_is_feasible_true():
    prev = {'A': 0.4, 'B': 0.4, 'C': 0.2}
    cons = Constraints(
        bounds=WeightBounds(0.0, 0.8),
        max_positions=MaxPositionsConstraint(3),
        group=GroupConstraint(group_map={'A': 'G1', 'B': 'G1', 'C': 'G2'}, group_max={'G1': 0.9}),
        turnover=MaxTurnoverConstraint(previous_weights=prev, max_turnover=0.6),
        leverage=LeverageConstraint(1.0),
        risk_budget=RiskBudgetConstraint(max_volatility=0.8),
    )
    w = pd.Series([0.4, 0.4, 0.2], index=['A', 'B', 'C'])
    cov = pd.DataFrame(np.eye(3) * 0.04, index=w.index, columns=w.index)
    assert cons.is_feasible(w, cov)


def test_is_feasible_false_sum():
    cons = Constraints(bounds=WeightBounds(0.0, 1.0))
    w = pd.Series([0.4, 0.4, 0.3], index=['A', 'B', 'C'])
    assert not cons.is_feasible(w)


def test_bounds_invalid_raises():
    cons = Constraints(bounds=WeightBounds(lower={'A': 0.6}, upper={'A': 0.4}))
    w = pd.Series([0.7, 0.2, 0.1], index=['A', 'B', 'C'])
    try:
        _ = cons.enforce_bounds(w)
        assert False, "Expected ValueError"
    except ValueError:
        assert True
import numpy as np
import pandas as pd
import pytest

from financial_analyzer.portfolio.constraints import PortfolioConstraints


def test_build_bounds_default_long_only():
    pc = PortfolioConstraints()
    tickers = ['A', 'B', 'C']
    bounds = pc.build_bounds(tickers)
    assert bounds == [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0)]


def test_build_bounds_with_global_min_max():
    pc = PortfolioConstraints()
    pc.add_allocation_limits(min_weight=0.05, max_weight=0.6)
    tickers = ['A', 'B', 'C', 'D']
    bounds = pc.build_bounds(tickers)
    for lb, ub in bounds:
        assert lb == pytest.approx(0.05)
        assert ub == pytest.approx(0.6)


def test_build_bounds_asset_specific_overrides():
    pc = PortfolioConstraints()
    pc.add_allocation_limits(min_weight=0.0, max_weight=0.5)
    pc.add_asset_bound('B', 0.1, 0.2)
    tickers = ['A', 'B', 'C']
    bounds = pc.build_bounds(tickers)
    assert bounds[1] == (0.1, 0.2)
    assert bounds[0] == (0.0, 0.5)
    assert bounds[2] == (0.0, 0.5)


def test_invalid_bounds_raises():
    pc = PortfolioConstraints()
    with pytest.raises(ValueError):
        pc.add_asset_bound('X', 0.7, 0.6)

    with pytest.raises(ValueError):
        pc.add_allocation_limits(min_weight=0.6, max_weight=0.5)


def test_long_only_toggle():
    pc = PortfolioConstraints()
    pc.add_long_only(False)
    tickers = ['A', 'B']
    bounds = pc.build_bounds(tickers)
    # Allow shorting down to -1 if no min bound provided
    assert bounds == [(-1.0, 1.0), (-1.0, 1.0)]


def test_sector_constraint_function_respects_limit():
    pc = PortfolioConstraints()
    pc.add_sector_constraint({'Tech': 0.3}, {'A': 'Tech', 'B': 'Tech', 'C': 'Other'})
    tickers = ['A', 'B', 'C']
    funcs = pc.sector_constraints_functions(tickers)
    assert len(funcs) == 1
    f = funcs[0]
    # Sum of Tech weights <= 0.3 should satisfy f(w) >= 0
    w = np.array([0.15, 0.10, 0.75])
    assert f(w) >= -1e-9
    # Violating should give negative value
    w2 = np.array([0.2, 0.2, 0.6])
    assert f(w2) < 0


def test_concentration_constraint_function():
    pc = PortfolioConstraints()
    pc.add_concentration_limit(0.35)
    func = pc.concentration_constraint_function()
    assert func is not None
    # Equi-weighted 4 assets: HHI = 4 * 0.25^2 = 0.25 <= 0.35
    w_ok = np.array([0.25, 0.25, 0.25, 0.25])
    assert func(w_ok) <= 0
    # Concentrated: 0.6^2 + 0.4^2 = 0.52 > 0.35
    w_bad = np.array([0.6, 0.4, 0.0, 0.0])
    assert func(w_bad) > 0


def test_custom_constraint_is_registered_and_called():
    pc = PortfolioConstraints()

    calls = {'count': 0}

    def custom(w, names):
        calls['count'] += 1
        # Contrainte: poids de 'A' <= 0.4  -> return w_A - 0.4 <= 0
        idx = names.index('A')
        return float(w[idx] - 0.4)

    pc.add_custom_constraint(custom)
    assert len(pc.custom_funcs) == 1

    # Simulate call as optimizer would
    w = np.array([0.3, 0.7])
    val = pc.custom_funcs[0](w, ['A', 'B'])
    assert val <= 0
    assert calls['count'] == 1


def test_sector_constraint_ignores_missing_tickers():
    pc = PortfolioConstraints()
    pc.add_sector_constraint({'Tech': 0.3}, {'X': 'Tech'})
    funcs = pc.sector_constraints_functions(['A', 'B'])
    # No overlapping tickers -> no constraints actually returned
    assert funcs == []
