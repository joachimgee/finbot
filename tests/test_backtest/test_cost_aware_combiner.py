"""Tests du combinateur cost-aware : bat le ridge/IC net de coûts quand un
facteur a un IC positif mais un turnover destructeur."""
import numpy as np
import pandas as pd

from financial_analyzer.backtest.factor_combiner import (
    CostAwareCombiner,
    walk_forward_combine,
    walk_forward_cost_aware,
)
from financial_analyzer.backtest.signal_evaluation import CostModel

# Coûts non négligeables : c'est ce qui rend le turnover coûteux.
COST = CostModel(commission_bps=8, slippage_bps=4)


def _slow_and_fast(n_dates=800, n_assets=25, beta=0.001, noise=0.015, phi=0.98, seed=0):
    """Deux facteurs à edge brut comparable mais turnover opposé :
    - slow : signal persistant AR(1) (classement stable -> turnover bas -> net positif).
    - fast : bruit i.i.d. quotidien (reshuffle chaque jour -> turnover max -> net négatif).
    Signaux volontairement FAIBLES (IC réaliste) pour que la différence de coûts
    soit ce qui départage les deux, comme sur données réelles.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    cols = [f"A{i}" for i in range(n_assets)]

    innov = rng.standard_normal((n_dates, n_assets)) * 0.15
    slow_arr = np.zeros((n_dates, n_assets))
    for t in range(1, n_dates):
        slow_arr[t] = phi * slow_arr[t - 1] + innov[t]
    slow = pd.DataFrame(slow_arr, index=dates, columns=cols)
    fast = pd.DataFrame(rng.standard_normal((n_dates, n_assets)), index=dates, columns=cols)

    def zc(df):
        return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1, ddof=0).replace(0, np.nan), axis=0).fillna(0.0)

    rets = (beta * zc(slow).shift(1).fillna(0.0)
            + beta * zc(fast).shift(1).fillna(0.0)
            + rng.standard_normal((n_dates, n_assets)) * noise)
    return {"slow": slow, "fast": fast}, rets


def test_cost_aware_beats_ridge_net_of_costs():
    panels, rets = _slow_and_fast(seed=1)
    ridge = walk_forward_combine(panels, rets, n_splits=5, cost_model=COST)
    ca = walk_forward_cost_aware(panels, rets, n_splits=5, cost_model=COST)
    # Le cost-aware doit obtenir un meilleur Sharpe NET que le ridge/IC
    assert ca["cost_aware"].net_sharpe > ridge["combined"].net_sharpe


def test_cost_aware_downweights_the_turnover_trap():
    panels, rets = _slow_and_fast(seed=2)
    ca = walk_forward_cost_aware(panels, rets, n_splits=5, cost_model=COST)
    w = ca["avg_weights"].abs()
    # Plus de poids sur le facteur lent (bas turnover) que sur le rapide (piège à coûts)
    assert w["slow"] > w["fast"]


def test_cost_aware_positive_net_sharpe_when_a_clean_signal_exists():
    panels, rets = _slow_and_fast(seed=3)
    ca = walk_forward_cost_aware(panels, rets, n_splits=5, cost_model=COST)
    assert ca["cost_aware"].net_sharpe > 0


def test_cost_aware_deterministic():
    panels, rets = _slow_and_fast(seed=4)
    a = walk_forward_cost_aware(panels, rets, n_splits=4, cost_model=COST)
    b = walk_forward_cost_aware(panels, rets, n_splits=4, cost_model=COST)
    assert a["cost_aware"].net_sharpe == b["cost_aware"].net_sharpe


def test_cost_aware_single_fit_predict_roundtrip():
    panels, rets = _slow_and_fast(n_dates=300, seed=5)
    c = CostAwareCombiner(cost_model=COST).fit(panels, rets)
    pred = c.predict(panels)
    assert pred.shape == rets.shape
    assert set(c.weights_.index) == {"slow", "fast"}
