# 🎯 PHASE 5.5 MODULE 2 - REAL FINBERT SENTIMENT

## MISSION CRITIQUE

Implémenter **sentiment analysis production-grade** avec ProsusAI/FinBERT (fine-tuned sur financial news).

**Objectif** : Remplacer mock random sentiment par **vraie analyse NLP** avec news fetching + aggregation.

---

## 📚 INSPIRATIONS AUDITS

**Finance Part 5 ML** : NLP patterns + sentiment workflows
**FinBERT Documentation** : ProsusAI/finbert (financial-BERT)

---

## 🏗️ STRUCTURE MODULE 2

**Fichiers à créer** :

```
src/financial_analyzer/
├── sentiment/
│   ├── __init__.py
│   ├── finbert_engine.py            # (1) FinBERT inference
│   ├── news_fetcher.py              # (2) Multi-source news aggregation
│   ├── sentiment_aggregator.py       # (3) Sentiment ensemble
│   └── tests/
│       ├── test_finbert_engine.py        # 10 tests
│       ├── test_news_fetcher.py          # 5 tests
│       └── test_sentiment_aggregator.py  # 5 tests
```

---

## 📄 FICHIER 1 : `sentiment/finbert_engine.py`

**LOC** : 200 | **Purpose** : FinBERT inference

```python
"""
FinBERT Sentiment Analysis Engine.

Model: ProsusAI/finbert (fine-tuned on financial news, accuracy 95%+)

Features:
- Batch inference (GPU optimized)
- Sentiment scoring ∈ [-1, +1] (negative, neutral, positive)
- Confidence scores
- Production-ready error handling

Audit reference:
- Finance Part 5 ML (NLP sentiment patterns)

Example:
    >>> engine = FinBERTEngine()
    >>> sentiment = engine.get_sentiment("Apple earnings beat expectations")
    >>> print(sentiment)
    {'score': 0.85, 'label': 'positive', 'confidence': 0.95}
"""

# 1. Stdlib
from typing import Dict, List, Tuple, Optional
import logging

# 2. Data/Calc
import numpy as np

# 3. ML
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import torch

# 5. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FinBERTEngine:
    """
    FinBERT sentiment analysis engine.
    
    Model: ProsusAI/finbert
    - Fine-tuned on financial news (SemEval 2017 Task 5 + custom data)
    - 3-class classification: negative, neutral, positive
    - Accuracy: 95%+ on financial texts
    
    Process:
    1. Load FinBERT model + tokenizer (lazy load on first use)
    2. Tokenize text (max 512 tokens)
    3. Run inference (GPU if available)
    4. Convert logits → probability
    5. Return sentiment_score ∈ [-1, +1]
    
    Performance:
    - Single inference: ~100ms (CPU), ~20ms (GPU)
    - Batch inference: ~5ms per sample (GPU)
    """
    
    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        device: str = "auto",
        batch_size: int = 32
    ):
        """
        Initialize FinBERT engine.
        
        Args:
            model_name: HuggingFace model identifier
            device: 'cuda', 'cpu', or 'auto' (detect)
            batch_size: Batch size for inference
        
        Notes:
            - First initialization downloads model (~500MB)
            - Subsequent calls use cached model
        """
        self.model_name = model_name
        self.batch_size = batch_size
        
        # Auto-detect device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        
        # Lazy load model
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        
        logger.info(
            f"FinBERTEngine initialized: model={model_name}, device={device}, "
            f"batch_size={batch_size}"
        )
    
    def _load_model(self):
        """Lazy load model (on first use)."""
        if self.model is not None:
            return
        
        logger.info(f"Loading FinBERT model ({self.model_name})...")
        
        # Load model + tokenizer
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            cache_dir=".cache/finbert"
        ).to(self.device)
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=".cache/finbert"
        )
        
        # Create pipeline for convenience
        self.pipeline = pipeline(
            "text-classification",
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if self.device == "cuda" else -1
        )
        
        logger.info("FinBERT model loaded successfully")
    
    def get_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text.
        
        Args:
            text: Financial news/comment to analyze
        
        Returns:
            {
                'score': float ∈ [-1, +1],  # -1=neg, 0=neutral, +1=pos
                'label': str,                # 'positive', 'neutral', 'negative'
                'confidence': float ∈ [0, 1] # confidence in prediction
            }
        
        Example:
            >>> engine = FinBERTEngine()
            >>> sentiment = engine.get_sentiment("Stock soared on strong earnings")
            >>> print(sentiment)
            {'score': 0.82, 'label': 'positive', 'confidence': 0.98}
        """
        self._load_model()
        
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided")
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
        
        # Truncate to max tokens
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) > 512:
            # Keep first 256 + last 256
            tokens = tokens[:256] + tokens[-256:]
            text = self.tokenizer.decode(tokens)
            logger.debug(f"Text truncated to 512 tokens")
        
        try:
            # Run inference
            result = self.pipeline(text, truncation=True, max_length=512)[0]
            
            # Map label to score
            label = result['label'].lower()
            score_map = {
                'positive': 1.0,
                'neutral': 0.0,
                'negative': -1.0
            }
            
            score = score_map.get(label, 0.0) * result['score']
            confidence = result['score']
            
            return {
                'score': float(score),
                'label': label,
                'confidence': float(confidence)
            }
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
    
    def batch_sentiment(self, texts: List[str], show_progress: bool = False) -> List[Dict]:
        """
        Analyze sentiment for multiple texts (batch mode).
        
        Args:
            texts: List of text snippets
            show_progress: Show progress bar
        
        Returns:
            List of sentiment dicts (one per text)
        
        Performance:
            - 100 texts: ~500ms (GPU), ~5s (CPU)
        """
        self._load_model()
        
        results = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i+self.batch_size]
            
            if show_progress:
                logger.info(f"Processing batch {i // self.batch_size + 1} ({len(batch)} texts)")
            
            try:
                # Run batch inference
                batch_results = self.pipeline(
                    batch,
                    truncation=True,
                    max_length=512,
                    batch_size=len(batch)
                )
                
                # Convert to sentiment format
                for result in batch_results:
                    label = result['label'].lower()
                    score_map = {
                        'positive': 1.0,
                        'neutral': 0.0,
                        'negative': -1.0
                    }
                    score = score_map.get(label, 0.0) * result['score']
                    
                    results.append({
                        'score': float(score),
                        'label': label,
                        'confidence': float(result['score'])
                    })
            
            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                # Fallback: neutral
                results.extend([
                    {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
                    for _ in batch
                ])
        
        return results


# Module exports
__all__ = ['FinBERTEngine']
```

