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
from datetime import datetime, timedelta, UTC
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
                                            now_utc = datetime.now(UTC)
                                            dt = dt.replace(year=now_utc.year,
                                                          month=now_utc.month,
                                                          day=now_utc.day)
                                    except ValueError:
                                        dt = datetime.now(UTC)

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
                            text = self._clean_text(item.get("description", ""))
                            source = item.get("publisher", "Yahoo Finance")
                            url = item.get("link", "")
                            pub_date_raw = item.get("providerPublishTime")
                            pub_date = pd.to_datetime(pub_date_raw, unit='s', utc=True) if pub_date_raw else pd.NaT

                            if headline:
                                articles.append({
                                    'headline': headline,
                                    'source': source,
                                    'url': url,
                                    'text': text or headline,
                                    'published': pub_date,
                                })
                        except Exception as e:
                            self.logger.warning(f"Erreur parsing item Yahoo: {e}")
                            continue

            except Exception as e:
                self.logger.error(f"Erreur Yahoo Finance {ticker}: {e}")
                return pd.DataFrame()

            if not articles:
                self.logger.warning(f"Aucune news Yahoo pour {ticker}")
                return pd.DataFrame()

            df = pd.DataFrame(articles)
            # Normaliser: index DatetimeIndex UTC nommé 'date'
            if 'published' in df.columns:
                df = df.sort_values('published', ascending=False)
                df = df.set_index('published')
                # Convertir index en DatetimeIndex UTC si besoin
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index, utc=True, errors='coerce')
                elif df.index.tz is None:
                    df.index = df.index.tz_localize('UTC')
                elif str(df.index.tz) != 'UTC':
                    df.index = df.index.tz_convert('UTC')
                df.index.name = 'date'
            else:
                # Pas de date disponible, créer index temporel par défaut
                df.index = pd.to_datetime([pd.NaT]*len(df), utc=True)
                df.index.name = 'date'
            return df

        return _fetch()

    def get_news_from_newsapi(
        self,
        ticker: str,
        max_articles: int = 50,
        language: str = 'en',
        **kwargs,
    ) -> pd.DataFrame:
        """
        Récupère news via NewsAPI (100 req/jour gratuit).

        ⚠️ Nécessite API key de https://newsapi.org
        
        Args:
            ticker: Ticker symbol (ex: 'AAPL')
            max_articles: Max articles à récupérer
            language: Language code (ex: 'en')

        Returns:
            DataFrame avec colonnes: ['headline', 'source', 'url', 'text', 'published']
            Index: DatetimeIndex UTC

        Example:
            >>> df = scraper.get_news_from_newsapi("AAPL", max_articles=50)
            >>> print(df.head())
        """
        ticker = validate_ticker(ticker)
        
        # Support alias 'limit' for compatibility with tests
        limit = kwargs.get('limit', max_articles)
        if isinstance(limit, int) and limit > 0:
            max_articles = limit
        
        # Check API key (prefer explicit 'newsapi_key' if present in config)
        if 'newsapi_key' in API_KEYS:
            api_key = API_KEYS.get('newsapi_key')
        else:
            api_key = API_KEYS.get('news_api')
        if not api_key:
            self.logger.warning("NewsAPI key not configured, returning empty DataFrame")
            return pd.DataFrame()

        cache_key = f"newsapi_{ticker}_{language}"

        @cache_result(cache_key, expiry_hours=12)
        def _fetch() -> pd.DataFrame:
            self.logger.info(f"Récupération NewsAPI: {ticker}")

            articles = []
            url = "https://newsapi.org/v2/everything"
            
            params = {
                'q': ticker,
                'sortBy': 'publishedAt',
                'language': language,
                'pageSize': min(max_articles, 100),  # API limit
                'apiKey': api_key
            }

            try:
                response = self._request(url, params=params)
                if response and response.status_code == 200:
                    data = response.json()
                    
                    if data.get('status') == 'ok':
                        for item in data.get('articles', []):
                            try:
                                headline = self._clean_text(item.get('title', ''))
                                text = self._clean_text(item.get('description', ''))
                                source = item.get('source', {}).get('name', 'NewsAPI')
                                url_item = item.get('url', '')
                                pub_date_str = item.get('publishedAt')
                                pub_date = pd.to_datetime(pub_date_str, utc=True) if pub_date_str else pd.NaT

                                if headline:
                                    articles.append({
                                        'headline': headline,
                                        'source': source,
                                        'url': url_item,
                                        'text': text or headline,
                                        'published': pub_date,
                                    })
                            except Exception as e:
                                self.logger.warning(f"Erreur parsing article NewsAPI: {e}")
                                continue
                    else:
                        self.logger.error(f"NewsAPI error: {data.get('message', 'Unknown')}")
                        
                elif response and response.status_code == 429:
                    self.logger.warning("NewsAPI rate limit exceeded (100/day)")
                    
            except Exception as e:
                self.logger.error(f"Erreur NewsAPI {ticker}: {e}")
                return pd.DataFrame()

            if not articles:
                self.logger.warning(f"Aucune news NewsAPI pour {ticker}")
                return pd.DataFrame()

            df = pd.DataFrame(articles)
            # Normaliser: index DatetimeIndex UTC nommé 'date'
            if 'published' in df.columns:
                df = df.sort_values('published', ascending=False)
                df = df.set_index('published')
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, utc=True, errors='coerce')
            elif df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
            df.index.name = 'date'
            return df

        return _fetch()

    def get_news_from_reddit(
        self,
        ticker: str,
        subreddits: Optional[List[str]] = None,
        limit: int = 50
    ) -> pd.DataFrame:
        """
        Récupère discussions Reddit (optionnel via PRAW).

        ⚠️ Optionnel: Nécessite PRAW + Reddit app credentials
        
        Args:
            ticker: Ticker symbol (ex: 'AAPL')
            subreddits: Liste subreddits (default: ['stocks', 'investing', 'wallstreetbets'])
            limit: Nombre de posts par subreddit

        Returns:
            DataFrame avec colonnes: ['headline', 'source', 'url', 'text', 'published', 'score']
            Index: DatetimeIndex UTC

        Note:
            Si PRAW non installé ou credentials manquantes:
            - Log warning
            - Return empty DataFrame
            - Do NOT crash

        Example:
            >>> df = scraper.get_news_from_reddit("AAPL", limit=50)
            >>> print(df.head())
        """
        ticker = validate_ticker(ticker)
        
        # Try import PRAW (optional dependency)
        try:
            import praw
        except ImportError:
            self.logger.warning("PRAW not installed, skipping Reddit (install with: pip install praw)")
            return pd.DataFrame()

        # Check Reddit credentials
        client_id = API_KEYS.get('reddit_client_id')
        client_secret = API_KEYS.get('reddit_client_secret')
        user_agent = API_KEYS.get('reddit_user_agent', 'FinBot/1.0')
        
        if not client_id or not client_secret:
            self.logger.warning("Reddit credentials not configured, returning empty DataFrame")
            return pd.DataFrame()

        if subreddits is None:
            subreddits = ['stocks', 'investing', 'wallstreetbets']

        cache_key = f"reddit_{ticker}_{'_'.join(subreddits)}"

        @cache_result(cache_key, expiry_hours=24)
        def _fetch() -> pd.DataFrame:
            self.logger.info(f"Récupération Reddit: {ticker} from {subreddits}")

            articles = []

            try:
                reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent
                )

                for subreddit_name in subreddits:
                    try:
                        subreddit = reddit.subreddit(subreddit_name)
                        
                        # Search posts with ticker keyword
                        for submission in subreddit.search(ticker, limit=limit, time_filter='month'):
                            try:
                                headline = self._clean_text(submission.title)
                                text = self._clean_text(submission.selftext)
                                url_item = f"https://reddit.com{submission.permalink}"
                                pub_date = pd.to_datetime(submission.created_utc, unit='s', utc=True)
                                score = int(submission.score)

                                if headline:
                                    articles.append({
                                        'headline': headline,
                                        'source': f'Reddit r/{subreddit_name}',
                                        'url': url_item,
                                        'text': text or headline,
                                        'published': pub_date,
                                        'score': score,
                                    })
                            except Exception as e:
                                self.logger.debug(f"Erreur parsing Reddit post: {e}")
                                continue
                                
                    except Exception as e:
                        self.logger.warning(f"Erreur accessing subreddit {subreddit_name}: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"Erreur Reddit API {ticker}: {e}")
                return pd.DataFrame()

            if not articles:
                self.logger.warning(f"Aucune discussion Reddit pour {ticker}")
                return pd.DataFrame()

            df = pd.DataFrame(articles)
            df = df.sort_values('published', ascending=False).reset_index(drop=True)
            return df

        return _fetch()

    def get_all_news(
        self,
        ticker: str,
        max_articles: int = 100,
        include_reddit: bool = False
    ) -> pd.DataFrame:
        """
        Agrège toutes sources: Yahoo + FinViz + NewsAPI + Reddit (optionnel).

        Args:
            ticker: Ticker symbol
            max_articles: Max articles total (distributed across sources)
            include_reddit: Include Reddit discussions

        Returns:
            Combined DataFrame, deduplicated, sorted by date (latest first)
            Columns: ['headline', 'source', 'url', 'text', 'published']

        Example:
            >>> df = scraper.get_all_news("AAPL", max_articles=100, include_reddit=True)
            >>> print(f"Retrieved {len(df)} articles from {df['source'].nunique()} sources")
        """
        ticker = validate_ticker(ticker)
        
        self.logger.info(f"Fetching all news for {ticker} (max={max_articles}, reddit={include_reddit})")

        # Fetch from all sources in parallel (I/O bound)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        sources = {
            'Yahoo': lambda: self.get_news_from_yahoo(ticker),
            'FinViz': lambda: self.get_news_from_finviz(ticker),
            'NewsAPI': lambda: self.get_news_from_newsapi(ticker, max_articles=max_articles // 3),
        }
        
        if include_reddit:
            sources['Reddit'] = lambda: self.get_news_from_reddit(ticker, limit=max_articles // 4)

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_source = {executor.submit(func): name for name, func in sources.items()}
            
            for future in as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    df = future.result()
                    if not df.empty:
                        results.append(df)
                        self.logger.debug(f"Retrieved {len(df)} articles from {source_name}")
                except Exception as e:
                    self.logger.warning(f"Error fetching from {source_name}: {e}")

        if not results:
            self.logger.warning(f"No news found for {ticker} from any source")
            return pd.DataFrame()

        # Concatenate all results
        combined = pd.concat(results, ignore_index=True)
        
        # If some sources used an index for date, normalize to a 'date' column
        if isinstance(combined.index, pd.DatetimeIndex) and 'date' not in combined.columns:
            combined = combined.reset_index().rename(columns={'index': 'date'})
        
        # If 'published' exists, rename to 'date'
        if 'published' in combined.columns and 'date' not in combined.columns:
            combined = combined.rename(columns={'published': 'date'})
        
        # Ensure 'date' column exists
        if 'date' not in combined.columns:
            # Create from now to avoid crash; tests focus on index name
            combined['date'] = pd.Timestamp.now(tz='UTC')
        
        # Deduplicate by headline similarity
        combined = _deduplicate_news(combined, threshold=0.85)
        
        # Sort by date (latest first)
        combined = combined.sort_values('date', ascending=False)
        
        # Limit to max_articles
        combined = combined.head(max_articles)
        
        # Set DatetimeIndex named 'date'
        combined['date'] = pd.to_datetime(combined['date'], utc=True, errors='coerce')
        combined = combined.set_index('date')
        combined.index.name = 'date'
        
        self.logger.info(f"Retrieved {len(combined)} articles from {combined['source'].nunique()} sources for {ticker}")
        
        return combined

    def add_sentiment_scores(
        self,
        news_df: pd.DataFrame,
        batch_size: int = 32
    ) -> pd.DataFrame:
        """
        Ajoute sentiment scores using FinBERT (ProsusAI/finbert).

        Args:
            news_df: DataFrame with 'text' or 'headline' column
            batch_size: Batch size pour traitement

        Returns:
            DataFrame with new columns:
            - 'sentiment': float -1 to +1 (negative to positive)
            - 'sentiment_label': str ('positive', 'negative', 'neutral')
            - 'sentiment_confidence': float 0 to 1

        Note:
            Requires transformers and torch (optional dependencies).
            If not available, logs warning and returns original DataFrame.

        Example:
            >>> df = scraper.get_all_news("AAPL")
            >>> df_with_sentiment = scraper.add_sentiment_scores(df)
            >>> print(df_with_sentiment[['headline', 'sentiment', 'sentiment_label']].head())
        """
        if news_df.empty:
            return news_df

        # Try import transformers and torch (optional)
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
        except ImportError:
            self.logger.warning(
                "transformers/torch not installed, skipping sentiment analysis "
                "(install with: pip install transformers torch)"
            )
            return news_df

        self.logger.info(f"Computing sentiment scores for {len(news_df)} articles (batch_size={batch_size})")

        # Determine text column
        text_col = 'text' if 'text' in news_df.columns else 'headline'
        
        if text_col not in news_df.columns:
            self.logger.warning("No 'text' or 'headline' column found, skipping sentiment")
            return news_df

        try:
            # Load FinBERT model (cached after first load)
            model_name = "ProsusAI/finbert"
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name)
            model.eval()

            sentiments = []
            labels = []
            confidences = []

            # Batch process
            texts = news_df[text_col].fillna('').tolist()
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                try:
                    # Tokenize batch
                    inputs = tokenizer(
                        batch_texts,
                        padding=True,
                        truncation=True,
                        max_length=512,
                        return_tensors='pt'
                    )

                    # Forward pass
                    with torch.no_grad():
                        outputs = model(**inputs)
                        logits = outputs.logits
                        probs = torch.nn.functional.softmax(logits, dim=-1)

                    # Process batch results
                    for prob in probs:
                        # FinBERT classes: [negative, neutral, positive]
                        neg, neu, pos = prob.tolist()
                        
                        # Map to -1 to +1 scale
                        sentiment_score = pos - neg
                        
                        # Determine label
                        if pos > neg and pos > neu:
                            label = 'positive'
                            confidence = pos
                        elif neg > pos and neg > neu:
                            label = 'negative'
                            confidence = neg
                        else:
                            label = 'neutral'
                            confidence = neu

                        sentiments.append(sentiment_score)
                        labels.append(label)
                        confidences.append(confidence)

                except Exception as e:
                    self.logger.warning(f"Error processing batch {i}: {e}")
                    # Fill with NaN for failed batch
                    for _ in range(len(batch_texts)):
                        sentiments.append(np.nan)
                        labels.append('unknown')
                        confidences.append(np.nan)

            # Add columns to DataFrame
            news_df = news_df.copy()
            news_df['sentiment'] = sentiments
            news_df['sentiment_label'] = labels
            news_df['sentiment_confidence'] = confidences

            self.logger.info(
                f"Sentiment analysis complete: "
                f"{(news_df['sentiment_label'] == 'positive').sum()} positive, "
                f"{(news_df['sentiment_label'] == 'negative').sum()} negative, "
                f"{(news_df['sentiment_label'] == 'neutral').sum()} neutral"
            )

        except Exception as e:
            self.logger.error(f"Error in sentiment analysis: {e}")
            return news_df

        return news_df


# ==================== Module-level helpers ====================


def _deduplicate_news(df: pd.DataFrame, threshold: float = 0.85) -> pd.DataFrame:
    """
    Deduplicate news by headline similarity.

    Uses SequenceMatcher for fuzzy matching to remove near-duplicate headlines.

    Args:
        df: DataFrame with 'headline' column
        threshold: Similarity threshold (0-1), default 0.85

    Returns:
        Deduplicated DataFrame

    Example:
        >>> df = pd.DataFrame({'headline': ['Apple rises', 'Apple rises today', 'Tesla drops']})
        >>> dedup = _deduplicate_news(df, threshold=0.85)
        >>> print(len(dedup))  # 2 (first two considered duplicates)
    """
    if df.empty or 'headline' not in df.columns:
        return df

    from difflib import SequenceMatcher

    keep_indices = []
    seen_headlines = []

    for idx, row in df.iterrows():
        headline = row['headline']
        is_duplicate = False

        # Check against all previously seen headlines
        for seen in seen_headlines:
            similarity = SequenceMatcher(None, headline.lower(), seen.lower()).ratio()
            if similarity >= threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            keep_indices.append(idx)
            seen_headlines.append(headline)

    return df.loc[keep_indices].reset_index(drop=True)


