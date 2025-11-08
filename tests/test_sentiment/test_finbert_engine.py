"""
Tests for FinBERTEngine - Sentiment Analysis.

Test Coverage:
- Initialization (device selection, lazy loading)
- Single text sentiment analysis
- Batch sentiment analysis
- Edge cases (empty text, long text, errors)
- GPU/CPU handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from financial_analyzer.sentiment import FinBERTEngine


@pytest.fixture
def mock_pipeline_result():
    """Mock HuggingFace pipeline result."""
    return [{'label': 'positive', 'score': 0.95}]


def test_init_default():
    """FinBERTEngine initializes with defaults."""
    engine = FinBERTEngine()
    
    assert engine.model_name == "ProsusAI/finbert"
    assert engine.device in ['cuda', 'cpu']
    assert engine.batch_size == 32
    assert engine.model is None  # Lazy loading


def test_init_custom_device():
    """FinBERTEngine respects custom device."""
    engine = FinBERTEngine(device='cpu')
    
    assert engine.device == 'cpu'


def test_init_invalid_device():
    """FinBERTEngine raises on invalid device."""
    with pytest.raises(ValueError, match="Invalid device"):
        FinBERTEngine(device='invalid')


@patch('financial_analyzer.sentiment.finbert_engine.pipeline')
@patch('financial_analyzer.sentiment.finbert_engine.AutoTokenizer')
@patch('financial_analyzer.sentiment.finbert_engine.AutoModelForSequenceClassification')
def test_get_sentiment_positive(mock_model, mock_tokenizer, mock_pipeline_fn):
    """get_sentiment returns positive sentiment."""
    # Mock pipeline
    mock_pipeline = Mock()
    mock_pipeline.return_value = [{'label': 'positive', 'score': 0.95}]
    mock_pipeline_fn.return_value = mock_pipeline
    
    engine = FinBERTEngine(device='cpu')
    result = engine.get_sentiment("Apple stock surges on earnings beat")
    
    assert result['label'] == 'positive'
    assert 0 < result['score'] <= 1
    assert result['confidence'] == 0.95


@patch('financial_analyzer.sentiment.finbert_engine.pipeline')
@patch('financial_analyzer.sentiment.finbert_engine.AutoTokenizer')
@patch('financial_analyzer.sentiment.finbert_engine.AutoModelForSequenceClassification')
def test_get_sentiment_negative(mock_model, mock_tokenizer, mock_pipeline_fn):
    """get_sentiment returns negative sentiment."""
    mock_pipeline = Mock()
    mock_pipeline.return_value = [{'label': 'negative', 'score': 0.87}]
    mock_pipeline_fn.return_value = mock_pipeline
    
    engine = FinBERTEngine(device='cpu')
    result = engine.get_sentiment("Company files for bankruptcy")
    
    assert result['label'] == 'negative'
    assert -1 <= result['score'] < 0
    assert result['confidence'] == 0.87


@patch('financial_analyzer.sentiment.finbert_engine.pipeline')
@patch('financial_analyzer.sentiment.finbert_engine.AutoTokenizer')
@patch('financial_analyzer.sentiment.finbert_engine.AutoModelForSequenceClassification')
def test_get_sentiment_neutral(mock_model, mock_tokenizer, mock_pipeline_fn):
    """get_sentiment returns neutral sentiment."""
    mock_pipeline = Mock()
    mock_pipeline.return_value = [{'label': 'neutral', 'score': 0.92}]
    mock_pipeline_fn.return_value = mock_pipeline
    
    engine = FinBERTEngine(device='cpu')
    result = engine.get_sentiment("The company released quarterly results")
    
    assert result['label'] == 'neutral'
    assert result['score'] == 0.0  # Neutral = 0
    assert result['confidence'] == 0.92


def test_get_sentiment_empty_text():
    """get_sentiment handles empty text."""
    engine = FinBERTEngine(device='cpu')
    result = engine.get_sentiment("")
    
    assert result['score'] == 0.0
    assert result['label'] == 'neutral'
    assert result['confidence'] == 0.0


@patch('financial_analyzer.sentiment.finbert_engine.pipeline')
@patch('financial_analyzer.sentiment.finbert_engine.AutoTokenizer')
@patch('financial_analyzer.sentiment.finbert_engine.AutoModelForSequenceClassification')
def test_batch_sentiment(mock_model, mock_tokenizer, mock_pipeline_fn):
    """batch_sentiment processes multiple texts."""
    mock_pipeline = Mock()
    mock_pipeline.return_value = [
        {'label': 'positive', 'score': 0.90},
        {'label': 'negative', 'score': 0.85},
        {'label': 'neutral', 'score': 0.80}
    ]
    mock_pipeline_fn.return_value = mock_pipeline
    
    engine = FinBERTEngine(device='cpu', batch_size=32)
    texts = [
        "Bullish on tech stocks",
        "Market crash expected",
        "Company maintains guidance"
    ]
    
    results = engine.batch_sentiment(texts)
    
    assert len(results) == 3
    assert results[0]['label'] == 'positive'
    assert results[1]['label'] == 'negative'
    assert results[2]['label'] == 'neutral'


@patch('financial_analyzer.sentiment.finbert_engine.pipeline')
@patch('financial_analyzer.sentiment.finbert_engine.AutoTokenizer')
@patch('financial_analyzer.sentiment.finbert_engine.AutoModelForSequenceClassification')
def test_batch_sentiment_error_handling(mock_model, mock_tokenizer, mock_pipeline_fn):
    """batch_sentiment handles errors gracefully."""
    mock_pipeline = Mock()
    mock_pipeline.side_effect = Exception("Model error")
    mock_pipeline_fn.return_value = mock_pipeline
    
    engine = FinBERTEngine(device='cpu')
    results = engine.batch_sentiment(["text1", "text2"])
    
    # Should return neutral for all
    assert len(results) == 2
    assert all(r['score'] == 0.0 for r in results)
    assert all(r['label'] == 'neutral' for r in results)


def test_batch_sentiment_empty_list():
    """batch_sentiment handles empty input list."""
    engine = FinBERTEngine(device='cpu')
    results = engine.batch_sentiment([])
    
    assert results == []
