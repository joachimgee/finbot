"""Univers **point-in-time** via l'API Polygon (anti biais de survie).

Valider des facteurs sur un univers de titres *actuellement* liquides conditionne
sur la survie : les titres delistés (faillites, fusions, radiations — souvent à
mauvais fondamentaux/momentum) sont exclus, ce qui **gonfle** les backtests. Ce
module fournit la matière première pour corriger ce biais :

- :func:`as_of_universe` — l'ensemble des titres *cotés à une date historique*
  (paramètre ``date`` de Polygon), y compris ceux delistés depuis.
- :func:`list_delisted` — les titres delistés, avec leur ``delisted_utc``.
- :func:`ticker_lifespans` — ``list_date`` / ``delisted_utc`` par titre (durée de
  vie cotée), pour bâtir un masque d'appartenance point-in-time.

Clé lue depuis ``POLYGON_API_KEY``. Aucune clé n'est stockée.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

_TICKERS_URL = "https://api.polygon.io/v3/reference/tickers"

__all__ = ["as_of_universe", "list_delisted", "ticker_lifespans"]


def _api_key(explicit: str | None) -> str:
    key = explicit or os.environ.get("POLYGON_API_KEY")
    if not key:
        raise ValueError("Clé Polygon absente (POLYGON_API_KEY).")
    return key


def _get(url: str, params: dict, key: str) -> dict:
    """GET avec gestion du quota (429 → attente ~13 s, free tier = 5 req/min)."""
    for attempt in range(6):
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            time.sleep(13 + attempt * 2)
            continue
        if resp.status_code != 200:
            logger.warning("Polygon tickers: %s %s", resp.status_code, resp.text[:120])
            return {}
        return resp.json()
    return {}


def _paginate(params: dict, key: str, max_pages: int = 12) -> list[dict]:
    """Suit ``next_url`` jusqu'à épuisement (borné par ``max_pages``)."""
    results: list[dict] = []
    url, first = _TICKERS_URL, dict(params)
    first["apiKey"] = key
    for _ in range(max_pages):
        j = _get(url, first if url == _TICKERS_URL else {"apiKey": key}, key)
        results.extend(j.get("results", []))
        nxt = j.get("next_url")
        if not nxt:
            break
        url = nxt
    return results


def as_of_universe(
    date: str,
    *,
    market: str = "stocks",
    ticker_type: str = "CS",
    active: bool = True,
    api_key: str | None = None,
) -> set[str]:
    """Ensemble des symboles **cotés à la date historique** ``date`` (YYYY-MM-DD).

    Point-in-time : Polygon renvoie l'univers tel qu'il était ce jour-là (les
    titres depuis delistés y figurent s'ils étaient cotés alors).
    """
    key = _api_key(api_key)
    params = {"market": market, "type": ticker_type, "date": date,
              "active": str(active).lower(), "limit": 1000}
    rows = _paginate(params, key)
    return {r["ticker"] for r in rows if r.get("ticker")}


def list_delisted(
    delisted_gte: str | None = None,
    *,
    market: str = "stocks",
    ticker_type: str = "CS",
    api_key: str | None = None,
    max_pages: int = 12,
) -> pd.DataFrame:
    """Titres **delistés** (``active=false``), avec ``delisted_utc``.

    Args:
        delisted_gte: si fourni (YYYY-MM-DD), ne garde que les delistings ≥ cette date.

    Returns:
        DataFrame ``[ticker, name, delisted_utc, list_date]`` trié par date de delist.
    """
    key = _api_key(api_key)
    params = {"market": market, "type": ticker_type, "active": "false", "limit": 1000}
    rows = _paginate(params, key, max_pages=max_pages)
    recs = []
    for r in rows:
        du = r.get("delisted_utc")
        recs.append({
            "ticker": r.get("ticker"), "name": r.get("name"),
            "delisted_utc": pd.to_datetime(du).tz_localize(None) if du else pd.NaT,
            "list_date": pd.to_datetime(r.get("list_date")) if r.get("list_date") else pd.NaT,
        })
    df = pd.DataFrame(recs)
    if delisted_gte and not df.empty:
        df = df[df["delisted_utc"] >= pd.Timestamp(delisted_gte)]
    return df.sort_values("delisted_utc").reset_index(drop=True)


def ticker_lifespans(
    tickers: list[str], *, api_key: str | None = None, sleep_between: float = 0.0
) -> pd.DataFrame:
    """``list_date`` et ``delisted_utc`` par titre (durée de vie cotée).

    Un appel de détail par ticker (quota Polygon serré : réserver aux petits
    univers, ou espacer via ``sleep_between``).

    Returns:
        DataFrame ``[ticker, list_date, delisted_utc, active]``.
    """
    key = _api_key(api_key)
    recs = []
    for tk in tickers:
        j = _get(f"{_TICKERS_URL}/{tk}", {"apiKey": key}, key)
        d = j.get("results", {}) or {}
        du = d.get("delisted_utc")
        recs.append({
            "ticker": tk,
            "list_date": pd.to_datetime(d.get("list_date")) if d.get("list_date") else pd.NaT,
            "delisted_utc": pd.to_datetime(du).tz_localize(None) if du else pd.NaT,
            "active": bool(d.get("active", True)),
        })
        if sleep_between:
            time.sleep(sleep_between)
    return pd.DataFrame(recs)
