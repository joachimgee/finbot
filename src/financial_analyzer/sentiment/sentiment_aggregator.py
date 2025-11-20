"""
Sentiment Aggregator - Multi-source Ensemble.

This module aggregates sentiment from multiple news sources using:
1. Existing FinancialNewsScraper (from data module) - NO DUPLICATION
2. FinBERTEngine for sentiment scoring
3. Recency-weighted aggregation
4. EMA smoothing for temporal consistency

Process:
1. Fetch N articles via FinancialNewsScraper.get_all_news()
2. Score each with FinBERT
3. Weight by recency (exponential decay)
4. Calculate aggregate sentiment
5. Smooth with EMA (α=0.3)
6. Return sentiment + confidence + metadata

Audit:
    AUDIT_FINANCE_PARTIE_5_ML.md pp.15-16 (sentiment aggregation patterns)
    
Example:
    >>> from financial_analyzer.data.news_scraper import FinancialNewsScraper
    >>> from financial_analyzer.sentiment import FinBERTEngine, SentimentAggregator
    >>> 
    >>> scraper = FinancialNewsScraper()
    >>> engine = FinBERTEngine()
    >>> agg = SentimentAggregator(finbert_engine=engine, news_scraper=scraper)
    >>> 
    >>> sentiment = agg.aggregate_sentiment('AAPL', window_days=7)
    >>> print(sentiment)
    {
        'sentiment_score': 0.35,
        'confidence': 0.78,
        'article_count': 12,
        'sources': ['Reuters', 'Bloomberg'],
        'bullish_pct': 0.58,
        'bearish_pct': 0.25,
        'neutral_pct': 0.17
    }
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import logging

import pandas as pd
import numpy as np

from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
from financial_analyzer.data.news_scraper import FinancialNewsScraper  # ✅ REUSE EXISTING

logger = get_logger(__name__)


class SentimentAggregator:
    """
    Aggregate sentiment from multiple news sources.
    
    Architecture:
    - Uses EXISTING FinancialNewsScraper (no duplication)
    - Scores articles with FinBERT
    - Weights by recency (exponential decay)
    - Smooths with EMA
    - Caches results for efficiency
    
    Algorithm:
    1. Fetch articles: scraper.get_all_news(ticker, max_articles)
    2. Score each: finbert.batch_sentiment(headlines)
    3. Weight by recency: w_i = exp(-age_hours / 24)
    4. Aggregate: sentiment = Σ(score_i * w_i) / Σ(w_i)
    5. Smooth: ema_sentiment = α * sentiment + (1-α) * prev_sentiment
    6. Calculate confidence + metadata
    
    Attributes:
        finbert: FinBERTEngine instance
        news_scraper: FinancialNewsScraper instance
        ema_alpha: EMA smoothing factor ∈ (0, 1)
        cache_hours: Cache lifetime in hours
        cache: Sentiment cache {ticker: result}
    
    Audit:
        AUDIT_FINANCE_PARTIE_5_ML.md p.15 (sentiment aggregation)
    """
    
    def __init__(
        self,
        finbert_engine: Optional[FinBERTEngine] = None,
        news_scraper: Optional[FinancialNewsScraper] = None,
        ema_alpha: float = 0.3,
        cache_hours: int = 1,
        default_method: str = "mean",
    ):
        """
        Initialize sentiment aggregator.
        
        Args:
            finbert_engine: FinBERTEngine instance (creates default if None)
            news_scraper: FinancialNewsScraper instance (creates default if None)
            ema_alpha: EMA smoothing factor
                0.3 = responsive (30% new, 70% old)
                0.5 = balanced
                0.1 = smooth (10% new, 90% old)
            cache_hours: Cache lifetime (avoid re-fetching news)
        
        Raises:
            ValueError: If ema_alpha not in (0, 1)
        
        Example:
            >>> agg = SentimentAggregator(ema_alpha=0.5, cache_hours=2)
        """
        if not 0 < ema_alpha < 1:
            raise ValueError(f"ema_alpha must be in (0, 1), got {ema_alpha}")
        if default_method not in {"mean", "median"}:
            raise ValueError("Méthode d'agrégation invalide: utilisez 'mean' ou 'median'")
        
        self.finbert = finbert_engine or FinBERTEngine()
        self.news_scraper = news_scraper or FinancialNewsScraper()
        self.ema_alpha = ema_alpha
        self.cache_hours = cache_hours
        self.default_method = default_method
        self.cache: Dict[str, Dict] = {}
        # Ensure logger propagates to root so pytest caplog can capture
        try:
            logger.propagate = True
        except Exception:
            pass
        
        logger.info(
            f"SentimentAggregator initialized: "
            f"ema_alpha={ema_alpha}, cache_hours={cache_hours}"
        )
    
    def aggregate_sentiment(
        self,
        ticker: str,
        window_days: int = 7,
        max_articles: int = 50,
        use_ema: bool = True,
        use_reddit: bool = False,
        previous_sentiment: Optional[float] = None
    ) -> Dict:
        """
        Aggregate sentiment for ticker from multiple news sources.
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL', 'MSFT')
            window_days: News lookback window (not enforced by scraper, informational)
            max_articles: Maximum articles to fetch
            use_ema: Apply EMA smoothing
            use_reddit: Include Reddit sources when fetching news (delegated to NewsScraper)
            previous_sentiment: Previous sentiment for EMA (if available)
        
        Returns:
            Dictionary with:
            - sentiment_score: float ∈ [-1, +1]
            - confidence: float ∈ [0, 1] (average confidence)
            - article_count: int (number of articles analyzed)
            - sources: List[str] (unique news sources)
            - bullish_pct: float (% positive articles)
            - bearish_pct: float (% negative articles)
            - neutral_pct: float (% neutral articles)
            - timestamp: datetime (aggregation time)
        
        Notes:
            - Returns neutral if no articles found
            - Uses cache if available (<cache_hours old)
            - Weights recent articles more heavily
        
        Example:
            >>> result = agg.aggregate_sentiment('TSLA', max_articles=100)
            >>> print(f"Sentiment: {result['sentiment_score']:.2f}")
            >>> print(f"Bullish: {result['bullish_pct']:.1%}")
        """
        # Check cache
        cache_key = ticker
        if cache_key in self.cache:
            cached_result = self.cache[cache_key]
            cached_time = cached_result['timestamp']
            age_hours = (datetime.now() - cached_time).total_seconds() / 3600
            
            if age_hours < self.cache_hours:
                logger.debug(f"Using cached sentiment for {ticker} (age={age_hours:.1f}h)")
                return cached_result
        
        # Fetch articles via existing NewsScraper
        try:
            logger.info(f"Fetching news for {ticker} (max={max_articles})")
            articles_df = self.news_scraper.get_all_news(
                ticker,
                max_articles=max_articles,
                include_reddit=use_reddit
            )
        except Exception as e:
            logger.error(f"News fetching failed for {ticker}: {e}")
            articles_df = pd.DataFrame()
        
        # Handle empty DataFrame
        if articles_df.empty:
            logger.warning(f"No articles found for {ticker}")
            return self._neutral_result()
        
        # Extract text for sentiment analysis
        # NewsScraper returns: ['headline', 'source', 'url', 'text', 'published']
        texts = []
        if 'headline' in articles_df.columns:
            texts = articles_df['headline'].dropna().tolist()
        elif 'text' in articles_df.columns:
            texts = articles_df['text'].dropna().tolist()
        else:
            logger.error(f"No text column found in articles for {ticker}")
            return self._neutral_result()
        
        if not texts:
            logger.warning(f"No valid text found in articles for {ticker}")
            return self._neutral_result()
        
        # Score each article with FinBERT
        logger.debug(f"Scoring {len(texts)} articles with FinBERT")
        article_sentiments = self.finbert.batch_sentiment(texts)
        
        # Extract scores, confidences, labels
        scores = np.array([s['score'] for s in article_sentiments])
        confidences = np.array([s['confidence'] for s in article_sentiments])
        labels = [s['label'] for s in article_sentiments]
        
        # Calculate recency weights (exponential decay)
        weights = self._calculate_recency_weights(articles_df)
        
        # Weighted average sentiment
        weighted_sentiment = np.sum(scores * weights)
        
        # EMA smoothing
        if use_ema and previous_sentiment is not None:
            ema_sentiment = (
                self.ema_alpha * weighted_sentiment +
                (1 - self.ema_alpha) * previous_sentiment
            )
            logger.debug(
                f"EMA applied: raw={weighted_sentiment:.3f}, "
                f"prev={previous_sentiment:.3f}, "
                f"ema={ema_sentiment:.3f}"
            )
        else:
            ema_sentiment = weighted_sentiment
        
        # Calculate confidence (average)
        avg_confidence = float(np.mean(confidences))
        
        # Label distribution
        n_bullish = sum(1 for label in labels if label == 'positive')
        n_bearish = sum(1 for label in labels if label == 'negative')
        n_neutral = len(labels) - n_bullish - n_bearish
        
        # Unique sources
        sources = []
        if 'source' in articles_df.columns:
            sources = list(set(articles_df['source'].dropna().tolist()))
        
        # Build result
        result = {
            'sentiment_score': float(ema_sentiment),
            'confidence': avg_confidence,
            'article_count': len(articles_df),
            'sources': sources,
            'bullish_pct': n_bullish / len(labels) if labels else 0.0,
            'bearish_pct': n_bearish / len(labels) if labels else 0.0,
            'neutral_pct': n_neutral / len(labels) if labels else 1.0,
            'timestamp': datetime.now()
        }
        
        # Cache result
        self.cache[cache_key] = result
        
        logger.info(
            f"Sentiment aggregated for {ticker}: "
            f"score={result['sentiment_score']:.2f}, "
            f"confidence={result['confidence']:.2f}, "
            f"articles={result['article_count']}, "
            f"sources={len(sources)}"
        )
        
        return result

    # --- API attendue par les tests -------------------------------------------------
    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """
        Valide que le DataFrame contient les colonnes minimales pour agrégation.

        Exigences minimales:
          - 'sentiment_score' (pour toutes les agrégations)
          - 'ticker' pour aggregate_by_ticker
          - 'source' pour aggregate_by_source et aggregate_weighted
        """
        if df is None or df.empty:
            raise ValueError("DataFrame vide")
        required = {"sentiment_score"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Colonnes manquantes: {sorted(missing)}")

    def _agg_func(self, series: pd.Series) -> float:
        return float(series.mean()) if self.default_method == "mean" else float(series.median())

    def aggregate_by_date(self, df: pd.DataFrame, period: str = "D") -> pd.DataFrame:
        """
        Agrège par date en utilisant resample sur l'index Datetime.
        Retourne un DataFrame avec colonnes: sentiment_score, count.
        """
        self._validate_dataframe(df)

        if not isinstance(df.index, pd.DatetimeIndex):
            # Essayer de convertir une colonne 'date' si présente
            if 'date' in df.columns:
                df = df.copy()
                df.index = pd.to_datetime(df['date'])
                df.index.name = 'date'
            else:
                df = df.copy()
                df.index = pd.to_datetime(df.index)
                df.index.name = 'date'

        valid_periods = {"D", "W", "M"}
        if period not in valid_periods:
            # Log via module logger and root logger for caplog capture
            logger.warning(f"Période invalide '{period}', fallback à 'D'")
            logging.warning(f"Période invalide '{period}', fallback à 'D'")
            period = "D"

        grouped = df.resample(period)
        agg_df = pd.DataFrame({
            "sentiment_score": grouped['sentiment_score'].apply(self._agg_func),
            "count": grouped['sentiment_score'].count(),
        })
        return agg_df

    def aggregate_by_ticker(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Agrège par ticker et retourne un dict[ticker, metrics]."""
        self._validate_dataframe(df)
        if 'ticker' not in df.columns:
            raise ValueError("Colonne 'ticker' manquante")

        grouped = df.groupby('ticker')
        result: Dict[str, Dict[str, float]] = {}
        for tkr, g in grouped:
            result[tkr] = {
                'sentiment_score': self._agg_func(g['sentiment_score']),
                'count': int(g['sentiment_score'].count()),
            }
        return result

    def aggregate_by_source(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Agrège par source et retourne un dict[source, metrics]."""
        self._validate_dataframe(df)
        if 'source' not in df.columns:
            raise ValueError("Colonne 'source' manquante")

        grouped = df.groupby('source')
        result: Dict[str, Dict[str, float]] = {}
        for src, g in grouped:
            result[src] = {
                'sentiment_score': self._agg_func(g['sentiment_score']),
                'count': int(g['sentiment_score'].count()),
            }
        return result

    def aggregate_weighted(self, df: pd.DataFrame, weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """
        Agrégation pondérée par source. Si weights est None, fallback sur moyenne simple.
        Retourne {'sentiment_score': float, 'count': int}
        """
        self._validate_dataframe(df)
        if weights is None:
            logger.warning("Pas de weights fournis, utilisation de la mean simple")
            logging.warning("Pas de weights fournis, utilisation de la mean simple")
            return {
                'sentiment_score': float(df['sentiment_score'].mean()) if not df.empty else 0.0,
                'count': int(df['sentiment_score'].count()),
            }
        if 'source' not in df.columns:
            raise ValueError("Colonne 'source' manquante pour agrégation pondérée")

        tmp = df.copy()
        tmp['__w__'] = tmp['source'].map(lambda s: float(weights.get(s, 0.0)))
        # Si aucune weight positive, fallback mean
        if tmp['__w__'].sum() <= 0:
            logger.warning("Weights non valides, fallback mean simple")
            return {
                'sentiment_score': float(df['sentiment_score'].mean()) if not df.empty else 0.0,
                'count': int(df['sentiment_score'].count()),
            }
        score = float((tmp['sentiment_score'] * tmp['__w__']).sum() / tmp['__w__'].sum())
        return {'sentiment_score': score, 'count': int(df['sentiment_score'].count())}

    def get_sentiment_trend(self, df: pd.DataFrame, period: str = 'D') -> pd.DataFrame:
        """Alias pratique pour aggregate_by_date (trend temporel)."""
        return self.aggregate_by_date(df, period=period)
    
    def _calculate_recency_weights(self, articles_df: pd.DataFrame) -> np.ndarray:
        """
        Calculate recency weights for articles (exponential decay).
        
        Weight function: w_i = exp(-age_hours / half_life)
        Half-life = 24 hours (weight halves every day)
        
        Args:
            articles_df: Articles DataFrame with 'published' or 'date' column
        
        Returns:
            Normalized weights array (sum = 1.0)
        """
        now = datetime.now()
        weights = []
        
        # Get timestamps
        if 'published' in articles_df.columns:
            timestamps = pd.to_datetime(articles_df['published'], errors='coerce')
        elif 'date' in articles_df.columns:
            timestamps = pd.to_datetime(articles_df['date'], errors='coerce')
        else:
            # No timestamp column -> equal weights
            return np.ones(len(articles_df)) / len(articles_df)
        
        # Calculate weights
        for ts in timestamps:
            if pd.isna(ts):
                weights.append(1.0)  # Fallback for missing timestamps
            else:
                age_hours = (now - ts).total_seconds() / 3600
                # Exponential decay: half-life = 24 hours
                weight = np.exp(-age_hours / 24)
                weights.append(weight)
        
        # Normalize to sum=1
        weights = np.array(weights)
        weights = weights / np.sum(weights)
        
        return weights
    
    def _neutral_result(self) -> Dict:
        """Return neutral sentiment result (used when no articles found)."""
        return {
            'sentiment_score': 0.0,
            'confidence': 0.0,
            'article_count': 0,
            'sources': [],
            'bullish_pct': 0.0,
            'bearish_pct': 0.0,
            'neutral_pct': 1.0,
            'timestamp': datetime.now()
        }
    
    def clear_cache(self) -> None:
        """Clear sentiment cache."""
        self.cache.clear()
        logger.debug("Sentiment cache cleared")


__all__ = ['SentimentAggregator']
