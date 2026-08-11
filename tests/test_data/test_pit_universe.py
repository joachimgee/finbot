"""Appartenance point-in-time à l'univers (P2) — anti biais de survie.

Verrouille : un titre n'est « vivant » qu'entre son introduction et sa radiation
(exclusion pré-IPO et post-delisting), et l'application du masque neutralise les
cases hors appartenance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.data.pit_loader import RealDataUnavailableError
from financial_analyzer.data.pit_universe import (
    PITUniverseLoader,
    apply_membership,
    build_membership_mask,
)


def _lifespans() -> pd.DataFrame:
    return pd.DataFrame([
        {"ticker": "OLD", "list_date": pd.Timestamp("2010-01-01"), "delisted_utc": pd.NaT},
        {"ticker": "IPO", "list_date": pd.Timestamp("2021-06-15"), "delisted_utc": pd.NaT},
        {"ticker": "DEAD", "list_date": pd.Timestamp("2010-01-01"), "delisted_utc": pd.Timestamp("2022-03-01")},
    ])


def test_membership_excludes_pre_ipo_and_post_delist() -> None:
    dates = pd.date_range("2020-01-01", "2023-01-01", freq="MS")
    m = build_membership_mask(dates, _lifespans())
    assert m["OLD"].all()                                    # coté sur toute la période
    assert not m.loc[m.index < "2021-06-15", "IPO"].any()    # pas avant l'IPO
    assert m.loc[m.index >= "2021-07-01", "IPO"].all()       # coté après l'IPO
    assert not m.loc[m.index >= "2022-04-01", "DEAD"].any()  # plus après la radiation
    assert m.loc[m.index < "2022-03-01", "DEAD"].all()       # vivant avant


def test_membership_handles_tz_aware_dates() -> None:
    dates = pd.date_range("2020-01-01", "2023-01-01", freq="MS", tz="UTC")
    m = build_membership_mask(dates, _lifespans())
    assert str(m.index.tz) == "UTC"
    assert not m.loc[m.index < pd.Timestamp("2021-06-15", tz="UTC"), "IPO"].any()


def test_apply_membership_nans_out_non_members() -> None:
    dates = pd.date_range("2020-01-01", "2023-01-01", freq="MS")
    panel = pd.DataFrame(1.0, index=dates, columns=["OLD", "IPO", "DEAD"])
    masked = apply_membership(panel, build_membership_mask(dates, _lifespans()))
    assert masked["OLD"].notna().all()
    assert masked.loc[masked.index < "2021-06-15", "IPO"].isna().all()
    assert masked.loc[masked.index >= "2022-04-01", "DEAD"].isna().all()


# --- Contrat fail-safe -------------------------------------------------------

def test_polygon_failure_raises_when_fallback_forbidden(monkeypatch) -> None:
    monkeypatch.setattr(
        "financial_analyzer.data.polygon_universe.ticker_lifespans",
        lambda *a, **k: pd.DataFrame(columns=["ticker", "list_date", "delisted_utc", "active"]),
    )
    loader = PITUniverseLoader(source="polygon", allow_synthetic_fallback=False)
    with pytest.raises(RealDataUnavailableError):
        loader.lifespans(["AAA"])


def test_synthetic_is_deterministic_and_has_some_delistings() -> None:
    a = PITUniverseLoader(source="synthetic").lifespans([f"T{i}" for i in range(40)])
    b = PITUniverseLoader(source="synthetic").lifespans([f"T{i}" for i in range(40)])
    pd.testing.assert_frame_equal(a, b)
    # Le synthétique doit inclure des radiations (sinon il ne teste rien d'utile).
    assert a["delisted_utc"].notna().any()
    assert np.issubdtype(a["list_date"].dtype, np.datetime64)


def test_unknown_source_rejected() -> None:
    with pytest.raises(ValueError, match="source inconnue"):
        PITUniverseLoader(source="crsp").lifespans(["AAA"])
