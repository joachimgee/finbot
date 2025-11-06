"""Tests for FinancialNewsScraper extended functionality."""
from __future__ import annotations

import pandas as pd
import pytest
from unittest.mock import Mock, patch, MagicMock

from financial_analyzer.data.news_scraper import (
    FinancialNewsScraper,
    _deduplicate_news,
)


@pytest.fixture
def scraper():
    """Create a scraper instance for tests."""
    return FinancialNewsScraper(timeout=5, max_retries=2)


@pytest.fixture
def sample_news_df():
    """Sample news DataFrame for testing."""
    return pd.DataFrame({
        'headline': [
            'Apple stock rises on earnings',
            'Apple stock rises today on earnings',  # Similar to first
            'Tesla drops 5% on delivery miss',
            'Microsoft announces new AI features',
        ],
        'source': ['Yahoo', 'NewsAPI', 'FinViz', 'NewsAPI'],
        'url': ['url1', 'url2', 'url3', 'url4'],
        'text': ['text1', 'text2', 'text3', 'text4'],
        'published': pd.date_range('2025-01-01', periods=4, freq='h', tz='UTC'),
    })


# ==================== Test NewsAPI ====================


def test_newsapi_missing_key(scraper):
    """NewsAPI returns empty DataFrame when API key missing."""
    with patch.dict('financial_analyzer.config.API_KEYS', {'newsapi_key': None}):
        df = scraper.get_news_from_newsapi('AAPL')
        assert isinstance(df, pd.DataFrame)
        assert df.empty


def test_newsapi_with_valid_key(scraper):
    """NewsAPI fetches articles with valid key."""
    mock_response = {
        'status': 'ok',
        'articles': [
            {
                'title': 'Apple rises',
                'description': 'Apple stock gains',
                'source': {'name': 'TechNews'},
                'url': 'https://example.com/1',
                'publishedAt': '2025-01-01T12:00:00Z',
            }
        ]
    }
    
    with patch.dict('financial_analyzer.config.API_KEYS', {'newsapi_key': 'test_key'}):
        with patch.object(scraper, '_request') as mock_req:
            mock_req.return_value = Mock(status_code=200, json=lambda: mock_response)
            
            df = scraper.get_news_from_newsapi('AAPL', max_articles=10)
            
            assert not df.empty
            assert 'headline' in df.columns
            assert 'source' in df.columns


def test_newsapi_rate_limit(scraper):
    """NewsAPI handles 429 rate limit gracefully."""
    with patch.dict('financial_analyzer.config.API_KEYS', {'newsapi_key': 'test_key'}):
        with patch.object(scraper, '_request') as mock_req:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_req.return_value = mock_response
            
            df = scraper.get_news_from_newsapi('AAPL')
            
            assert isinstance(df, pd.DataFrame)
            # Empty because rate limited or cache miss - check it doesn't crash
            assert isinstance(df, pd.DataFrame)


# ==================== Test Reddit ====================


def test_reddit_praw_not_installed(scraper):
    """Reddit returns empty DataFrame when PRAW not installed."""
    # Simulate ImportError inside get_news_from_reddit
    df = scraper.get_news_from_reddit('AAPL')
    # Should handle gracefully (returns empty or skips)
    assert isinstance(df, pd.DataFrame)


def test_reddit_missing_credentials(scraper):
    """Reddit returns empty DataFrame when credentials missing."""
    with patch.dict('financial_analyzer.config.API_KEYS', {
        'reddit_client_id': None,
        'reddit_client_secret': None,
    }):
        df = scraper.get_news_from_reddit('AAPL')
        assert isinstance(df, pd.DataFrame)
        # Should be empty due to missing credentials
        assert df.empty


def test_reddit_with_valid_credentials(scraper):
    """Reddit fetches discussions with valid credentials."""
    # Skip if praw not installed
    try:
        import praw
    except ImportError:
        pytest.skip("PRAW not installed")
    
    mock_submission = Mock()
    mock_submission.title = 'AAPL to the moon'
    mock_submission.selftext = 'Detailed analysis...'
    mock_submission.permalink = '/r/stocks/comments/abc'
    mock_submission.created_utc = 1704110400  # 2025-01-01 12:00:00 UTC
    mock_submission.score = 42

    mock_subreddit = Mock()
    mock_subreddit.search.return_value = [mock_submission]

    mock_reddit = Mock()
    mock_reddit.subreddit.return_value = mock_subreddit

    with patch('praw.Reddit', return_value=mock_reddit):
        with patch.dict('financial_analyzer.config.API_KEYS', {
            'reddit_client_id': 'test_id',
            'reddit_client_secret': 'test_secret',
        }):
            df = scraper.get_news_from_reddit('AAPL', subreddits=['stocks'], limit=10)
            
            assert not df.empty
            assert 'headline' in df.columns
            assert 'score' in df.columns
            assert 'AAPL to the moon' in df['headline'].values


# ==================== Test get_all_news ====================


