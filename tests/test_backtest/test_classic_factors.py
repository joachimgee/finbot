"""Tests des facteurs classiques (offline, sur prix synthétiques)."""
import numpy as np
import pandas as pd

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)


def _prices(n_dates=400, n_assets=10, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    cols = [f"T{i}" for i in range(n_assets)]
    rets = rng.standard_normal((n_dates, n_assets)) * 0.01
    prices = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=cols)
    return prices


def test_returns_shape_and_first_nan():
    p = _prices()
    r = daily_returns(p)
    assert r.shape == p.shape
    assert r.iloc[0].isna().all()  # pas de rendement au 1er jour


def test_factor_panels_present_and_aligned():
    p = _prices()
    f = compute_classic_factors(p)
    assert set(f) == {"momentum_12_1", "reversal_5", "low_vol"}
    for panel in f.values():
        assert panel.shape == p.shape
        assert list(panel.columns) == list(p.columns)


def test_factors_only_use_past():
    """Chaque facteur en t ne doit dépendre que des prix <= t : tronquer le futur
    ne change pas les valeurs passées."""
    p = _prices(n_dates=400, seed=1)
    f_full = compute_classic_factors(p)
    cutoff = 300
    f_trunc = compute_classic_factors(p.iloc[:cutoff])
    for name in f_full:
        a = f_full[name].iloc[:cutoff]
        b = f_trunc[name]
        # comparer les valeurs communes (hors NaN de warm-up) via indexation numpy
        common = (a.notna() & b.notna()).values
        assert np.allclose(a.values[common], b.values[common])


def test_low_vol_sign():
    """low_vol doit être plus élevé (moins négatif) pour l'actif le moins volatil."""
    dates = pd.date_range("2020-01-01", periods=120, freq="B")
    calm = pd.Series(100 * np.exp(np.cumsum(np.full(120, 0.0001))), index=dates)
    wild = pd.Series(100 * np.exp(np.cumsum(np.tile([0.05, -0.05], 60))), index=dates)
    p = pd.DataFrame({"CALM": calm, "WILD": wild})
    lv = compute_classic_factors(p)["low_vol"].iloc[-1]
    assert lv["CALM"] > lv["WILD"]
