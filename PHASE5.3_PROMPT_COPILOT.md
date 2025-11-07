# 🚀 PHASE 5.3 - NEWS & SENTIMENT INTEGRATION - PROMPT COMPLET POUR COPILOT

**PRIORITÉ ABSOLUE: QUALITÉ > VITESSE**
- Type hints 100%
- Google docstrings exhaustives
- Tests compréhensifs (60+ tests)
- Error handling robuste
- Academic references
- Production-grade code
- utilisation des forks dans AUDIT_FORKS

---

## 📋 CONTEXT

**Vous avez déjà:**
- ✅ `news_scraper.py` (1000+ LOC, 4 sources, FinBERT sentiment batch)
- ✅ `feature_engineering.py` (91 technical/value/alternative factors)
- ✅ `feature_optimization.py` (cache + parallel)
- ✅ `feature_selection_advanced.py` (IC analysis)

**Mission Phase 5.3:**
Intégrer news + sentiment → signaux de trading news-driven.

**Références académiques (à citer dans docstrings):**
- MacKinlay (1997): Event studies methodology
- Tetlock (2007): News sentiment → stock returns
- Bollen et al. (2011): Twitter sentiment → market prediction
- Loughran-McDonald (2011): Financial sentiment lexicon

---

## 📦 FICHIER 1/4: `sentiment_factor_engine.py`

**Path:** `src/financial_analyzer/ml/sentiment_factor_engine.py`

**Objectif:** Générer 15+ facteurs alpha à partir des scores de sentiment des news.

### Spécifications Complètes:

