"""
News-driven trading signal generator.

Combines sentiment factors with technical factors to generate
actionable buy/sell/hold signals with confidence scores.

Methodology:
- Sentiment score → normalized [0, 1] scale
- Technical composite → IC-weighted or equal-weighted average
- Signal logic → rule-based thresholds (sentiment + technical confirmation)
- Confidence → based on signal strength + news volume/attention

Signal Types:
- **Strong Buy (2)**: High positive sentiment + bullish technicals + high news volume
- **Buy (1)**: Positive sentiment + neutral/bullish technicals
- **Hold (0)**: Neutral sentiment or mixed signals
- **Sell (-1)**: Negative sentiment + neutral/bearish technicals
- **Strong Sell (-2)**: High negative sentiment + bearish technicals + high news volume

References:
- Tetlock, P. C. (2007). "Giving content to investor sentiment: The measure of media
  pessimism." Journal of Finance, 62(3), 1139-1168.
  https://doi.org/10.1111/j.1540-6261.2007.01232.x
- Loughran, T., & McDonald, B. (2011). "When is a liability not a liability? Textual
  analysis, dictionaries, and 10-Ks." Journal of Finance, 66(1), 35-65.
  https://doi.org/10.1111/j.1540-6261.2010.01625.x
- Antweiler, W., & Frank, M. Z. (2004). "Is all that talk just noise? The information
  content of internet stock message boards." Journal of Finance, 59(3), 1259-1294.

Example:
    >>> from financial_analyzer.ml.news_signal_generator import NewsSignalGenerator
    >>> from financial_analyzer.ml.sentiment_factor_engine import SentimentFactorEngine
    >>> from financial_analyzer.ml.feature_engineering import AlphaFactorEngine
    >>> 
    >>> # Initialize with sentiment + technical factors
    >>> sent_engine = SentimentFactorEngine(news_with_sentiment)
    >>> sent_factors = sent_engine.compute_sentiment_factors()
    >>> 
    >>> alpha_engine = AlphaFactorEngine(ohlcv_df)
    >>> tech_factors = alpha_engine.compute_all_factors()
    >>> 
    >>> generator = NewsSignalGenerator(
    ...     sentiment_factors=sent_factors,
    ...     technical_factors=tech_factors,
    ...     prices=ohlcv_df['close']
    ... )
    >>> 
    >>> # Generate signals with custom thresholds
    >>> signals = generator.generate_signals(
    ...     sentiment_threshold=0.3,  # Strong positive sentiment
    ...     technical_score_threshold=0.6,  # Technical confirmation
    ...     news_count_threshold=10  # Minimum attention
    ... )
    >>> 
    >>> # Access signals
    >>> print(signals[['signal', 'strength', 'sentiment_score']].tail())
                signal  strength  sentiment_score
    2024-01-25       2      0.85             0.75
    2024-01-26       1      0.62             0.68
    2024-01-27       0      0.45             0.52
    >>> 
    >>> # Backtest signals
    >>> backtest = generator.backtest_signals(signals, holding_period=5)
    >>> print(f"Hit rate: {backtest['hit_rate'].mean():.2%}")
    Hit rate: 58.50%
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class NewsSignalGenerator:
    """
    Generate trading signals from news sentiment + technical factors.
    
    Combines sentiment-based factors (from SentimentFactorEngine) with
    technical factors (from AlphaFactorEngine) to produce actionable
    trading signals with confidence scores.
    
    Signal Logic:
        **Strong Buy (2)**:
        - Sentiment score > 0.5 + sentiment_threshold (e.g., >0.8)
        - Technical score > technical_score_threshold (e.g., >0.6)
        - News count >= news_count_threshold (e.g., >=5 articles)
        
        **Buy (1)**:
        - Sentiment score > 0.5 (positive)
        - Technical score > 0.5 (bullish)
        
        **Hold (0)**:
        - Neutral sentiment (around 0.5)
        - Mixed technical signals
        - Default signal when conditions not met
        
        **Sell (-1)**:
        - Sentiment score < 0.5 (negative)
        - Technical score < 0.5 (bearish)
        
        **Strong Sell (-2)**:
        - Sentiment score < 0.5 - sentiment_threshold (e.g., <0.2)
        - Technical score < 1 - technical_score_threshold (e.g., <0.4)
        - News count >= news_count_threshold (high attention)
    
    Confidence Scoring:
        Strength = distance from neutral (0.5) * 2 → [0, 1]
        Adjusted by news confidence: min(news_count / threshold, 1.0)
        Final: strength * (0.5 + 0.5 * news_confidence)
    
    Args:
        sentiment_factors: Dict of sentiment factors from SentimentFactorEngine.
                           Must include 'SENT_MA_5D' and 'NEWS_COUNT_5D'.
        technical_factors: Dict of technical factors from AlphaFactorEngine.
                           Will use top momentum/trend factors if available.
        prices: Price series (typically close prices) for returns calculation
                and backtesting. Must have DatetimeIndex.
                 
    Raises:
        ValueError: If required sentiment factors are missing
        TypeError: If inputs have incorrect types
        
    Example:
        >>> # Initialize
        >>> generator = NewsSignalGenerator(
        ...     sentiment_factors=sent_factors,
        ...     technical_factors=tech_factors,
        ...     prices=ohlcv['close']
        ... )
        >>> 
        >>> # Generate signals with default parameters
        >>> signals = generator.generate_signals()
        >>> print(signals['signal'].value_counts().sort_index())
        -2     5
        -1    12
         0    28
         1    14
         2     6
        >>> 
        >>> # Analyze signal distribution
        >>> buy_signals = signals[signals['signal'] > 0]
        >>> print(f"Buy signals: {len(buy_signals)}, avg strength: {buy_signals['strength'].mean():.2f}")
        Buy signals: 20, avg strength: 0.68
    """
    
    def __init__(
        self,
        sentiment_factors: Union[Dict[str, Any], pd.DataFrame],
        technical_factors: Union[Dict[str, Any], pd.DataFrame],
        prices: pd.Series
    ) -> None:
        """Initialize signal generator.
        
        Args:
            sentiment_factors: Sentiment factors from SentimentFactorEngine.
                               Accepts two formats:
                               1. Dict[str, SentimentFactorResult] (from compute_sentiment_factors())
                               2. pd.DataFrame (columns = factor names, rows = dates)
                               If dict provided, automatically converted to DataFrame.
            technical_factors: Technical factors from AlphaFactorEngine.
                               Accepts two formats:
                               1. Dict[str, FactorResult] (from compute_all_factors())
                               2. pd.DataFrame (columns = factor names, rows = dates)
                               If dict provided, automatically converted to DataFrame.
            prices: Price series (close prices) with DatetimeIndex
            
        Raises:
            ValueError: If required factors missing or data invalid
            TypeError: If inputs have incorrect types
            
        Example:
            >>> generator = NewsSignalGenerator(
            ...     sentiment_factors=sent_factors,
            ...     technical_factors=tech_factors,
            ...     prices=ohlcv['close']
            ... )
            >>> print(f"Initialized with {len(generator.prices)} price points")
        """
        # Type validation and conversion
        if isinstance(sentiment_factors, dict):
            # Convert dict to DataFrame
            sentiment_factors = pd.DataFrame({
                k: v.values if hasattr(v, 'values') else v
                for k, v in sentiment_factors.items()
            })
        elif not isinstance(sentiment_factors, pd.DataFrame):
            raise TypeError(
                f"sentiment_factors must be dict or DataFrame, got {type(sentiment_factors).__name__}"
            )
        
        if isinstance(technical_factors, dict):
            # Convert dict to DataFrame
            technical_factors = pd.DataFrame({
                k: v.values if hasattr(v, 'values') else v
                for k, v in technical_factors.items()
            })
        elif not isinstance(technical_factors, pd.DataFrame):
            raise TypeError(
                f"technical_factors must be dict or DataFrame, got {type(technical_factors).__name__}"
            )
        
        if not isinstance(prices, pd.Series):
            raise TypeError(
                f"prices must be pandas Series, got {type(prices).__name__}"
            )
        
        # Validate required sentiment factors
        required_sent = ['SENT_MA_5D', 'NEWS_COUNT_5D']
        missing_sent = [f for f in required_sent if f not in sentiment_factors.columns]
        if missing_sent:
            raise ValueError(
                f"Missing required sentiment factors: {missing_sent}. "
                f"Available: {list(sentiment_factors.columns)}"
            )
        
        self.sentiment_factors = sentiment_factors
        self.technical_factors = technical_factors
        self.prices = prices
        
        logger.info(
            f"NewsSignalGenerator initialized: "
            f"{len(sentiment_factors)} sentiment factors, "
            f"{len(technical_factors)} technical factors, "
            f"{len(prices)} price points"
        )
        
    def generate_signals(
        self,
        sentiment_threshold: float = 0.3,
        technical_score_threshold: float = 0.6,
        news_count_threshold: int = 5,
        use_strong_signals: bool = True
    ) -> pd.DataFrame:
        """
        Generate trading signals from sentiment + technical factors.
        
        Combines normalized sentiment with technical score to produce
        5-level signals (-2, -1, 0, 1, 2) with confidence scores.
        
        Args:
            sentiment_threshold: Minimum sentiment deviation for strong signal
                                 (0-1 scale after normalization). Default: 0.3
                                 Strong buy: sentiment > 0.5 + 0.3 = 0.8
                                 Strong sell: sentiment < 0.5 - 0.3 = 0.2
            technical_score_threshold: Minimum technical score (0-1 scale)
                                        for strong signal confirmation. Default: 0.6
            news_count_threshold: Minimum news articles required for high confidence
                                  strong signals. Default: 5
            use_strong_signals: If True, generate strong buy/sell (-2, 2).
                                If False, only generate regular signals (-1, 0, 1).
                                Default: True
            
        Returns:
            DataFrame with columns:
            - signal: -2 (strong sell), -1 (sell), 0 (hold), 1 (buy), 2 (strong buy)
            - strength: Confidence score [0, 1] based on sentiment distance + news volume
            - sentiment_score: Normalized sentiment [0, 1]
            - technical_score: Composite technical score [0, 1]
            - news_count: Number of news articles (5-day rolling sum)
            
        Example:
            >>> # Conservative signals (higher thresholds)
            >>> signals = generator.generate_signals(
            ...     sentiment_threshold=0.4,  # Strong sentiment required
            ...     technical_score_threshold=0.7,  # Strong technicals required
            ...     news_count_threshold=10  # High attention required
            ... )
            >>> print(signals[signals['signal'] != 0])  # Non-hold signals only
            
            >>> # Aggressive signals (lower thresholds)
            >>> signals = generator.generate_signals(
            ...     sentiment_threshold=0.2,
            ...     technical_score_threshold=0.5,
            ...     news_count_threshold=3
            ... )
            
            >>> # Backtest generated signals
            >>> backtest = generator.backtest_signals(signals, holding_period=5)
            >>> print(f"Hit rate: {backtest['hit_rate'].mean():.2%}")
        """
        # Normalize sentiment to [0, 1]
        # SENT_MA_5D is in [-1, 1] → map to [0, 1]
        sent_ma_5d = self.sentiment_factors['SENT_MA_5D'].values
        sent_norm = (sent_ma_5d + 1) / 2  # [-1,1] → [0,1]
        
        # Compute technical composite score
        tech_score = self._compute_technical_score()
        
        # News count (attention/confidence proxy)
        news_count = self.sentiment_factors['NEWS_COUNT_5D'].values
        
        # Create signals DataFrame aligned with prices index
        signals = pd.DataFrame(index=self.prices.index)
        signals['sentiment_score'] = sent_norm
        signals['technical_score'] = tech_score
        signals['news_count'] = news_count
        
        # ===================================================================
        # SIGNAL GENERATION LOGIC
        # ===================================================================
        # Note on Strong Signals (2, -2):
        # Default thresholds are intentionally conservative (high precision, low recall).
        # This ensures strong signals are only generated when there is high confidence:
        #   - Extreme sentiment (>0.8 or <0.2 on [0,1] scale with default threshold=0.3)
        #   - Strong technical confirmation (score >0.6)
        #   - High news attention (count >=5 articles in 5-day window)
        # 
        # To generate more strong signals, reduce thresholds in generate_signals() call:
        #   generator.generate_signals(
        #       sentiment_threshold=0.2,      # Less strict (default: 0.3)
        #       technical_score_threshold=0.5, # Less strict (default: 0.6)
        #       news_count_threshold=3         # Less strict (default: 5)
        #   )
        # ===================================================================
        
        # Initialize all signals to 0 (hold)
        signals['signal'] = 0
        
        # ===================================================================
        # BUY SIGNALS
        # ===================================================================
        
        # Buy condition (1): Positive sentiment + bullish technicals
        buy_mask = (
            (sent_norm > 0.5) &  # Positive sentiment
            (tech_score > 0.5)    # Bullish technicals
        )
        signals.loc[buy_mask, 'signal'] = 1
        
        # Strong buy condition (2): Very positive sentiment + strong technicals + high attention
        if use_strong_signals:
            strong_buy_mask = (
                (sent_norm > 0.5 + sentiment_threshold) &
                (tech_score > technical_score_threshold) &
                (news_count >= news_count_threshold)
            )
            signals.loc[strong_buy_mask, 'signal'] = 2
        
        # ===================================================================
        # SELL SIGNALS
        # ===================================================================
        
        # Sell condition (-1): Negative sentiment + bearish technicals
        sell_mask = (
            (sent_norm < 0.5) &  # Negative sentiment
            (tech_score < 0.5)    # Bearish technicals
        )
        signals.loc[sell_mask, 'signal'] = -1
        
        # Strong sell condition (-2): Very negative sentiment + weak technicals + high attention
        if use_strong_signals:
            strong_sell_mask = (
                (sent_norm < 0.5 - sentiment_threshold) &
                (tech_score < 1 - technical_score_threshold) &
                (news_count >= news_count_threshold)
            )
            signals.loc[strong_sell_mask, 'signal'] = -2
        
        # ===================================================================
        # CONFIDENCE/STRENGTH SCORE
        # ===================================================================
        
        # Base strength: distance from neutral (0.5) * 2 → [0, 1]
        signals['strength'] = np.abs(sent_norm - 0.5) * 2
        
        # Adjust strength by news count (more news = higher confidence)
        # Normalize news count to [0, 1] with threshold as reference
        news_confidence = np.clip(news_count / news_count_threshold, 0, 1)
        
        # Final strength: weighted combination (50% base + 50% news-adjusted)
        signals['strength'] = signals['strength'] * (0.5 + 0.5 * news_confidence)
        
        # Log signal distribution
        signal_counts = signals['signal'].value_counts().sort_index()
        logger.info(
            f"Generated signals: "
            f"{signal_counts.get(2, 0)} strong buy, "
            f"{signal_counts.get(1, 0)} buy, "
            f"{signal_counts.get(0, 0)} hold, "
            f"{signal_counts.get(-1, 0)} sell, "
            f"{signal_counts.get(-2, 0)} strong sell"
        )
        
        return signals
    
    def _compute_technical_score(self) -> pd.Series:
        """
        Compute composite technical score from factor IC rankings.
        
        Uses top momentum + trend factors weighted equally (or by IC if available).
        Normalizes each factor to [0, 1] via percentile rank, then averages.
        
        Returns:
            Series with technical score normalized to [0, 1]
            
        Note:
            If no technical factors are available, returns neutral score of 0.5
            for all dates.
        """
        # Define preferred technical factors (momentum + trend)
        preferred_factors = [
            'ROC_10', 'ROC_20', 'RSI_14', 
            'MACD_line', 'MACD_histogram',
            'SMA_50', 'EMA_12', 'ADX_14'
        ]
        
        scores = []
        
        for name in preferred_factors:
            if name not in self.technical_factors.columns:
                continue
            
            # Get column as Series
            values = self.technical_factors[name]
            
            # Normalize to [0, 1] via percentile rank
            # This makes factors comparable across different scales
            rank_norm = values.rank(pct=True, method='average')
            scores.append(rank_norm)
        
        if len(scores) == 0:
            # Fallback: neutral score 0.5 (no technical bias)
            logger.warning(
                "No technical factors available from preferred list. "
                "Using neutral technical score (0.5)"
            )
            return pd.Series(0.5, index=self.prices.index)
        
        # Average all normalized factor scores
        tech_score = pd.concat(scores, axis=1).mean(axis=1)
        
        # Align with prices index (fill missing dates with NaN)
        tech_score = tech_score.reindex(self.prices.index)
        
        logger.debug(
            f"Computed technical score from {len(scores)} factors "
            f"(mean: {tech_score.mean():.3f})"
        )
        
        return tech_score
    
    def backtest_signals(
        self,
        signals: pd.DataFrame,
        holding_period: int = 5
    ) -> pd.DataFrame:
        """
        Backtest generated signals using forward returns.
        
        Computes forward returns over the holding period and evaluates
        whether signals correctly predicted return direction (hit rate).
        
        Args:
            signals: DataFrame from generate_signals()
            holding_period: Days to hold position (default: 5 trading days)
            
        Returns:
            DataFrame with columns:
            - signal: Original signal (-2, -1, 0, 1, 2)
            - strength: Signal confidence [0, 1]
            - forward_return: Cumulative return over holding_period
            - hit_rate: 1 if signal matches return direction, 0 otherwise
            - signal_strength_product: signal * strength (for weighted metrics)
            
        Example:
            >>> signals = generator.generate_signals()
            >>> backtest = generator.backtest_signals(signals, holding_period=5)
            >>> 
            >>> # Overall hit rate
            >>> print(f"Overall hit rate: {backtest['hit_rate'].mean():.2%}")
            Overall hit rate: 58.50%
            >>> 
            >>> # Hit rate by signal type
            >>> for signal_val in [-2, -1, 0, 1, 2]:
            ...     subset = backtest[backtest['signal'] == signal_val]
            ...     if len(subset) > 0:
            ...         hit_rate = subset['hit_rate'].mean()
            ...         avg_return = subset['forward_return'].mean()
            ...         print(f"Signal {signal_val:+d}: hit_rate={hit_rate:.2%}, "
            ...               f"avg_return={avg_return:.2%}")
            Signal -2: hit_rate=62.50%, avg_return=-3.20%
            Signal -1: hit_rate=55.00%, avg_return=-1.50%
            Signal +1: hit_rate=60.00%, avg_return=+2.10%
            Signal +2: hit_rate=66.67%, avg_return=+3.80%
            >>> 
            >>> # Strength-weighted returns
            >>> weighted_returns = (backtest['signal'] * backtest['strength'] * 
            ...                     backtest['forward_return'])
            >>> print(f"Weighted return: {weighted_returns.mean():.2%}")
        """
        # Compute daily returns
        returns = self.prices.pct_change()
        
        # Compute forward returns over holding period
        # rolling().sum() gives cumulative return over window
        forward_returns = returns.shift(-holding_period).rolling(holding_period).sum()
        
        # Create backtest DataFrame (copy signals)
        backtest = signals.copy()
        backtest['forward_return'] = forward_returns
        
        # Compute hit rate: signal direction matches return direction
        # Buy signals (>0) should have positive returns
        # Sell signals (<0) should have negative returns
        # Hold signals (0) are always counted as "hit" (neutral)
        backtest['hit_rate'] = (
            ((backtest['signal'] > 0) & (backtest['forward_return'] > 0)) |  # Buy correct
            ((backtest['signal'] < 0) & (backtest['forward_return'] < 0)) |  # Sell correct
            (backtest['signal'] == 0)  # Hold is always "correct" (neutral)
        ).astype(int)
        
        # Add signal-strength product for weighted analysis
        backtest['signal_strength_product'] = backtest['signal'] * backtest['strength']
        
        # Compute summary statistics
        total_signals = len(backtest)
        non_hold_signals = (backtest['signal'] != 0).sum()
        overall_hit_rate = backtest['hit_rate'].mean()
        non_hold_hit_rate = (
            backtest[backtest['signal'] != 0]['hit_rate'].mean()
            if non_hold_signals > 0
            else 0.0
        )
        avg_forward_return = backtest['forward_return'].mean()
        
        logger.info(
            f"Backtest complete ({total_signals} signals, {non_hold_signals} non-hold): "
            f"Overall hit_rate={overall_hit_rate:.2%}, "
            f"Non-hold hit_rate={non_hold_hit_rate:.2%}, "
            f"Avg forward_return={avg_forward_return:.2%}"
        )
        
        return backtest
    
    def analyze_signal_performance(
        self,
        backtest: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Analyze performance metrics by signal type.
        
        Computes hit rate, average return, and signal count for each
        signal type (-2, -1, 0, 1, 2).
        
        Args:
            backtest: DataFrame from backtest_signals()
            
        Returns:
            DataFrame with columns:
            - signal: Signal type
            - count: Number of occurrences
            - hit_rate: % of correct predictions
            - avg_return: Average forward return
            - avg_strength: Average confidence score
            - total_return: Sum of forward returns
            
        Example:
            >>> backtest = generator.backtest_signals(signals)
            >>> performance = generator.analyze_signal_performance(backtest)
            >>> print(performance)
               signal  count  hit_rate  avg_return  avg_strength  total_return
            0      -2      5     0.625      -0.032         0.750        -0.160
            1      -1     12     0.550      -0.015         0.620        -0.180
            2       0     28     1.000       0.008         0.420         0.224
            3       1     14     0.600       0.021         0.680         0.294
            4       2      6     0.667       0.038         0.820         0.228
        """
        results = []
        
        for signal_val in sorted(backtest['signal'].unique()):
            subset = backtest[backtest['signal'] == signal_val]
            
            results.append({
                'signal': signal_val,
                'count': len(subset),
                'hit_rate': subset['hit_rate'].mean(),
                'avg_return': subset['forward_return'].mean(),
                'avg_strength': subset['strength'].mean(),
                'total_return': subset['forward_return'].sum()
            })
        
        performance_df = pd.DataFrame(results)
        
        logger.info(
            f"Signal performance analysis: "
            f"{len(performance_df)} signal types analyzed"
        )
        
        return performance_df