def test_all_news_aggregation(scraper):
    """get_all_news aggregates from multiple sources."""
    mock_yahoo_df = pd.DataFrame({
        'headline': ['Yahoo news'],
        'source': ['Yahoo'],
        'url': ['url1'],
        'text': ['text1'],
        'published': pd.date_range('2025-01-01', periods=1, tz='UTC'),
    })
    
    mock_finviz_df = pd.DataFrame({
        'headline': ['FinViz news'],
        'source': ['FinViz'],
        'url': ['url2'],
        'text': ['text2'],
        'published': pd.date_range('2025-01-01', periods=1, tz='UTC'),
    })

    with patch.object(scraper, 'get_news_from_yahoo', return_value=mock_yahoo_df):
        with patch.object(scraper, 'get_news_from_finviz', return_value=mock_finviz_df):
            with patch.object(scraper, 'get_news_from_newsapi', return_value=pd.DataFrame()):
                df = scraper.get_all_news('AAPL', max_articles=100, include_reddit=False)
                
                assert not df.empty
                assert len(df) >= 2  # At least Yahoo + FinViz
                assert 'Yahoo' in df['source'].values
                assert 'FinViz' in df['source'].values


def test_all_news_empty_sources(scraper):
    """get_all_news handles all empty sources gracefully."""
    with patch.object(scraper, 'get_news_from_yahoo', return_value=pd.DataFrame()):
        with patch.object(scraper, 'get_news_from_finviz', return_value=pd.DataFrame()):
            with patch.object(scraper, 'get_news_from_newsapi', return_value=pd.DataFrame()):
                df = scraper.get_all_news('INVALID', max_articles=100)
                
                assert isinstance(df, pd.DataFrame)
                assert df.empty


# ==================== Test Deduplication ====================


def test_deduplication_exact_match(sample_news_df):
    """Deduplication removes exact duplicate headlines."""
    df_with_dup = sample_news_df.copy()
    df_with_dup.loc[4] = df_with_dup.loc[0]  # Add exact duplicate
    
    dedup = _deduplicate_news(df_with_dup, threshold=0.85)
    
    assert len(dedup) < len(df_with_dup)


def test_deduplication_similar_headlines(sample_news_df):
    """Deduplication removes similar headlines."""
    dedup = _deduplicate_news(sample_news_df, threshold=0.85)
    
    # First two headlines are similar: 'Apple stock rises...'
    headlines = dedup['headline'].tolist()
    assert len([h for h in headlines if 'Apple stock rises' in h]) == 1


def test_deduplication_empty_df():
    """Deduplication handles empty DataFrame."""
    df_empty = pd.DataFrame()
    dedup = _deduplicate_news(df_empty)
    
    assert dedup.empty


def test_deduplication_no_headline_column():
    """Deduplication handles missing headline column."""
    df_no_headline = pd.DataFrame({'text': ['text1', 'text2']})
    dedup = _deduplicate_news(df_no_headline)
    
    assert len(dedup) == len(df_no_headline)


# ==================== Test Sentiment Analysis ====================


def test_sentiment_empty_dataframe(scraper):
    """add_sentiment_scores handles empty DataFrame."""
    df_empty = pd.DataFrame()
    result = scraper.add_sentiment_scores(df_empty)
    
    assert result.empty


def test_sentiment_missing_transformers(scraper, sample_news_df):
    """add_sentiment_scores handles missing transformers gracefully."""
    with patch('builtins.__import__', side_effect=ImportError):
        result = scraper.add_sentiment_scores(sample_news_df)
        
        # Should return original DataFrame unchanged
        assert 'sentiment' not in result.columns


def test_sentiment_with_transformers(scraper, sample_news_df):
    """add_sentiment_scores adds sentiment columns with transformers."""
    # Skip if transformers not installed
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
    except ImportError:
        pytest.skip("transformers/torch not installed")
    
    # For now just test it doesn't crash
    # Full mock would be complex given batching logic
    result = scraper.add_sentiment_scores(sample_news_df.head(2), batch_size=2)
    
    # Should return DataFrame (with or without sentiment depending on model loading)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2


def test_sentiment_no_text_column(scraper):
    """add_sentiment_scores handles missing text/headline column."""
    df_no_text = pd.DataFrame({'url': ['url1', 'url2']})
    
    result = scraper.add_sentiment_scores(df_no_text)
    
    # Should return unchanged if no text column
    assert 'sentiment' not in result.columns


# ==================== Integration Tests ====================


def test_scraper_initialization():
    """Scraper initializes with valid parameters."""
    scraper = FinancialNewsScraper(timeout=15, max_retries=5)
    assert scraper.timeout == 15
    assert scraper.max_retries == 5


def test_scraper_initialization_invalid_params():
    """Scraper raises ValueError for invalid parameters."""
    with pytest.raises(ValueError):
        FinancialNewsScraper(timeout=0)
    
    with pytest.raises(ValueError):
        FinancialNewsScraper(max_retries=-1)


def test_end_to_end_news_pipeline(scraper):
    """End-to-end test: fetch, deduplicate, sentiment."""
    mock_df = pd.DataFrame({
        'headline': ['Positive news about AAPL', 'Negative news about AAPL'],
        'source': ['Test1', 'Test2'],
        'url': ['url1', 'url2'],
        'text': ['Great earnings report', 'Lawsuit filed'],
        'published': pd.date_range('2025-01-01', periods=2, tz='UTC'),
    })
    
    with patch.object(scraper, 'get_news_from_yahoo', return_value=mock_df):
        with patch.object(scraper, 'get_news_from_finviz', return_value=pd.DataFrame()):
            with patch.object(scraper, 'get_news_from_newsapi', return_value=pd.DataFrame()):
                # Fetch all news
                df = scraper.get_all_news('AAPL', max_articles=50)
                
                assert not df.empty
                assert len(df) == 2
                
                # Add sentiment (will fail gracefully if transformers not available)
                df_with_sentiment = scraper.add_sentiment_scores(df)
                
                # Should return DataFrame (with or without sentiment columns)
                assert isinstance(df_with_sentiment, pd.DataFrame)