```python
"""
Sentiment-based alpha factor engine.

Integrates news sentiment scores with technical/fundamental factors
to generate news-driven trading signals.

This module implements sentiment factor computation following the
methodologies outlined in:
- Tetlock (2007): "Giving Content to Investor Sentiment"
- Loughran & McDonald (2011): "When Is a Liability Not a Liability?"
- Bollen et al. (2011): "Twitter mood predicts the stock market"

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
    
    Attributes:
        name: Factor name (unique identifier)
        values: Time series of factor values (DatetimeIndex)
        description: Human-readable description
        category: Category (always 'Sentiment')
        valid_data: Count of non-NaN values
        
    Example:
        >>> factor = SentimentFactorResult(
        ...     name='SENT_MA_5D',
        ...     values=pd.Series([0.2, 0.3, 0.25]),
        ...     description='5-day moving average of sentiment',
        ...     category='Sentiment',
        ...     valid_data=3
        ... )
    """
    name: str
    values: pd.Series
    description: str
    category: str = "Sentiment"
    valid_data: int = 0
    
    def __post_init__(self) -> None:
        """Compute valid_data after initialization."""
        self.valid_data = int(self.values.notna().sum())


class SentimentFactorEngine:
    """
    Generate alpha factors from news sentiment data.
    
    Computes sentiment-based factors following academic research on
    news sentiment and market returns. Implements moving averages,
    volatility, momentum, and dispersion measures.
    
    Factors computed:
    - **SENT_MA_{period}D**: Moving average of sentiment over N days
    - **SENT_VOL_{period}D**: Volatility of sentiment (std dev)
    - **SENT_MOMENTUM_{period}D**: Change in sentiment over N days
    - **SENT_DISPERSION**: Disagreement in sentiment (std of scores)
    - **SENT_SURPRISE**: Deviation from expected sentiment
    - **NEWS_COUNT_{period}D**: Number of news articles per period
    - **SENT_WEIGHTED**: Sentiment weighted by news recency
    - **SENT_EXTREME_POS**: % of extremely positive news (>0.5)
    - **SENT_EXTREME_NEG**: % of extremely negative news (<-0.5)
    
    Args:
        news_df: DataFrame with columns ['published', 'sentiment', 'sentiment_label']
                 Index should be DatetimeIndex or 'published' column present.
                 
    Raises:
        ValueError: If required columns are missing
        TypeError: If news_df is not a pandas DataFrame
        
    Example:
        >>> # Create engine from news with sentiment
        >>> engine = SentimentFactorEngine(news_with_sentiment)
        >>> 
        >>> # Compute all factors with custom periods
        >>> factors = engine.compute_sentiment_factors(periods=[1, 5, 20, 60])
        >>> 
        >>> # Access individual factors
        >>> print(factors['SENT_MA_5D'].description)
        '5-day moving average of sentiment'
        >>> 
        >>> # Get factors as DataFrame
        >>> df = engine.get_factors_dataframe(factors)
        >>> print(df.shape)  # (n_days, n_factors)
    """
    
    def __init__(self, news_df: pd.DataFrame) -> None:
        """Initialize with news + sentiment data.
        
        Args:
            news_df: DataFrame with news and sentiment scores
            
        Raises:
            ValueError: If required columns missing or data invalid
            TypeError: If news_df is not DataFrame
        """
        if not isinstance(news_df, pd.DataFrame):
            raise TypeError(f"news_df must be DataFrame, got {type(news_df)}")
        
        # Validation
        required_cols = ['sentiment']
        missing_cols = [col for col in required_cols if col not in news_df.columns]
        if missing_cols:
            raise ValueError(
                f"news_df missing required columns: {missing_cols}. "
                f"Available: {list(news_df.columns)}"
            )
        
        # Ensure published is DatetimeIndex
        if not isinstance(news_df.index, pd.DatetimeIndex):
            if 'published' in news_df.columns:
                news_df = news_df.set_index('published')
            else:
                raise ValueError(
                    "news_df must have DatetimeIndex or 'published' column"
                )
        
        # Ensure timezone-aware (UTC)
        if news_df.index.tz is None:
            news_df.index = news_df.index.tz_localize('UTC')
        
        self.news_df = news_df.sort_index()
        
        logger.info(
            f"SentimentFactorEngine initialized with {len(news_df)} news articles "
            f"spanning {news_df.index.min()} to {news_df.index.max()}"
        )
        
    def compute_sentiment_factors(
        self,
        periods: Optional[List[int]] = None
    ) -> Dict[str, SentimentFactorResult]:
        """
        Compute all sentiment-based factors.
        
        Args:
            periods: List of lookback periods (days) for rolling calculations.
                     Default: [1, 5, 20, 60]
            
        Returns:
            Dictionary mapping factor_name → SentimentFactorResult
            
        Example:
            >>> factors = engine.compute_sentiment_factors(periods=[1, 5, 20])
            >>> print(f"Generated {len(factors)} factors")
            Generated 15 factors
        """
        if periods is None:
            periods = [1, 5, 20, 60]
        
        factors = {}
        
        # Resample to daily frequency
        # Aggregations: mean, std (dispersion), count
        daily_sentiment = self.news_df.resample('D')['sentiment'].agg({
            'mean': 'mean',
            'std': 'std',
            'count': 'count',
            'min': 'min',
            'max': 'max'
        })
        
        # Forward-fill NaN for days without news (optional: can be left as NaN)
        # For now: leave as NaN to avoid introducing artificial signals
        
        logger.info(f"Resampled to daily: {len(daily_sentiment)} days")
        
        # === Period-based factors ===
        for period in periods:
            # 1. Moving average
            factors[f'SENT_MA_{period}D'] = SentimentFactorResult(
                name=f'SENT_MA_{period}D',
                values=daily_sentiment['mean'].rolling(period, min_periods=1).mean(),
                description=f'{period}-day moving average of sentiment',
                category='Sentiment'
            )
            
            # 2. Sentiment volatility (risk)
            factors[f'SENT_VOL_{period}D'] = SentimentFactorResult(
                name=f'SENT_VOL_{period}D',
                values=daily_sentiment['mean'].rolling(period, min_periods=1).std(),
                description=f'{period}-day volatility of sentiment (uncertainty)',
                category='Sentiment'
            )
            
            # 3. Sentiment momentum (change)
            factors[f'SENT_MOM_{period}D'] = SentimentFactorResult(
                name=f'SENT_MOM_{period}D',
                values=daily_sentiment['mean'].diff(period),
                description=f'{period}-day change in sentiment (momentum)',
                category='Sentiment'
            )
            
            # 4. News count (attention/coverage)
            factors[f'NEWS_COUNT_{period}D'] = SentimentFactorResult(
                name=f'NEWS_COUNT_{period}D',
                values=daily_sentiment['count'].rolling(period, min_periods=1).sum(),
                description=f'{period}-day total news article count (attention)',
                category='Sentiment'
            )
        
        # === Non-period-dependent factors ===
        
        # 5. Daily dispersion (disagreement)
        factors['SENT_DISPERSION'] = SentimentFactorResult(
            name='SENT_DISPERSION',
            values=daily_sentiment['std'],
            description='Daily sentiment dispersion (disagreement among news)',
            category='Sentiment'
        )
        
        # 6. Sentiment surprise (deviation from 5D MA)
        sent_ma_5d = daily_sentiment['mean'].rolling(5, min_periods=1).mean()
        factors['SENT_SURPRISE'] = SentimentFactorResult(
            name='SENT_SURPRISE',
            values=daily_sentiment['mean'] - sent_ma_5d,
            description='Sentiment surprise (deviation from 5D moving average)',
            category='Sentiment'
        )
        
        # 7. Extreme positive sentiment ratio
        # Compute % of extremely positive news per day (sentiment > 0.5)
        extreme_pos_ratio = self.news_df.resample('D').apply(
            lambda x: (x['sentiment'] > 0.5).sum() / len(x) if len(x) > 0 else np.nan
        )
        factors['SENT_EXTREME_POS'] = SentimentFactorResult(
            name='SENT_EXTREME_POS',
            values=extreme_pos_ratio,
            description='Ratio of extremely positive news (sentiment > 0.5)',
            category='Sentiment'
        )
        
        # 8. Extreme negative sentiment ratio
        extreme_neg_ratio = self.news_df.resample('D').apply(
            lambda x: (x['sentiment'] < -0.5).sum() / len(x) if len(x) > 0 else np.nan
        )
        factors['SENT_EXTREME_NEG'] = SentimentFactorResult(
            name='SENT_EXTREME_NEG',
            values=extreme_neg_ratio,
            description='Ratio of extremely negative news (sentiment < -0.5)',
            category='Sentiment'
        )
        
        # 9. Sentiment range (max - min)
        factors['SENT_RANGE'] = SentimentFactorResult(
            name='SENT_RANGE',
            values=daily_sentiment['max'] - daily_sentiment['min'],
            description='Daily sentiment range (max - min)',
            category='Sentiment'
        )
        
        # 10. Recency-weighted sentiment
        # Weight recent news more heavily (exponential decay)
        # Compute within 5-day rolling window
        def compute_weighted_sentiment(group: pd.DataFrame) -> float:
            """Compute exponentially-weighted sentiment."""
            if len(group) == 0:
                return np.nan
            # Weights: newer = higher (reverse order)
            weights = np.exp(np.linspace(0, 1, len(group)))
            return np.average(group['sentiment'], weights=weights)
        
        weighted_sent = self.news_df.resample('D').apply(compute_weighted_sentiment)
        factors['SENT_WEIGHTED'] = SentimentFactorResult(
            name='SENT_WEIGHTED',
            values=weighted_sent,
            description='Recency-weighted sentiment (exponential decay)',
            category='Sentiment'
        )
        
        logger.info(f"Computed {len(factors)} sentiment factors")
        
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
        around corporate events.
        
        Args:
            event_dates: Dates of events (timezone-aware UTC)
            window_before: Days before event to include
            window_after: Days after event to include
            
        Returns:
            DataFrame with columns:
            - event_date: Date of event
            - pre_sentiment: Mean sentiment before event
            - post_sentiment: Mean sentiment after event
            - sentiment_change: Change in sentiment (post - pre)
            - news_count_pre: # of news before event
            - news_count_post: # of news after event
            
        Example:
            >>> # Analyze sentiment around earnings dates
            >>> earnings_dates = pd.to_datetime([
            ...     '2024-01-25', '2024-04-25', '2024-07-25'
            ... ], utc=True)
            >>> event_sent = engine.compute_event_sentiment(
            ...     earnings_dates, window_before=3, window_after=3
            ... )
            >>> print(event_sent)
        """
        results = []
        
        for event_date in event_dates:
            # Get news around event
            start = event_date - pd.Timedelta(days=window_before)
            end = event_date + pd.Timedelta(days=window_after)
            
            news_window = self.news_df.loc[start:end]
            
            if len(news_window) > 0:
                # Split pre/post event
                pre_event_news = news_window[news_window.index < event_date]
                post_event_news = news_window[news_window.index >= event_date]
                
                pre_sentiment = pre_event_news['sentiment'].mean() if len(pre_event_news) > 0 else np.nan
                post_sentiment = post_event_news['sentiment'].mean() if len(post_event_news) > 0 else np.nan
                
                results.append({
                    'event_date': event_date,
                    'pre_sentiment': pre_sentiment,
                    'post_sentiment': post_sentiment,
                    'sentiment_change': post_sentiment - pre_sentiment,
                    'news_count_pre': len(pre_event_news),
                    'news_count_post': len(post_event_news)
                })
            else:
                logger.warning(f"No news found around event {event_date}")
        
        return pd.DataFrame(results)
    
    def get_factors_dataframe(
        self,
        factors: Dict[str, SentimentFactorResult]
    ) -> pd.DataFrame:
        """
        Convert factor dictionary to DataFrame.
        
        Args:
            factors: Dict of SentimentFactorResult (from compute_sentiment_factors)
            
        Returns:
            DataFrame with columns = factor names, index = dates
            
        Example:
            >>> factors = engine.compute_sentiment_factors()
            >>> df = engine.get_factors_dataframe(factors)
            >>> print(df.columns)
            Index(['SENT_MA_1D', 'SENT_MA_5D', ...], dtype='object')
        """
        df = pd.DataFrame({
            name: result.values
            for name, result in factors.items()
        })
        
        return df
```

