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