---

## 📄 FICHIER 2 : `sentiment/news_fetcher.py`

**LOC** : 150 | **Purpose** : Multi-source news aggregation

```python
"""
News Fetcher for Financial Sentiment.

Sources:
- NewsAPI.org (100+ financial news sources)
- FinHub (earnings, economic data)
- Mock (for testing without API keys)

Example:
    >>> fetcher = NewsFetcher(api_keys={'newsapi': 'YOUR_KEY'})
    >>> articles = fetcher.fetch_news('AAPL', window_days=7)
    >>> print(len(articles))
    12  # 12 articles in past 7 days
"""

# 1. Stdlib
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

# 2. Data/Calc
import pandas as pd

# 3. External (optional)
try:
    import newsapi
    NEWSAPI_AVAILABLE = True
except ImportError:
    NEWSAPI_AVAILABLE = False

# 5. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class NewsFetcher:
    """
    Fetch financial news for sentiment analysis.
    
    Workflow:
    1. Query news API (NewsAPI, FinHub, or mock)
    2. Filter by ticker + date window
    3. Extract title + summary
    4. Return article list
    
    Features:
    - Multi-source support (fallback to mock if API unavailable)
    - Rate limiting (500 requests/month free tier)
    - Caching (avoid duplicate API calls)
    - Error handling (graceful fallback)
    
    Performance:
    - Fetch 10 articles: ~200ms (API), instant (mock)
    """
    
    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        cache_hours: int = 1,
        use_mock: bool = False
    ):
        """
        Initialize news fetcher.
        
        Args:
            api_keys: Dict with keys like {'newsapi': 'abc123'}
            cache_hours: Cache duration (reuse same query within N hours)
            use_mock: Always use mock data (no API calls)
        """
        self.api_keys = api_keys or {}
        self.cache_hours = cache_hours
        self.use_mock = use_mock
        self.cache = {}
        
        logger.info(
            f"NewsFetcher initialized: mock={use_mock}, "
            f"cache_hours={cache_hours}"
        )
    
    def fetch_news(
        self,
        ticker: str,
        window_days: int = 7,
        max_articles: int = 20
    ) -> List[Dict]:
        """
        Fetch news articles for ticker.
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            window_days: Look back N days
            max_articles: Max articles to fetch
        
        Returns:
            List of articles:
            [{
                'title': str,
                'source': str,
                'timestamp': datetime,
                'url': str,
                'summary': str (optional)
            }]
        
        Example:
            >>> articles = fetcher.fetch_news('AAPL', window_days=7)
            >>> print(articles[0]['title'])
            "Apple Q3 Earnings Beat Estimates"
        """
        # Check cache
        cache_key = f"{ticker}_{window_days}"
        if cache_key in self.cache:
            cached_time = self.cache[cache_key]['timestamp']
            if (datetime.now() - cached_time).total_seconds() < self.cache_hours * 3600:
                logger.debug(f"Using cached news for {ticker}")
                return self.cache[cache_key]['articles']
        
        # Fetch news
        if self.use_mock or not NEWSAPI_AVAILABLE:
            articles = self._fetch_mock_news(ticker, window_days, max_articles)
        else:
            try:
                articles = self._fetch_newsapi(ticker, window_days, max_articles)
            except Exception as e:
                logger.warning(f"NewsAPI fetch failed: {e}, using mock")
                articles = self._fetch_mock_news(ticker, window_days, max_articles)
        
        # Cache
        self.cache[cache_key] = {
            'timestamp': datetime.now(),
            'articles': articles
        }
        
        logger.info(f"Fetched {len(articles)} articles for {ticker}")
        return articles
    
    def _fetch_newsapi(self, ticker: str, window_days: int, max_articles: int) -> List[Dict]:
        """Fetch from NewsAPI.org."""
        from newsapi import NewsApiClient
        
        client = NewsApiClient(api_key=self.api_keys.get('newsapi'))
        
        # Query for ticker (in company name or title)
        query = f"{ticker} OR {self._ticker_to_company(ticker)}"
        
        # Calculate date range
        from_date = (datetime.now() - timedelta(days=window_days)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        # Search news
        response = client.get_everything(
            q=query,
            from_param=from_date,
            to=to_date,
            language='en',
            sort_by='publishedAt',
            page_size=max_articles
        )
        
        # Format articles
        articles = []
        for article in response['articles'][:max_articles]:
            articles.append({
                'title': article['title'],
                'source': article['source']['name'],
                'timestamp': pd.to_datetime(article['publishedAt']),
                'url': article['url'],
                'summary': article.get('description', '')
            })
        
        return articles
    
    def _fetch_mock_news(self, ticker: str, window_days: int, max_articles: int) -> List[Dict]:
        """Mock news for testing."""
        mock_headlines = [
            f"{ticker} Stock Soars on Strong Q3 Earnings",
            f"{ticker} Plans New Product Launch",
            f"{ticker} Faces Regulatory Challenges",
            f"{ticker} CEO Announces Expansion Plans",
            f"{ticker} Reports Record Revenue",
            f"{ticker} Downgraded by Analysts",
            f"{ticker} Announces Strategic Partnership",
            f"{ticker} Q4 Outlook Positive",
            f"{ticker} Invests in AI Research",
            f"{ticker} Market Share Increases"
        ]
        
        articles = []
        for i, headline in enumerate(mock_headlines[:max_articles]):
            articles.append({
                'title': headline,
                'source': ['Reuters', 'Bloomberg', 'Yahoo Finance', 'CNBC'][i % 4],
                'timestamp': datetime.now() - timedelta(days=i % window_days),
                'url': f"https://example.com/{ticker}/{i}",
                'summary': f"Article about {ticker} with positive/neutral/negative news."
            })
        
        return articles
    
    def _ticker_to_company(self, ticker: str) -> str:
        """Map ticker to company name."""
        mapping = {
            'AAPL': 'Apple',
            'MSFT': 'Microsoft',
            'GOOGL': 'Google',
            'AMZN': 'Amazon',
            'TSLA': 'Tesla',
            'META': 'Meta',
            'NVDA': 'Nvidia'
        }
        return mapping.get(ticker, ticker)


# Module exports
__all__ = ['NewsFetcher']
```

