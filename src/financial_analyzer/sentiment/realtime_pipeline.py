"""Real-time sentiment analysis pipeline.

Aggregates sentiment from multiple sources:
    - Twitter/X (via tweepy)
    - Reddit (via praw)
    - NewsAPI (headlines)
    - Alpha Vantage News Sentiment

Architecture:
    1. Fetch recent mentions for symbols
    2. Score sentiment per source (FinBERT)
    3. Aggregate weighted average
    4. Cache results (15min TTL)
    5. Integrate into portfolio adjustments

References:
    - Liu & Zhang (2012): Sentiment analysis and opinion mining
    - Bollen et al. (2011): Twitter mood predicts stock market
    - Tetlock (2007): Giving content to investor sentiment

Example:
    >>> from financial_analyzer.sentiment.realtime_pipeline import RealtimeSentimentPipeline
    >>> pipeline = RealtimeSentimentPipeline(api_keys=keys)
    >>> scores = pipeline.get_sentiment(['AAPL', 'MSFT'], lookback_hours=6)
    >>> print(scores)  # {'AAPL': 0.65, 'MSFT': 0.52}
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import time

import numpy as np
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class SentimentSource:
    """Sentiment from a single source."""
    source: str  # 'twitter', 'reddit', 'news', 'alpha_vantage'
    score: float  # [-1, 1]
    weight: float = 1.0  # Source reliability weight
    count: int = 0  # Number of mentions
    timestamp: datetime = field(default_factory=datetime.now)


class RealtimeSentimentPipeline:
    """Real-time multi-source sentiment aggregation.
    
    Features:
        - Twitter/X streaming (optional: requires API keys)
        - Reddit posts/comments (PRAW)
        - NewsAPI headlines
        - Alpha Vantage news sentiment
        - FinBERT scoring
        - Caching (avoid rate limits)
    
    Attributes:
        cache: In-memory sentiment cache
        cache_ttl: Time-to-live for cache entries (seconds)
        source_weights: Relative importance of each source
    """
    
    DEFAULT_WEIGHTS = {
        'twitter': 0.3,
        'reddit': 0.2,
        'news': 0.4,
        'alpha_vantage': 0.1,
    }
    
    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        cache_ttl: int = 900,  # 15 minutes
        source_weights: Optional[Dict[str, float]] = None,
        finbert_engine: Optional[Any] = None,
    ):
        """Initialize pipeline with API keys.
        
        Args:
            api_keys: Dictionary with keys: 'twitter_bearer', 'reddit_client_id',
                     'reddit_client_secret', 'newsapi_key', 'alpha_vantage_key'
            cache_ttl: Cache lifetime in seconds
            source_weights: Custom source weights (defaults to DEFAULT_WEIGHTS)
            finbert_engine: Optional FinBERT engine instance
        """
        self.api_keys = api_keys or {}
        self.cache_ttl = cache_ttl
        self.source_weights = source_weights or self.DEFAULT_WEIGHTS.copy()
        
        # Initialize cache
        self.cache: Dict[str, Tuple[Dict[str, float], float]] = {}
        
        # Initialize FinBERT
        self.finbert = finbert_engine
        if self.finbert is None:
            try:
                from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
                self.finbert = FinBERTEngine()
                logger.info("FinBERT engine initialized")
            except Exception as e:
                logger.warning(f"FinBERT unavailable: {e}")
        
        # Initialize API clients (lazy)
        self._twitter_client = None
        self._reddit_client = None
        self._newsapi_client = None
        
        logger.info(
            f"RealtimeSentimentPipeline initialized: "
            f"cache_ttl={cache_ttl}s, sources={list(self.source_weights.keys())}"
        )
    
    def get_sentiment(
        self,
        symbols: List[str],
        lookback_hours: int = 6,
        use_cache: bool = True,
    ) -> Dict[str, float]:
        """Get aggregated sentiment for symbols.
        
        Args:
            symbols: List of ticker symbols
            lookback_hours: Hours to look back for mentions
            use_cache: Use cached results if available
            
        Returns:
            Dictionary mapping symbol to sentiment score [-1, 1]
        """
        sentiment_scores = {}
        
        for symbol in symbols:
            # Check cache
            if use_cache:
                cached = self._get_from_cache(symbol)
                if cached is not None:
                    sentiment_scores[symbol] = cached
                    continue
            
            # Fetch from all sources
            sources = self._fetch_all_sources(symbol, lookback_hours)
            
            # Aggregate
            if sources:
                aggregated = self._aggregate_sentiment(sources)
                sentiment_scores[symbol] = aggregated
                
                # Update cache
                self._update_cache(symbol, aggregated)
            else:
                # Neutral if no data
                sentiment_scores[symbol] = 0.0
                logger.debug(f"No sentiment data for {symbol}, defaulting to 0.0")
        
        return sentiment_scores
    
    def _fetch_all_sources(
        self,
        symbol: str,
        lookback_hours: int
    ) -> List[SentimentSource]:
        """Fetch sentiment from all available sources."""
        sources = []
        
        # Twitter
        if 'twitter_bearer' in self.api_keys:
            try:
                twitter_sentiment = self._fetch_twitter(symbol, lookback_hours)
                if twitter_sentiment:
                    sources.append(twitter_sentiment)
            except Exception as e:
                logger.warning(f"Twitter fetch failed for {symbol}: {e}")
        
        # Reddit
        if 'reddit_client_id' in self.api_keys:
            try:
                reddit_sentiment = self._fetch_reddit(symbol, lookback_hours)
                if reddit_sentiment:
                    sources.append(reddit_sentiment)
            except Exception as e:
                logger.warning(f"Reddit fetch failed for {symbol}: {e}")
        
        # NewsAPI
        if 'newsapi_key' in self.api_keys:
            try:
                news_sentiment = self._fetch_news(symbol, lookback_hours)
                if news_sentiment:
                    sources.append(news_sentiment)
            except Exception as e:
                logger.warning(f"NewsAPI fetch failed for {symbol}: {e}")
        
        # Alpha Vantage
        if 'alpha_vantage_key' in self.api_keys:
            try:
                av_sentiment = self._fetch_alpha_vantage(symbol)
                if av_sentiment:
                    sources.append(av_sentiment)
            except Exception as e:
                logger.warning(f"Alpha Vantage fetch failed for {symbol}: {e}")
        
        return sources
    
    def _fetch_twitter(self, symbol: str, lookback_hours: int) -> Optional[SentimentSource]:
        """Fetch Twitter mentions (placeholder)."""
        # Twitter API v2 requires bearer token
        # Placeholder: Would use tweepy here
        logger.debug(f"Twitter fetch for {symbol} (placeholder)")
        return None  # Implement with tweepy if keys available
    
    def _fetch_reddit(self, symbol: str, lookback_hours: int) -> Optional[SentimentSource]:
        """Fetch Reddit mentions (placeholder)."""
        # PRAW for Reddit API
        # Search r/wallstreetbets, r/stocks, r/investing
        logger.debug(f"Reddit fetch for {symbol} (placeholder)")
        return None  # Implement with praw if keys available
    
    def _fetch_news(self, symbol: str, lookback_hours: int) -> Optional[SentimentSource]:
        """Fetch NewsAPI headlines."""
        if not self.api_keys.get('newsapi_key'):
            return None
        
        try:
            from newsapi import NewsApiClient
            newsapi = NewsApiClient(api_key=self.api_keys['newsapi_key'])
            
            # Fetch recent articles
            cutoff = datetime.now() - timedelta(hours=lookback_hours)
            articles = newsapi.get_everything(
                q=f'"{symbol}" OR "${symbol}"',
                from_param=cutoff.isoformat(),
                language='en',
                sort_by='publishedAt',
                page_size=100
            )
            
            if not articles or not articles.get('articles'):
                return None
            
            # Score headlines with FinBERT
            texts = [a['title'] + ' ' + (a.get('description') or '') for a in articles['articles']]
            scores = self._score_texts(texts)
            
            avg_score = float(np.mean(scores)) if scores else 0.0
            
            return SentimentSource(
                source='news',
                score=avg_score,
                weight=self.source_weights.get('news', 0.4),
                count=len(articles['articles'])
            )
        
        except Exception as e:
            logger.error(f"NewsAPI error for {symbol}: {e}")
            return None
    
    def _fetch_alpha_vantage(self, symbol: str) -> Optional[SentimentSource]:
        """Fetch Alpha Vantage news sentiment."""
        if not self.api_keys.get('alpha_vantage_key'):
            return None
        
        try:
            import requests
            url = 'https://www.alphavantage.co/query'
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol,
                'apikey': self.api_keys['alpha_vantage_key'],
                'limit': 50
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'feed' not in data:
                return None
            
            # Extract ticker sentiment scores
            scores = []
            for item in data['feed']:
                for ticker_sentiment in item.get('ticker_sentiment', []):
                    if ticker_sentiment.get('ticker') == symbol:
                        score = float(ticker_sentiment.get('ticker_sentiment_score', 0.0))
                        scores.append(score)
            
            if not scores:
                return None
            
            avg_score = float(np.mean(scores))
            
            return SentimentSource(
                source='alpha_vantage',
                score=avg_score,
                weight=self.source_weights.get('alpha_vantage', 0.1),
                count=len(scores)
            )
        
        except Exception as e:
            logger.error(f"Alpha Vantage error for {symbol}: {e}")
            return None
    
    def _score_texts(self, texts: List[str]) -> List[float]:
        """Score texts using FinBERT.
        
        Args:
            texts: List of text strings
            
        Returns:
            Sentiment scores [-1, 1]
        """
        if not self.finbert or not texts:
            return []
        
        try:
            scores = []
            for text in texts:
                # FinBERT returns probabilities for [positive, negative, neutral]
                result = self.finbert.predict_sentiment(text)
                # Map to [-1, 1]: positive=1, negative=-1, neutral=0
                if result == 'positive':
                    scores.append(0.7)
                elif result == 'negative':
                    scores.append(-0.7)
                else:
                    scores.append(0.0)
            return scores
        except Exception as e:
            logger.warning(f"FinBERT scoring failed: {e}")
            return []
    
    def _aggregate_sentiment(self, sources: List[SentimentSource]) -> float:
        """Aggregate sentiment from multiple sources.
        
        Uses weighted average based on source reliability and count.
        
        Args:
            sources: List of sentiment sources
            
        Returns:
            Aggregated score [-1, 1]
        """
        if not sources:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for source in sources:
            # Weight by source importance and mention count
            effective_weight = source.weight * np.log1p(source.count)
            weighted_sum += source.score * effective_weight
            total_weight += effective_weight
        
        if total_weight < 1e-8:
            return 0.0
        
        aggregated = weighted_sum / total_weight
        
        # Clip to valid range
        return float(np.clip(aggregated, -1.0, 1.0))
    
    def _get_from_cache(self, symbol: str) -> Optional[float]:
        """Get sentiment from cache if valid."""
        if symbol not in self.cache:
            return None
        
        score, timestamp = self.cache[symbol]
        
        # Check expiration
        if time.time() - timestamp > self.cache_ttl:
            del self.cache[symbol]
            return None
        
        return score.get(symbol)
    
    def _update_cache(self, symbol: str, score: float) -> None:
        """Update cache with new sentiment."""
        self.cache[symbol] = ({symbol: score}, time.time())
    
    def clear_cache(self) -> None:
        """Clear all cached sentiment."""
        self.cache.clear()
        logger.info("Sentiment cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'total_entries': len(self.cache),
            'expired': sum(
                1 for _, (_, ts) in self.cache.items()
                if time.time() - ts > self.cache_ttl
            )
        }


__all__ = ['RealtimeSentimentPipeline', 'SentimentSource']
