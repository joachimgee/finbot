"""Hierarchical Risk Parity — allocation robuste (López de Prado)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.portfolio.hrp import hrp_weights


def _returns(vols, n=400, seed=0, common=0.0):
    """Rendements ; ``vols`` par actif, facteur commun optionnel (corrélation)."""
    rng = np.random.default_rng(seed)
    mkt = rng.normal(0, 0.01, n)
    cols = {f"A{i}": common * mkt + (1 - common) * rng.normal(0, v, n)
            for i, v in enumerate(vols)}
    return pd.DataFrame(cols, index=pd.date_range("2023-01-01", periods=n, freq="B"))


def test_weights_sum_to_one_and_nonnegative() -> None:
    w = hrp_weights(_returns([0.01, 0.02, 0.015, 0.008], seed=1))
    assert w.sum() == pytest.approx(1.0, abs=1e-9)
    assert (w >= 0).all()
    assert set(w.index) == {"A0", "A1", "A2", "A3"}


def test_lower_vol_asset_gets_more_weight() -> None:
    """À corrélations comparables, l'actif le moins volatil pèse plus (risk parity)."""
    w = hrp_weights(_returns([0.005, 0.04], n=600, seed=2))
    assert w["A0"] > w["A1"]  # A0 bien moins volatil


def test_single_asset_gets_full_weight() -> None:
    w = hrp_weights(_returns([0.01], seed=3))
    assert w.to_dict() == {"A0": 1.0}


def test_zero_variance_columns_dropped() -> None:
    r = _returns([0.01, 0.02], seed=4)
    r["FLAT"] = 100.0  # variance nulle -> écarté
    w = hrp_weights(r)
    assert "FLAT" not in w.index
    assert w.sum() == pytest.approx(1.0, abs=1e-9)


def test_empty_returns_gives_empty() -> None:
    assert hrp_weights(pd.DataFrame()).empty


def test_diversifies_across_correlated_clusters() -> None:
    """Deux clusters corrélés en interne : HRP ne met pas tout sur un seul."""
    rng = np.random.default_rng(5)
    n = 500
    f1 = rng.normal(0, 0.01, n)
    f2 = rng.normal(0, 0.01, n)
    cols = {}
    for i in range(3):
        cols[f"G1_{i}"] = f1 + rng.normal(0, 0.003, n)  # cluster 1
    for i in range(3):
        cols[f"G2_{i}"] = f2 + rng.normal(0, 0.003, n)  # cluster 2
    r = pd.DataFrame(cols, index=pd.date_range("2023-01-01", periods=n, freq="B"))
    w = hrp_weights(r)
    g1 = w[[c for c in w.index if c.startswith("G1")]].sum()
    g2 = w[[c for c in w.index if c.startswith("G2")]].sum()
    # Les deux clusters reçoivent une part substantielle (pas de concentration).
    assert 0.25 < g1 < 0.75 and 0.25 < g2 < 0.75
