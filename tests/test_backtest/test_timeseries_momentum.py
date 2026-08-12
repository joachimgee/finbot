"""Time-series momentum (Tier 2) — score vol-normalisé, sans look-ahead."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.timeseries_momentum import tsmom_ensemble_score


def _prices(drift: float, n: int = 320, seed: int = 0, cols=("A", "B", "C")) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {c: 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, n))) for c in cols}, index=idx)


def test_score_shape_and_labels_preserved() -> None:
    px = _prices(0.0005)
    score = tsmom_ensemble_score(px)
    assert score.shape == px.shape
    assert list(score.columns) == list(px.columns)
    assert score.index.equals(px.index)


def test_uptrend_scores_positive_downtrend_negative() -> None:
    up = tsmom_ensemble_score(_prices(0.003, seed=1)).iloc[-1]
    down = tsmom_ensemble_score(_prices(-0.003, seed=2)).iloc[-1]
    assert (up > 0).all()
    assert (down < 0).all()


def test_no_lookahead_future_price_does_not_change_past_score() -> None:
    """Modifier un prix à t ne doit pas changer le score à t (n'utilise que ≤ t)."""
    px = _prices(0.001, seed=3)
    base = tsmom_ensemble_score(px)
    shocked = px.copy()
    shocked.iloc[260, 0] *= 1.5  # choc à t=260 sur A
    after = tsmom_ensemble_score(shocked)
    # Le score à t=260 pour A n'utilise que des prix <= 260 avec shift -> inchangé
    # aux dates strictement antérieures.
    assert base["A"].iloc[:260].equals(after["A"].iloc[:260])


def test_vol_normalization_makes_trends_comparable() -> None:
    """À dérive égale, un titre calme obtient un score de tendance plus élevé
    qu'un titre agité (même tendance mais plus de bruit -> t-stat plus faible)."""
    rng = np.random.default_rng(4)
    idx = pd.date_range("2023-01-01", periods=320, freq="B")
    calm = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.005, 320)))
    wild = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, 320)))
    px = pd.DataFrame({"CALM": calm, "WILD": wild}, index=idx)
    score = tsmom_ensemble_score(px).iloc[-1]
    assert score["CALM"] > score["WILD"]


def test_insufficient_history_is_nan() -> None:
    px = _prices(0.001, n=40)  # < plus long lookback (252)
    score = tsmom_ensemble_score(px)
    assert score.iloc[-1].isna().all()


def test_rejects_bad_lookbacks() -> None:
    px = _prices(0.001, n=60)
    with pytest.raises(ValueError):
        tsmom_ensemble_score(px, lookbacks=())
    with pytest.raises(ValueError):
        tsmom_ensemble_score(px, lookbacks=(21, 0))
