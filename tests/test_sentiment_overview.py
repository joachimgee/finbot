"""
Tests unitaires pour les modules sentiment : FinancialSentimentAnalyzer et SentimentAggregator.

- 100% mock, pas d'appels transformers réels
- Structure : pytest + unittest.mock
- Fixtures, parametrize, coverage >80%
- Respect conventions .github/copilot-instructions.md
"""
# Imports
import pytest
import pandas as pd
import numpy as np
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
import torch

from financial_analyzer.sentiment.finbert_analyzer import FinancialSentimentAnalyzer
from financial_analyzer.sentiment.sentiment_aggregator import SentimentAggregator

# Fixtures
@pytest.fixture
def sample_news_df() -> pd.DataFrame:
    """DataFrame news avec colonnes sentiment."""
    idx = pd.date_range("2023-01-01", periods=10, freq="D", tz="UTC")
    df = pd.DataFrame({
        "headline": [f"News {i}" for i in range(10)],
        "ticker": ["AAPL"] * 5 + ["MSFT"] * 5,
        "source": ["Yahoo Finance"] * 3 + ["NewsAPI"] * 3 + ["FinViz"] * 4,
        "sentiment_score": [0.8, 0.6, 0.4, -0.2, -0.5, 0.3, 0.1, -0.1, -0.3, 0.5],
        "positive": [0.85, 0.70, 0.65, 0.30, 0.20, 0.60, 0.55, 0.40, 0.35, 0.70],
        "negative": [0.05, 0.10, 0.25, 0.50, 0.70, 0.30, 0.45, 0.50, 0.65, 0.20],
        "neutral": [0.10, 0.20, 0.10, 0.20, 0.10, 0.10, 0.00, 0.10, 0.00, 0.10],
        "label": ["positive"] * 3 + ["negative"] * 2 + ["positive"] * 2 + ["negative"] * 2 + ["positive"]
    }, index=idx)
    df.index.name = "date"
    return df

@pytest.fixture
def sample_sentiment_scores() -> dict:
    """Scores de sentiment FinBERT de test."""
    return {
        'positive': 0.85,
        'negative': 0.05,
        'neutral': 0.10,
        'sentiment_score': 0.80,
        'label': 'positive'
    }

@pytest.fixture
def mock_model():
    """Mock du modèle FinBERT."""
    model = MagicMock()
    model.eval.return_value = None
    
    # Mock outputs
    mock_outputs = MagicMock()
    mock_logits = torch.tensor([[2.0, -1.0, 0.0]])  # positive=2.0, negative=-1.0, neutral=0.0
    mock_outputs.logits = mock_logits
    model.return_value = mock_outputs
    
    return model

@pytest.fixture
def mock_tokenizer():
    """Mock du tokenizer."""
    tokenizer = MagicMock()
    tokenizer.return_value = {
        'input_ids': torch.tensor([[1, 2, 3]]),
        'attention_mask': torch.tensor([[1, 1, 1]])
    }
    return tokenizer

@pytest.fixture
def sentiment_analyzer(mock_model, mock_tokenizer):
    """Instance FinancialSentimentAnalyzer avec mocks."""
    with patch('financial_analyzer.sentiment.finbert_analyzer.AutoModelForSequenceClassification') as mock_model_cls, \
         patch('financial_analyzer.sentiment.finbert_analyzer.AutoTokenizer') as mock_tokenizer_cls, \
         patch('financial_analyzer.sentiment.finbert_analyzer.torch.cuda.is_available', return_value=False), \
         patch('financial_analyzer.sentiment.finbert_analyzer.torch.backends.mps.is_available', return_value=False):
        
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer
        
        analyzer = FinancialSentimentAnalyzer()
        return analyzer

@pytest.fixture
def sentiment_aggregator() -> SentimentAggregator:
    """Instance SentimentAggregator."""
    return SentimentAggregator()

