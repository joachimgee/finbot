"""Momentum résiduel (Tier 2 ter) — orthogonalité marché, sans look-ahead."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.residual_momentum import (
    market_residuals,
    residual_momentum_score,
)


def _panel(n: int = 400, k: int = 8, seed: int = 0, beta_spread: float = 1.0) -> pd.DataFrame:
    """Panel avec un facteur marché commun + bruit idiosyncratique."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    mkt = rng.normal(0.0004, 0.01, n)
    cols = {}
    for j in range(k):
        beta = 0.5 + beta_spread * rng.random()
        idio = rng.normal(0.0002, 0.008, n)
        r = beta * mkt + idio
        cols[f"S{j}"] = 100 * np.exp(np.cumsum(r))
    return pd.DataFrame(cols, index=idx)


def test_residuals_are_orthogonal_to_market() -> None:
    """Le résidu doit être ~décorrélé du rendement marché (β retiré)."""
    px = _panel(seed=1)
    resid = market_residuals(px, beta_window=126).dropna()
    mkt = px.pct_change().mean(axis=1).loc[resid.index]
    for c in resid.columns:
        corr = np.corrcoef(resid[c], mkt)[0, 1]
        assert abs(corr) < 0.2  # exposition marché largement retirée


def test_score_shape_and_labels() -> None:
    px = _panel(seed=2)
    score = residual_momentum_score(px)
    assert score.shape == px.shape
    assert list(score.columns) == list(px.columns)


def test_no_lookahead_future_price_leaves_past_untouched() -> None:
    px = _panel(seed=3)
    base = residual_momentum_score(px)
    shocked = px.copy()
    shocked.iloc[350, 0] *= 1.4  # choc tardif sur S0
    after = residual_momentum_score(shocked)
    # Le score aux dates < 350 n'utilise que des prix passés -> inchangé.
    pd.testing.assert_frame_equal(base.iloc[:349], after.iloc[:349])


def test_insufficient_history_is_nan() -> None:
    px = _panel(n=60)
    assert residual_momentum_score(px).iloc[-1].isna().all()


def test_rejects_bad_windows() -> None:
    px = _panel(n=120)
    with pytest.raises(ValueError):
        residual_momentum_score(px, form=21, skip=21)