**KEY REQUIREMENTS:**

1. ✅ **Type hints 100%**: All functions, all parameters
2. ✅ **Google docstrings**: Args, Returns, Raises, Examples
3. ✅ **Academic references**: Cite papers in module docstring
4. ✅ **Error handling**: ValueError, TypeError with helpful messages
5. ✅ **Logging**: Info logs for major operations
6. ✅ **Edge cases**: Handle empty data, NaN gracefully
7. ✅ **Vectorized**: Use pandas/numpy operations (no Python loops)
8. ✅ **15+ factors**: MA, Vol, Momentum, Count, Dispersion, Surprise, Extremes, Range, Weighted

**Estimated LOC**: 400+ (with comprehensive docstrings + examples)

---

## 📦 FICHIER 2/4: `news_signal_generator.py`

**Path:** `src/financial_analyzer/ml/news_signal_generator.py`

**Objectif:** Combiner sentiment + technical factors → signaux Buy/Sell/Hold.

### Spécifications Complètes:

```python
"""
News-driven trading signal generator.

Combines sentiment factors with technical factors to generate
actionable buy/sell/hold signals with confidence scores.

Methodology:
- Sentiment score → normalized [0, 1]
- Technical composite → IC-weighted average
- Signal logic → rule-based with thresholds
- Confidence → based on signal strength + news volume

References:
- Tetlock (2007): News sentiment predictive power
- Loughran & McDonald (2011): Financial sentiment → returns

Example:
    >>> from financial_analyzer.ml.news_signal_generator import NewsSignalGenerator
    >>> 
    >>> # Initialize with sentiment + technical factors
    >>> generator = NewsSignalGenerator(
    ...     sentiment_factors=sentiment_factors,
    ...     technical_factors=alpha_factors,
    ...     prices=ohlcv_df['close']
    ... )
    >>> 
    >>> # Generate signals
    >>> signals = generator.generate_signals(
    ...     sentiment_threshold=0.3,  # Strong positive sentiment
    ...     technical_score_threshold=0.6  # Technical confirmation
    ... )
    >>> 
    >>> # Access signals
    >>> print(signals[['signal', 'strength', 'sentiment_score']].tail())
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class NewsSignalGenerator:
    """
    Generate trading signals from news sentiment + technical factors.
    
    Signal Logic:
    1. **Strong Buy (2)**: High positive sentiment + bullish technicals + high news volume
    2. **Buy (1)**: Positive sentiment + neutral/bullish technicals
    3. **Hold (0)**: Neutral sentiment or mixed signals
    4. **Sell (-1)**: Negative sentiment + neutral/bearish technicals
    5. **Strong Sell (-2)**: High negative sentiment + bearish technicals + high news volume
    
    Args:
        sentiment_factors: Dict of sentiment factors from SentimentFactorEngine
        technical_factors: Dict of technical factors from AlphaFactorEngine
        prices: Price series (for returns calculation)
        
    Example:
        >>> generator = NewsSignalGenerator(
        ...     sentiment_factors=sent_factors,
        ...     technical_factors=tech_factors,
        ...     prices=ohlcv['close']
        ... )
        >>> signals = generator.generate_signals()
    """
    
    def __init__(
        self,
        sentiment_factors: Dict[str, 'SentimentFactorResult'],
        technical_factors: Dict[str, 'FactorResult'],
        prices: pd.Series
    ) -> None:
        """Initialize signal generator.
        
        Args:
            sentiment_factors: Sentiment factors (from SentimentFactorEngine)
            technical_factors: Technical factors (from AlphaFactorEngine)
            prices: Price series (close prices)
            
        Raises:
            ValueError: If required factors missing
        """
        # Validate required sentiment factors
        required_sent = ['SENT_MA_5D', 'NEWS_COUNT_5D']
        missing_sent = [f for f in required_sent if f not in sentiment_factors]
        if missing_sent:
            raise ValueError(f"Missing sentiment factors: {missing_sent}")
        
        self.sentiment_factors = sentiment_factors
        self.technical_factors = technical_factors
        self.prices = prices
        
        logger.info(
            f"NewsSignalGenerator initialized with {len(sentiment_factors)} sentiment "
            f"and {len(technical_factors)} technical factors"
        )
        
    def generate_signals(
        self,
        sentiment_threshold: float = 0.3,
        technical_score_threshold: float = 0.6,
        news_count_threshold: int = 5,
        use_strong_signals: bool = True
    ) -> pd.DataFrame:
        """
        Generate trading signals.
        
        Args:
            sentiment_threshold: Minimum sentiment for strong signal (0-1 scale after norm)
            technical_score_threshold: Minimum technical score (0-1 scale)
            news_count_threshold: Minimum news articles for confidence
            use_strong_signals: Generate strong buy/sell (-2, 2) if True, else (-1, 1)
            
        Returns:
            DataFrame with columns:
            - signal: -2 (strong sell), -1 (sell), 0 (hold), 1 (buy), 2 (strong buy)
            - strength: Confidence score [0, 1]
            - sentiment_score: Normalized sentiment [0, 1]
            - technical_score: Composite technical score [0, 1]
            - news_count: Number of news articles
            
        Example:
            >>> signals = generator.generate_signals(
            ...     sentiment_threshold=0.4,
            ...     technical_score_threshold=0.7,
            ...     news_count_threshold=10
            ... )
            >>> print(signals[signals['signal'] != 0])  # Non-hold signals
        """
        # Normalize sentiment to [0, 1]
        sent_ma_5d = self.sentiment_factors['SENT_MA_5D'].values
        sent_norm = (sent_ma_5d + 1) / 2  # [-1,1] → [0,1]
        
        # Compute technical composite score (IC-weighted if available)
        tech_score = self._compute_technical_score()
        
        # News count
        news_count = self.sentiment_factors['NEWS_COUNT_5D'].values
        
        # Create signals DataFrame
        signals = pd.DataFrame(index=self.prices.index)
        signals['sentiment_score'] = sent_norm
        signals['technical_score'] = tech_score
        signals['news_count'] = news_count
        
        # Initialize signals to 0 (hold)
        signals['signal'] = 0
        
        # === BUY SIGNALS ===
        
        # Buy condition (1)
        buy_mask = (
            (sent_norm > 0.5) &  # Positive sentiment
            (tech_score > 0.5)    # Bullish technicals
        )
        signals.loc[buy_mask, 'signal'] = 1
        
        # Strong buy condition (2)
        if use_strong_signals:
            strong_buy_mask = (
                (sent_norm > 0.5 + sentiment_threshold) &
                (tech_score > technical_score_threshold) &
                (news_count >= news_count_threshold)
            )
            signals.loc[strong_buy_mask, 'signal'] = 2
        
        # === SELL SIGNALS ===
        
        # Sell condition (-1)
        sell_mask = (
            (sent_norm < 0.5) &  # Negative sentiment
            (tech_score < 0.5)    # Bearish technicals
        )
        signals.loc[sell_mask, 'signal'] = -1
        
        # Strong sell condition (-2)
        if use_strong_signals:
            strong_sell_mask = (
                (sent_norm < 0.5 - sentiment_threshold) &
                (tech_score < 1 - technical_score_threshold) &
                (news_count >= news_count_threshold)
            )
            signals.loc[strong_sell_mask, 'signal'] = -2
        
        # === CONFIDENCE SCORE ===
        
        # Strength = distance from neutral (0.5) * 2 → [0, 1]
        signals['strength'] = np.abs(sent_norm - 0.5) * 2
        
        # Adjust strength by news count (more news = higher confidence)
        news_confidence = np.clip(news_count / news_count_threshold, 0, 1)
        signals['strength'] = signals['strength'] * (0.5 + 0.5 * news_confidence)
        
        logger.info(
            f"Generated signals: "
            f"{(signals['signal'] > 0).sum()} buy, "
            f"{(signals['signal'] < 0).sum()} sell, "
            f"{(signals['signal'] == 0).sum()} hold"
        )
        
        return signals
    
    def _compute_technical_score(self) -> pd.Series:
        """
        Compute composite technical score from factor IC rankings.
        
        Uses top momentum + trend factors weighted equally (or by IC if available).
        
        Returns:
            Series with technical score normalized to [0, 1]
        """
        # Use top technical factors (if available)
        factor_names = ['ROC_10', 'RSI_14', 'MACD', 'SMA_50']
        
        scores = []
        
        for name in factor_names:
            factor = self.technical_factors.get(name)
            if factor is not None:
                # Normalize to [0, 1] via percentile rank
                values = factor.values
                if isinstance(values, pd.Series):
                    rank_norm = values.rank(pct=True, method='average')
                    scores.append(rank_norm)
        
        if len(scores) == 0:
            # Fallback: neutral score
            logger.warning("No technical factors available, using neutral score 0.5")
            return pd.Series(0.5, index=self.prices.index)
        
        # Average scores
        tech_score = pd.concat(scores, axis=1).mean(axis=1)
        
        return tech_score
    
    def backtest_signals(
        self,
        signals: pd.DataFrame,
        holding_period: int = 5
    ) -> pd.DataFrame:
        """
        Backtest generated signals (simple forward returns).
        
        Args:
            signals: DataFrame from generate_signals()
            holding_period: Days to hold position
            
        Returns:
            DataFrame with columns:
            - signal: Original signal
            - forward_return: Return over holding_period
            - hit_rate: 1 if signal correct, 0 otherwise
            
        Example:
            >>> signals = generator.generate_signals()
            >>> backtest = generator.backtest_signals(signals, holding_period=5)
            >>> print(f"Hit rate: {backtest['hit_rate'].mean():.2%}")
        """
        returns = self.prices.pct_change()
        forward_returns = returns.shift(-holding_period).rolling(holding_period).sum()
        
        backtest = signals.copy()
        backtest['forward_return'] = forward_returns
        
        # Hit rate: signal matches forward return direction
        backtest['hit_rate'] = (
            (backtest['signal'] > 0) & (backtest['forward_return'] > 0)
        ) | (
            (backtest['signal'] < 0) & (backtest['forward_return'] < 0)
        )
        backtest['hit_rate'] = backtest['hit_rate'].astype(int)
        
        logger.info(
            f"Backtest complete: "
            f"Hit rate={backtest['hit_rate'].mean():.2%}, "
            f"Avg return={backtest['forward_return'].mean():.2%}"
        )
        
        return backtest
```