# Test FinancialSentimentAnalyzer
class TestFinancialSentimentAnalyzer:
    def test_init_valid_model(self, sentiment_analyzer):
        """Initialisation avec modèle valide."""
        assert sentiment_analyzer.model_name == "ProsusAI/finbert"
        assert sentiment_analyzer.device in ["cpu", "cuda", "mps"]
        assert sentiment_analyzer.batch_size == 32

    @patch('financial_analyzer.sentiment.finbert_analyzer.torch.cuda.is_available', return_value=False)
    @patch('financial_analyzer.sentiment.finbert_analyzer.torch.backends.mps.is_available', return_value=False)
    def test_init_device_fallback(self, mock_mps, mock_cuda):
        """Device fallback vers CPU si cuda/mps non disponibles."""
        with patch('financial_analyzer.sentiment.finbert_analyzer.AutoModelForSequenceClassification'), \
             patch('financial_analyzer.sentiment.finbert_analyzer.AutoTokenizer'):
            analyzer = FinancialSentimentAnalyzer()
            assert analyzer.device == "cpu"

    def test_analyze_single_valid(self, sentiment_analyzer):
        """Texte valide retourne dict avec scores."""
        result = sentiment_analyzer.analyze_single("Apple stock surges on strong earnings")
        assert isinstance(result, dict)
        assert 'sentiment_score' in result
        assert 'positive' in result
        assert 'negative' in result
        assert 'neutral' in result
        assert 'label' in result
        assert -1.0 <= result['sentiment_score'] <= 1.0

    def test_analyze_single_empty(self, sentiment_analyzer):
        """ValueError si texte vide."""
        with pytest.raises(ValueError, match="vide"):
            sentiment_analyzer.analyze_single("")

    def test_analyze_single_invalid_type(self, sentiment_analyzer):
        """ValueError si pas string."""
        with pytest.raises(ValueError, match="string"):
            sentiment_analyzer.analyze_single(12345)

    def test_analyze_batch_valid(self, sentiment_analyzer):
        """Batch retourne List[Dict]."""
        texts = ["Good news", "Bad news", "Neutral news"]
        results = sentiment_analyzer.analyze_batch(texts)
        assert isinstance(results, list)
        assert len(results) == 3
        assert all('sentiment_score' in r for r in results)

    def test_analyze_batch_empty(self, sentiment_analyzer):
        """ValueError si liste vide."""
        with pytest.raises(ValueError, match="non-vide"):
            sentiment_analyzer.analyze_batch([])

    def test_analyze_dataframe_valid(self, sentiment_analyzer):
        """Ajoute colonnes sentiment correctement."""
        df = pd.DataFrame({"headline": ["Good news", "Bad news"]})
        df_result = sentiment_analyzer.analyze_dataframe(df, text_column="headline")
        assert 'sentiment_score' in df_result.columns
        assert 'positive' in df_result.columns
        assert 'label' in df_result.columns
        assert len(df_result) == 2

    def test_analyze_dataframe_missing_column(self, sentiment_analyzer):
        """ValueError si colonne manquante."""
        df = pd.DataFrame({"text": ["Good news"]})
        with pytest.raises(ValueError, match="non trouvée"):
            sentiment_analyzer.analyze_dataframe(df, text_column="headline")

