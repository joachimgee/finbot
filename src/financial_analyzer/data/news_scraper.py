"""
Module de scraping des news financières multi-sources.

Scrape les news financières de:
- FinViz : News table scraping
- Yahoo Finance : yfinance.Ticker.news API
- NewsAPI : API officielle (100 req/jour gratuit)
- Reddit : Optionnel via PRAW

Usage:
    >>> from financial_analyzer.data.news_scraper import FinancialNewsScraper
    >>> scraper = FinancialNewsScraper(timeout=10)
    >>> 
    >>> # Toutes les sources
    >>> df = scraper.get_all_news("AAPL", max_articles=100)
    >>> print(df.head())
    >>> 
    >>> # Source spécifique
    >>> df_finviz = scraper.get_news_from_finviz("MSFT")
"""

# 1. Stdlib
import os
import time
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timedelta
import logging

# 2. Données & Calculs
import pandas as pd
import numpy as np

# 5. Web/API
import requests
from bs4 import BeautifulSoup
import yfinance as yf

# 6. Projet local
from financial_analyzer.config import API_KEYS
from financial_analyzer.utils.helpers import get_logger, cache_result, validate_ticker


class FinancialNewsScraper:
    """
    Scraper multi-sources pour news financières.

    Sources:
    - FinViz: News HTML scraping (gratuit, mais fragile)
    - Yahoo Finance: yfinance API (gratuit, fiable)
    - NewsAPI: API (100 req/jour gratuit)
    - Reddit: PRAW API (optionnel, besoin keys)

    Args:
        timeout: Timeout requêtes HTTP en secondes (défaut: 10)
        max_retries: Tentatives en cas d'erreur (défaut: 3)
        user_agent: User-Agent personnalisé

    Raises:
        ValueError: Si configuration invalide

    Example:
        >>> scraper = FinancialNewsScraper(timeout=10, max_retries=3)
        >>> 
        >>> # Récupérer toutes les news
        >>> df = scraper.get_all_news("AAPL", max_articles=100)
        >>> print(df.head())
        >>> # Output:
        >>> #                     headline              source                        url
        >>> # date
        >>> # 2025-11-03 12:00  Apple stock rises...  Yahoo Finance  https://...
        >>> # 2025-11-03 11:30  AAPL Q4 results...    NewsAPI        https://...
    """

    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 3,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Initialiser le scraper.

        Args:
            timeout: Timeout HTTP en secondes
            max_retries: Nombre de retries avec backoff
            user_agent: User-Agent HTTP personnalisé

        Raises:
            ValueError: Si timeout ou max_retries invalides
        """
        if timeout <= 0 or max_retries <= 0:
            raise ValueError("timeout et max_retries doivent être > 0")

        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent or "Mozilla/5.0 (compatible; FinBot/1.0)"
        self.logger = get_logger(__name__)

        # Session réutilisable pour meilleure performance
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        self.logger.info(
            f"FinancialNewsScraper initialisé | "
            f"timeout={timeout}s | retries={max_retries}"
        )

    def _clean_text(self, text: str) -> str:
        """
        Nettoie et normalise le texte.

        Args:
            text: Texte brut

        Returns:
            Texte nettoyé (espaces normalisés, newlines supprimées)

        Example:
            >>> scraper._clean_text("  Hello   \\n\\n  World  ")
            'Hello World'
        """
        if not text or not isinstance(text, str):
            return ""
        return " ".join(text.strip().replace("\n", " ").replace("\r", " ").split())

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[requests.Response]:
        """
        Effectue requête HTTP avec retry + backoff.

        Args:
            url: URL à requêter
            params: Paramètres query (optionnel)
            headers: Headers personnalisés (optionnel)

        Returns:
            Response objet si succès, None sinon

        Example:
            >>> resp = scraper._request("https://finviz.com/quote.ashx?t=AAPL")
            >>> if resp:
            ...     print(resp.status_code)
        """
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )

                if resp.status_code == 200:
                    self.logger.debug(f"✓ Requête {url}: 200 OK")
                    return resp

                # Gestion des erreurs HTTP
                elif resp.status_code == 429:  # Rate limit
                    wait_time = 2 ** (attempt + 1)
                    self.logger.warning(
                        f"Rate limited (429) | Attente {wait_time}s "
                        f"(tentative {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)

                elif resp.status_code in [404, 403]:  # Not found / Forbidden
                    self.logger.warning(f"HTTP {resp.status_code} sur {url}")
                    return None  # Pas la peine de retry

                elif resp.status_code >= 500:  # Server error
                    wait_time = 2 ** (attempt + 1)
                    self.logger.warning(
                        f"Server error {resp.status_code} | Attente {wait_time}s "
                        f"(tentative {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)

                else:
                    self.logger.error(f"Erreur HTTP {resp.status_code} sur {url}")
                    return None

            except requests.Timeout:
                self.logger.warning(
                    f"Timeout sur {url} "
                    f"(tentative {attempt + 1}/{self.max_retries})"
                )
                time.sleep(2 ** (attempt + 1))

            except requests.RequestException as e:
                self.logger.error(
                    f"Exception requête {url}: {type(e).__name__}: {str(e)} "
                    f"(tentative {attempt + 1}/{self.max_retries})"
                )
                time.sleep(2 ** (attempt + 1))

        self.logger.error(f"✗ Tous les retries épuisés pour {url}")
        return None

    def get_news_from_finviz(self, ticker: str) -> pd.DataFrame:
        """
        Scrape news FinViz pour un ticker.

        ⚠️ Fragile car structure HTML peut changer. À utiliser comme fallback.

        Args:
            ticker: Ticker symbol (ex: 'AAPL')

        Returns:
            DataFrame avec colonnes: ['headline', 'source', 'url', 'text']
            Index: DatetimeIndex UTC trié décroissant

        Example:
            >>> df = scraper.get_news_from_finviz("AAPL")
            >>> print(df.head())
        """
        ticker = validate_ticker(ticker)

        cache_key = f"finviz_{ticker}"

        @cache_result(cache_key, expiry_hours=6)
        def _scrape() -> pd.DataFrame:
            self.logger.info(f"Scraping FinViz: {ticker}")

            url = f"https://finviz.com/quote.ashx?t={ticker}"
            resp = self._request(url)

            articles = []

            if resp:
                try:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    news_table = soup.find("table", class_="fullview-news-outer")

                    if news_table:
                        for row in news_table.find_all("tr"):
                            cols = row.find_all("td")
                            if len(cols) >= 2:
                                try:
                                    # Parsing date
                                    date_str = cols[0].text.strip()
                                    try:
                                        if " " in date_str:
                                            dt = datetime.strptime(date_str, "%b-%d-%y %I:%M%p")
                                        else:
                                            dt = datetime.strptime(date_str, "%I:%M%p")
                                            dt = dt.replace(year=datetime.utcnow().year,
                                                          month=datetime.utcnow().month,
                                                          day=datetime.utcnow().day)
                                    except ValueError:
                                        dt = datetime.utcnow()

                                    # Parsing headline + URL
                                    link = cols[1].find("a")
                                    headline = self._clean_text(cols[1].text)
                                    url_link = link.get("href", "") if link else ""

                                    articles.append({
                                        "date": pd.Timestamp(dt, tz="UTC"),
                                        "headline": headline,
                                        "source": "FinViz",
                                        "url": url_link,
                                        "text": headline,
                                        "ticker": ticker
                                    })

                                except Exception as e:
                                    self.logger.debug(f"Erreur parsing FinViz row: {e}")
                                    continue
                    else:
                        self.logger.warning(f"Table news FinViz non trouvée pour {ticker}")

                except Exception as e:
                    self.logger.error(f"Erreur parsing FinViz HTML: {e}")

            else:
                self.logger.error(f"Impossible de requêter FinViz pour {ticker}")

            # Créer DataFrame
            df = pd.DataFrame(articles)

            if not df.empty:
                # Remove duplicates, sort, set index
                df = df.drop_duplicates(subset=["headline"])
                df = df.sort_values("date", ascending=False)
                df.set_index("date", inplace=True)
                self.logger.info(f"✓ FinViz {ticker}: {len(df)} articles")
            else:
                self.logger.warning(f"Aucun article FinViz pour {ticker}")
                df = pd.DataFrame(columns=["headline", "source", "url", "text", "ticker"])
                df.index = pd.DatetimeIndex([], tz="UTC", name="date")

            return df

        return _scrape()

    def get_news_from_yahoo(self, ticker: str) -> pd.DataFrame:
        """
        Récupère news Yahoo Finance via yfinance API.

        ✓ Fiable et robuste, pas de scraping HTML.

        Args:
            ticker: Ticker symbol (ex: 'AAPL')

        Returns:
            DataFrame avec colonnes: ['headline', 'source', 'url', 'text']
            Index: DatetimeIndex UTC trié décroissant

        Example:
            >>> df = scraper.get_news_from_yahoo("AAPL")
            >>> print(df.head())
        """
        ticker = validate_ticker(ticker)

        cache_key = f"yahoo_{ticker}"

        @cache_result(cache_key, expiry_hours=6)
        def _fetch() -> pd.DataFrame:
            self.logger.info(f"Récupération Yahoo Finance: {ticker}")

            articles = []

            try:
                ticker_obj = yf.Ticker(ticker)

                if hasattr(ticker_obj, 'news') and ticker_obj.news:
                    for item in ticker_obj.news:
                        try:
                            headline = self._clean_text(item.get("title", ""))
                            text = self._clean_text(item