**KEY REQUIREMENTS:**

1. ✅ 5 signal types: -2, -1, 0, 1, 2
2. ✅ Confidence scoring based on strength + news volume
3. ✅ Technical composite score (IC-weighted or equal-weight)
4. ✅ Backtest method for validation
5. ✅ Type hints, docstrings, logging
6. ✅ Error handling (missing factors)

**Estimated LOC**: 300+

---

## 📦 FICHIER 3/4: `event_study_analyzer.py`

**Path:** `src/financial_analyzer/ml/event_study_analyzer.py`

**Objectif:** Analyser CAR (Cumulative Abnormal Returns) autour des événements.

### Spécifications Complètes:

```python
"""
Event study analyzer for news-driven abnormal returns.

Implements event study methodology to measure Cumulative Abnormal Returns (CAR)
around news events using the market model (CAPM).

Methodology follows:
- MacKinlay (1997): "Event Studies in Economics and Finance"
- Brown & Warner (1985): "Using daily stock returns"

Example:
    >>> from financial_analyzer.ml.event_study_analyzer import EventStudyAnalyzer
    >>> 
    >>> # Define earnings announcement dates
    >>> event_dates = pd.to_datetime([
    ...     '2024-01-25', '2024-04-25', '2024-07-25'
    ... ], utc=True)
    >>> 
    >>> # Run event study
    >>> analyzer = EventStudyAnalyzer(
    ...     prices=ohlcv_df['close'],
    ...     market_returns=sp500_returns,
    ...     event_dates=event_dates
    ... )
    >>> 
    >>> car = analyzer.compute_car(window_before=5, window_after=5)
    >>> analyzer.plot_car()
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


class EventStudyAnalyzer:
    """
    Analyze abnormal returns around news events using event study methodology.
    
    Methodology:
    1. **Estimate normal returns** using market model (CAPM):
       R_it = alpha + beta * R_mt + epsilon_it
    2. **Compute abnormal returns** (AR):
       AR_it = R_it - (alpha + beta * R_mt)
    3. **Aggregate across events** → Average Abnormal Return (AAR)
    4. **Cumulate** → Cumulative Abnormal Return (CAR)
    
    Args:
        prices: Asset price series (DatetimeIndex)
        market_returns: Market return series (e.g., S&P 500)
        event_dates: Dates of news events (DatetimeIndex, UTC)
        estimation_window: Days to estimate market model (default: 252 = 1 year)
        
    Example:
        >>> analyzer = EventStudyAnalyzer(
        ...     prices=aapl_prices,
        ...     market_returns=spy_returns,
        ...     event_dates=earnings_dates,
        ...     estimation_window=252
        ... )
        >>> car_results = analyzer.compute_car()
    """
    
    def __init__(
        self,
        prices: pd.Series,
        market_returns: pd.Series,
        event_dates: pd.DatetimeIndex,
        estimation_window: int = 252
    ) -> None:
        """Initialize event study analyzer.
        
        Args:
            prices: Asset price series
            market_returns: Market benchmark returns
            event_dates: Event dates
            estimation_window: Days for beta estimation
            
        Raises:
            ValueError: If inputs invalid or insufficient data
        """
        self.prices = prices
        self.returns = prices.pct_change().dropna()
        self.market_returns = market_returns
        self.event_dates = event_dates
        self.estimation_window = estimation_window
        
        # Validate inputs
        if len(self.returns) < estimation_window:
            raise ValueError(
                f"Insufficient data: need {estimation_window} days, "
                f"got {len(self.returns)}"
            )
        
        if len(event_dates) == 0:
            raise ValueError("event_dates cannot be empty")
        
        # Estimate beta (market model)
        self.beta, self.alpha = self._estimate_market_model()
        
        logger.info(
            f"EventStudyAnalyzer initialized: "
            f"alpha={self.alpha:.4f}, beta={self.beta:.4f}, "
            f"{len(event_dates)} events"
        )
        
    def _estimate_market_model(self) -> Tuple[float, float]:
        """
        Estimate alpha and beta using market model (CAPM).
        
        Uses OLS regression on estimation window:
        R_asset = alpha + beta * R_market + epsilon
        
        Returns:
            (beta, alpha)
        """
        # Align returns and market returns
        df = pd.DataFrame({
            'asset': self.returns,
            'market': self.market_returns
        }).dropna()
        
        if len(df) < self.estimation_window:
            logger.warning(
                f"Using {len(df)} days for estimation (requested {self.estimation_window})"
            )
        
        # Use last N days for estimation (avoid look-ahead bias)
        df = df.tail(self.estimation_window)
        
        # OLS regression
        X = df['market'].values.reshape(-1, 1)
        y = df['asset'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        beta = float(model.coef_[0])
        alpha = float(model.intercept_)
        
        logger.debug(f"Market model: R = {alpha:.4f} + {beta:.4f} * R_m")
        
        return beta, alpha
    
    def compute_abnormal_returns(self) -> pd.Series:
        """
        Compute abnormal returns (AR) for all dates.
        
        AR_t = R_t - (alpha + beta * R_market_t)
        
        Returns:
            Series of abnormal returns (DatetimeIndex)
            
        Example:
            >>> ar = analyzer.compute_abnormal_returns()
            >>> print(f"Mean AR: {ar.mean():.4f}")
        """
        # Expected returns from market model
        expected_returns = self.alpha + self.beta * self.market_returns
        
        # Align with actual returns
        ar = self.returns - expected_returns
        ar = ar.dropna()
        
        logger.debug(f"Computed AR for {len(ar)} days, mean={ar.mean():.4f}")
        
        return ar
    
    def compute_car(
        self,
        window_before: int = 5,
        window_after: int = 5
    ) -> pd.DataFrame:
        """
        Compute Cumulative Abnormal Returns (CAR) around events.
        
        For each event, computes:
        - CAR: Sum of abnormal returns in event window
        - AAR_pre: Average abnormal return before event
        - AAR_post: Average abnormal return after event
        
        Args:
            window_before: Days before event
            window_after: Days after event (inclusive of event day)
            
        Returns:
            DataFrame with columns:
            - event_date: Date of event
            - CAR: Cumulative abnormal return
            - AAR_pre: Avg AR before event
            - AAR_post: Avg AR after event (includes event day)
            - days_coverage: Actual days with data in window
            
        Example:
            >>> car_df = analyzer.compute_car(window_before=3, window_after=7)
            >>> print(f"Avg CAR: {car_df['CAR'].mean():.2%}")
        """
        ar = self.compute_abnormal_returns()
        
        results = []
        
        for event_date in self.event_dates:
            # Define event window
            start = event_date - pd.Timedelta(days=window_before)
            end = event_date + pd.Timedelta(days=window_after)
            
            # Get AR in window
            try:
                ar_window = ar.loc[start:end]
            except KeyError:
                logger.warning(f"Event {event_date} outside AR range, skipping")
                continue
            
            if len(ar_window) == 0:
                logger.warning(f"No AR data for event {event_date}, skipping")
                continue
            
            # CAR = sum of AR
            car = ar_window.sum()
            
            # Split pre/post event
            ar_pre = ar_window[ar_window.index < event_date]
            ar_post = ar_window[ar_window.index >= event_date]
            
            aar_pre = ar_pre.mean() if len(ar_pre) > 0 else np.nan
            aar_post = ar_post.mean() if len(ar_post) > 0 else np.nan
            
            results.append({
                'event_date': event_date,
                'CAR': car,
                'AAR_pre': aar_pre,
                'AAR_post': aar_post,
                'days_coverage': len(ar_window)
            })
        
        df = pd.DataFrame(results)
        
        if len(df) > 0:
            logger.info(
                f"CAR computed for {len(df)} events: "
                f"mean={df['CAR'].mean():.4f}, std={df['CAR'].std():.4f}"
            )
        
        return df
    
    def compute_aar_series(
        self,
        window_before: int = 5,
        window_after: int = 5
    ) -> pd.Series:
        """
        Compute Average Abnormal Return (AAR) series across all events.
        
        Useful for plotting AAR over event time.
        
        Args:
            window_before: Days before event
            window_after: Days after event
            
        Returns:
            Series with index = days relative to event (e.g., -5 to +5)
            
        Example:
            >>> aar = analyzer.compute_aar_series(window_before=5, window_after=5)
            >>> print(aar)
            -5   -0.002
            -4   -0.001
            ...
        """
        ar = self.compute_abnormal_returns()
        
        # Collect AR for each event, aligned to event time
        event_ar_list = []
        
        for event_date in self.event_dates:
            start = event_date - pd.Timedelta(days=window_before)
            end = event_date + pd.Timedelta(days=window_after)
            
            try:
                ar_window = ar.loc[start:end].copy()
            except KeyError:
                continue
            
            if len(ar_window) == 0:
                continue
            
            # Convert index to days relative to event
            ar_window.index = (ar_window.index - event_date).days
            
            event_ar_list.append(ar_window)
        
        if len(event_ar_list) == 0:
            logger.warning("No events with sufficient data")
            return pd.Series(dtype=float)
        
        # Concatenate and group by relative day
        all_ar = pd.concat(event_ar_list)
        aar = all_ar.groupby(all_ar.index).mean()
        aar = aar.sort_index()
        
        return aar
    
    def plot_car(
        self,
        window_before: int = 5,
        window_after: int = 5,
        figsize: Tuple[int, int] = (12, 6),
        save_path: Optional[str] = None
    ) -> None:
        """
        Plot Cumulative Abnormal Returns around events.
        
        Args:
            window_before: Days before event
            window_after: Days after event
            figsize: Figure size (width, height)
            save_path: Path to save plot (optional)
            
        Example:
            >>> analyzer.plot_car(window_before=10, window_after=10)
        """
        # Compute AAR series
        aar = self.compute_aar_series(window_before, window_after)
        
        if len(aar) == 0:
            logger.error("No data to plot")
            return
        
        # Cumulative sum → CAR
        car = aar.cumsum()
        
        # Plot
        fig, ax = plt.subplots(figsize=figsize)
        
        ax.plot(car.index, car.values, marker='o', linewidth=2, label='CAR')
        ax.axvline(0, color='red', linestyle='--', linewidth=2, label='Event Date')
        ax.axhline(0, color='black', linestyle='-', alpha=0.3)
        
        ax.set_xlabel('Days Relative to Event', fontsize=12)
        ax.set_ylabel('Cumulative Abnormal Return', fontsize=12)
        ax.set_title(
            f'Event Study: CAR Around {len(self.event_dates)} Events '
            f'(β={self.beta:.2f})',
            fontsize=14
        )
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")
        
        plt.show()
```

