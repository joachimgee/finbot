"""Fondamentaux point-in-time (P2) — le test central : AUCUN look-ahead.

L'as-of par ``filing_date`` garantit qu'à la date t on ne voit que ce qui était
publié (déposé) au plus tard t — jamais une valeur restatée publiée plus tard.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.data.fundamentals_pit_loader import (
    FundamentalsPITLoader,
    add_ttm_columns,
    build_asof_panel,
)
from financial_analyzer.data.pit_loader import RealDataUnavailableError


def _long(ticker="AAA"):
    return pd.DataFrame({
        "ticker": [ticker, ticker],
        "end_date": [pd.Timestamp("2022-03-31"), pd.Timestamp("2022-06-30")],
        # Déposés ~1 mois après la fin de période.
        "filing_date": [pd.Timestamp("2022-05-01"), pd.Timestamp("2022-08-01")],
        "equity": [100.0, 110.0],
    })


def test_asof_has_no_lookahead() -> None:
    """La valeur est NaN avant le 1er dépôt, puis prend la valeur du dépôt en vigueur."""
    dates = pd.date_range("2022-01-01", "2022-12-31", freq="B")
    panel = build_asof_panel(_long(), dates, "equity")["AAA"]

    # Avant le premier dépôt (2022-05-01) : rien n'est connu.
    assert panel.loc[panel.index < "2022-05-01"].isna().all()
    # Entre le 1er et le 2e dépôt : valeur du Q1 (100), PAS celle du Q2 déposée plus tard.
    mid = panel.loc[(panel.index >= "2022-05-01") & (panel.index < "2022-08-01")]
    assert (mid == 100.0).all()
    # À partir du 2e dépôt : 110.
    assert (panel.loc[panel.index >= "2022-08-01"] == 110.0).all()


def test_asof_keys_on_filing_not_period_end() -> None:
    """Un fondamental de période close en mars n'est visible qu'à sa date de dépôt (mai)."""
    dates = pd.DatetimeIndex(["2022-04-15", "2022-05-01", "2022-05-02"])
    panel = build_asof_panel(_long(), dates, "equity")["AAA"]
    assert np.isnan(panel.loc["2022-04-15"])   # après la fin de période mais avant dépôt
    assert panel.loc["2022-05-01"] == 100.0     # jour du dépôt
    assert panel.loc["2022-05-02"] == 100.0


def test_ttm_is_rolling_four_quarters() -> None:
    q = pd.date_range("2021-03-31", periods=5, freq="QE")
    long = pd.DataFrame({
        "ticker": ["Z"] * 5,
        "end_date": q,
        "filing_date": q + pd.Timedelta(days=30),
        "net_income": [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    out = add_ttm_columns(long)
    ttm = out.sort_values("end_date")["ttm_net_income"].tolist()
    assert np.isnan(ttm[0]) and np.isnan(ttm[2])       # < 4 trimestres -> NaN
    assert ttm[3] == pytest.approx(10 + 20 + 30 + 40)  # 4 premiers
    assert ttm[4] == pytest.approx(20 + 30 + 40 + 50)  # fenêtre glissante


def test_asof_handles_tz_aware_dates() -> None:
    """Index de prix timezone-aware (Alpaca=UTC) vs filing_date naïf : pas d'erreur
    de merge, et l'alignement PIT reste correct (régression du MergeError)."""
    dates = pd.date_range("2022-01-01", "2022-12-31", freq="B", tz="UTC")
    panel = build_asof_panel(_long(), dates, "equity")
    assert str(panel.index.tz) == "UTC" and not panel.empty
    cut = pd.Timestamp("2022-05-01", tz="UTC")
    assert panel.loc[panel.index < cut, "AAA"].isna().all()
    assert (panel.loc[panel.index >= cut, "AAA"].dropna() > 0).all()


def test_empty_panel_is_safe() -> None:
    panel = build_asof_panel(pd.DataFrame(), pd.date_range("2022-01-01", periods=3), "equity")
    assert panel.empty or panel.isna().all().all()


# --- Contrat fail-safe (comme pit_loader prix) ------------------------------

def test_polygon_no_data_raises_when_fallback_forbidden(monkeypatch) -> None:
    monkeypatch.setattr(
        "financial_analyzer.data.polygon_fundamentals.fetch_fundamentals",
        lambda *a, **k: pd.DataFrame(),
    )
    loader = FundamentalsPITLoader(source="polygon", allow_synthetic_fallback=False)
    with pytest.raises(RealDataUnavailableError):
        loader.load(["AAA"], "2020-01-01", "2022-12-31")


def test_polygon_no_data_falls_back_to_synthetic_when_allowed(monkeypatch) -> None:
    monkeypatch.setattr(
        "financial_analyzer.data.polygon_fundamentals.fetch_fundamentals",
        lambda *a, **k: pd.DataFrame(),
    )
    loader = FundamentalsPITLoader(source="polygon", allow_synthetic_fallback=True)
    df = loader.load(["AAA", "BBB"], "2021-01-01", "2022-12-31")
    assert not df.empty and "ttm_net_income" in df.columns


def test_synthetic_is_deterministic() -> None:
    a = FundamentalsPITLoader(source="synthetic").load(["AAA"], "2021-01-01", "2022-12-31")
    b = FundamentalsPITLoader(source="synthetic").load(["AAA"], "2021-01-01", "2022-12-31")
    pd.testing.assert_frame_equal(a, b)
    # Les dépôts synthétiques suivent bien la fin de période (lag positif).
    assert (a["filing_date"] > a["end_date"]).all()


def test_unknown_source_rejected() -> None:
    with pytest.raises(ValueError, match="source inconnue"):
        FundamentalsPITLoader(source="bloomberg").load(["AAA"], "2021-01-01", "2022-12-31")
