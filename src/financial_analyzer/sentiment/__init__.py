"""
Sentiment Analysis Module.

Provides FinBERT-based sentiment analysis for financial news:
- FinBERTEngine: ProsusAI/finbert model inference
- SentimentAggregator: Multi-source sentiment aggregation
- RealtimeSentimentPipeline: Real-time multi-source sentiment (Twitter, Reddit, NewsAPI)

Example:
    >>> from financial_analyzer.sentiment import FinBERTEngine, SentimentAggregator
    >>> 
    >>> engine = FinBERTEngine()
    >>> sentiment = engine.get_sentiment("Apple earnings beat expectations")
    >>> print(sentiment)
    {'score': 0.85, 'label': 'positive', 'confidence': 0.95}
    >>> 
    >>> agg = SentimentAggregator(finbert_engine=engine)
    >>> result = agg.aggregate_sentiment('AAPL', max_articles=50)
    >>> print(f"Sentiment: {result['sentiment_score']:.2f}")
"""

from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
from financial_analyzer.sentiment.sentiment_aggregator import SentimentAggregator
from financial_analyzer.sentiment.realtime_pipeline import RealtimeSentimentPipeline

__all__ = ['FinBERTEngine', 'SentimentAggregator', 'RealtimeSentimentPipeline']
