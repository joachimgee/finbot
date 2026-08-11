"""Calibration du modèle de coûts (P1) — mesure d'écart bid-ask et preset Alpaca."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.cost_calibration import (
    corwin_schultz_spread,
    effective_spread_bps,
    estimate_effective_spread_bps,
    summarize_quote_spreads,
)
from financial_analyzer.backtest.signal_evaluation import CostModel

# --- Écart effectif d'une cotation ------------------------------------------

def test_effective_spread_bps_known_value() -> None:
    # bid=99.95, ask=100.05 -> spread=0.10, mid=100 -> 10 bps
    assert effective_spread_bps(99.95, 100.05) == pytest.approx(10.0, abs=1e-6)


def test_effective_spread_bps_rejects_invalid() -> None:
    assert effective_spread_bps(100.0, 99.0) is None   # ask < bid
    assert effective_spread_bps(0.0, 100.0) is None     # bid <= 0
    assert effective_spread_bps(100.0, 0.0) is None     # ask <= 0
    assert effective_spread_bps(None, 100.0) is None


def test_effective_spread_zero_when_locked() -> None:
    assert effective_spread_bps(100.0, 100.0) == pytest.approx(0.0)


# --- Agrégation robuste des cotations ---------------------------------------

def test_summarize_trims_stale_outliers() -> None:
    quotes = {
        "AAPL": (100.0, 100.02),   # 2 bps
        "KO": (50.0, 50.005),      # 1 bps
        "T": (25.0, 25.01),        # 4 bps
        "STALE": (100.0, 105.0),   # ~488 bps -> écrêté (périmée)
        "BAD": (100.0, 99.0),      # invalide -> écarté
    }
    est = summarize_quote_spreads(quotes, trim_bps=30.0, impact_buffer_bps=1.0)
    assert est.n_quotes == 3          # AAPL, KO, T
    assert est.n_dropped == 2         # STALE (trop large) + BAD (invalide)
    assert 1.0 <= est.median_spread_bps <= 4.0
    # slippage recommandé = demi-spread médian + impact
    assert est.recommended_slippage_bps == pytest.approx(
        est.median_half_spread_bps + 1.0, abs=1e-9
    )


def test_summarize_empty_when_all_dropped() -> None:
    est = summarize_quote_spreads({"X": (100.0, 200.0)}, trim_bps=30.0)
    assert est.n_quotes == 0
    assert np.isnan(est.median_spread_bps)


# --- Corwin-Schultz : propriétés (borne haute, pas calibration) -------------

def test_corwin_schultz_zero_when_high_equals_low() -> None:
    idx = pd.date_range("2024-01-01", periods=30)
    h = pd.Series(100.0, index=idx)
    spread = corwin_schultz_spread(h, h).dropna()
    assert (spread == 0).all()


def test_corwin_schultz_monotonic_and_nonnegative() -> None:
    idx = pd.date_range("2024-01-01", periods=60)
    mid = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.01, 60))), index=idx)
    prev = -1.0
    for band in (0.0005, 0.002, 0.005):
        s = corwin_schultz_spread(mid * (1 + band), mid * (1 - band)).dropna()
        assert (s >= 0).all()
        assert s.mean() > prev  # plus la bande H/L est large, plus l'estimation croît
        prev = s.mean()


def test_estimate_effective_spread_handles_empty() -> None:
    est = estimate_effective_spread_bps({}, min_days=60)
    assert est.n_tickers == 0
    assert np.isnan(est.recommended_slippage_bps)


# --- Preset CostModel Alpaca -------------------------------------------------

def test_alpaca_equities_preset() -> None:
    cm = CostModel.alpaca_equities()
    assert cm.commission_bps == 0.0          # Alpaca sans commission
    assert cm.slippage_bps == pytest.approx(2.5)
    # coût aller simple ~2.5 bps, bien en-dessous du défaut générique (25 bps)
    assert cm.cost_rate * 1e4 == pytest.approx(2.5)
    assert cm.cost_rate < CostModel().cost_rate
