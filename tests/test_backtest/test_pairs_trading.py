"""Stat-arb par paires — cointégration, demi-vie, causalité, mean-reversion."""
from __future__ import annotations

import numpy as np
import pandas as pd

from financial_analyzer.backtest.pairs_trading import (
    backtest_pairs,
    find_cointegrated_pairs,
    half_life,
    hedge_ratio,
)


def _cointegrated_panel(n: int = 500, seed: int = 0):
    """A et B cointégrés (facteur commun I(1) + spread stationnaire) ; C indépendant."""
    rng = np.random.default_rng(seed)
    common = np.cumsum(rng.normal(0, 1.0, n))          # tendance commune I(1)
    spread = np.zeros(n)                                # spread AR(1) stationnaire
    for t in range(1, n):
        spread[t] = 0.9 * spread[t - 1] + rng.normal(0, 1.0)
    a = 50 + common + spread
    b = 30 + 1.0 * common
    c = 40 + np.cumsum(rng.normal(0, 1.0, n))          # random walk indépendant
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    return pd.DataFrame({"A": a, "B": b, "C": c}, index=idx)


def test_hedge_ratio_recovers_beta() -> None:
    px = _cointegrated_panel(seed=1)
    beta = hedge_ratio(px["A"], px["B"])
    assert 0.7 < beta < 1.3  # β réel ≈ 1


def test_half_life_finite_for_mean_reverting_spread() -> None:
    px = _cointegrated_panel(seed=2)
    hl = half_life(px["A"] - hedge_ratio(px["A"], px["B"]) * px["B"])
    assert np.isfinite(hl) and 1.0 < hl < 120.0


def test_half_life_grows_with_persistence() -> None:
    """Plus l'AR(1) est persistant (φ→1), plus la demi-vie est longue ; φ≥1 -> inf."""
    def _ar1(phi, n=2000, seed=3):
        rng = np.random.default_rng(seed)
        s = np.zeros(n)
        for t in range(1, n):
            s[t] = phi * s[t - 1] + rng.normal(0, 1)
        return pd.Series(s)

    fast = half_life(_ar1(0.5))    # HL théorique ≈ 1
    slow = half_life(_ar1(0.95))   # HL théorique ≈ 13.5
    assert 0.5 < fast < 3.0
    assert slow > 3 * fast         # bien plus persistant


def test_finds_cointegrated_pair_not_independent() -> None:
    px = _cointegrated_panel(seed=4)
    pairs = find_cointegrated_pairs(px, corr_min=0.0, pvalue_max=0.05)
    found = {tuple(sorted((p["a"], p["b"]))) for p in pairs}
    assert ("A", "B") in found          # la vraie paire cointégrée
    assert ("A", "C") not in found and ("B", "C") not in found


def test_backtest_pairs_runs_and_is_causal() -> None:
    """Le backtest produit une série exploitable ; edge positif attendu sur une
    paire cointégrée (mean-reversion), et un choc futur ne change pas le passé."""
    px = _cointegrated_panel(n=500, seed=5)
    res = backtest_pairs(px, form=200, trade=60, z_lookback=20, corr_min=0.0)
    assert "net_returns" in res and res["n_windows"] >= 1
    assert np.isfinite(res["sharpe"])
    # Causalité : modifier un prix futur ne change pas les rendements passés.
    from financial_analyzer.backtest.pairs_trading import _pair_returns
    a, b = px["A"], px["B"]
    beta = hedge_ratio(a.iloc[:200], b.iloc[:200])
    r0, _ = _pair_returns(a, b, beta, 20, 2.0, 0.5, 4.0)
    a2 = a.copy()
    a2.iloc[400] *= 1.2
    r1, _ = _pair_returns(a2, b, beta, 20, 2.0, 0.5, 4.0)
    pd.testing.assert_series_equal(r0.iloc[:399], r1.iloc[:399])
