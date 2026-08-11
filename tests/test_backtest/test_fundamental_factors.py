"""Facteurs value/quality point-in-time (P2)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from financial_analyzer.backtest.fundamental_factors import (
    FUNDAMENTAL_FACTORS,
    compute_fundamental_factors,
)


def _prices() -> pd.DataFrame:
    dates = pd.date_range("2022-09-01", "2022-12-31", freq="B")
    # CHEAP bas prix, RICH prix élevé ; même fondamental -> CHEAP a un E/P, B/P plus haut.
    return pd.DataFrame({"CHEAP": 10.0, "RICH": 200.0}, index=dates)


def _fundamentals() -> pd.DataFrame:
    # Déposé avant la fenêtre de prix -> visible sur toute la fenêtre.
    common = dict(end_date=pd.Timestamp("2022-06-30"), filing_date=pd.Timestamp("2022-08-01"))
    rows = []
    for tk in ("CHEAP", "RICH"):
        rows.append({
            "ticker": tk, **common,
            "ttm_net_income": 1e8, "equity": 1e9, "assets": 2e9,
            "ttm_gross_profit": 5e8, "shares": 1e8,
        })
    return pd.DataFrame(rows)


def test_all_four_factors_computed() -> None:
    factors = compute_fundamental_factors(_prices(), _fundamentals())
    assert set(FUNDAMENTAL_FACTORS).issubset(factors)
    for name in FUNDAMENTAL_FACTORS:
        assert factors[name].shape == _prices().shape


def test_cheaper_name_has_higher_value_scores() -> None:
    """Même fondamental, prix plus bas -> E/P et B/P plus élevés (plus 'value')."""
    factors = compute_fundamental_factors(_prices(), _fundamentals())
    ep = factors["earnings_yield"].iloc[-1]
    bp = factors["book_to_price"].iloc[-1]
    assert ep["CHEAP"] > ep["RICH"]
    assert bp["CHEAP"] > bp["RICH"]


def test_quality_factors_price_independent() -> None:
    """ROE et GP/A ne dépendent pas du prix -> identiques entre CHEAP et RICH ici."""
    factors = compute_fundamental_factors(_prices(), _fundamentals())
    roe = factors["roe"].iloc[-1]
    gpa = factors["gross_profitability"].iloc[-1]
    assert roe["CHEAP"] == roe["RICH"]
    assert gpa["CHEAP"] == gpa["RICH"]
    assert roe["CHEAP"] > 0 and gpa["CHEAP"] > 0


def test_negative_equity_yields_nan_book_ratios() -> None:
    prices = _prices()
    fund = _fundamentals()
    fund.loc[fund.ticker == "CHEAP", "equity"] = -5e8  # capitaux propres négatifs
    factors = compute_fundamental_factors(prices, fund)
    assert np.isnan(factors["book_to_price"].iloc[-1]["CHEAP"])
    assert np.isnan(factors["roe"].iloc[-1]["CHEAP"])
