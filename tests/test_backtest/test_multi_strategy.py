"""Combinaison multi-stratégie — risk-weighting (inverse-vol / ERC)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.multi_strategy import (
    combine,
    inverse_vol_weights,
    risk_parity_weights,
    strategy_report,
)


def _rets(specs, n=1500, seed=0):
    """specs: dict {nom: (mean, vol)} ; rendements indépendants."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    return pd.DataFrame({k: rng.normal(m, v, n) for k, (m, v) in specs.items()}, index=idx)


def test_inverse_vol_gives_more_to_low_vol() -> None:
    w = inverse_vol_weights(_rets({"calm": (0.0005, 0.005), "wild": (0.0005, 0.03)}))
    assert w.sum() == pytest.approx(1.0)
    assert w["calm"] > w["wild"]


def test_risk_parity_equalizes_risk_contributions() -> None:
    r = _rets({"A": (0.0004, 0.008), "B": (0.0004, 0.02), "C": (0.0004, 0.014)}, seed=1)
    w = risk_parity_weights(r)
    assert w.sum() == pytest.approx(1.0, abs=1e-6)
    cov = r.cov().to_numpy()
    wv = w.to_numpy()
    rc = wv * (cov @ wv)          # contributions au risque
    # Contributions ~égales (ERC) : écart-type relatif faible.
    assert rc.std() / rc.mean() < 0.05


def test_diversification_beats_average_single() -> None:
    """Deux stratégies indépendantes : le Sharpe combiné > la *moyenne* des Sharpe
    seuls (≈ √2× à vol égale) — le gain de diversification, robuste au bruit
    d'échantillon (contrairement à « > meilleur seul », faussé par la chance)."""
    r = _rets({"m": (0.0006, 0.01), "p": (0.0006, 0.01)}, n=3000, seed=2)
    rep = strategy_report(r, method="risk_parity")
    avg = np.mean(list(rep["per_strategy_sharpe"].values()))
    assert rep["combined_sharpe"] > avg


def test_combine_weights_sum_to_one_and_series_aligned() -> None:
    r = _rets({"A": (0.0005, 0.01), "B": (0.0004, 0.012)}, seed=3)
    combined, w = combine(r, method="inverse_vol")
    assert w.sum() == pytest.approx(1.0)
    assert len(combined) == len(r)


def test_equal_method_and_bad_method() -> None:
    r = _rets({"A": (0.0005, 0.01), "B": (0.0004, 0.012)}, seed=4)
    _, w = combine(r, method="equal")
    assert w["A"] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        combine(r, method="nope")


def test_report_correlation_and_single_strategy() -> None:
    r = _rets({"A": (0.0005, 0.01)}, seed=5)
    rep = strategy_report(r)
    assert rep["weights"] == {"A": 1.0}
    assert "A" in rep["correlation"].columns


def test_degenerate_columns_dropped() -> None:
    r = _rets({"A": (0.0005, 0.01)}, seed=6)
    r["FLAT"] = 0.0  # variance nulle -> écartée
    w = inverse_vol_weights(r)
    assert "FLAT" not in w.index and w.sum() == pytest.approx(1.0)
