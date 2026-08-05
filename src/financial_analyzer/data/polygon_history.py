"""Récupération d'historique quotidien ajusté via Polygon (plan gratuit).

Le plan gratuit Polygon donne les barres EOD ajustées sur ~2 ans glissants,
limité à 5 requêtes/minute. Ce module récupère un panel (dates × tickers) de
clôtures ajustées, en respectant la limite de débit, avec cache disque pour ne
pas refetch.

Clé lue depuis POLYGON_API_KEY.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests

__all__ = ["fetch_daily_history", "load_or_fetch"]

_BASE = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"


def _fetch_one(ticker: str, start: str, end: str, api_key: str, timeout: int = 30) -> pd.Series:
    """Clôtures ajustées pour un ticker, indexées par date (peut être vide)."""
    url = _BASE.format(ticker=ticker, start=start, end=end)
    r = requests.get(
        url,
        params={"apiKey": api_key, "adjusted": "true", "sort": "asc", "limit": 50000},
        timeout=timeout,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return pd.Series(dtype=float, name=ticker)
    idx = pd.to_datetime([bar["t"] for bar in results], unit="ms").normalize()
    close = [float(bar["c"]) for bar in results]
    return pd.Series(close, index=idx, name=ticker)


def fetch_daily_history(
    tickers: List[str],
    start: str,
    end: str,
    api_key: Optional[str] = None,
    requests_per_min: int = 5,
    progress: bool = True,
) -> pd.DataFrame:
    """Panel (dates × tickers) de clôtures ajustées.

    Respecte la limite de débit du plan gratuit (5 req/min par défaut).
    """
    api_key = api_key or os.environ.get("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY manquante.")

    min_interval = 60.0 / max(1, requests_per_min) + 0.5  # marge de sécurité
    series = []
    for i, tk in enumerate(tickers):
        if i > 0:
            time.sleep(min_interval)
        try:
            s = _fetch_one(tk, start, end, api_key)
            if progress:
                print(f"  [{i+1}/{len(tickers)}] {tk}: {len(s)} jours")
            if not s.empty:
                series.append(s)
        except Exception as e:  # pragma: no cover - réseau
            if progress:
                print(f"  [{i+1}/{len(tickers)}] {tk}: échec {repr(e)[:80]}")
    if not series:
        return pd.DataFrame()
    panel = pd.concat(series, axis=1).sort_index()
    return panel


def load_or_fetch(
    tickers: List[str],
    start: str,
    end: str,
    cache_path: str,
    api_key: Optional[str] = None,
    requests_per_min: int = 5,
) -> pd.DataFrame:
    """Charge le panel depuis cache_path (CSV) s'il existe, sinon fetch + cache."""
    p = Path(cache_path)
    if p.exists():
        return pd.read_csv(p, index_col=0, parse_dates=True)
    panel = fetch_daily_history(tickers, start, end, api_key=api_key, requests_per_min=requests_per_min)
    if not panel.empty:
        p.parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(p)
    return panel