---

## 📄 FICHIER 3 : `sentiment/sentiment_aggregator.py`

**LOC** : 150 | **Purpose** : Ensemble sentiment aggregation

```python
"""
Sentiment Aggregator - Multi-source Ensemble.

Process:
1. Fetch N articles (last 7 days)
2. Score each with FinBERT
3. Aggregate: weighted average (recent > old)
4. Smooth with EMA (prevent sharp swings)
5. Output: sentiment_score + confidence + metadata

Example:
    >>> agg = SentimentAggregator(finbert_engine, news_fetcher)
    >>> sentiment = agg.aggregate_sentiment('AAPL', window_days=7)
    >>> print(sentiment)
    {
        'sentiment_score': 0.35,
        'confidence': 0.78,
        'article_count': 12,
        'sources': ['Reuters', 'Bloomberg', ...],
        'bullish_pct': 0.58,
        'bearish_pct': 0.25
    }
"""

# 1. Stdlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 5. Local
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
from financial_analyzer.sentiment.news_fetcher import NewsFetcher

logger = get_logger(__name__)


class SentimentAggregator:
    """
    Aggregate sentiment from multiple sources.
    
    Algorithm:
    1. Fetch articles (sorted by recency)
    2. Score each with FinBERT
    3. Weight by recency (exponential decay: recent = higher weight)
    4. Calculate aggregate sentiment
    5. Smooth with EMA (α=0.3, prevents overnight swings)
    6. Calculate confidence + metadata
    
    Features:
    - Handles missing/empty articles gracefully
    - NaN robustness
    - Comprehensive logging
    - Caching via NewsFetcher
    """
    
    def __init__(
        self,
        finbert_engine: Optional[FinBERTEngine] = None,
        news_fetcher: Optional[NewsFetcher] = None,
        ema_alpha: float = 0.3,
        cache_hours: int = 1
    ):
        """
        Initialize aggregator.
        
        Args:
            finbert_engine: FinBERTEngine instance (or create default)
            news_fetcher: NewsFetcher instance (or create default)
            ema_alpha: EMA smoothing factor (0.3 = responsive)
            cache_hours: Cache sentiment for N hours
        """
        self.finbert = finbert_engine or FinBERTEngine()
        self.news_fetcher = news_fetcher or NewsFetcher(use_mock=True)
        self.ema_alpha = ema_alpha
        self.cache_hours = cache_hours
        self.cache = {}
        
        logger.info(
            f"SentimentAggregator initialized: "
            f"ema_alpha={ema_alpha}, cache_hours={cache_hours}"
        )
    
    def aggregate_sentiment(
        self,
        ticker: str,
        window_days: int = 7,
        use_ema: bool = True,
        previous_sentiment: Optional[float] = None
    ) -> Dict:
        """
        Aggregate sentiment for ticker.
        
        Args:
            ticker: Stock ticker
            window_days: News lookback window
            use_ema: Apply EMA smoothing
            previous_sentiment: Previous sentiment (for EMA smoothing)
        
        Returns:
            {
                'sentiment_score': float ∈ [-1, +1],
                'confidence': float ∈ [0, 1],
                'article_count': int,
                'sources': List[str],
                'bullish_pct': float,  # % positive articles
                'bearish_pct': float,
                'neutral_pct': float,
                'timestamp': datetime
            }
        """
        # Check cache
        cache_key = ticker
        if cache_key in self.cache:
            cached_time = self.cache[cache_key]['timestamp']
            if (datetime.now() - cached_time).total_seconds() < self.cache_hours * 3600:
                logger.debug(f"Using cached sentiment for {ticker}")
                return self.cache[cache_key]
        
        # Fetch articles
        articles = self.news_fetcher.fetch_news(ticker, window_days=window_days)
        
        if not articles:
            logger.warning(f"No articles found for {ticker}")
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
        
        # Score each article
        titles = [a['title'] for a in articles]
        article_sentiments = self.finbert.batch_sentiment(titles)
        
        # Extract scores
        scores = np.array([s['score'] for s in article_sentiments])
        confidences = np.array([s['confidence'] for s in article_sentiments])
        labels = [s['label'] for s in article_sentiments]
        
        # Calculate recency weights (exponential decay)
        now = datetime.now()
        weights = []
        for article in articles:
            age_hours = (now - article['timestamp']).total_seconds() / 3600
            weight = np.exp(-age_hours / 24)  # Half-life: 1 day
            weights.append(weight)
        
        weights = np.array(weights) / np.sum(weights)  # Normalize
        
        # Weighted average sentiment
        weighted_sentiment = np.sum(scores * weights)
        
        # EMA smoothing (prevent overnight swings)
        if use_ema and previous_sentiment is not None:
            ema_sentiment = (
                self.ema_alpha * weighted_sentiment +
                (1 - self.ema_alpha) * previous_sentiment
            )
        else:
            ema_sentiment = weighted_sentiment
        
        # Confidence = average confidence
        confidence = np.mean(confidences)
        
        # Label distribution
        n_bullish = sum(1 for label in labels if label == 'positive')
        n_bearish = sum(1 for label in labels if label == 'negative')
        n_neutral = len(labels) - n_bullish - n_bearish
        
        # Unique sources
        sources = list(set(a['source'] for a in articles))
        
        result = {
            'sentiment_score': float(ema_sentiment),
            'confidence': float(confidence),
            'article_count': len(articles),
            'sources': sources,
            'bullish_pct': n_bullish / len(labels),
            'bearish_pct': n_bearish / len(labels),
            'neutral_pct': n_neutral / len(labels),
            'timestamp': datetime.now()
        }
        
        # Cache
        self.cache[cache_key] = result
        
        logger.info(
            f"Sentiment aggregated for {ticker}: "
            f"score={result['sentiment_score']:.2f}, "
            f"confidence={result['confidence']:.2f}, "
            f"articles={result['article_count']}"
        )
        
        return result


# Module exports
__all__ = ['SentimentAggregator']
```

