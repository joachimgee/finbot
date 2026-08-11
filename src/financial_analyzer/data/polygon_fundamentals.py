"""Fondamentaux trimestriels via l'API Polygon (avec **date de dépôt**).

Ce module récupère les états financiers trimestriels depuis
``/vX/reference/financials``. La clé point-in-time est le champ **``filing_date``**
(date de publication du dépôt) : un fondamental n'est *connu du marché* qu'à partir
de cette date. Le reste du pipeline (``FundamentalsPITLoader``) s'appuie dessus pour
un alignement sans biais de look-ahead (pas de fuite via les restatements).

Clé lue depuis ``POLYGON_API_KEY``. Aucune clé n'est stockée.

Champs extraits par dépôt : ``net_income``, ``revenues``, ``cost_of_revenue``,
``gross_profit`` (= revenues − cost_of_revenue quand disponible), ``equity``
(valeur comptable), ``assets``, ``shares`` (actions diluées moyennes) — de quoi
calculer E/P, B/P, ROE, GP/A en aval.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

_URL = "https://api.polygon.io/vX/reference/financials"

__all__ = ["FUNDAMENTAL_FIELDS", "fetch_fundamentals"]

# Colonnes numériques du panel long renvoyé.
FUNDAMENTAL_FIELDS = [
    "net_income", "revenues", "cost_of_revenue", "gross_profit",
    "equity", "assets", "shares",
]


def _api_key(explicit: str | None) -> str:
    key = explicit or os.environ.get("POLYGON_API_KEY")
    if not key:
        raise ValueError("Clé Polygon absente (POLYGON_API_KEY).")
    return key


def _val(node: dict, stmt: str, field: str) -> float | None:
    """Extrait ``financials[stmt][field].value`` de façon défensive."""
    item = node.get(stmt, {}).get(field)
    if isinstance(item, dict):
        v = item.get("value")
        return float(v) if v is not None else None
    return None


def _parse_result(ticker: str, r: dict) -> dict | None:
    """Transforme un résultat Polygon en ligne plate ; None si pas de filing_date."""
    filing = r.get("filing_date")
    end = r.get("end_date")
    if not filing or not end:
        return None  # sans date de dépôt, impossible d'aligner point-in-time -> écarté
    fin = r.get("financials", {})
    net_income = _val(fin, "income_statement", "net_income_loss")
    revenues = _val(fin, "income_statement", "revenues")
    cogs = _val(fin, "income_statement", "cost_of_revenue")
    gross = _val(fin, "income_statement", "gross_profit")
    if gross is None and revenues is not None and cogs is not None:
        gross = revenues - cogs
    shares = (
        _val(fin, "income_statement", "diluted_average_shares")
        or _val(fin, "income_statement", "basic_average_shares")
    )
    return {
        "ticker": ticker,
        "fiscal_period": r.get("fiscal_period"),
        "fiscal_year": r.get("fiscal_year"),
        "end_date": pd.to_datetime(end),
        "filing_date": pd.to_datetime(filing),
        "net_income": net_income,
        "revenues": revenues,
        "cost_of_revenue": cogs,
        "gross_profit": gross,
        "equity": _val(fin, "balance_sheet", "equity"),
        "assets": _val(fin, "balance_sheet", "assets"),
        "shares": shares,
    }


def _fetch_one(ticker: str, start: str, end: str, key: str, timeframe: str,
               max_pages: int = 6) -> list[dict]:
    rows: list[dict] = []
    params = {
        "ticker": ticker, "timeframe": timeframe,
        "period_of_report_date.gte": start, "period_of_report_date.lte": end,
        "limit": 100, "apiKey": key, "order": "asc", "sort": "period_of_report_date",
    }
    url = _URL
    for _ in range(max_pages):
        for attempt in range(6):
            resp = requests.get(url, params=params if url == _URL else {"apiKey": key}, timeout=30)
            if resp.status_code == 429:  # quota (free tier = 5 req/min) -> attente fixe
                logger.debug("Polygon 429 (%s) — attente quota…", ticker)
                time.sleep(13 + attempt * 2)  # ~respecte 5/min, léger palier croissant
                continue
            break
        if resp.status_code != 200:
            logger.warning("Polygon financials %s: %s %s", ticker, resp.status_code, resp.text[:120])
            break
        j = resp.json()
        for r in j.get("results", []):
            parsed = _parse_result(ticker, r)
            if parsed is not None:
                rows.append(parsed)
        url = j.get("next_url")
        if not url:
            break
    return rows


def fetch_fundamentals(
    tickers: list[str],
    start: str = "2018-01-01",
    end: str | None = None,
    *,
    timeframe: str = "quarterly",
    api_key: str | None = None,
    progress: bool = False,
    sleep_between: float = 0.0,
) -> pd.DataFrame:
    """Récupère les fondamentaux trimestriels (avec dates de dépôt) pour un univers.

    Args:
        tickers: symboles.
        start/end: bornes sur la date de période (``end`` défaut = aujourd'hui).
        timeframe: ``"quarterly"`` (défaut) ou ``"annual"``.
        sleep_between: pause entre tickers (utile pour les quotas Polygon serrés).

    Returns:
        DataFrame long trié : une ligne par (ticker, dépôt), colonnes
        ``[ticker, fiscal_period, fiscal_year, end_date, filing_date, *FUNDAMENTAL_FIELDS]``.
        Vide si aucune donnée (clé absente lève ``ValueError`` en amont).
    """
    key = _api_key(api_key)
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    all_rows: list[dict] = []
    for i, tk in enumerate(tickers):
        if progress and i % 10 == 0:
            logger.info("Polygon fundamentals: %d/%d (%s)", i, len(tickers), tk)
        try:
            all_rows.extend(_fetch_one(tk, start, end, key, timeframe))
        except Exception as e:  # noqa: BLE001 - un ticker en échec ne doit pas tout stopper
            logger.warning("Polygon fundamentals %s échoué: %s", tk, e)
        if sleep_between:
            time.sleep(sleep_between)
    if not all_rows:
        return pd.DataFrame(
            columns=["ticker", "fiscal_period", "fiscal_year", "end_date", "filing_date", *FUNDAMENTAL_FIELDS]
        )
    df = pd.DataFrame(all_rows)
    return df.sort_values(["ticker", "filing_date", "end_date"]).reset_index(drop=True)
