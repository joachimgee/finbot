"""Historique quotidien **longue durée** via l'API chart de Yahoo (gratuit, ~decennies).

Alpaca IEX (feed gratuit) ne remonte qu'à ~2020 ; Polygon est bridé par le quota.
Yahoo Finance sert des **décennies** de clôtures ajustées (splits + dividendes)
gratuitement — ce qui lève la limite d'**échantillon court** (pas le biais de survie :
Yahoo ne porte que les titres *encore cotés*, comme Alpaca).

Implémentation **requests** (pas ``yfinance``/curl_cffi, qui ignore le proxy de
l'environnement) : l'endpoint ``/v8/finance/chart`` est appelé par symbole, en
respectant ``HTTPS_PROXY`` et le CA du proxy. Renvoie un panel dates × tickers de
**clôtures ajustées** (``adjclose``), au même format que ``alpaca_history`` — donc
directement consommable par ``load_or_fetch`` (cache CSV) et tous les scripts portail.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests

__all__ = ["fetch_daily_close", "fetch_daily_ohlcv_yahoo", "load_or_fetch_yahoo"]

_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _epoch(day: str) -> int:
    return int(time.mktime(time.strptime(day, "%Y-%m-%d")))


def _fetch_one(symbol: str, p1: int, p2: int, timeout: int) -> Optional[pd.Series]:
    """Clôtures ajustées d'un symbole (``adjclose``), ``None`` si indisponible."""
    params = {"period1": p1, "period2": p2, "interval": "1d", "events": "div,splits"}
    for host in _HOSTS:
        url = f"https://{host}/v8/finance/chart/{symbol}"
        try:
            r = requests.get(url, headers=_HEADERS, params=params, timeout=timeout)
            if r.status_code != 200:
                continue
            res = (r.json().get("chart", {}).get("result") or [None])[0]
            if not res or "timestamp" not in res:
                continue
            ts = pd.to_datetime(res["timestamp"], unit="s").normalize()
            ind = res.get("indicators", {})
            adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
            close = adj if adj is not None else (ind.get("quote") or [{}])[0].get("close")
            if close is None:
                continue
            s = pd.Series(close, index=ts, name=symbol).dropna()
            return s[~s.index.duplicated(keep="last")]
        except Exception:  # noqa: BLE001 - on tente l'hôte suivant / on abandonne ce symbole
            continue
    return None


def fetch_daily_close(
    tickers: List[str], start: str, end: str, *,
    timeout: int = 30, pause: float = 0.15, progress: bool = False,
) -> pd.DataFrame:
    """Panel de clôtures **ajustées** (dates × tickers) sur [start, end] via Yahoo.

    Args:
        tickers: symboles.
        start/end: dates ``YYYY-MM-DD``.
        pause: délai entre symboles (politesse, évite le throttling).
        progress: journalise l'avancement.
    """
    p1, p2 = _epoch(start), _epoch(end)
    cols: dict[str, pd.Series] = {}
    for i, sym in enumerate(sorted(set(tickers))):
        s = _fetch_one(sym, p1, p2, timeout)
        if s is not None and not s.empty:
            cols[sym] = s
        if progress and (i + 1) % 10 == 0:
            print(f"  Yahoo {i + 1}/{len(set(tickers))} — {len(cols)} OK", flush=True)
        time.sleep(pause)
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def _fetch_one_ohlcv(symbol: str, p1: int, p2: int, timeout: int) -> Optional[pd.DataFrame]:
    """Barres quotidiennes ``close`` (ajusté) + ``volume`` d'un symbole."""
    params = {"period1": p1, "period2": p2, "interval": "1d", "events": "div,splits"}
    for host in _HOSTS:
        url = f"https://{host}/v8/finance/chart/{symbol}"
        try:
            r = requests.get(url, headers=_HEADERS, params=params, timeout=timeout)
            if r.status_code != 200:
                continue
            res = (r.json().get("chart", {}).get("result") or [None])[0]
            if not res or "timestamp" not in res:
                continue
            ts = pd.to_datetime(res["timestamp"], unit="s").normalize()
            ind = res.get("indicators", {})
            quote = (ind.get("quote") or [{}])[0]
            adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
            close = adj if adj is not None else quote.get("close")
            volume = quote.get("volume")
            if close is None or volume is None:
                continue
            df = pd.DataFrame({"close": close, "volume": volume}, index=ts).dropna()
            return df[~df.index.duplicated(keep="last")]
        except Exception:  # noqa: BLE001 - hôte suivant / symbole abandonné
            continue
    return None


def fetch_daily_ohlcv_yahoo(
    tickers: List[str], start: str, end: str, *,
    timeout: int = 30, pause: float = 0.15, progress: bool = False,
) -> dict[str, pd.DataFrame]:
    """``{ticker: DataFrame(close, volume)}`` sur [start, end] via Yahoo.

    Étend :func:`fetch_daily_close` avec le **volume** — nécessaire aux mesures de
    liquidité (Amihud, turnover) sur un historique long (décennies), là où le feed
    Alpaca IEX gratuit s'arrête vers 2020.
    """
    p1, p2 = _epoch(start), _epoch(end)
    out: dict[str, pd.DataFrame] = {}
    uniq = sorted(set(tickers))
    for i, sym in enumerate(uniq):
        df = _fetch_one_ohlcv(sym, p1, p2, timeout)
        if df is not None and not df.empty:
            out[sym] = df
        if progress and (i + 1) % 25 == 0:
            print(f"  Yahoo OHLCV {i + 1}/{len(uniq)} — {len(out)} OK", flush=True)
        time.sleep(pause)
    return out


def load_or_fetch_yahoo(
    tickers: List[str], start: str, end: str, cache_path: str, *, progress: bool = False,
) -> pd.DataFrame:
    """Charge le cache CSV s'il existe, sinon fetch Yahoo + cache (même contrat qu'Alpaca)."""
    p = Path(cache_path)
    if p.exists():
        return pd.read_csv(p, index_col=0, parse_dates=True)
    panel = fetch_daily_close(tickers, start, end, progress=progress)
    if not panel.empty:
        p.parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(p)
    return panel