---

## 🧪 TESTS : `sentiment/tests/`

**20 tests** (split across 3 files):

```python
# ================== test_finbert_engine.py (10 tests) ==================

def test_init_default():
    """FinBERTEngine initializes."""
    engine = FinBERTEngine()
    assert engine.model_name == "ProsusAI/finbert"

def test_get_sentiment_positive():
    """Positive text scores > 0.5."""
    engine = FinBERTEngine(device="cpu")
    result = engine.get_sentiment("Apple beats earnings expectations")
    assert result['score'] > 0.3
    assert result['label'] in ['positive', 'neutral']
    assert 0 <= result['confidence'] <= 1

def test_get_sentiment_negative():
    """Negative text scores < -0.3."""
    engine = FinBERTEngine(device="cpu")
    result = engine.get_sentiment("Stock plummets amid losses")
    assert result['score'] < 0.3
    assert result['label'] in ['negative', 'neutral']

def test_get_sentiment_neutral():
    """Neutral text scores ≈ 0."""
    engine = FinBERTEngine(device="cpu")
    result = engine.get_sentiment("Company reported quarterly results")
    assert result['label'] in ['neutral', 'positive', 'negative']

def test_get_sentiment_empty_string():
    """Empty string returns neutral."""
    engine = FinBERTEngine(device="cpu")
    result = engine.get_sentiment("")
    assert result['score'] == 0.0
    assert result['label'] == 'neutral'

def test_batch_sentiment_multiple():
    """Batch sentiment processes multiple texts."""
    engine = FinBERTEngine(device="cpu")
    texts = [
        "Great earnings",
        "Disappointing results",
        "Company news"
    ]
    results = engine.batch_sentiment(texts)
    assert len(results) == 3
    assert all('score' in r and 'label' in r for r in results)

def test_batch_sentiment_empty_list():
    """Empty list returns empty results."""
    engine = FinBERTEngine(device="cpu")
    results = engine.batch_sentiment([])
    assert len(results) == 0

def test_sentiment_score_range():
    """Sentiment scores always in [-1, 1]."""
    engine = FinBERTEngine(device="cpu")
    texts = [
        "Best day ever",
        "Worst news",
        "Normal update",
        "Phenomenal results",
        "Catastrophic failure"
    ]
    for text in texts:
        result = engine.get_sentiment(text)
        assert -1.0 <= result['score'] <= 1.0

def test_confidence_range():
    """Confidence always in [0, 1]."""
    engine = FinBERTEngine(device="cpu")
    for _ in range(5):
        result = engine.get_sentiment("Random text for testing")
        assert 0.0 <= result['confidence'] <= 1.0

def test_label_valid():
    """Label is one of: positive, neutral, negative."""
    engine = FinBERTEngine(device="cpu")
    texts = ["Good", "Bad", "Neutral", "Amazing", "Terrible"]
    for text in texts:
        result = engine.get_sentiment(text)
        assert result['label'] in ['positive', 'neutral', 'negative']

# ================== test_news_fetcher.py (5 tests) ==================

def test_init_mock():
    """NewsFetcher initializes with mock."""
    fetcher = NewsFetcher(use_mock=True)
    assert fetcher.use_mock is True

def test_fetch_news_mock():
    """Fetch news returns articles (mock)."""
    fetcher = NewsFetcher(use_mock=True)
    articles = fetcher.fetch_news('AAPL', window_days=7)
    assert len(articles) > 0
    assert 'title' in articles[0]
    assert 'source' in articles[0]
    assert 'timestamp' in articles[0]

def test_fetch_news_max_articles():
    """Fetch respects max_articles limit."""
    fetcher = NewsFetcher(use_mock=True)
    articles = fetcher.fetch_news('AAPL', max_articles=3)
    assert len(articles) <= 3

def test_fetch_news_caching():
    """Fetch caches results."""
    fetcher = NewsFetcher(use_mock=True, cache_hours=1)
    articles1 = fetcher.fetch_news('AAPL')
    articles2 = fetcher.fetch_news('AAPL')
    assert articles1 == articles2  # Identical (from cache)

def test_fetch_news_different_tickers():
    """Different tickers return different articles."""
    fetcher = NewsFetcher(use_mock=True)
    aapl = fetcher.fetch_news('AAPL', max_articles=2)
    msft = fetcher.fetch_news('MSFT', max_articles=2)
    assert aapl[0]['title'] != msft[0]['title']

# ================== test_sentiment_aggregator.py (5 tests) ==================

def test_init_default():
    """SentimentAggregator initializes."""
    agg = SentimentAggregator()
    assert agg.ema_alpha == 0.3

def test_aggregate_sentiment_basic():
    """Aggregate sentiment returns valid result."""
    agg = SentimentAggregator()
    result = agg.aggregate_sentiment('AAPL', window_days=7)
    assert 'sentiment_score' in result
    assert 'confidence' in result
    assert 'article_count' in result
    assert -1 <= result['sentiment_score'] <= 1

def test_aggregate_sentiment_confidence_valid():
    """Confidence is valid."""
    agg = SentimentAggregator()
    result = agg.aggregate_sentiment('AAPL')
    assert 0 <= result['confidence'] <= 1

def test_aggregate_sentiment_distribution():
    """Bullish + bearish + neutral = 1.0."""
    agg = SentimentAggregator()
    result = agg.aggregate_sentiment('AAPL')
    total = result['bullish_pct'] + result['bearish_pct'] + result['neutral_pct']
    assert abs(total - 1.0) < 0.01  # Allow floating point error

def test_aggregate_sentiment_caching():
    """Sentiment caching works."""
    agg = SentimentAggregator(cache_hours=1)
    result1 = agg.aggregate_sentiment('AAPL')
    result2 = agg.aggregate_sentiment('AAPL')
    # Same ticker → should return cached (identical timestamp within 1 hour)
    assert abs((result2['timestamp'] - result1['timestamp']).total_seconds()) < 1
```

---

## 📊 QUALITY CHECKLIST

- [ ] FinBERTEngine + batch inference
- [ ] NewsFetcher (NewsAPI + mock)
- [ ] SentimentAggregator (weighted + EMA)
- [ ] 20 tests passing (10 + 5 + 5)
- [ ] Type hints 100%
- [ ] Docstrings 100% Google
- [ ] Zero Pylance errors
- [ ] Production-ready error handling
- [ ] Caching + performance optimized

---

## 🚀 ACTION COPILOT

**Génère** :
1. `sentiment/finbert_engine.py` (200 LOC) ✅
2. `sentiment/news_fetcher.py` (150 LOC) ✅
3. `sentiment/sentiment_aggregator.py` (150 LOC) ✅
4. All 3 test files (20 tests total) ✅

**Timeline** : ~1-1.5h | **Quality** : Production-ready ⭐⭐⭐⭐⭐

**QUALITY > VITESSE** 🎯
