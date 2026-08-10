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
    assert set(f) == {
        "momentum_12_1",
        "momentum_6_1",
        "reversal_5",
        "reversal_21",
        "low_vol",
        "low_vol_60",
        "max_lottery",
        "high_52w",
    }
    for panel in f.values():
        assert panel.shape == p.shape
        assert list(panel.columns) == list(p.columns)


def test_high_52w_in_unit_range():
    """La proximité au plus-haut 52 semaines est dans (0, 1] (prix / plus-haut)."""
    p = _prices(n_dates=400, seed=3)
    h = compute_classic_factors(p)["high_52w"]
    vals = h.values[~np.isnan(h.values)]
    assert (vals > 0).all()
    assert (vals <= 1.0 + 1e-9).all()


def test_max_lottery_sign():
    """max_lottery doit être plus bas (plus négatif) pour l'actif à gros pic."""
    dates = pd.date_range("2020-01-01", periods=60, freq="B")
    steady = pd.Series(100 * np.exp(np.cumsum(np.full(60, 0.0005))), index=dates)
    spikes = np.full(60, 0.0005)
    spikes[50] = 0.20  # rendement « loterie », dans la fenêtre 21j du dernier jour
    lottery = pd.Series(100 * np.exp(np.cumsum(spikes)), index=dates)
    p = pd.DataFrame({"STEADY": steady, "LOTTERY": lottery})
    ml = compute_classic_factors(p)["max_lottery"].iloc[-1]
    assert ml["LOTTERY"] < ml["STEADY"]


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
