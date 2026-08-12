"""Univers liquide *large* depuis Alpaca — pour tester la breadth (Tier 2 bis).

Le portail a montré que le vrai plafond de FinBot est la **breadth** (loi de
Grinold-Kahn : IR ≈ IC·√Breadth). Avec ~80 large-caps très corrélées, l'espace de
paris indépendants est étroit. Ce module construit un univers **beaucoup plus
large** (centaines de titres liquides) directement depuis le courtier réel
(Alpaca), pour re-tester les signaux à breadth élevée.

Deux phases :

1. **Liste** : ``/v2/assets`` (equities US actives, tradables, NASDAQ/NYSE/AMEX),
   d'où l'on **retire les fonds/ETF** par le champ *name* (un test de facteur
   *action* ne doit pas être contaminé par des paniers).
2. **Liquidité** : classe les titres par **dollar-volume médian** récent et garde
   les ``n`` plus liquides au-dessus d'un plancher.

⚠️ **Biais de survie assumé** : Alpaca ne liste que les titres *encore cotés*
aujourd'hui. Cet univers reste survivor-biased (les délistés manquent — biais de
36.8 % mesuré sur 2020). Il sert à mesurer l'effet *breadth* (paris indépendants),
pas à estimer un rendement absolu non biaisé — ce qui exigerait un dataset type
Sharadar/CRSP. Le caveat est répété là où les résultats sont rapportés.

Responsabilité unique : produire une *liste de tickers* liquide et propre. Les prix
et l'évaluation restent au loader/portail existants.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests

from financial_analyzer.data.alpaca_history import _keys

__all__ = [
    "is_probable_fund",
    "median_dollar_volume",
    "rank_liquid_symbols",
    "top_liquid_us_equities",
]

_ASSETS_URL = "https://paper-api.alpaca.markets/v2/assets"
_BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"

# Marqueurs de *nom* trahissant un fonds/ETF/ETN/panier (à exclure d'un test action).
_FUND_MARKERS = (
    "ETF", "ETN", "FUND", "TRUST", "SPDR", "ISHARES", "PROSHARES", "INDEX",
    "PORTFOLIO", "INVESCO", "VANGUARD", "WISDOMTREE", "DIREXION", "GLOBAL X",
    "SELECT SECTOR", "BOND", "TREASURY", "GOLD SHARES", "BITCOIN", "ETHER",
    "REIT INDEX", "MSCI", "S&P 500", "NASDAQ-100",
)
_VALID_EXCHANGES = frozenset({"NASDAQ", "NYSE", "AMEX", "NYSEARCA", "ARCA", "BATS"})


def is_probable_fund(name: str) -> bool:
    """Vrai si le *nom* de l'actif ressemble à un fonds/ETF (à exclure)."""
    up = (name or "").upper()
    return any(m in up for m in _FUND_MARKERS)


def median_dollar_volume(bars: list[dict]) -> float:
    """Dollar-volume médian d'une liste de barres journalières (``c``×``v``)."""
    if not bars:
        return 0.0
    return float(np.median([b["c"] * b["v"] for b in bars if b.get("v")]))


def rank_liquid_symbols(
    dollar_volume: dict[str, float], n: int, min_dollar: float,
) -> list[str]:
    """Garde les titres au-dessus du plancher de liquidité, top ``n`` décroissant."""
    eligible = {s: dv for s, dv in dollar_volume.items() if dv >= min_dollar}
    return sorted(eligible, key=eligible.get, reverse=True)[:n]


def _fetch_common_stock_symbols(timeout: int = 30) -> list[str]:
    """Liste des actions US tradables (fonds/ETF retirés par le nom)."""
    import re

    headers = _keys(None, None)
    resp = requests.get(
        _ASSETS_URL, headers=headers,
        params={"status": "active", "asset_class": "us_equity"}, timeout=timeout,
    )
    resp.raise_for_status()
    out = []
    for a in resp.json():
        sym = a.get("symbol", "")
        if not (a.get("tradable") and a.get("exchange") in _VALID_EXCHANGES):
            continue
        if not re.fullmatch(r"[A-Z]{1,5}", sym):
            continue
        if is_probable_fund(a.get("name", "")):
            continue
        out.append(sym)
    return sorted(set(out))


def _fetch_dollar_volume(
    symbols: list[str], start: str, end: str,
    chunk_size: int = 200, timeout: int = 30,
) -> dict[str, float]:
    """Dollar-volume médian par titre sur [start, end] (barres journalières)."""
    headers = _keys(None, None)
    dv: dict[str, float] = {}
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        token = None
        while True:
            params = {
                "symbols": ",".join(chunk), "timeframe": "1Day",
                "start": start, "end": end, "limit": 10000, "feed": "iex",
            }
            if token:
                params["page_token"] = token
            r = requests.get(_BARS_URL, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            payload = r.json()
            for sym, bars in (payload.get("bars") or {}).items():
                dv[sym] = median_dollar_volume(bars)
            token = payload.get("next_page_token")
            if not token:
                break
    return dv


def top_liquid_us_equities(
    n: int = 500,
    rank_start: str = "2026-06-15",
    rank_end: str = "2026-07-31",
    min_dollar: float = 5e6,
    cache_path: str | None = None,
) -> list[str]:
    """Top ``n`` actions US **liquides** (fonds exclus), classées par dollar-volume.

    Args:
        n: taille cible de l'univers.
        rank_start/rank_end: fenêtre récente servant au classement de liquidité.
        min_dollar: plancher de dollar-volume médian (défaut 5 M$).
        cache_path: si fourni, met en cache le classement {symbole: dollar-volume}
            (JSON) pour éviter de re-scanner tout le marché.

    Returns:
        Liste de tickers (ordre décroissant de liquidité).
    """
    import json
    from pathlib import Path

    ranking: dict[str, float] | None = None
    if cache_path and Path(cache_path).exists():
        ranking = json.loads(Path(cache_path).read_text())
    if ranking is None:
        symbols = _fetch_common_stock_symbols()
        ranking = _fetch_dollar_volume(symbols, rank_start, rank_end)
        if cache_path:
            Path(cache_path).write_text(json.dumps(ranking))
    return rank_liquid_symbols(ranking, n, min_dollar)


def load_prices_for_universe(
    symbols: list[str], start: str, end: str, cache_path: str | None = None,
) -> pd.DataFrame:
    """Charge les clôtures ajustées de l'univers (délègue au loader Alpaca)."""
    from financial_analyzer.data.alpaca_history import load_or_fetch

    return load_or_fetch(symbols, start, end, cache_path=cache_path)
