"""Tearsheet de performance — compose métriques + robustesse."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
from financial_analyzer.backtest.tearsheet import format_tearsheet, tearsheet


def _predictive_panel(n_days=260, n_assets=40, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n_days, freq="B")
    cols = [f"A{i}" for i in range(n_assets)]
    returns = pd.DataFrame(rng.normal(0, 0.01, (n_days, n_assets)), index=idx, columns=cols)
    scores = returns.shift(-1) + rng.normal(0, 0.03, returns.shape)  # signal prédictif bruité
    return scores, returns


def _result(seed=1):
    scores, returns = _predictive_panel(seed=seed)
    return evaluate_signal(scores, returns, cost_model=CostModel())


def test_tearsheet_has_all_keys_and_finite_core() -> None:
    m = tearsheet(_result())
    for k in ("net_sharpe", "sortino", "calmar", "max_drawdown_pct", "psr",
              "ic_t_stat", "avg_turnover", "n_periods"):
        assert k in m
    # Sur un signal prédictif, ces métriques sont finies.
    assert math.isfinite(m["net_sharpe"])
    assert math.isfinite(m["sortino"])
    assert math.isfinite(m["max_drawdown_pct"])
    assert 0.0 <= m["psr"] <= 1.0


def test_max_drawdown_is_non_positive() -> None:
    assert tearsheet(_result())["max_drawdown_pct"] <= 0.0


def test_sortino_ge_or_relates_to_sharpe_sign() -> None:
    """Un edge net-positif a Sharpe et Sortino de même signe (positif)."""
    m = tearsheet(_result())
    if m["net_sharpe"] > 0:
        assert m["sortino"] > 0


def test_empty_result_is_all_nan_no_exception() -> None:
    from financial_analyzer.backtest.signal_evaluation import SignalEvalResult

    empty = SignalEvalResult(
        ic_mean=math.nan, ic_t_stat=math.nan, ic_hit_rate=math.nan,
        gross_sharpe=0.0, net_sharpe=0.0, gross_ann_return=0.0, net_ann_return=0.0,
        avg_turnover=0.0, n_periods=0,
    )
    m = tearsheet(empty)
    assert math.isnan(m["sortino"]) and math.isnan(m["calmar"])


def test_format_tearsheet_contains_labels() -> None:
    txt = format_tearsheet(_result(), name="momentum_test")
    assert "Tearsheet : momentum_test" in txt
    assert "Sortino" in txt and "Calmar" in txt and "Max drawdown" in txt
    assert "PSR" in txt
