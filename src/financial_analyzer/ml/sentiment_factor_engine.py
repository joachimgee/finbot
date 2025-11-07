"""
Sentiment-based alpha factor engine.

Integrates news sentiment scores with technical/fundamental factors
to generate news-driven trading signals.

This module implements sentiment factor computation following the
methodologies outlined in:
- Tetlock (2007): "Giving Content to Investor Sentiment: The Measure of Media Pessimism"
  https://doi.org/10.1111/j.1540-6261.2007.01232.x
- Loughran & McDonald (2011): "When Is a Liability Not a Liability? Textual Analysis,
  Dictionaries, and 10-Ks"
  https://doi.org/10.1111/j.1540-6261.2010.01625.x
- Bollen et al. (2011): "Twitter mood predicts the stock market"
  https://doi.org/10.1016/j.jocs.2010.12.007

The engine computes 15+ sentiment-based alpha factors including:
- Moving averages of sentiment (trend)
- Sentiment volatility (uncertainty)
- Sentiment momentum (change)
- News attention metrics (article counts)
- Dispersion measures (disagreement)
- Extreme sentiment ratios
- Recency-weighted sentiment

Example:
    >>> from financial_analyzer.ml.sentiment_factor_engine import SentimentFactorEngine
    >>> from financial_analyzer.data.news_scraper import FinancialNewsScraper
    >>> 
    >>> # Fetch news with sentiment
    >>> scraper = FinancialNewsScraper()
    >>> news_df = scraper.get_all_news("AAPL", max_articles=100)
    >>> news_with_sentiment = scraper.add_sentiment_scores(news_df)
    >>> 
    >>> # Generate sentiment factors
    >>> engine = SentimentFactorEngine(news_with_sentiment)
    >>> sentiment_factors = engine.compute_sentiment_factors()
    >>> 
    >>> # Access specific factors
    >>> sent_ma_5d = sentiment_factors['SENT_MA_5D']
    >>> print(f"5-day sentiment MA: {sent_ma_5d.values[-1]:.3f}")
    5-day sentiment MA: 0.245
    >>> 
    >>> # Get factors as DataFrame
    >>> factors_df = engine.get_factors_dataframe(sentiment_factors)
    >>> print(factors_df.shape)
    (50, 23)  # 50 days, 23 factors
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SentimentFactorResult:
    """Result of sentiment factor computation.
    
    Stores the factor name, values (time series), description, category,
    and count of valid (non-NaN) data points.
    
    Attributes:
        name: Factor name (unique identifier, e.g., 'SENT_MA_5D')
        values: Time series of factor values with DatetimeIndex
        description: Human-readable description of the factor
        category: Category label (always 'Sentiment' for this engine)
        valid_data: Count of non-NaN values in the series
        
    Example:
        >>> factor = SentimentFactorResult(
        ...     name='SENT_MA_5D',
        ...     values=pd.Series([0.2, 0.3, 0.25], index=pd.date_range('2024-01-01', periods=3)),
        ...     description='5-day moving average of sentiment',
        ...     category='Sentiment',
        ...     valid_data=3
        ... )
        >>> print(factor.name)
        SENT_MA_5D
        >>> print(factor.valid_data)
        3
    """
    name: str
    values: pd.Series
    description: str
    category: str = "Sentiment"
    valid_data: int = 0
    
    def __post_init__(self) -> None:
        """Compute valid_data count after initialization."""
        if isinstance(self.values, pd.Series):
            self.valid_data = int(self.values.notna().sum())
        else:
            self.valid_data = 0


class SentimentFactorEngine:
    """
    Generate alpha factors from news sentiment data.
    
    Computes sentiment-based factors following academic research on
    news sentiment and market returns. Implements moving averages,
    volatility, momentum, and dispersion measures.
    
    The engine expects news data with sentiment scores (typically from
    FinBERT or similar sentiment analysis models) and produces daily
    aggregated sentiment factors that can be used for trading signal
    generation or combined with technical factors.
    
    Factors Computed:
        **Period-based factors** (for each period in [1, 5, 20, 60] days):
        - SENT_MA_{period}D: Moving average of sentiment over N days
        - SENT_VOL_{period}D: Volatility of sentiment (standard deviation)
        - SENT_MOM_{period}D: Change in sentiment over N days (momentum)
        - NEWS_COUNT_{period}D: Rolling sum of news article counts
        
        **Non-period-dependent factors**:
        - SENT_DISPERSION: Daily standard deviation of sentiment (disagreement)
        - SENT_SURPRISE: Deviation from 5-day moving average
        - SENT_EXTREME_POS: Ratio of extremely positive news (sentiment > 0.5)
        - SENT_EXTREME_NEG: Ratio of extremely negative news (sentiment < -0.5)
        - SENT_RANGE: Daily range (max - min sentiment)
        - SENT_WEIGHTED: Recency-weighted sentiment (exponential decay)
    
    Args:
        news_df: DataFrame with news and sentiment scores. Must contain:
                 - 'sentiment' column: Sentiment scores (float, typically [-1, 1])
                 - DatetimeIndex or 'published' column with dates
                 Optional columns: 'sentiment_label', 'headline', 'source'
                 
    Raises:
        ValueError: If required columns are missing, data is empty, or dates are invalid
        TypeError: If news_df is not a pandas DataFrame
        
    Example:
        >>> # Create engine from news with sentiment
        >>> engine = SentimentFactorEngine(news_with_sentiment)
        >>> 
        >>> # Compute all factors with default periods [1, 5, 20, 60]
        >>> factors = engine.compute_sentiment_factors()
        >>> print(f"Generated {len(factors)} factors")
        Generated 23 factors
        >>> 
        >>> # Compute with custom periods
        >>> factors_custom = engine.compute_sentiment_factors(periods=[1, 5, 10, 30])
        >>> 
        >>> # Access individual factors
        >>> print(factors['SENT_MA_5D'].description)
        5-day moving average of sentiment
        >>> 
        >>> # Get factors as DataFrame
        >>> df = engine.get_factors_dataframe(factors)
        >>> print(df.shape)  # (n_days, n_factors)
        (50, 23)
        >>> 
        >>> # Check valid data coverage
        >>> for name, factor in factors.items():
        ...     coverage = factor.valid_data / len(factor.values)
        ...     print(f"{name}: {coverage:.1%} coverage")
    
    References:
        - Tetlock, P. C. (2007). "Giving content to investor sentiment: The measure
          of media pessimism." Journal of Finance, 62(3), 1139-1168.
        - Loughran, T., & McDonald, B. (2011). "When is a liability not a liability?
          Textual analysis, dictionaries, and 10‐Ks." Journal of Finance, 66(1), 35-65.
        - Bollen, J., Mao, H., & Zeng, X. (2011). "Twitter mood predicts the stock
          market." Journal of Computational Science, 2(1), 1-8.
    """
    
    def __init__(self, news_df: pd.DataFrame) -> None:
        """Initialize with news + sentiment data.
        
        Args:
            news_df: DataFrame with news and sentiment scores
            
        Raises:
            ValueError: If required columns missing, data empty, or dates invalid
            TypeError: If news_df is not DataFrame
            
        Example:
            >>> engine = SentimentFactorEngine(news_with_sentiment)
            >>> print(f"Initialized with {len(engine.news_df)} articles")
        """
        if not isinstance(news_df, pd.DataFrame):
            raise TypeError(
                f"news_df must be pandas DataFrame, got {type(news_df).__name__}"
            )
        
        if len(news_df) == 0:
            raise ValueError("news_df cannot be empty")
        
        # Validation: Check required columns
        required_cols = ['sentiment']
        missing_cols = [col for col in required_cols if col not in news_df.columns]
        if missing_cols:
            raise ValueError(
                f"news_df missing required columns: {missing_cols}. "
                f"Available columns: {list(news_df.columns)}"
            )
        
        # Ensure published is DatetimeIndex
        if not isinstance(news_df.index, pd.DatetimeIndex):
            if 'published' in news_df.columns:
                news_df = news_df.set_index('published')
                logger.debug("Set 'published' column as index")
            else:
                raise ValueError(
                    "news_df must have DatetimeIndex or 'published' column. "
                    f"Current index type: {type(news_df.index).__name__}"
                )
        
        # Ensure timezone-aware (UTC)
        if news_df.index.tz is None:
            news_df.index = news_df.index.tz_localize('UTC')
            logger.debug("Localized index to UTC timezone")
        elif str(news_df.index.tz) != 'UTC':
            news_df.index = news_df.index.tz_convert('UTC')
            logger.debug(f"Converted index to UTC (was {news_df.index.tz})")
        
        # Sort by date (oldest to newest)
        self.news_df = news_df.sort_index()
        
        # Validate sentiment values
        if not np.issubdtype(self.news_df['sentiment'].dtype, np.number):
            raise ValueError(
                f"'sentiment' column must be numeric, got {self.news_df['sentiment'].dtype}"
            )
        
        logger.info(
            f"SentimentFactorEngine initialized with {len(self.news_df)} news articles "
            f"spanning {self.news_df.index.min().date()} to {self.news_df.index.max().date()}"
        )
        
    def compute_sentiment_factors(
        self,
        periods: Optional[List[int]] = None
    ) -> Dict[str, SentimentFactorResult]:
        """
        Compute all sentiment-based factors.
        
        Generates both period-dependent factors (MA, volatility, momentum, news count)
        and period-independent factors (dispersion, surprise, extremes, range, weighted).
        
        Args:
            periods: List of lookback periods (days) for rolling calculations.
                     Default: [1, 5, 20, 60] (1D, 1W, 1M, 3M approximations)
            
        Returns:
            Dictionary mapping factor_name → SentimentFactorResult
            Contains 4*len(periods) + 6 factors (23 with default periods)
            
        Example:
            >>> # Default periods
            >>> factors = engine.compute_sentiment_factors()
            >>> print(f"Generated {len(factors)} factors")
            Generated 23 factors
            >>> 
            >>> # Custom periods
            >>> factors = engine.compute_sentiment_factors(periods=[1, 5, 20])
            >>> print(list(factors.keys())[:5])
            ['SENT_MA_1D', 'SENT_MA_5D', 'SENT_MA_20D', 'SENT_VOL_1D', 'SENT_VOL_5D']
            >>> 
            >>> # Check a specific factor
            >>> sent_ma_5d = factors['SENT_MA_5D']
            >>> print(f"Valid data: {sent_ma_5d.valid_data}/{len(sent_ma_5d.values)}")
            Valid data: 45/50
        """
        if periods is None:
            periods = [1, 5, 20, 60]
        
        factors: Dict[str, SentimentFactorResult] = {}
        
        # Resample to daily frequency
        # Aggregations: mean (average sentiment), std (dispersion), count (attention),
        # min/max (range calculation)
        daily_sentiment = self.news_df.resample('D')['sentiment'].agg([
            ('mean', 'mean'),
            ('std', 'std'),
            ('count', 'count'),
            ('min', 'min'),
            ('max', 'max')
        ])
        
        # Note: We keep NaN for days without news (no artificial fill)
        # This preserves signal quality and avoids introducing bias
        
        logger.info(
            f"Resampled to daily: {len(daily_sentiment)} days, "
            f"{daily_sentiment['count'].sum():.0f} total articles"
        )
        
        # ===================================================================
        # PERIOD-BASED FACTORS (4 factors per period)
        # ===================================================================
        
        for period in periods:
            # 1. Sentiment Moving Average (trend indicator)
            factors[f'SENT_MA_{period}D'] = SentimentFactorResult(
                name=f'SENT_MA_{period}D',
                values=daily_sentiment['mean'].rolling(period, min_periods=1).mean(),
                description=f'{period}-day moving average of sentiment (trend indicator)',
                category='Sentiment'
            )
            
            # 2. Sentiment Volatility (uncertainty/risk indicator)
            factors[f'SENT_VOL_{period}D'] = SentimentFactorResult(
                name=f'SENT_VOL_{period}D',
                values=daily_sentiment['mean'].rolling(period, min_periods=1).std(),
                description=f'{period}-day volatility of sentiment (uncertainty measure)',
                category='Sentiment'
            )
            
            # 3. Sentiment Momentum (rate of change)
            factors[f'SENT_MOM_{period}D'] = SentimentFactorResult(
                name=f'SENT_MOM_{period}D',
                values=daily_sentiment['mean'].diff(period),
                description=f'{period}-day change in sentiment (momentum indicator)',
                category='Sentiment'
            )
            
            # 4. News Count (attention/coverage metric)
            factors[f'NEWS_COUNT_{period}D'] = SentimentFactorResult(
                name=f'NEWS_COUNT_{period}D',
                values=daily_sentiment['count'].rolling(period, min_periods=1).sum(),
                description=f'{period}-day total news article count (attention proxy)',
                category='Sentiment'
            )
        
        # ===================================================================
        # NON-PERIOD-DEPENDENT FACTORS (6 factors)
        # ===================================================================
        
        # 5. Daily Dispersion (disagreement among news sources)
        factors['SENT_DISPERSION'] = SentimentFactorResult(
            name='SENT_DISPERSION',
            values=daily_sentiment['std'],
            description='Daily sentiment dispersion (disagreement among news sources)',
            category='Sentiment'
        )
        
        # 6. Sentiment Surprise (deviation from expected sentiment)
        sent_ma_5d = daily_sentiment['mean'].rolling(5, min_periods=1).mean()
        factors['SENT_SURPRISE'] = SentimentFactorResult(
            name='SENT_SURPRISE',
            values=daily_sentiment['mean'] - sent_ma_5d,
            description='Sentiment surprise (deviation from 5D moving average)',
            category='Sentiment'
        )
        
        # 7. Extreme Positive Sentiment Ratio
        # Compute % of extremely positive news per day (sentiment > 0.5)
        def compute_extreme_pos_ratio(group: pd.DataFrame) -> float:
            """Compute ratio of extremely positive news."""
            if len(group) == 0:
                return np.nan
            return (group['sentiment'] > 0.5).sum() / len(group)
        
        extreme_pos_ratio = self.news_df.resample('D').apply(compute_extreme_pos_ratio)
        factors['SENT_EXTREME_POS'] = SentimentFactorResult(
            name='SENT_EXTREME_POS',
            values=extreme_pos_ratio,
            description='Ratio of extremely positive news (sentiment > 0.5)',
            category='Sentiment'
        )
        
        # 8. Extreme Negative Sentiment Ratio
        def compute_extreme_neg_ratio(group: pd.DataFrame) -> float:
            """Compute ratio of extremely negative news."""
            if len(group) == 0:
                return np.nan
            return (group['sentiment'] < -0.5).sum() / len(group)
        
        extreme_neg_ratio = self.news_df.resample('D').apply(compute_extreme_neg_ratio)
        factors['SENT_EXTREME_NEG'] = SentimentFactorResult(
            name='SENT_EXTREME_NEG',
            values=extreme_neg_ratio,
            description='Ratio of extremely negative news (sentiment < -0.5)',
            category='Sentiment'
        )
        
        # 9. Sentiment Range (intraday volatility proxy)
        factors['SENT_RANGE'] = SentimentFactorResult(
            name='SENT_RANGE',
            values=daily_sentiment['max'] - daily_sentiment['min'],
            description='Daily sentiment range (max - min, volatility proxy)',
            category='Sentiment'
        )
        
        # 10. Recency-Weighted Sentiment (exponentially weighted for recent bias)
        def compute_weighted_sentiment(group: pd.DataFrame) -> float:
            """Compute exponentially-weighted sentiment within daily group.
            
            Assigns higher weights to more recent news within the day.
            """
            if len(group) == 0:
                return np.nan
            # Weights: newer articles = higher weight (exponential decay)
            # Use linspace to create increasing weights (0 to 1)
            weights = np.exp(np.linspace(0, 1, len(group)))
            return float(np.average(group['sentiment'], weights=weights))
        
        weighted_sent = self.news_df.resample('D').apply(compute_weighted_sentiment)
        factors['SENT_WEIGHTED'] = SentimentFactorResult(
            name='SENT_WEIGHTED',
            values=weighted_sent,
            description='Recency-weighted sentiment (exponential decay within day)',
            category='Sentiment'
        )
        
        logger.info(
            f"Computed {len(factors)} sentiment factors: "
            f"{4*len(periods)} period-based + {len(factors) - 4*len(periods)} general"
        )
        
        return factors
    
    def compute_event_sentiment(
        self,
        event_dates: pd.DatetimeIndex,
        window_before: int = 5,
        window_after: int = 5
    ) -> pd.DataFrame:
        """
        Compute sentiment around specific events (earnings, M&A, etc.).
        
        Useful for event study analysis to measure sentiment shifts
        around corporate events. Splits sentiment into pre-event and
        post-event windows.
        
        Args:
            event_dates: Dates of events (timezone-aware UTC recommended)
            window_before: Days before event to include (default: 5)
            window_after: Days after event to include (default: 5)
            
        Returns:
            DataFrame with columns:
            - event_date: Date of event
            - pre_sentiment: Mean sentiment before event (window_before days)
            - post_sentiment: Mean sentiment after event (window_after days)
            - sentiment_change: Change in sentiment (post - pre)
            - news_count_pre: Number of news articles before event
            - news_count_post: Number of news articles after event
            
        Example:
            >>> # Analyze sentiment around earnings dates
            >>> earnings_dates = pd.to_datetime([
            ...     '2024-01-25', '2024-04-25', '2024-07-25'
            ... ], utc=True)
            >>> event_sent = engine.compute_event_sentiment(
            ...     earnings_dates, window_before=3, window_after=3
            ... )
            >>> print(event_sent)
               event_date  pre_sentiment  post_sentiment  sentiment_change  ...
            0  2024-01-25          0.120           0.350             0.230  ...
            >>> 
            >>> # Find events with largest sentiment shift
            >>> top_shifts = event_sent.nlargest(3, 'sentiment_change')
            >>> print(top_shifts[['event_date', 'sentiment_change']])
        """
        # Ensure event_dates is DatetimeIndex
        if not isinstance(event_dates, pd.DatetimeIndex):
            event_dates = pd.DatetimeIndex(event_dates)
        
        # Ensure timezone-aware
        if event_dates.tz is None:
            event_dates = event_dates.tz_localize('UTC')
            logger.debug("Localized event_dates to UTC")
        
        results: List[Dict] = []
        
        for event_date in event_dates:
            # Get news around event
            start = event_date - pd.Timedelta(days=window_before)
            end = event_date + pd.Timedelta(days=window_after)
            
            try:
                news_window = self.news_df.loc[start:end]
            except KeyError:
                logger.warning(
                    f"Event {event_date.date()} outside news range, skipping"
                )
                continue
            
            if len(news_window) == 0:
                logger.warning(
                    f"No news found around event {event_date.date()} "
                    f"(window: {window_before}d before, {window_after}d after)"
                )
                continue
            
            # Split pre/post event
            pre_event_news = news_window[news_window.index < event_date]
            post_event_news = news_window[news_window.index >= event_date]
            
            pre_sentiment = (
                pre_event_news['sentiment'].mean() 
                if len(pre_event_news) > 0 
                else np.nan
            )
            post_sentiment = (
                post_event_news['sentiment'].mean() 
                if len(post_event_news) > 0 
                else np.nan
            )
            
            results.append({
                'event_date': event_date,
                'pre_sentiment': pre_sentiment,
                'post_sentiment': post_sentiment,
                'sentiment_change': post_sentiment - pre_sentiment,
                'news_count_pre': len(pre_event_news),
                'news_count_post': len(post_event_news)
            })
        
        df = pd.DataFrame(results)
        
        if len(df) > 0:
            logger.info(
                f"Event sentiment computed for {len(df)}/{len(event_dates)} events "
                f"(mean change: {df['sentiment_change'].mean():.4f})"
            )
        else:
            logger.warning("No events had sufficient news data")
        
        return df
    
    def get_factors_dataframe(
        self,
        factors: Dict[str, SentimentFactorResult]
    ) -> pd.DataFrame:
        """
        Convert factor dictionary to DataFrame.
        
        Combines all factor time series into a single DataFrame with
        factors as columns and dates as rows.
        
        Args:
            factors: Dict of SentimentFactorResult (from compute_sentiment_factors)
            
        Returns:
            DataFrame with columns = factor names, index = dates (DatetimeIndex)
            
        Example:
            >>> factors = engine.compute_sentiment_factors()
            >>> df = engine.get_factors_dataframe(factors)
            >>> print(df.columns)
            Index(['SENT_MA_1D', 'SENT_MA_5D', 'SENT_MA_20D', ...], dtype='object')
            >>> print(df.shape)
            (50, 23)  # 50 days, 23 factors
            >>> 
            >>> # Check for NaN coverage
            >>> nan_ratio = df.isna().sum() / len(df)
            >>> print(nan_ratio[nan_ratio > 0.5])  # Factors with >50% NaN
        """
        df = pd.DataFrame({
            name: result.values
            for name, result in factors.items()
        })
        
        logger.debug(
            f"Created factors DataFrame: {df.shape[0]} days x {df.shape[1]} factors"
        )
        
        return df
