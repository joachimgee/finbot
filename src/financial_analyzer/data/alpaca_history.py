"""Récupération d'historique quotidien ajusté via l'API market-data Alpaca.

Avantages vs Polygon free : historique daily long (IEX, ~depuis 2016), 200
requêtes/min, et le multi-symbole en une requête paginée. Utilise le feed IEX
(inclus dans le plan gratuit) et l'ajustement des splits/dividendes.

Clés lues depuis l'environnement : ALPACA_API_KEY / ALPACA_SECRET_KEY
(fallback APCA_API_KEY_ID / APCA_API_SECRET_KEY). Aucune clé n'est stockée.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

__all__ = ["fetch_daily_history", "load_or_fetch"]

_URL = "https://data.alpaca.markets/v2/stocks/bars"


def _keys(api_key: Optional[str], secret_key: Optional[str]) -> Dict[str, str]:
    api_key = api_key or os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID")
    secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError(
            "Clés Alpaca manquantes. Définir ALPACA_API_KEY et ALPACA_SECRET_KEY "
            "(ou APCA_API_KEY_ID / APCA_API_SECRET_KEY)."
        )
    return {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}


def fetch_daily_history(
    tickers: List[str],
    start: str,
    end: str,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    feed: str = "iex",
    timeout: int = 30,
    chunk_size: int = 200,
    progress: bool = True,
) -> pd.DataFrame:
    """Panel (dates × tickers) de clôtures ajustées via Alpaca.

    Symboles fetchés par lots (chunk_size) pour éviter les URL trop longues ;
    pagination automatique (next_page_token) à l'intérieur de chaque lot.
    """
    headers = _keys(api_key, secret_key)
    closes: Dict[str, Dict[pd.Timestamp, float]] = {}

    chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    for ci, chunk in enumerate(chunks):
        page_token: Optional[str] = None
        while True:
            params = {
                "symbols": ",".join(chunk),
                "timeframe": "1Day",
                "start": start,
                "end": end,
                "limit": 10000,
                "adjustment": "all",
                "feed": feed,
            }
            if page_token:
                params["page_token"] = page_token
            r = requests.get(_URL, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            payload = r.json()
            bars = payload.get("bars") or {}
            for sym, sym_bars in bars.items():
                d = closes.setdefault(sym, {})
                for bar in sym_bars:
                    d[pd.Timestamp(bar["t"]).normalize()] = float(bar["c"])
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        if progress:
            print(f"  lot {ci+1}/{len(chunks)} ({len(chunk)} sym) : {len(closes)} tickers avec données")

    series = [pd.Series(v, name=sym).sort_index() for sym, v in closes.items() if v]
    if not series:
        return pd.DataFrame()
    return pd.concat(series, axis=1).sort_index()


def load_or_fetch(
    tickers: List[str],
    start: str,
    end: str,
    cache_path: str,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    feed: str = "iex",
) -> pd.DataFrame:
    """Charge depuis cache_path (CSV) s'il existe, sinon fetch Alpaca + cache."""
    p = Path(cache_path)
    if p.exists():
        return pd.read_csv(p, index_col=0, parse_dates=True)
    panel = fetch_daily_history(tickers, start, end, api_key=api_key, secret_key=secret_key, feed=feed)
    if not panel.empty:
        p.parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(p)
    return panel