# Test SentimentAggregator
class TestSentimentAggregator:
    def test_init_valid_method(self):
        """Initialisation réussie."""
        aggregator = SentimentAggregator(default_method='mean')
        assert aggregator.default_method == 'mean'

    def test_init_invalid_method(self):
        """ValueError si méthode invalide."""
        with pytest.raises(ValueError, match="invalide"):
            SentimentAggregator(default_method='invalid')

    def test_aggregate_by_date_daily(self, sentiment_aggregator, sample_news_df):
        """Agrégation journalière fonctionne."""
        daily = sentiment_aggregator.aggregate_by_date(sample_news_df, period='D')
        assert isinstance(daily, pd.DataFrame)
        assert 'sentiment_score' in daily.columns
        assert 'count' in daily.columns
        assert isinstance(daily.index, pd.DatetimeIndex)

    def test_aggregate_by_date_weekly(self, sentiment_aggregator, sample_news_df):
        """Agrégation hebdomadaire fonctionne."""
        weekly = sentiment_aggregator.aggregate_by_date(sample_news_df, period='W')
        assert isinstance(weekly, pd.DataFrame)
        assert len(weekly) <= len(sample_news_df)

    def test_aggregate_by_date_invalid_period(self, sentiment_aggregator, sample_news_df, caplog):
        """Période auto-corrigée."""
        daily = sentiment_aggregator.aggregate_by_date(sample_news_df, period='invalid')
        assert isinstance(daily, pd.DataFrame)
        assert "Période invalide" in caplog.text or "invalid" in caplog.text.lower()

    def test_aggregate_by_ticker_valid(self, sentiment_aggregator, sample_news_df):
        """Dict[ticker, scores] corrects."""
        ticker_scores = sentiment_aggregator.aggregate_by_ticker(sample_news_df)
        assert isinstance(ticker_scores, dict)
        assert 'AAPL' in ticker_scores
        assert 'MSFT' in ticker_scores
        assert 'sentiment_score' in ticker_scores['AAPL']
        assert 'count' in ticker_scores['AAPL']

    def test_aggregate_by_source_valid(self, sentiment_aggregator, sample_news_df):
        """Dict[source, scores] corrects."""
        source_scores = sentiment_aggregator.aggregate_by_source(sample_news_df)
        assert isinstance(source_scores, dict)
        assert 'Yahoo Finance' in source_scores
        assert 'sentiment_score' in source_scores['Yahoo Finance']

    def test_aggregate_weighted_with_weights(self, sentiment_aggregator, sample_news_df):
        """Pondération appliquée."""
        weights = {"Yahoo Finance": 0.5, "NewsAPI": 0.3, "FinViz": 0.2}
        weighted = sentiment_aggregator.aggregate_weighted(sample_news_df, weights=weights)
        assert isinstance(weighted, dict)
        assert 'sentiment_score' in weighted
        assert 'count' in weighted

    def test_aggregate_weighted_no_weights(self, sentiment_aggregator, sample_news_df, caplog):
        """Fallback moyenne simple."""
        weighted = sentiment_aggregator.aggregate_weighted(sample_news_df, weights=None)
        assert isinstance(weighted, dict)
        assert "Pas de weights" in caplog.text or "mean simple" in caplog.text.lower()

    def test_get_sentiment_trend_valid(self, sentiment_aggregator, sample_news_df):
        """Trend retourne DataFrame valide."""
        trend = sentiment_aggregator.get_sentiment_trend(sample_news_df, period='D')
        assert isinstance(trend, pd.DataFrame)
        assert 'sentiment_score' in trend.columns
        assert isinstance(trend.index, pd.DatetimeIndex)

    def test_validate_dataframe_empty(self, sentiment_aggregator):
        """ValueError si DataFrame vide."""
        df = pd.DataFrame()
        with pytest.raises(ValueError, match="vide"):
            sentiment_aggregator._validate_dataframe(df)

    def test_validate_dataframe_missing_columns(self, sentiment_aggregator):
        """ValueError si colonnes manquantes."""
        df = pd.DataFrame({"col1": [1, 2]})
        with pytest.raises(ValueError, match="manquantes"):
            sentiment_aggregator._validate_dataframe(df)

# Tests d'intégration
class TestSentimentIntegration:
    def test_pipeline_news_to_sentiment(self, sentiment_analyzer, sentiment_aggregator):
        """Pipeline complet: news → sentiment → aggregation."""
        # 1. Créer DataFrame news
        news_df = pd.DataFrame({
            "headline": ["Good news", "Bad news", "Neutral news"],
            "ticker": ["AAPL", "AAPL", "AAPL"],
            "source": ["Yahoo Finance", "NewsAPI", "FinViz"]
        })
        news_df.index = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
        news_df.index.name = "date"
        
        # 2. Analyser sentiment
        news_with_sentiment = sentiment_analyzer.analyze_dataframe(news_df, text_column="headline")
        
        # 3. Agréger
        daily = sentiment_aggregator.aggregate_by_date(news_with_sentiment, period='D')
        ticker_scores = sentiment_aggregator.aggregate_by_ticker(news_with_sentiment)
        
        assert isinstance(daily, pd.DataFrame)
        assert isinstance(ticker_scores, dict)
        assert 'AAPL' in ticker_scores

    def test_multi_ticker_sentiment(self, sentiment_analyzer, sentiment_aggregator):
        """Plusieurs tickers analysés."""
        news_df = pd.DataFrame({
            "headline": ["AAPL good", "MSFT bad", "GOOGL neutral"],
            "ticker": ["AAPL", "MSFT", "GOOGL"],
            "source": ["Yahoo Finance"] * 3
        })
        news_df.index = pd.date_range("2023-01-01", periods=3, freq="D", tz="UTC")
        news_df.index.name = "date"
        
        news_with_sentiment = sentiment_analyzer.analyze_dataframe(news_df, text_column="headline")
        ticker_scores = sentiment_aggregator.aggregate_by_ticker(news_with_sentiment)
        
        assert len(ticker_scores) == 3
        assert all(ticker in ticker_scores for ticker in ["AAPL", "MSFT", "GOOGL"])
