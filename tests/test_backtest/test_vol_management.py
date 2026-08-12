"""Gestion de volatilité (Tier 1) — risk-managed momentum, sans look-ahead."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.vol_management import (
    annualized_vol,
    apply_vol_target,
    sharpe,
    vol_target_leverage,
)


def test_annualized_vol_constant_series() -> None:
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0, 0.01, 400))
    v = annualized_vol(r, lookback=126).dropna()
    # ~0.01 quotidien * sqrt(252) ≈ 0.159
    assert v.iloc[-1] == pytest.approx(0.01 * np.sqrt(252), rel=0.25)


def test_leverage_has_no_lookahead() -> None:
    """Le levier à t ne dépend pas du rendement à t (utilise <= t-1)."""
    rng = np.random.default_rng(2)
    r = pd.Series(rng.normal(0, 0.01, 300))
    lev = vol_target_leverage(r, target_vol=0.10, lookback=126)
    # Modifier r[t] ne doit pas changer lev[t] (il n'utilise que le passé).
    r2 = r.copy()
    r2.iloc[200] = 5.0  # choc énorme à t=200
    lev2 = vol_target_leverage(r2, target_vol=0.10, lookback=126)
    assert lev.iloc[200] == pytest.approx(lev2.iloc[200])   # inchangé
    assert lev.iloc[201] != pytest.approx(lev2.iloc[201])   # le passé bouge à t+1


def test_leverage_capped_and_warmup_is_one() -> None:
    rng = np.random.default_rng(3)
    r = pd.Series(rng.normal(0, 0.02, 300))
    lev = vol_target_leverage(r, target_vol=0.10, lookback=126, max_leverage=2.0)
    assert lev.max() <= 2.0 + 1e-9
    assert (lev >= 0).all()
    assert lev.iloc[0] == pytest.approx(1.0)  # warm-up -> pas de levier


def test_higher_vol_gets_lower_leverage() -> None:
    calm = np.random.default_rng(4).normal(0, 0.005, 300)
    wild = np.random.default_rng(5).normal(0, 0.03, 300)
    lev_calm = vol_target_leverage(pd.Series(calm), target_vol=0.10).iloc[-1]
    lev_wild = vol_target_leverage(pd.Series(wild), target_vol=0.10).iloc[-1]
    assert lev_wild < lev_calm


def test_vol_target_improves_sharpe_on_clustered_series() -> None:
    """Sur une série à vol groupée (calme→krach→calme), le ciblage améliore le Sharpe."""
    rng = np.random.default_rng(6)
    r = pd.Series(np.concatenate([
        rng.normal(0.0005, 0.008, 400),
        rng.normal(-0.001, 0.04, 120),   # cluster de krach
        rng.normal(0.0005, 0.008, 400),
    ]))
    scaled, lev = apply_vol_target(r, target_vol=0.10, lookback=126)
    assert sharpe(scaled) > sharpe(r)
    # Le levier est réduit pendant le krach (vol haute) vs le calme.
    assert lev.iloc[400:520].mean() < lev.iloc[100:300].mean()


def test_sharpe_degenerate() -> None:
    assert sharpe(pd.Series([0.01])) == 0.0        # < 2 points
    assert sharpe(pd.Series([0.01, 0.01, 0.01])) == 0.0  # std 0


# --- Overlay ex-ante (sizing portefeuille) ----------------------------------

def _close(vol: float, n: int = 300, seed: int = 0, drift: float = 0.0003, cols=("A", "B", "C")):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {c: 100 * np.exp(np.cumsum(rng.normal(drift, vol, n))) for c in cols}, index=idx)


def test_ex_ante_vol_higher_for_wilder_names() -> None:
    from financial_analyzer.backtest.vol_management import ex_ante_vol
    w = {"A": 0.4, "B": 0.3, "C": 0.3}
    calm = ex_ante_vol(w, _close(0.008, seed=1))
    wild = ex_ante_vol(w, _close(0.03, seed=2))
    assert calm is not None and wild is not None and wild > calm


def test_ex_ante_vol_none_on_insufficient_data() -> None:
    from financial_analyzer.backtest.vol_management import ex_ante_vol
    tiny = _close(0.01, n=5)
    assert ex_ante_vol({"A": 1.0}, tiny) is None


def test_exposure_de_risk_only_by_default() -> None:
    """max_exposure=1.0 => l'overlay ne peut que réduire (jamais > 1)."""
    from financial_analyzer.backtest.vol_management import exposure_scalar
    w = {"A": 0.5, "B": 0.5}
    # Titres très volatils -> exposition réduite bien en dessous de 1.
    exp, diag = exposure_scalar(w, _close(0.03, seed=3), target_vol=0.10, max_exposure=1.0)
    assert 0.0 <= exp <= 1.0 and diag["vol_scalar"] <= 1.0


def test_trend_scalar_risk_off_on_downtrend() -> None:
    from financial_analyzer.backtest.vol_management import trend_scalar
    up = _close(0.01, seed=4, drift=0.002)
    down = _close(0.01, seed=5, drift=-0.002)
    assert trend_scalar(up, ma_window=200) == 1.0
    assert trend_scalar(down, ma_window=200, risk_off_factor=0.5) == 0.5
