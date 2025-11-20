import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from financial_analyzer.portfolio.constraints import PortfolioConstraints
from financial_analyzer.portfolio.optimizer import PortfolioOptimizer


def test_sector_caps_enforced_in_mv_optimization(tmp_path):
    # Synthétique: 6 actifs, 3 Tech / 3 Health
    tickers = [f"T{i}" for i in range(3)] + [f"H{i}" for i in range(3)]
    dates = pd.date_range("2024-01-01", periods=252, freq="B")
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0.0005, 0.01, size=(len(dates), len(tickers))), index=dates, columns=tickers)

    # Caps secteurs: Tech <= 0.4, Healthcare <= 0.7
    sector_limits = {"Technology": 0.4, "Healthcare": 0.7}
    mapping = {**{t: "Technology" for t in tickers[:3]}, **{t: "Healthcare" for t in tickers[3:]}}

    opt = PortfolioOptimizer(returns=rets, risk_free_rate=0.0)
    cons = PortfolioConstraints(sector_mapping=mapping)
    cons.add_allocation_limits(0.0, 1.0)
    cons.add_sector_constraint(sector_limits, mapping)
    opt.add_constraint(cons)

    res = opt._optimize_max_sharpe_mv()
    w = res["weights"] if isinstance(res, dict) else res.weights

    tech_weight = float(w.loc[tickers[:3]].sum())
    health_weight = float(w.loc[tickers[3:]].sum())

    assert abs(float(w.sum()) - 1.0) < 1e-6
    assert tech_weight <= 0.4000001
    assert health_weight <= 0.7000001


def test_turnover_constraint_custom_function():
    # 4 actifs, prev weights fortement concentrés sur A
    tickers = ["A", "B", "C", "D"]
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    rng = np.random.default_rng(1)
    rets = pd.DataFrame(rng.normal(0.0004, 0.012, size=(len(dates), len(tickers))), index=dates, columns=tickers)

    opt = PortfolioOptimizer(returns=rets, risk_free_rate=0.0)
    cons = PortfolioConstraints()
    cons.add_allocation_limits(0.0, 1.0)

    prev = pd.Series({"A": 0.8, "B": 0.2, "C": 0.0, "D": 0.0})
    cons.add_turnover_limit(previous_weights=prev, max_turnover=0.5)
    opt.add_constraint(cons)

    res = opt._optimize_max_sharpe_mv()
    w = res["weights"] if isinstance(res, dict) else res.weights

    # Vérifie somme 1 et turnover <= 0.5 + tol
    turnover = float((w - prev.reindex(w.index).fillna(0.0)).abs().sum())
    assert abs(float(w.sum()) - 1.0) < 1e-6
    assert turnover <= 0.500001
