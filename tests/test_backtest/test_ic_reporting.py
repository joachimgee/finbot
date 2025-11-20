import numpy as np
import pandas as pd
from financial_analyzer.backtest.ic_reporting import compute_cross_sectional_ic, ic_summary, compute_ic_decay


def test_ic_reporting_basic_positive_ic():
    # Construire facteurs corrélés positivement aux retours futurs
    rng = np.random.default_rng(0)
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    assets = [f"S{i}" for i in range(20)]
    base = rng.normal(0, 1, size=(len(dates), len(assets)))
    factors = pd.DataFrame(base, index=dates, columns=assets)
    future_noise = rng.normal(0, 0.5, size=(len(dates), len(assets)))
    fwd = pd.DataFrame(base * 0.2 + future_noise, index=dates, columns=assets)

    ic = compute_cross_sectional_ic(factors, fwd, method="spearman")
    summ = ic_summary(ic)
    assert summ["mean"] > 0.05
    assert 0.0 < summ["hit_rate"] < 1.0


def test_ic_decay_monotonic_drop_expected():
    rng = np.random.default_rng(1)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    assets = ["A","B","C","D","E"]
    base = rng.normal(0, 1, size=(len(dates), len(assets)))
    factors = pd.DataFrame(base, index=dates, columns=assets)
    returns = pd.DataFrame(rng.normal(0, 0.3, size=(len(dates), len(assets))), index=dates, columns=assets)
    # Injecter relation courte horizon 1
    returns.iloc[:-1] += factors.iloc[1:].values * 0.2

    decay = compute_ic_decay(factors, returns, max_horizon=4)
    # On attend une décroissance en magnitude
    assert abs(decay.iloc[0]) >= abs(decay.iloc[-1])