**KEY REQUIREMENTS:**

1. ✅ Market model (CAPM) estimation with OLS
2. ✅ Abnormal returns computation
3. ✅ CAR calculation around events
4. ✅ AAR series (average across events)
5. ✅ Plotting functionality
6. ✅ Academic references (MacKinlay 1997)
7. ✅ Type hints, docstrings, error handling

**Estimated LOC**: 400+

---

## 📦 FICHIER 4/4: `test_news_sentiment_integration.py`

**Path:** `tests/test_ml/test_news_sentiment_integration.py`

**Objectif:** 60+ tests compréhensifs pour Phase 5.3.

### Structure des Tests:

```python
"""
Comprehensive test suite for news + sentiment integration.

Test Coverage:
- SentimentFactorEngine (20 tests)
- NewsSignalGenerator (20 tests)
- EventStudyAnalyzer (20 tests)
- Integration (10 tests)

Total: 70 tests
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from financial_analyzer.ml.sentiment_factor_engine import (
    SentimentFactorEngine,
    SentimentFactorResult
)
from financial_analyzer.ml.news_signal_generator import NewsSignalGenerator
from financial_analyzer.ml.event_study_analyzer import EventStudyAnalyzer


# ==================== FIXTURES ====================

@pytest.fixture
def sample_news_with_sentiment():
    """Sample news DataFrame with sentiment scores."""
    dates = pd.date_range('2024-01-01', periods=50, freq='D', tz='UTC')
    news_data = []
    
    for date in dates:
        # Generate 0-3 news per day
        n_news = np.random.randint(0, 4)
        for _ in range(n_news):
            news_data.append({
                'published': date + pd.Timedelta(hours=np.random.randint(0, 24)),
                'headline': f'News on {date.date()}',
                'sentiment': np.random.uniform(-1, 1),
                'sentiment_label': 'neutral'
            })
    
    df = pd.DataFrame(news_data)
    df = df.set_index('published')
    return df


@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV data."""
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    close = 100 * (1 + np.random.normal(0.001, 0.02, 60)).cumprod()
    
    return pd.DataFrame({
        'open': close * 0.99,
        'high': close * 1.01,
        'low': close * 0.98,
        'close': close,
        'volume': np.random.randint(1_000_000, 10_000_000, 60)
    }, index=dates)


@pytest.fixture
def sample_market_returns():
    """Sample market returns."""
    dates = pd.date_range('2024-01-01', periods=300, freq='D')
    returns = np.random.normal(0.0005, 0.01, 300)
    return pd.Series(returns, index=dates)


# ==================== TEST SENTIMENT_FACTOR_ENGINE ====================

def test_sentiment_factor_engine_init(sample_news_with_sentiment):
    """Test SentimentFactorEngine initialization."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    assert engine is not None
    assert len(engine.news_df) > 0


def test_sentiment_factor_engine_missing_column():
    """Test error when sentiment column missing."""
    df = pd.DataFrame({'headline': ['test']}, index=pd.date_range('2024-01-01', periods=1))
    
    with pytest.raises(ValueError, match="missing required columns"):
        SentimentFactorEngine(df)


def test_compute_sentiment_factors_default_periods(sample_news_with_sentiment):
    """Test computing sentiment factors with default periods."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    factors = engine.compute_sentiment_factors()
    
    assert len(factors) >= 15  # At least 15 factors
    assert 'SENT_MA_5D' in factors
    assert 'SENT_VOL_5D' in factors
    assert 'NEWS_COUNT_5D' in factors


def test_compute_sentiment_factors_custom_periods(sample_news_with_sentiment):
    """Test computing sentiment factors with custom periods."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    factors = engine.compute_sentiment_factors(periods=[1, 3, 7])
    
    assert 'SENT_MA_1D' in factors
    assert 'SENT_MA_3D' in factors
    assert 'SENT_MA_7D' in factors


def test_sentiment_factor_values_type(sample_news_with_sentiment):
    """Test that factor values are pandas Series."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    factors = engine.compute_sentiment_factors()
    
    for name, factor in factors.items():
        assert isinstance(factor, SentimentFactorResult)
        assert isinstance(factor.values, pd.Series)


def test_sentiment_dispersion_factor(sample_news_with_sentiment):
    """Test SENT_DISPERSION factor."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    factors = engine.compute_sentiment_factors()
    
    assert 'SENT_DISPERSION' in factors
    dispersion = factors['SENT_DISPERSION'].values
    assert dispersion.notna().any()


def test_sentiment_extreme_factors(sample_news_with_sentiment):
    """Test extreme sentiment factors."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    factors = engine.compute_sentiment_factors()
    
    assert 'SENT_EXTREME_POS' in factors
    assert 'SENT_EXTREME_NEG' in factors


def test_compute_event_sentiment(sample_news_with_sentiment):
    """Test event sentiment computation."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    
    event_dates = pd.to_datetime([
        '2024-01-15', '2024-01-30'
    ], utc=True)
    
    event_sent = engine.compute_event_sentiment(event_dates, window_before=3, window_after=3)
    
    assert isinstance(event_sent, pd.DataFrame)
    assert 'event_date' in event_sent.columns
    assert 'sentiment_change' in event_sent.columns


def test_get_factors_dataframe(sample_news_with_sentiment):
    """Test converting factors to DataFrame."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    factors = engine.compute_sentiment_factors()
    
    df = engine.get_factors_dataframe(factors)
    
    assert isinstance(df, pd.DataFrame)
    assert len(df.columns) >= 15


def test_sentiment_factors_no_nan_explosion(sample_news_with_sentiment):
    """Test that factors don't produce all-NaN columns."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    factors = engine.compute_sentiment_factors()
    
    df = engine.get_factors_dataframe(factors)
    
    # Check that at least 50% of values are non-NaN for each factor
    for col in df.columns:
        non_nan_ratio = df[col].notna().sum() / len(df)
        assert non_nan_ratio > 0.3, f"Factor {col} has too many NaN ({non_nan_ratio:.1%})"


# ... CONTINUE WITH 10 MORE TESTS FOR SENTIMENT_FACTOR_ENGINE ...

# ==================== TEST NEWS_SIGNAL_GENERATOR ====================

def test_news_signal_generator_init(sample_news_with_sentiment, sample_ohlcv):
    """Test NewsSignalGenerator initialization."""
    # Create minimal factors
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    sent_factors = engine.compute_sentiment_factors()
    
    # Mock technical factors (simplified)
    tech_factors = {}
    
    generator = NewsSignalGenerator(
        sentiment_factors=sent_factors,
        technical_factors=tech_factors,
        prices=sample_ohlcv['close']
    )
    
    assert generator is not None


def test_news_signal_generator_missing_required_factors(sample_ohlcv):
    """Test error when required factors missing."""
    with pytest.raises(ValueError, match="Missing sentiment factors"):
        NewsSignalGenerator(
            sentiment_factors={},  # Missing SENT_MA_5D
            technical_factors={},
            prices=sample_ohlcv['close']
        )


def test_generate_signals_default_params(sample_news_with_sentiment, sample_ohlcv):
    """Test signal generation with default parameters."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    sent_factors = engine.compute_sentiment_factors()
    
    generator = NewsSignalGenerator(
        sentiment_factors=sent_factors,
        technical_factors={},
        prices=sample_ohlcv['close']
    )
    
    signals = generator.generate_signals()
    
    assert isinstance(signals, pd.DataFrame)
    assert 'signal' in signals.columns
    assert 'strength' in signals.columns
    assert signals['signal'].isin([-2, -1, 0, 1, 2]).all()


def test_generate_signals_strength_range(sample_news_with_sentiment, sample_ohlcv):
    """Test that signal strength is in [0, 1]."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    sent_factors = engine.compute_sentiment_factors()
    
    generator = NewsSignalGenerator(
        sentiment_factors=sent_factors,
        technical_factors={},
        prices=sample_ohlcv['close']
    )
    
    signals = generator.generate_signals()
    
    assert signals['strength'].min() >= 0
    assert signals['strength'].max() <= 1


def test_backtest_signals(sample_news_with_sentiment, sample_ohlcv):
    """Test signal backtesting."""
    engine = SentimentFactorEngine(sample_news_with_sentiment)
    sent_factors = engine.compute_sentiment_factors()
    
    generator = NewsSignalGenerator(
        sentiment_factors=sent_factors,
        technical_factors={},
        prices=sample_ohlcv['close']
    )
    
    signals = generator.generate_signals()
    backtest = generator.backtest_signals(signals, holding_period=5)
    
    assert 'forward_return' in backtest.columns
    assert 'hit_rate' in backtest.columns


# ... CONTINUE WITH 15 MORE TESTS FOR NEWS_SIGNAL_GENERATOR ...

# ==================== TEST EVENT_STUDY_ANALYZER ====================

def test_event_study_analyzer_init(sample_ohlcv, sample_market_returns):
    """Test EventStudyAnalyzer initialization."""
    event_dates = pd.to_datetime(['2024-01-20', '2024-02-15'], utc=True)
    
    analyzer = EventStudyAnalyzer(
        prices=sample_ohlcv['close'],
        market_returns=sample_market_returns,
        event_dates=event_dates
    )
    
    assert analyzer is not None
    assert analyzer.beta != 0
    assert analyzer.alpha is not None


def test_event_study_insufficient_data():
    """Test error when insufficient data."""
    prices = pd.Series([100, 101], index=pd.date_range('2024-01-01', periods=2))
    market_returns = pd.Series([0.01, 0.02], index=pd.date_range('2024-01-01', periods=2))
    event_dates = pd.to_datetime(['2024-01-01'])
    
    with pytest.raises(ValueError, match="Insufficient data"):
        EventStudyAnalyzer(prices, market_returns, event_dates, estimation_window=252)


def test_compute_abnormal_returns(sample_ohlcv, sample_market_returns):
    """Test abnormal returns computation."""
    event_dates = pd.to_datetime(['2024-01-20'], utc=True)
    
    analyzer = EventStudyAnalyzer(
        prices=sample_ohlcv['close'],
        market_returns=sample_market_returns,
        event_dates=event_dates
    )
    
    ar = analyzer.compute_abnormal_returns()
    
    assert isinstance(ar, pd.Series)
    assert len(ar) > 0


def test_compute_car(sample_ohlcv, sample_market_returns):
    """Test CAR computation."""
    event_dates = pd.to_datetime(['2024-01-20', '2024-02-10'], utc=True)
    
    analyzer = EventStudyAnalyzer(
        prices=sample_ohlcv['close'],
        market_returns=sample_market_returns,
        event_dates=event_dates
    )
    
    car_df = analyzer.compute_car(window_before=5, window_after=5)
    
    assert isinstance(car_df, pd.DataFrame)
    assert 'CAR' in car_df.columns
    assert 'AAR_pre' in car_df.columns
    assert 'AAR_post' in car_df.columns


def test_compute_aar_series(sample_ohlcv, sample_market_returns):
    """Test AAR series computation."""
    event_dates = pd.to_datetime(['2024-01-20'], utc=True)
    
    analyzer = EventStudyAnalyzer(
        prices=sample_ohlcv['close'],
        market_returns=sample_market_returns,
        event_dates=event_dates
    )
    
    aar = analyzer.compute_aar_series(window_before=5, window_after=5)
    
    assert isinstance(aar, pd.Series)
    assert len(aar) > 0


def test_plot_car_no_crash(sample_ohlcv, sample_market_returns):
    """Test that plot_car doesn't crash."""
    event_dates = pd.to_datetime(['2024-01-20'], utc=True)
    
    analyzer = EventStudyAnalyzer(
        prices=sample_ohlcv['close'],
        market_returns=sample_market_returns,
        event_dates=event_dates
    )
    
    with patch('matplotlib.pyplot.show'):
        analyzer.plot_car(window_before=3, window_after=3)


# ... CONTINUE WITH 15 MORE TESTS FOR EVENT_STUDY_ANALYZER ...

# ==================== INTEGRATION TESTS ====================

def test_end_to_end_pipeline(sample_news_with_sentiment, sample_ohlcv, sample_market_returns):
    """Test complete news → sentiment → signals → event study pipeline."""
    # 1. Compute sentiment factors
    sent_engine = SentimentFactorEngine(sample_news_with_sentiment)
    sent_factors = sent_engine.compute_sentiment_factors()
    
    # 2. Generate signals
    signal_gen = NewsSignalGenerator(
        sentiment_factors=sent_factors,
        technical_factors={},
        prices=sample_ohlcv['close']
    )
    signals = signal_gen.generate_signals()
    
    # 3. Backtest signals
    backtest = signal_gen.backtest_signals(signals)
    
    # 4. Event study on signal dates
    signal_dates = signals[signals['signal'] != 0].index[:5]
    if len(signal_dates) > 0:
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=signal_dates
        )
        car = analyzer.compute_car()
        
        assert len(car) > 0


# ... CONTINUE WITH 10 MORE INTEGRATION TESTS ...
```

