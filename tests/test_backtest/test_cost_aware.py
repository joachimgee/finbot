"""Rééquilibrage cost-aware (#4) — bande de non-transaction."""
from __future__ import annotations

import numpy as np
import pandas as pd

from financial_analyzer.backtest.cost_aware import apply_no_trade_band


def test_band_zero_is_noop() -> None:
    tgt = pd.Series({"A": 0.5, "B": -0.5})
    prev = pd.Series({"A": 0.1, "B": -0.1})
    pd.testing.assert_series_equal(apply_no_trade_band(tgt, prev, 0.0), tgt)


def test_none_prev_returns_target() -> None:
    tgt = pd.Series({"A": 0.5, "B": -0.5})
    pd.testing.assert_series_equal(apply_no_trade_band(tgt, None, 0.05), tgt)


def test_small_move_is_held_large_move_trades() -> None:
    prev = pd.Series({"A": 0.50, "B": 0.30, "C": 0.20})
    tgt = pd.Series({"A": 0.52, "B": 0.10, "C": 0.20})  # A:+0.02, B:-0.20, C:0
    out = apply_no_trade_band(tgt, prev, band=0.05)
    assert out["A"] == 0.50  # mouvement 0.02 < bande -> tenu
    assert out["B"] == 0.10  # mouvement 0.20 >= bande -> tradé au cible
    assert out["C"] == 0.20  # inchangé


def test_band_reduces_turnover_below_it() -> None:
    """Somme des mouvements sous la bande : aucun trade ; au-dessus : trade plein."""
    prev = pd.Series({"A": 0.4, "B": 0.4, "C": 0.2})
    tgt = pd.Series({"A": 0.41, "B": 0.39, "C": 0.20})  # tous |Δ| ≤ 0.01
    out = apply_no_trade_band(tgt, prev, band=0.05)
    assert float((out - prev).abs().sum()) == 0.0  # rien ne bouge


def test_band_reduces_cumulative_turnover_on_continuous_weights() -> None:
    """Cas d'usage réel (poids CONTINUS, façon Black-Litterman du pipeline live) :
    une cible qui dérive un peu à chaque pas -> la bande coupe le turnover cumulé.

    (Sur un book quantile équipondéré, les poids sont discrets 0/±step ; la bande
    y est ~sans effet — elle est faite pour des poids continus, cf. docstring.)"""
    rng = np.random.default_rng(3)
    names = ["A", "B", "C", "D", "E"]
    prev = pd.Series(1.0 / len(names), index=names)
    base_prev, band_prev = prev.copy(), prev.copy()
    base_to, band_to = 0.0, 0.0
    for _ in range(60):
        target = prev + pd.Series(rng.normal(0, 0.01, len(names)), index=names)  # dérive
        target = target / target.sum()
        base_to += float((target - base_prev).abs().sum())
        base_prev = target
        banded = apply_no_trade_band(target, band_prev, band=0.02)
        band_to += float((banded - band_prev).abs().sum())
        band_prev = banded
    assert band_to < base_to * 0.7  # nette réduction du turnover cumulé
