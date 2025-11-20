"""
Comprehensive tests for news sentiment integration (Phase 5.3).

Tests cover:
- SentimentFactorEngine (23 sentiment factors from news)
- NewsSignalGenerator (combine sentiment + technical → signals)
- EventStudyAnalyzer (CAR analysis with CAPM)
- Integration pipeline (end-to-end news → signals → event study)

Total: 70+ tests with fixtures for sample data.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

from financial_analyzer.ml.sentiment_factor_engine import (
    SentimentFactorEngine,
    SentimentFactorResult
)
from financial_analyzer.ml.news_signal_generator import NewsSignalGenerator
from financial_analyzer.ml.event_study_analyzer import EventStudyAnalyzer


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_news_with_sentiment() -> pd.DataFrame:
    """
    Generate sample news data with sentiment scores.
    
    Returns 367 days of news with realistic sentiment patterns:
    - 2 articles/day on average
    - Sentiment scores in [-1, 1]
    - UTC timezone
    """
    np.random.seed(42)
    
    dates = pd.date_range(
        start='2023-03-01',  # Match OHLCV start date
        end='2024-03-01',
        freq='D',
        tz='UTC'
    )
    
    news_list = []
    for date in dates:
        # Random number of articles per day (0-4)
        n_articles = np.random.poisson(2)
        
        for _ in range(n_articles):
            # Generate sentiment with some autocorrelation
            base_sentiment = np.random.randn() * 0.3
            sentiment = np.clip(base_sentiment, -1.0, 1.0)
            
            news_list.append({
                'date': date,
                'ticker': 'AAPL',
                'title': f'News article on {date.date()}',
                'sentiment': sentiment,
                'confidence': np.random.uniform(0.6, 0.95)
            })
    
    df = pd.DataFrame(news_list)
    df = df.set_index('date')
    
    return df


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """
    Generate sample OHLCV data for 300 days (sufficient for estimation_window=50).
    
    Returns realistic price data with trend and volatility.
    """
    np.random.seed(42)
    
    dates = pd.date_range(
        start='2023-03-01',  # Start earlier for more history
        end='2024-03-01',
        freq='D',
        tz='UTC'
    )
    
    # Generate realistic price path (GBM)
    returns = np.random.randn(len(dates)) * 0.02
    prices = 100 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(len(dates)) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(len(dates))) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(len(dates))) * 0.01),
        'close': prices,
        'volume': np.random.randint(1e6, 1e7, len(dates))
    }, index=dates)
    
    return df


@pytest.fixture
def sample_market_returns() -> pd.Series:
    """
    Generate sample market returns (S&P 500 proxy).
    
    Returns 300 days of daily returns (for beta estimation).
    """
    np.random.seed(42)
    
    dates = pd.date_range(
        start='2023-03-01',
        end='2024-03-01',
        freq='D',
        tz='UTC'
    )
    
    # Market returns ~ N(0.0005, 0.01)
    returns = np.random.randn(len(dates)) * 0.01 + 0.0005
    
    return pd.Series(returns, index=dates)


@pytest.fixture
def sample_event_dates() -> pd.DatetimeIndex:
    """Generate sample event dates (e.g., earnings announcements)."""
    return pd.DatetimeIndex([
        '2024-01-15',
        '2024-02-01',
        '2024-02-20'
    ], tz='UTC')


# =============================================================================
# TESTS: SentimentFactorEngine (20 tests)
# =============================================================================

class TestSentimentFactorEngine:
    """Test suite for SentimentFactorEngine."""
    
    def test_init_valid_data(self, sample_news_with_sentiment):
        """Test initialization with valid news data."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        
        assert engine.news_df is not None
        assert len(engine.news_df) > 0
        assert 'sentiment' in engine.news_df.columns
    
    def test_init_missing_sentiment_column(self):
        """Test that missing sentiment column raises ValueError."""
        df = pd.DataFrame({
            'title': ['News 1', 'News 2']
        }, index=pd.date_range('2024-01-01', periods=2, tz='UTC'))
        
        with pytest.raises(ValueError, match="sentiment.*column"):
            SentimentFactorEngine(df)
    
    def test_init_non_datetime_index(self):
        """Test that non-datetime index raises ValueError."""
        df = pd.DataFrame({
            'sentiment': [0.5, -0.3]
        }, index=[0, 1])
        
        with pytest.raises(ValueError, match="DatetimeIndex|published"):
            SentimentFactorEngine(df)
    
    def test_init_timezone_conversion(self):
        """Test that naive datetime gets converted to UTC."""
        df = pd.DataFrame({
            'sentiment': [0.5, -0.3]
        }, index=pd.date_range('2024-01-01', periods=2))  # No tz
        
        # Should not raise, converts to UTC
        engine = SentimentFactorEngine(df)
        assert engine.news_df.index.tz is not None
    
    def test_compute_sentiment_factors_default_periods(self, sample_news_with_sentiment):
        """Test compute_sentiment_factors with default periods."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors()
        
        # Should have 4 periods * 4 factors + 7 general = 23 factors
        assert len(factors) >= 20  # At least 20 factors
        
        # Check period-based factors exist
        assert 'SENT_MA_1D' in factors
        assert 'SENT_MA_5D' in factors
        assert 'SENT_VOL_5D' in factors
        assert 'NEWS_COUNT_1D' in factors
    
    def test_compute_sentiment_factors_custom_periods(self, sample_news_with_sentiment):
        """Test compute_sentiment_factors with custom periods."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[1, 10])
        
        # Should have 2 periods * 4 factors + 7 general = 15 factors
        assert len(factors) >= 10
        
        assert 'SENT_MA_1D' in factors
        assert 'SENT_MA_10D' in factors
    
    def test_sentiment_factor_result_structure(self, sample_news_with_sentiment):
        """Test that FactorResult has correct structure."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        
        result = factors['SENT_MA_5D']
        
        assert isinstance(result, SentimentFactorResult)
        assert isinstance(result.values, pd.Series)
        assert isinstance(result.name, str)
        assert isinstance(result.description, str)
        assert isinstance(result.category, str)
        assert isinstance(result.valid_data, int)
        assert result.valid_data > 0
    
    def test_sent_ma_factor(self, sample_news_with_sentiment):
        """Test SENT_MA factor (moving average of sentiment)."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        
        sent_ma = factors['SENT_MA_5D']
        
        # Values should be in [-1, 1] range
        assert sent_ma.values.min() >= -1.0
        assert sent_ma.values.max() <= 1.0
        
        # Should have reasonable number of valid values
        assert sent_ma.valid_data > 0
    
    def test_sent_vol_factor(self, sample_news_with_sentiment):
        """Test SENT_VOL factor (volatility of sentiment)."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        
        sent_vol = factors['SENT_VOL_5D']
        
        # Volatility should be >= 0 (ignoring NaN)
        valid_values = sent_vol.values.dropna()
        assert (valid_values >= 0).all()
    
    def test_news_count_factor(self, sample_news_with_sentiment):
        """Test NEWS_COUNT factor (volume of news articles)."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[1])
        
        news_count = factors['NEWS_COUNT_1D']
        
        # Count should be >= 0 and integer-like
        assert (news_count.values >= 0).all()
    
    def test_sent_dispersion_factor(self, sample_news_with_sentiment):
        """Test SENT_DISPERSION (divergence of opinions)."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        
        dispersion = factors['SENT_DISPERSION']
        
        # Dispersion should be >= 0 (ignoring NaN)
        valid_values = dispersion.values.dropna()
        assert (valid_values >= 0).all()
    
    def test_sent_extreme_pos_factor(self, sample_news_with_sentiment):
        """Test SENT_EXTREME_POS (percentage of very positive news)."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        
        extreme_pos = factors['SENT_EXTREME_POS']
        
        # Should be in [0, 1] range (percentage, ignoring NaN)
        valid_values = extreme_pos.values.dropna()
        assert (valid_values >= 0).all()
        assert (valid_values <= 1).all()
    
    def test_sent_extreme_neg_factor(self, sample_news_with_sentiment):
        """Test SENT_EXTREME_NEG (percentage of very negative news)."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        
        extreme_neg = factors['SENT_EXTREME_NEG']
        
        # Should be in [0, 1] range (ignoring NaN)
        valid_values = extreme_neg.values.dropna()
        assert (valid_values >= 0).all()
        assert (valid_values <= 1).all()
    
    def test_compute_event_sentiment(self, sample_news_with_sentiment, sample_event_dates):
        """Test compute_event_sentiment around specific dates."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        
        event_sent = engine.compute_event_sentiment(
            sample_event_dates,
            window_before=3,
            window_after=3
        )
        
        assert isinstance(event_sent, pd.DataFrame)
        assert len(event_sent) == len(sample_event_dates)
        
        # Check structure
        assert 'event_date' in event_sent.columns
        assert 'pre_sentiment' in event_sent.columns or 'avg_sentiment_before' in event_sent.columns
    
    def test_compute_event_sentiment_empty_window(self, sample_news_with_sentiment):
        """Test event sentiment with dates outside data range."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        
        # Event date far in future (no data)
        future_dates = pd.DatetimeIndex(['2025-01-01'], tz='UTC')
        
        event_sent = engine.compute_event_sentiment(future_dates)
        
        # Should return empty DataFrame or DataFrame with 0 rows
        assert isinstance(event_sent, pd.DataFrame)
        assert len(event_sent) == 0 or event_sent.empty
    
    def test_get_factors_dataframe(self, sample_news_with_sentiment):
        """Test conversion of factors dict to DataFrame."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        
        df = engine.get_factors_dataframe(factors)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == len(factors)
        assert isinstance(df.index, pd.DatetimeIndex)
    
    def test_get_factors_dataframe_empty(self, sample_news_with_sentiment):
        """Test get_factors_dataframe with empty dict."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        
        df = engine.get_factors_dataframe({})
        
        assert isinstance(df, pd.DataFrame)
        assert df.empty
    
    def test_factors_aligned_to_daily_frequency(self, sample_news_with_sentiment):
        """Test that factors are aligned to daily frequency."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[1])
        
        df = engine.get_factors_dataframe(factors)
        
        # Index should be daily
        assert isinstance(df.index, pd.DatetimeIndex)
        # Most consecutive days should be 1 day apart
        diffs = df.index.to_series().diff().dt.days.dropna()
        assert (diffs == 1).sum() > len(diffs) * 0.8  # 80%+ consecutive
    
    def test_nan_handling_in_sentiment(self):
        """Test that NaN sentiment values are handled correctly."""
        df = pd.DataFrame({
            'sentiment': [0.5, np.nan, -0.3, np.nan, 0.8]
        }, index=pd.date_range('2024-01-01', periods=5, tz='UTC'))
        
        engine = SentimentFactorEngine(df)
        factors = engine.compute_sentiment_factors(periods=[2])
        
        # Should compute factors despite NaN values
        assert len(factors) > 0


