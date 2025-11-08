"""
Tests for SentimentAggregator - Multi-source Sentiment Ensemble.

Test Coverage:
- Initialization
- Sentiment aggregation with mocked NewsScraper
- Caching mechanism
- EMA smoothing
- Recency weighting
- Edge cases (empty news, errors)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

from financial_analyzer.sentiment import FinBERTEngine, SentimentAggregator


@pytest.fixture
def mock_news_df():
    """Mock news DataFrame from NewsScraper."""
    return pd.DataFrame({
        'headline': [
            'Apple stock surges on earnings beat',
            'Microsoft announces layoffs amid restructuring',
            'Google releases new AI model with strong performance'
        ],
        'source': ['Reuters', 'Bloomberg', 'TechCrunch'],
        'published': [
            datetime.now() - timedelta(hours=1),
            datetime.now() - timedelta(hours=3),
            datetime.now() - timedelta(hours=5)
        ]
    })


@pytest.fixture
def mock_finbert():
    """Mock FinBERTEngine."""
    engine = Mock(spec=FinBERTEngine)
    engine.batch_sentiment.return_value = [
        {'score': 0.85, 'label': 'positive', 'confidence': 0.92},
        {'score': -0.65, 'label': 'negative', 'confidence': 0.88},
        {'score': 0.35, 'label': 'positive', 'confidence': 0.75}
    ]
    return engine


def test_init_default():
    """SentimentAggregator initializes with defaults."""
    agg = SentimentAggregator()
    
    assert agg.ema_alpha == 0.3
    assert agg.cache_hours == 1
    assert isinstance(agg.finbert, FinBERTEngine)
    assert agg.cache == {}


def test_init_custom_params(mock_finbert):
    """SentimentAggregator accepts custom parameters."""
    from financial_analyzer.data.news_scraper import FinancialNewsScraper
    scraper = Mock(spec=FinancialNewsScraper)
    
    agg = SentimentAggregator(
        finbert_engine=mock_finbert,
        news_scraper=scraper,
        ema_alpha=0.5,
        cache_hours=2
    )
    
    assert agg.ema_alpha == 0.5
    assert agg.cache_hours == 2
    assert agg.finbert == mock_finbert


def test_init_invalid_ema_alpha():
    """SentimentAggregator raises on invalid ema_alpha."""
    with pytest.raises(ValueError, match="ema_alpha must be in"):
        SentimentAggregator(ema_alpha=1.5)


def test_aggregate_sentiment_basic(mock_news_df, mock_finbert):
    """aggregate_sentiment returns valid result."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    # Mock NewsScraper.get_all_news()
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL', window_days=7)
    
    assert 'sentiment_score' in result
    assert 'confidence' in result
    assert 'article_count' in result
    assert 'sources' in result
    assert 'bullish_pct' in result
    assert 'bearish_pct' in result
    assert 'neutral_pct' in result
    assert 'timestamp' in result
    
    assert -1 <= result['sentiment_score'] <= 1
    assert result['article_count'] == 3
    assert len(result['sources']) == 3


def test_aggregate_sentiment_empty_news(mock_finbert):
    """aggregate_sentiment handles empty news DataFrame."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    # Mock empty DataFrame
    with patch.object(agg.news_scraper, 'get_all_news', return_value=pd.DataFrame()):
        result = agg.aggregate_sentiment('INVALID')
    
    assert result['sentiment_score'] == 0.0
    assert result['article_count'] == 0
    assert result['confidence'] == 0.0
    assert result['neutral_pct'] == 1.0


def test_aggregate_sentiment_confidence_valid(mock_news_df, mock_finbert):
    """Confidence is in [0, 1]."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL')
    
    assert 0 <= result['confidence'] <= 1


def test_aggregate_sentiment_distribution(mock_news_df, mock_finbert):
    """Bullish + bearish + neutral percentages sum to 1.0."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL')
    
    total = result['bullish_pct'] + result['bearish_pct'] + result['neutral_pct']
    assert abs(total - 1.0) < 0.01  # Allow float precision tolerance


def test_aggregate_sentiment_caching(mock_news_df, mock_finbert):
    """Sentiment caching works correctly."""
    agg = SentimentAggregator(finbert_engine=mock_finbert, cache_hours=1)
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result1 = agg.aggregate_sentiment('AAPL')
        result2 = agg.aggregate_sentiment('AAPL')
    
    # Same ticker should return cached result (identical timestamps)
    assert result1['timestamp'] == result2['timestamp']
    assert result1['sentiment_score'] == result2['sentiment_score']


def test_aggregate_sentiment_ema_smoothing(mock_news_df, mock_finbert):
    """EMA smoothing reduces sentiment volatility."""
    agg = SentimentAggregator(finbert_engine=mock_finbert, ema_alpha=0.3)
    
    # Clear cache to force fresh computation
    agg.clear_cache()
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        # Without EMA
        result_no_ema = agg.aggregate_sentiment('AAPL', use_ema=False)
        
        # With EMA (previous sentiment = 0.0)
        agg.clear_cache()
        result_with_ema = agg.aggregate_sentiment(
            'AAPL',
            use_ema=True,
            previous_sentiment=0.0
        )
    
    # With EMA and previous=0, current sentiment should be dampened
    if result_no_ema['sentiment_score'] > 0:
        assert abs(result_with_ema['sentiment_score']) < abs(result_no_ema['sentiment_score'])


def test_aggregate_sentiment_sources_extracted(mock_news_df, mock_finbert):
    """Sources are correctly extracted from DataFrame."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL')
    
    assert 'sources' in result
    assert len(result['sources']) > 0
    assert 'Reuters' in result['sources']
    assert 'Bloomberg' in result['sources']


def test_aggregate_sentiment_no_headline_column(mock_finbert):
    """Handles DataFrame without headline or text column."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    # DataFrame without headline/text
    df_no_headline = pd.DataFrame({
        'url': ['url1', 'url2'],
        'source': ['Source1', 'Source2']
    })
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=df_no_headline):
        result = agg.aggregate_sentiment('AAPL')
    
    assert result['sentiment_score'] == 0.0
    assert result['article_count'] == 0


def test_aggregate_sentiment_exception_handling(mock_finbert):
    """Handles NewsScraper exceptions gracefully."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    # Mock exception in get_all_news()
    with patch.object(agg.news_scraper, 'get_all_news', side_effect=Exception("API error")):
        result = agg.aggregate_sentiment('AAPL')
    
    assert result['sentiment_score'] == 0.0
    assert result['article_count'] == 0
    assert result['confidence'] == 0.0


def test_clear_cache(mock_news_df, mock_finbert):
    """clear_cache() removes cached results."""
    agg = SentimentAggregator(finbert_engine=mock_finbert)
    
    # Add to cache
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        agg.aggregate_sentiment('AAPL')
    
    assert len(agg.cache) > 0
    
    # Clear cache
    agg.clear_cache()
    assert len(agg.cache) == 0