**KEY REQUIREMENTS:**

1. ✅ 70+ tests total (20 + 20 + 20 + 10)
2. ✅ Fixtures for sample data
3. ✅ Edge case testing (missing data, invalid inputs)
4. ✅ Integration tests (end-to-end pipeline)
5. ✅ Mock/patch for external dependencies
6. ✅ Type validation
7. ✅ Error message validation

**Estimated LOC**: 800+

---

## 🚀 COMMANDES DE VALIDATION

```bash
# Après génération des 4 fichiers:

# 1. Run tests
cd /workspaces/finbot
python -m pytest tests/test_ml/test_news_sentiment_integration.py -v --tb=short

# 2. Type checking
mypy src/financial_analyzer/ml/sentiment_factor_engine.py
mypy src/financial_analyzer/ml/news_signal_generator.py
mypy src/financial_analyzer/ml/event_study_analyzer.py

# 3. Coverage
pytest tests/test_ml/test_news_sentiment_integration.py --cov=financial_analyzer.ml --cov-report=term-missing

# 4. Integration test
python -c "
from financial_analyzer.ml.sentiment_factor_engine import SentimentFactorEngine
from financial_analyzer.data.news_scraper import FinancialNewsScraper
print('✅ All imports successful')
"
```

---

## 📊 MÉTRIQUES ATTENDUES

| Métrique | Target | Validation |
|----------|--------|------------|
| Tests | 70+ | 100% pass |
| Type hints | 100% | mypy clean |
| Docstrings | 100% | Google style |
| Code quality | 9.9/10 | Pylint/Flake8 |
| LOC | 1900+ | 4 fichiers |
| Coverage | 95%+ | pytest-cov |

---

## ✅ CHECKLIST FINAL

Avant de marquer Phase 5.3 comme complétée:

- [ ] 4 fichiers créés
- [ ] 70+ tests passing
- [ ] Type hints 100%
- [ ] Google docstrings exhaustives
- [ ] Academic references citées
- [ ] Error handling robuste
- [ ] Logging compréhensif
- [ ] Edge cases couverts
- [ ] Integration tests passent
- [ ] Documentation complète

---

**QUALITY OVER SPEED - NO COMPROMISES**

Prends le temps nécessaire pour que chaque fichier soit production-grade.
Si un fichier prend 2h au lieu de 1h, c'est OK.

**TARGET: 9.9/10 QUALITY SCORE**

---

**🎯 READY TO START? COPY THIS ENTIRE PROMPT TO COPILOT**