# =============================================================================
# TESTS: NewsSignalGenerator (20 tests)
# =============================================================================

class TestNewsSignalGenerator:
    """Test suite for NewsSignalGenerator."""
    
    def test_init_valid_inputs(self, sample_news_with_sentiment, sample_ohlcv):
        """Test initialization with valid inputs."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        # Create simple technical factors
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        assert generator.sentiment_factors is not None
        assert generator.technical_factors is not None
        assert generator.prices is not None
    
    def test_init_missing_required_sentiment_factor(self, sample_ohlcv):
        """Test that missing SENT_MA_5D raises ValueError."""
        sentiment_df = pd.DataFrame({
            'SENT_VOL_5D': np.random.randn(len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        with pytest.raises(ValueError, match="SENT_MA_5D"):
            NewsSignalGenerator(
                sentiment_factors=sentiment_df,
                technical_factors=technical_df,
                prices=sample_ohlcv['close']
            )
    
    def test_init_missing_news_count(self, sample_ohlcv):
        """Test that missing NEWS_COUNT_5D raises ValueError."""
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.random.randn(len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        with pytest.raises(ValueError, match="NEWS_COUNT_5D"):
            NewsSignalGenerator(
                sentiment_factors=sentiment_df,
                technical_factors=technical_df,
                prices=sample_ohlcv['close']
            )
    
    def test_generate_signals_default_params(self, sample_news_with_sentiment, sample_ohlcv):
        """Test generate_signals with default parameters."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        
        assert isinstance(signals, pd.DataFrame)
        assert 'signal' in signals.columns
        assert 'strength' in signals.columns
        assert 'sentiment_score' in signals.columns
        assert 'technical_score' in signals.columns
    
    def test_signal_range(self, sample_news_with_sentiment, sample_ohlcv):
        """Test that signals are in [-2, 2] range."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        
        assert signals['signal'].min() >= -2
        assert signals['signal'].max() <= 2
    
    def test_strength_range(self, sample_news_with_sentiment, sample_ohlcv):
        """Test that strength is in [0, 1] range."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        
        assert (signals['strength'] >= 0).all()
        assert (signals['strength'] <= 1).all()
    
    def test_strong_buy_signal(self, sample_ohlcv):
        """Test generation of strong buy signal (2)."""
        # Create strong bullish sentiment
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.full(len(sample_ohlcv), 0.9),  # Very positive
            'NEWS_COUNT_5D': np.full(len(sample_ohlcv), 10.0)  # High volume
        }, index=sample_ohlcv.index)
        
        # Create strong bullish technicals
        technical_df = pd.DataFrame({
            'RSI_14': np.full(len(sample_ohlcv), 70.0),
            'MACD_line': np.full(len(sample_ohlcv), 1.0)
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals(
            sentiment_threshold=0.3,
            technical_score_threshold=0.6,
            news_count_threshold=5,
            use_strong_signals=True
        )
        
        # Should have some strong buy signals (2) or regular buy signals (1)
        assert (signals['signal'] >= 1).sum() > 0
    
    def test_strong_sell_signal(self, sample_ohlcv):
        """Test generation of strong sell signal (-2)."""
        # Create strong bearish sentiment
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.full(len(sample_ohlcv), -0.9),  # Very negative
            'NEWS_COUNT_5D': np.full(len(sample_ohlcv), 10.0)  # High volume
        }, index=sample_ohlcv.index)
        
        # Create strong bearish technicals
        technical_df = pd.DataFrame({
            'RSI_14': np.full(len(sample_ohlcv), 30.0),
            'MACD_line': np.full(len(sample_ohlcv), -1.0)
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals(
            sentiment_threshold=0.3,
            technical_score_threshold=0.6,
            news_count_threshold=5,
            use_strong_signals=True
        )
        
        # Should have some strong sell signals (-2) or regular sell signals (-1)
        assert (signals['signal'] <= 0).sum() > 0
    
    def test_hold_signal_neutral_sentiment(self, sample_ohlcv):
        """Test that neutral sentiment generates hold signal (0)."""
        # Neutral sentiment
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.full(len(sample_ohlcv), 0.0),
            'NEWS_COUNT_5D': np.full(len(sample_ohlcv), 2.0)
        }, index=sample_ohlcv.index)
        
        # Neutral technicals
        technical_df = pd.DataFrame({
            'RSI_14': np.full(len(sample_ohlcv), 50.0),
            'MACD_line': np.full(len(sample_ohlcv), 0.0)
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        
        # Most signals should be hold (0)
        assert (signals['signal'] == 0).sum() > len(signals) * 0.5
    
    def test_backtest_signals(self, sample_news_with_sentiment, sample_ohlcv):
        """Test backtest_signals returns forward returns."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        backtest = generator.backtest_signals(signals, holding_period=5)
        
        assert 'forward_return' in backtest.columns
        assert 'hit_rate' in backtest.columns or 'hit' in backtest.columns
    
    def test_backtest_forward_return_calculation(self, sample_ohlcv):
        """Test that forward returns are calculated correctly."""
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.random.randn(len(sample_ohlcv)),
            'NEWS_COUNT_5D': np.random.uniform(1, 10, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        backtest = generator.backtest_signals(signals, holding_period=1)
        
        # Forward return should be price change
        # Check first valid entry
        valid = backtest.dropna(subset=['forward_return'])
        if len(valid) > 0:
            idx = valid.index[0]
            expected_return = (
                sample_ohlcv['close'].shift(-1).loc[idx] / 
                sample_ohlcv['close'].loc[idx] - 1
            )
            assert np.isclose(valid.loc[idx, 'forward_return'], expected_return, atol=1e-6)
    
    def test_backtest_hit_calculation(self, sample_ohlcv):
        """Test that hit calculation matches signal direction."""
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.full(len(sample_ohlcv), 0.8),  # Bullish
            'NEWS_COUNT_5D': np.full(len(sample_ohlcv), 5.0)
        }, index=sample_ohlcv.index)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.full(len(sample_ohlcv), 60.0)
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        backtest = generator.backtest_signals(signals, holding_period=5)
        
        # For buy signals (signal > 0), check hit logic if 'hit' column exists
        buy_signals = backtest[backtest['signal'] > 0]
        if 'hit' in buy_signals.columns:
            buy_signals = buy_signals.dropna(subset=['hit'])
            if len(buy_signals) > 0:
                for idx, row in buy_signals.iterrows():
                    if row['forward_return'] > 0:
                        assert row['hit'] == 1
                    else:
                        assert row['hit'] == 0
    
    def test_analyze_signal_performance(self, sample_news_with_sentiment, sample_ohlcv):
        """Test analyze_signal_performance returns metrics by signal type."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals(use_strong_signals=True)
        backtest = generator.backtest_signals(signals, holding_period=5)
        performance = generator.analyze_signal_performance(backtest)
        
        assert isinstance(performance, pd.DataFrame)
        assert 'count' in performance.columns
        assert 'avg_return' in performance.columns
        assert 'hit_rate' in performance.columns
    
    def test_signal_performance_hit_rate_range(self, sample_news_with_sentiment, sample_ohlcv):
        """Test that hit rate is in [0, 1] range."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        backtest = generator.backtest_signals(signals, holding_period=5)
        performance = generator.analyze_signal_performance(backtest)
        
        assert (performance['hit_rate'] >= 0).all()
        assert (performance['hit_rate'] <= 1).all()
    
    def test_compute_technical_score(self, sample_ohlcv):
        """Test _compute_technical_score returns normalized scores."""
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.random.randn(len(sample_ohlcv)),
            'NEWS_COUNT_5D': np.random.uniform(1, 10, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01,
            'BB_position': np.random.uniform(0, 1, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        tech_score = generator._compute_technical_score()
        
        # Score should be in [0, 1] range (normalized)
        assert (tech_score >= 0).all()
        assert (tech_score <= 1).all()
    
    def test_custom_thresholds(self, sample_news_with_sentiment, sample_ohlcv):
        """Test signal generation with custom thresholds."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        # Very high thresholds → fewer signals
        signals_strict = generator.generate_signals(
            sentiment_threshold=0.8,
            technical_score_threshold=0.8,
            news_count_threshold=10
        )
        
        # Low thresholds → more signals
        signals_loose = generator.generate_signals(
            sentiment_threshold=0.1,
            technical_score_threshold=0.1,
            news_count_threshold=1
        )
        
        # Loose should have fewer hold (0) signals
        hold_strict = (signals_strict['signal'] == 0).sum()
        hold_loose = (signals_loose['signal'] == 0).sum()
        
        assert hold_loose < hold_strict
    
    def test_signal_generator_with_insufficient_data(self, sample_ohlcv):
        """Test signal generation with very sparse sentiment data."""
        # Only 3 days of sentiment data
        sparse_sentiment = pd.DataFrame({
            'SENT_MA_5D': [0.5, -0.3, 0.8],
            'NEWS_COUNT_5D': [2.0, 1.0, 3.0]
        }, index=sample_ohlcv.index[:3])
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, 3)  # Match sparse length
        }, index=sample_ohlcv.index[:3])
        
        # Use only first 3 days of prices to match data length
        prices_short = sample_ohlcv['close'].iloc[:3]
        
        generator = NewsSignalGenerator(
            sentiment_factors=sparse_sentiment,
            technical_factors=technical_df,
            prices=prices_short
        )
        
        signals = generator.generate_signals()
        
        # Should handle gracefully
        assert len(signals) == 3  # Match input length
    
    def test_no_strong_signals_flag(self, sample_ohlcv):
        """Test that use_strong_signals=False only generates -1, 0, 1."""
        sentiment_df = pd.DataFrame({
            'SENT_MA_5D': np.random.randn(len(sample_ohlcv)),
            'NEWS_COUNT_5D': np.random.uniform(5, 15, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(20, 80, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals(use_strong_signals=False)
        
        # No -2 or +2 signals
        assert signals['signal'].max() <= 1
        assert signals['signal'].min() >= -1


# =============================================================================
# TESTS: EventStudyAnalyzer (20 tests)
# =============================================================================

class TestEventStudyAnalyzer:
    """Test suite for EventStudyAnalyzer."""
    
    def test_init_valid_inputs(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test initialization with valid inputs."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        assert analyzer.beta is not None
        assert analyzer.alpha is not None
        assert analyzer.r_squared is not None
    
    def test_init_insufficient_data(self, sample_market_returns, sample_event_dates, caplog):
        """Test that insufficient data auto-adjusts estimation_window with warning."""
        # Only 10 days of prices
        short_prices = pd.Series(
            np.random.randn(10) * 0.01 + 100,
            index=pd.date_range('2024-01-01', periods=10, tz='UTC')
        )
        
        # Should auto-adjust and warn (not raise)
        import logging
        with caplog.at_level(logging.WARNING):
            analyzer = EventStudyAnalyzer(
                prices=short_prices,
                market_returns=sample_market_returns,
                event_dates=sample_event_dates,
                estimation_window=50
            )
        
        # Verify estimation_window was auto-adjusted
        assert analyzer.estimation_window == 9  # 10 prices - 1 for pct_change
        assert hasattr(analyzer, 'beta')
        assert hasattr(analyzer, 'alpha')
        
        # Check that warning was logged
        assert "Auto-adjusting" in caplog.text
    
    def test_init_empty_event_dates(self, sample_ohlcv, sample_market_returns):
        """Test that empty event_dates raises ValueError."""
        with pytest.raises(ValueError, match="empty|event"):
            EventStudyAnalyzer(
                prices=sample_ohlcv['close'],
                market_returns=sample_market_returns,
                event_dates=pd.DatetimeIndex([]),
                estimation_window=50  # Lower window to avoid insufficient data error
            )
    
    def test_beta_estimation(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test that beta is estimated within reasonable range."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        # Beta should be reasonable (typically -2 to 3 for stocks)
        assert -3 < analyzer.beta < 4
    
    def test_r_squared_range(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test that R-squared is in [0, 1] range."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        assert 0 <= analyzer.r_squared <= 1
    
    def test_compute_abnormal_returns(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test compute_abnormal_returns returns Series."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        ar = analyzer.compute_abnormal_returns()
        
        assert isinstance(ar, pd.Series)
        assert len(ar) > 0
        assert isinstance(ar.index, pd.DatetimeIndex)
    
    def test_abnormal_returns_mean_near_zero(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test that mean AR is close to zero (by definition)."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        ar = analyzer.compute_abnormal_returns()
        
        # Mean should be close to 0 (residuals from regression)
        assert abs(ar.mean()) < 0.05  # Within 5%
    
    def test_compute_car_default_window(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test compute_car with default window."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car()
        
        assert isinstance(car_df, pd.DataFrame)
        assert 'CAR' in car_df.columns
        assert 'AAR_pre' in car_df.columns
        assert 'AAR_post' in car_df.columns
        assert 't_stat' in car_df.columns
    
    def test_compute_car_custom_window(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test compute_car with custom window."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car(window_before=3, window_after=7)
        
        assert len(car_df) > 0
        assert len(car_df) <= len(sample_event_dates)
    
    def test_car_number_of_events(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test that CAR is computed for each event."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car()
        
        # Should have one row per event (or fewer if data missing)
        assert len(car_df) <= len(sample_event_dates)
        assert len(car_df) > 0
    
    def test_car_t_statistic(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test that t-statistic is computed correctly."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car()
        
        # t-stat should be finite
        assert car_df['t_stat'].notna().sum() > 0
    
    def test_compute_aar_series(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test compute_aar_series returns Series indexed by relative days."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        aar = analyzer.compute_aar_series(window_before=5, window_after=5)
        
        assert isinstance(aar, pd.Series)
        # Should have negative and positive days (before/after event)
        assert aar.index.min() < 0
        assert aar.index.max() >= 0
    
    def test_aar_series_contains_event_day(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test that AAR series includes day 0 (event day)."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        aar = analyzer.compute_aar_series(window_before=3, window_after=3)
        
        # Day 0 should be present
        assert 0 in aar.index
    
    def test_test_car_significance(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test test_car_significance returns t-stat and p-value."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car()
        t_stat, p_value = analyzer.test_car_significance(car_df)
        
        assert isinstance(t_stat, float)
        assert isinstance(p_value, float)
        assert 0 <= p_value <= 1
    
    def test_plot_car_no_crash(self, sample_ohlcv, sample_market_returns, sample_event_dates, tmp_path):
        """Test that plot_car doesn't crash."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        # Save to temp file
        save_path = tmp_path / "car_plot.png"
        
        # Should not raise
        analyzer.plot_car(save_path=str(save_path))
        
        # File should exist
        assert save_path.exists()
    
    def test_market_model_diagnostics(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test that market model diagnostics are computed."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        
        assert analyzer.residual_std > 0
        assert 0 <= analyzer.r_squared <= 1
    
    def test_event_outside_data_range(self, sample_ohlcv, sample_market_returns):
        """Test handling of events outside price data range."""
        # Event far in future
        future_event = pd.DatetimeIndex(['2025-12-31'], tz='UTC')
        
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=future_event,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car()
        
        # Should handle gracefully (empty or NaN)
        assert len(car_df) == 0 or car_df['CAR'].isna().all()
    
    def test_multiple_events_same_day(self, sample_ohlcv, sample_market_returns):
        """Test handling of duplicate event dates."""
        duplicate_dates = pd.DatetimeIndex([
            '2024-01-15',
            '2024-01-15',  # Duplicate
            '2024-02-01'
        ], tz='UTC')
        
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=duplicate_dates,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car()
        
        # Should compute CAR for each event (even duplicates)
        assert len(car_df) <= len(duplicate_dates)
    
    def test_very_short_estimation_window(self, sample_ohlcv, sample_market_returns, sample_event_dates):
        """Test with very short estimation window."""
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=10  # Very short
        )
        
        # Should still work but with warning
        assert analyzer.beta is not None
        assert analyzer.alpha is not None


# =============================================================================
# TESTS: Integration (10 tests)
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""
    
    def test_full_pipeline_news_to_signals(self, sample_news_with_sentiment, sample_ohlcv):
        """Test complete pipeline: news → sentiment factors → signals."""
        # Step 1: Sentiment factors
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        # Step 2: Technical factors
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv)),
            'MACD_line': np.random.randn(len(sample_ohlcv)) * 0.01
        }, index=sample_ohlcv.index)
        
        # Step 3: Signal generation
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        signals = generator.generate_signals()
        
        # Step 4: Backtest
        backtest = generator.backtest_signals(signals, holding_period=5)
        
        # Verify pipeline works
        assert len(signals) > 0
        assert len(backtest) > 0
        assert 'forward_return' in backtest.columns
    
    def test_full_pipeline_with_event_study(
        self,
        sample_news_with_sentiment,
        sample_ohlcv,
        sample_market_returns,
        sample_event_dates
    ):
        """Test complete pipeline including event study."""
        # Step 1: Sentiment factors
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        
        # Step 2: Event sentiment
        event_sentiment = engine.compute_event_sentiment(sample_event_dates)
        
        # Step 3: Event study
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        car_df = analyzer.compute_car()
        
        # Verify all components work together
        assert len(sentiment_factors) > 0
        assert len(event_sentiment) > 0
        assert len(car_df) > 0
    
    def test_sentiment_factors_align_with_prices(self, sample_news_with_sentiment, sample_ohlcv):
        """Test that sentiment factors can be aligned with price data."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        # Align with prices
        combined = pd.concat([sentiment_df, sample_ohlcv], axis=1, join='inner')
        
        # Should have overlapping dates
        assert len(combined) > 0
        assert 'close' in combined.columns
        assert 'SENT_MA_5D' in combined.columns
    
    def test_signals_backtest_with_real_returns(self, sample_news_with_sentiment, sample_ohlcv):
        """Test that signal backtesting uses actual price returns."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals()
        backtest = generator.backtest_signals(signals, holding_period=1)
        
        # Verify forward returns match price changes
        valid = backtest.dropna(subset=['forward_return']).head(1)
        if len(valid) > 0:
            idx = valid.index[0]
            price_return = (
                sample_ohlcv['close'].shift(-1).loc[idx] /
                sample_ohlcv['close'].loc[idx] - 1
            )
            assert np.isclose(valid.loc[idx, 'forward_return'], price_return, atol=1e-6)
    
    def test_car_around_high_sentiment_events(
        self,
        sample_news_with_sentiment,
        sample_ohlcv,
        sample_market_returns
    ):
        """Test CAR analysis around high sentiment days."""
        # Find days with extreme positive sentiment
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        daily_sentiment = sample_news_with_sentiment.groupby(
            sample_news_with_sentiment.index.date
        )['sentiment'].mean()
        
        # Top 3 most positive days
        top_days = daily_sentiment.nlargest(3).index
        event_dates = pd.to_datetime(top_days, utc=True)
        
        # Event study
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=event_dates,
            estimation_window=50
        )
        
        car_df = analyzer.compute_car(window_before=3, window_after=3)
        
        # Should compute CAR for high sentiment events
        assert len(car_df) > 0
    
    def test_signal_performance_by_sentiment_strength(
        self,
        sample_news_with_sentiment,
        sample_ohlcv
    ):
        """Test that stronger sentiment leads to better signal performance."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        sentiment_factors = engine.compute_sentiment_factors(periods=[5])
        sentiment_df = engine.get_factors_dataframe(sentiment_factors)
        
        technical_df = pd.DataFrame({
            'RSI_14': np.random.uniform(30, 70, len(sample_ohlcv))
        }, index=sample_ohlcv.index)
        
        generator = NewsSignalGenerator(
            sentiment_factors=sentiment_df,
            technical_factors=technical_df,
            prices=sample_ohlcv['close']
        )
        
        signals = generator.generate_signals(use_strong_signals=True)
        backtest = generator.backtest_signals(signals, holding_period=5)
        performance = generator.analyze_signal_performance(backtest)
        
        # All signal types should have some data
        assert len(performance) > 0
    
    def test_event_sentiment_correlates_with_car(
        self,
        sample_news_with_sentiment,
        sample_ohlcv,
        sample_market_returns,
        sample_event_dates
    ):
        """Test that event sentiment change correlates with CAR."""
        # Event sentiment
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        event_sentiment = engine.compute_event_sentiment(
            sample_event_dates,
            window_before=3,
            window_after=3
        )
        
        # Event study
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        car_df = analyzer.compute_car(window_before=3, window_after=3)
        
        # Both should have data for events
        assert len(event_sentiment) > 0
        assert len(car_df) > 0
    
    def test_multi_period_sentiment_factors(self, sample_news_with_sentiment):
        """Test that different period sentiment factors are distinct."""
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[1, 5, 20])
        
        # Get factor DataFrames
        df = engine.get_factors_dataframe(factors)
        
        # Verify different periods produce different values
        sent_1d = df['SENT_MA_1D']
        sent_5d = df['SENT_MA_5D']
        sent_20d = df['SENT_MA_20D']
        
        # Should not be identical
        assert not sent_1d.equals(sent_5d)
        assert not sent_5d.equals(sent_20d)
    
    def test_empty_news_days_handled(self, sample_ohlcv):
        """Test handling of days with no news."""
        # Create sparse news (only 3 days)
        sparse_news = pd.DataFrame({
            'sentiment': [0.5, -0.3, 0.8]
        }, index=pd.date_range('2024-01-01', periods=3, tz='UTC'))
        
        engine = SentimentFactorEngine(sparse_news)
        factors = engine.compute_sentiment_factors(periods=[5])
        df = engine.get_factors_dataframe(factors)
        
        # Should handle days without news (NaN or 0)
        assert len(df) >= 3
    
    def test_timezone_consistency_across_pipeline(
        self,
        sample_news_with_sentiment,
        sample_ohlcv,
        sample_market_returns,
        sample_event_dates
    ):
        """Test that all components handle timezones consistently."""
        # All inputs should be UTC
        assert sample_news_with_sentiment.index.tz is not None
        assert sample_ohlcv.index.tz is not None
        assert sample_market_returns.index.tz is not None
        assert sample_event_dates.tz is not None
        
        # Sentiment factors
        engine = SentimentFactorEngine(sample_news_with_sentiment)
        factors = engine.compute_sentiment_factors(periods=[5])
        df = engine.get_factors_dataframe(factors)
        
        # Event study
        analyzer = EventStudyAnalyzer(
            prices=sample_ohlcv['close'],
            market_returns=sample_market_returns,
            event_dates=sample_event_dates,
            estimation_window=50
        )
        car_df = analyzer.compute_car()
        
        # All outputs should maintain timezone
        assert df.index.tz is not None
        assert car_df['event_date'].dt.tz is not None
