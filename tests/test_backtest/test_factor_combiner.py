"""Tests du combinateur de facteurs (B), validé out-of-sample via le harness A."""
import numpy as np
import pandas as pd

from financial_analyzer.backtest.factor_combiner import (
    FactorCombiner,
    walk_forward_combine,
)
from financial_analyzer.backtest.signal_evaluation import CostModel

CHEAP = CostModel(commission_bps=2, slippage_bps=1)


def _panel(rng, n_dates, n_assets, cols):
    dates = pd.date_range("2019-01-01", periods=n_dates, freq="B")
    return pd.DataFrame(rng.standard_normal((n_dates, n_assets)), index=dates, columns=cols)


def _one_good_two_noise(n_dates=700, n_assets=25, beta=0.035, noise=0.02, seed=0):
    """s_good prédit le rendement ; s_noise1/2 sont du bruit indépendant."""
    rng = np.random.default_rng(seed)
    cols = [f"A{i}" for i in range(n_assets)]
    s_good = _panel(rng, n_dates, n_assets, cols)
    s_noise1 = _panel(rng, n_dates, n_assets, cols)
    s_noise2 = _panel(rng, n_dates, n_assets, cols)
    rets = beta * s_good.shift(1).fillna(0.0) + rng.standard_normal((n_dates, n_assets)) * noise
    return {"good": s_good, "noise1": s_noise1, "noise2": s_noise2}, rets


def _two_good(n_dates=700, n_assets=25, beta=0.025, noise=0.02, seed=1):
    """s1 et s2 prédisent indépendamment -> diversification possible."""
    rng = np.random.default_rng(seed)
    cols = [f"A{i}" for i in range(n_assets)]
    s1 = _panel(rng, n_dates, n_assets, cols)
    s2 = _panel(rng, n_dates, n_assets, cols)
    rets = beta * (s1.shift(1).fillna(0.0) + s2.shift(1).fillna(0.0)) + rng.standard_normal((n_dates, n_assets)) * noise
    return {"s1": s1, "s2": s2}, rets


def test_combiner_learns_to_downweight_noise():
    panels, rets = _one_good_two_noise(seed=2)
    out = walk_forward_combine(panels, rets, n_splits=5, cost_model=CHEAP)
    # Le combinateur appris bat l'égal-poids hors échantillon (il ignore le bruit)
    assert out["combined"].ic_mean > out["equal_weight"].ic_mean
    # et il donne plus de poids à la bonne source
    w = out["avg_weights"].abs()
    assert w["good"] > w["noise1"] and w["good"] > w["noise2"]


def test_combiner_recovers_positive_oos_edge():
    panels, rets = _one_good_two_noise(seed=3)
    out = walk_forward_combine(panels, rets, n_splits=5, cost_model=CHEAP)
    assert out["combined"].ic_mean > 0.03
    assert out["combined"].ic_t_stat > 2


def test_combiner_diversifies_two_good_sources():
    panels, rets = _two_good(seed=4)
    out = walk_forward_combine(panels, rets, n_splits=5, cost_model=CHEAP)
    combined_ic = out["combined"].ic_mean
    # La combinaison bat chaque source seule (bénéfice de diversification)
    assert combined_ic > out["per_source"]["s1"].ic_mean
    assert combined_ic > out["per_source"]["s2"].ic_mean


def test_equal_weight_method_is_uniform():
    panels, rets = _two_good(seed=5)
    fwd = rets.shift(-1)
    ew = FactorCombiner(method="equal").fit(panels, fwd)
    assert abs(ew.weights_["s1"] - 0.5) < 1e-9
    assert abs(ew.weights_["s2"] - 0.5) < 1e-9


def test_combiner_deterministic():
    panels, rets = _one_good_two_noise(seed=6)
    a = walk_forward_combine(panels, rets, n_splits=4, cost_model=CHEAP)
    b = walk_forward_combine(panels, rets, n_splits=4, cost_model=CHEAP)
    assert a["combined"].ic_mean == b["combined"].ic_mean
    assert a["avg_weights"].round(9).equals(b["avg_weights"].round(9))
