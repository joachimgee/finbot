"""Tests unitaires pour FinBotBacktester.

Couverture: init, rebalance, stop-loss et take-profit.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from financial_analyzer.backtesting.finbot_strategy import (
    FinBotBacktester,
    RiskConfig,
)


def make_prices(trend: float = 0.0, vol: float = 0.01, periods: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(123)
    idx = pd.date_range("2024-01-01", periods=periods, freq="B")
    rets = rng.normal(trend, vol, len(idx))
    prices = 100 * (1 + pd.Series(rets, index=idx)).cumprod()
    return pd.DataFrame({"Close": prices})


def make_data(tickers=("AAA", "BBB", "CCC"), periods: int = 120) -> Dict[str, pd.DataFrame]:
    return {t: make_prices(0.0005 + 0.0002 * i, 0.01 + 0.002 * i, periods) for i, t in enumerate(tickers)}


def run_steps(bt: FinBotBacktester, steps: int) -> None:
    bt.init()
    for i in range(steps):
        bt.next(i)


def test_init_and_equity_progression():
    data = make_data(periods=30)
    bt = FinBotBacktester(data=data, lookback_days=10)
    run_steps(bt, steps=min(len(df) for df in data.values()))
    eq = bt.equity()
    assert not eq.empty
    assert eq.iloc[0] > 0
    assert eq.iloc[-1] > 0


def test_rebalance_respects_max_position():
    data = make_data(periods=80)
    risk = RiskConfig(max_position=0.25, rebalance_period=5)
    bt = FinBotBacktester(data=data, lookback_days=20, risk=risk)
    run_steps(bt, steps=min(len(df) for df in data.values()))
    pos = bt.positions()
    assert all(0.0 <= w <= 0.25 + 1e-9 for w in pos.values())
    assert 0.0 <= sum(pos.values()) <= 1.0 + 1e-9


def test_stop_loss_triggers_close():
    # Données avec chute brutale > 20%
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    prices = pd.Series([100, 101, 102, 80, 79, 78, 77, 76, 75, 74], index=idx)
    data = {"SL": pd.DataFrame({"Close": prices})}
    risk = RiskConfig(stop_loss_pct=0.15, rebalance_period=10)
    bt = FinBotBacktester(data=data, lookback_days=3, risk=risk)
    run_steps(bt, steps=len(idx))
    # Après forte baisse, la position doit être coupée
    assert bt.positions().get("SL", 0.0) <= 1e-9


def test_take_profit_scales_down_and_resets_entry():
    # Setup: forte hausse puis stabilisation pour déclencher take-profit après entrée
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    # Phase 1: prix stable -> entrée
    base = [100 + 0.1 * i for i in range(10)]
    # Phase 2: spike > 60%
    spike = [170 + i for i in range(5)]
    # Phase 3: stabilisation -> prise de profit potentielle
    tail = [175 + 0.5 * i for i in range(15)]
    prices = pd.Series(base + spike + tail, index=idx)
    data = {"TP": pd.DataFrame({"Close": prices})}
    risk = RiskConfig(take_profit_pct=0.5, rebalance_period=5)
    bt = FinBotBacktester(data=data, lookback_days=5, risk=risk)
    run_steps(bt, steps=len(idx))
    w = bt.positions().get("TP", 0.0)
    # Après spike + rééquilibrage, la position doit être réduite mais non nulle
    assert 0.0 < w < 1.0


def test_equity_monotonic_when_all_cash():
    # Avec max_position=0, on reste en cash; equity doit rester constant
    data = make_data(periods=30)
    risk = RiskConfig(max_position=0.0, rebalance_period=1)
    bt = FinBotBacktester(data=data, lookback_days=10, risk=risk)
    run_steps(bt, steps=min(len(df) for df in data.values()))
    eq = bt.equity()
    assert (eq.diff().fillna(0.0) >= -1e-9).all()
