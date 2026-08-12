"""Sentiment de presse **point-in-time** via l'API Polygon News.

Chaque article porte un ``published_utc`` : c'est sa **date de connaissance** — le
sentiment n'est disponible qu'à partir de là. Polygon fournit aussi, sur les
articles récents, un champ ``insights[].sentiment`` (positive/negative/neutral)
par ticker ; on le mappe en score ±1/0.

L'anti-look-ahead est structurel (comme les autres loaders PIT) : le panel
quotidien à la date t n'agrège que les articles ``published_utc ≤ t``.

Contrat fail-safe : source réelle (Polygon) ou abstention/synthétique. Clé lue
depuis ``POLYGON_API_KEY``.

⚠️ Limites de données honnêtes : (1) le ``sentiment`` natif Polygon n'existe que
sur les articles **récents** (~2024+) ; (2) le quota free tier (5 req/min) et le
volume d'articles bornent l'échelle d'un backtest long.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from financial_analyzer.data.pit_loader import RealDataUnavailableError
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

_NEWS_URL = "https://api.polygon.io/v2/reference/news"
_SENTIMENT_MAP = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}

__all__ = [
    "NewsSentimentLoader",
    "article_text",
    "build_sentiment_panel",
    "fetch_news_articles",
    "fetch_news_sentiment",
]


def article_text(art: dict) -> str:
    """Texte notable d'un article = titre + description (ce que FinBERT lit).

    Pur (testable sans réseau). Concatène ``title`` et ``description`` en évitant
    la duplication si la description répète le titre. Chaîne vide si rien d'exploitable.
    """
    title = (art.get("title") or "").strip()
    desc = (art.get("description") or "").strip()
    if desc and desc.lower() not in title.lower():
        return f"{title}. {desc}".strip(". ").strip() if title else desc
    return title


def fetch_news_articles(
    tickers: list[str],
    start: str,
    end: str | None = None,
    *,
    api_key: str | None = None,
    max_pages_per_ticker: int = 4,
) -> pd.DataFrame:
    """Récupère les **articles avec leur texte** (titre+description) par ticker.

    Contrairement à :func:`fetch_news_sentiment` (qui ne garde que les articles
    porteurs d'un ``insight`` Polygon), on garde **tout article ayant du texte** —
    c'est FinBERT qui notera le sentiment en aval, sans dépendre du champ natif.

    Returns:
        DataFrame long ``[ticker, published_utc, text]`` (une ligne par article
        avec du texte exploitable).
    """
    key = _api_key(api_key)
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    rows: list[dict] = []
    for tk in tickers:
        params = {
            "ticker": tk, "published_utc.gte": start, "published_utc.lte": end,
            "order": "asc", "sort": "published_utc", "limit": 1000, "apiKey": key,
        }
        url = _NEWS_URL
        for _ in range(max_pages_per_ticker):
            resp = robust_get(url, params if url == _NEWS_URL else {"apiKey": key})
            if resp is None or resp.status_code != 200:
                logger.warning("Polygon news %s: %s", tk, getattr(resp, "status_code", "n/a"))
                break
            j = resp.json()
            for art in j.get("results", []):
                txt = article_text(art)
                if not txt:
                    continue
                rows.append({
                    "ticker": tk,
                    "published_utc": pd.to_datetime(art.get("published_utc")).tz_localize(None),
                    "text": txt,
                })
            url = j.get("next_url")
            if not url:
                break
    cols = ["ticker", "published_utc", "text"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows).sort_values(["ticker", "published_utc"]).reset_index(drop=True)


def _api_key(explicit: str | None) -> str:
    key = explicit or os.environ.get("POLYGON_API_KEY")
    if not key:
        raise ValueError("Clé Polygon absente (POLYGON_API_KEY).")
    return key


def fetch_news_sentiment(
    tickers: list[str],
    start: str,
    end: str | None = None,
    *,
    api_key: str | None = None,
    max_pages_per_ticker: int = 3,
) -> pd.DataFrame:
    """Récupère les articles + sentiment natif par ticker.

    Returns:
        DataFrame long ``[ticker, published_utc, sentiment]`` (sentiment ∈ {−1,0,1}),
        une ligne par (article, ticker mentionné) porteur d'un insight de sentiment.
    """
    key = _api_key(api_key)
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    rows: list[dict] = []
    for tk in tickers:
        params = {
            "ticker": tk, "published_utc.gte": start, "published_utc.lte": end,
            "order": "asc", "sort": "published_utc", "limit": 1000, "apiKey": key,
        }
        url = _NEWS_URL
        for _ in range(max_pages_per_ticker):
            resp = None
            for attempt in range(5):
                resp = requests_get(url, params if url == _NEWS_URL else {"apiKey": key})
                if resp.status_code == 429:
                    time.sleep(13 + attempt * 2)
                    continue
                break
            if resp is None or resp.status_code != 200:
                logger.warning("Polygon news %s: %s", tk, getattr(resp, "status_code", "n/a"))
                break
            j = resp.json()
            for art in j.get("results", []):
                pub = art.get("published_utc")
                for ins in art.get("insights", []) or []:
                    if ins.get("ticker") == tk and ins.get("sentiment") in _SENTIMENT_MAP:
                        rows.append({
                            "ticker": tk,
                            "published_utc": pd.to_datetime(pub).tz_localize(None),
                            "sentiment": _SENTIMENT_MAP[ins["sentiment"]],
                        })
            url = j.get("next_url")
            if not url:
                break
    if not rows:
        return pd.DataFrame(columns=["ticker", "published_utc", "sentiment"])
    return pd.DataFrame(rows).sort_values(["ticker", "published_utc"]).reset_index(drop=True)


def requests_get(url: str, params: dict):
    """Wrapper isolable (facilite le mock en test)."""
    import requests

    return requests.get(url, params=params, timeout=30)


def robust_get(url: str, params: dict, *, tries: int = 6):
    """GET tolérant : réessaie sur 429 **et** sur les aléas réseau/proxy (timeouts).

    Le proxy sortant peut avoir des hoquets transitoires (handshake TLS qui expire).
    Un backoff exponentiel évite qu'un seul aléa ne fasse tout perdre. Renvoie la
    dernière réponse HTTP obtenue, ou ``None`` si toutes les tentatives échouent.
    """
    import requests

    delay = 4.0
    resp = None
    for attempt in range(tries):
        try:
            resp = requests_get(url, params)
        except requests.exceptions.RequestException as e:  # proxy/timeout/connexion
            logger.warning("Polygon news réseau (essai %d/%d): %s", attempt + 1, tries, e)
            time.sleep(delay)
            delay = min(delay * 2, 60.0)
            continue
        if resp.status_code == 429:  # quota free tier
            time.sleep(13 + attempt * 2)
            continue
        return resp
    return resp


def build_sentiment_panel(
    long_df: pd.DataFrame, dates: pd.DatetimeIndex, window_days: int = 30
) -> pd.DataFrame:
    """Panel (dates × tickers) **point-in-time** du sentiment net moyen.

    À la date t, sentiment[t, tk] = moyenne des scores des articles de ``tk``
    publiés dans ``(t − window_days, t]`` — donc uniquement connus à t (aucun
    look-ahead). ``NaN`` si aucun article dans la fenêtre.
    """
    idx = pd.DatetimeIndex(dates)
    naive = idx.tz_localize(None) if idx.tz is not None else idx
    if long_df.empty:
        return pd.DataFrame(index=idx)
    window = pd.Timedelta(days=window_days)
    cols: dict[str, np.ndarray] = {}
    for tk, g in long_df.groupby("ticker"):
        pub = g["published_utc"].to_numpy()
        sent = g["sentiment"].to_numpy()
        vals = np.full(len(naive), np.nan)
        for i, t in enumerate(naive.to_numpy()):
            lo = t - np.timedelta64(window)
            mask = (pub > lo) & (pub <= t)
            if mask.any():
                vals[i] = float(sent[mask].mean())
        cols[tk] = vals
    return pd.DataFrame(cols, index=idx)


@dataclass
class NewsSentimentLoader:
    """Charge un panel de sentiment point-in-time, contrat fail-safe.

    Args:
        source: ``"polygon"`` (réel) ou ``"synthetic"`` (déterministe, tests).
        allow_synthetic_fallback: si faux, un échec du réel lève
            ``RealDataUnavailableError`` au lieu de retomber sur le synthétique.
        window_days: fenêtre d'agrégation du sentiment (jours).
    """

    source: str = "polygon"
    allow_synthetic_fallback: bool = True
    window_days: int = 30

    def load(self, tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
        """Renvoie le panel long ``[ticker, published_utc, sentiment]``."""
        if self.source == "polygon":
            try:
                df = fetch_news_sentiment(list(tickers), start, end)
                if df.empty:
                    raise RealDataUnavailableError(
                        "Polygon n'a renvoyé aucun sentiment d'article "
                        "(le sentiment natif n'existe que sur les articles récents)."
                    )
                logger.info("News sentiment: %d articles notés, %d tickers.",
                            len(df), df["ticker"].nunique())
                return df
            except RealDataUnavailableError:
                if not self.allow_synthetic_fallback:
                    raise
                logger.warning("News sentiment: aucun réel — REPLI SYNTHÉTIQUE.")
            except Exception as e:
                if not self.allow_synthetic_fallback:
                    raise RealDataUnavailableError(
                        f"Sentiment réel indisponible, repli interdit : {e}"
                    ) from e
                logger.warning("News sentiment: échec réel (%s) — REPLI SYNTHÉTIQUE.", e)
        elif self.source != "synthetic":
            raise ValueError(f"source inconnue : {self.source!r} (attendu 'polygon' ou 'synthetic').")

        return self._synthetic(list(tickers), start, end)

    @staticmethod
    def _synthetic(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
        """Flux d'articles notés déterministe (tests / hors-ligne)."""
        import hashlib

        end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
        days = pd.date_range(start=start, end=end, freq="3D")
        rows = []
        for tk in tickers:
            rng = np.random.default_rng(int(hashlib.sha256(tk.encode()).hexdigest()[:8], 16))
            for d in days:
                if rng.random() < 0.5:  # ~1 article tous les 6 jours
                    rows.append({"ticker": tk, "published_utc": d,
                                 "sentiment": float(rng.choice([-1.0, 0.0, 1.0]))})
        cols = ["ticker", "published_utc", "sentiment"]
        df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
        return df.sort_values(["ticker", "published_utc"]).reset_index(drop=True)
