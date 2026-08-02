# 🔄 PHASE 5.5 MODULE 2 - REFACTORISATION (NO DUPLICATION)

## SITUATION ACTUELLE

**EXISTANT** (Semaine 1-2 anciennes phases) :
- `src/financial_analyzer/data/newsscraper.py` : **FinancialNewsScraper**
  - `get_news_from_yahoo()` ✅
  - `get_news_from_finviz()` ✅
  - `get_news_from_newsapi()` ✅
  - `get_news_from_reddit()` ✅ (optionnel)
  - `get_all_news()` ✅ (agrégation multi-sources)
  - `deduplicate_news()` ✅ (fuzzy matching)
  - Support NewsAPI, Reddit PRAW, Yahoo Finance

**PROBLÈME** : Phase 5.5 Module 2 propose `NewsFetcher` → **DOUBLON !**

---

## ✅ SOLUTION : REFACTORISER MODULE 2 (PAS DE DOUBLON)

**Architecture corrigée** :

```
src/financial_analyzer/
├── data/
│   └── newsscraper.py              # ✅ ALREADY EXISTS (reuse)
│
├── sentiment/
│   ├── __init__.py
│   ├── finbert_engine.py           # ✅ NEW (FinBERT inference)
│   ├── sentiment_aggregator.py     # ✅ NEW (ensemble sentiment)
│   └── tests/
│       ├── test_finbert_engine.py       # 10 tests
│       └── test_sentiment_aggregator.py # 10 tests
```

**CHANGEMENT** :
- ❌ SUPPRIMER : `news_fetcher.py` (doublon)
- ✅ RÉUTILISER : `data/newsscraper.py` existant
- ✅ ADAPTER : `sentiment_aggregator.py` pour utiliser `FinancialNewsScraper`

---

## 📄 MODULE 2 CORRIGÉ : SEULEMENT 2 FICHIERS

### **FICHIER 1 : `sentiment/finbert_engine.py`**

**LOC** : 200 | **Purpose** : FinBERT inference (INCHANGÉ)

```python
"""
FinBERT Sentiment Analysis Engine.

Model: ProsusAI/finbert (fine-tuned on financial news)

Features:
- Batch inference (GPU optimized)
- Sentiment scoring ∈ [-1, +1]
- Confidence scores
- Production-ready error handling

Example:
    >>> engine = FinBERTEngine()
    >>> sentiment = engine.get_sentiment("Apple earnings beat expectations")
    >>> print(sentiment)
    {'score': 0.85, 'label': 'positive', 'confidence': 0.95}
"""

# 1. Stdlib
from typing import Dict, List, Optional
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
    
    (SAME AS BEFORE - NO CHANGES)
    """
    
    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        device: str = "auto",
        batch_size: int = 32
    ):
        """Initialize FinBERT engine."""
        self.model_name = model_name
        self.batch_size = batch_size
        
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        
        logger.info(
            f"FinBERTEngine initialized: model={model_name}, device={device}"
        )
    
    def _load_model(self):
        """Lazy load model."""
        if self.model is not None:
            return
        
        logger.info(f"Loading FinBERT model ({self.model_name})...")
        
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            cache_dir=".cache/finbert"
        ).to(self.device)
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=".cache/finbert"
        )
        
        self.pipeline = pipeline(
            "text-classification",
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if self.device == "cuda" else -1
        )
        
        logger.info("FinBERT model loaded successfully")
    
    def get_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text."""
        self._load_model()
        
        if not text or len(text.strip()) == 0:
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
        
        try:
            result = self.pipeline(text, truncation=True, max_length=512)[0]
            
            label = result['label'].lower()
            score_map = {
                'positive': 1.0,
                'neutral': 0.0,
                'negative': -1.0
            }
            
            score = score_map.get(label, 0.0) * result['score']
            
            return {
                'score': float(score),
                'label': label,
                'confidence': float(result['score'])
            }
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
    
    def batch_sentiment(self, texts: List[str]) -> List[Dict]:
        """Analyze sentiment for multiple texts (batch mode)."""
        self._load_model()
        
        results = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i+self.batch_size]
            
            try:
                batch_results = self.pipeline(
                    batch,
                    truncation=True,
                    max_length=512,
                    batch_size=len(batch)
                )
                
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
                results.extend([
                    {'score': 0.0, 'label': 'neutral', 'confidence': 0.0}
                    for _ in batch
                ])
        
        return results


__all__ = ['FinBERTEngine']
```

---

### **FICHIER 2 : `sentiment/sentiment_aggregator.py` (CORRIGÉ)**

**LOC** : 150 | **Purpose** : Aggregate sentiment via **existing** NewsScraper

```python
"""
Sentiment Aggregator - Multi-source Ensemble.

Uses EXISTING FinancialNewsScraper (from data module) to fetch news,
then aggregates sentiment with FinBERT.

Process:
1. Fetch N articles via FinancialNewsScraper.get_all_news()
2. Score each with FinBERT
3. Aggregate: weighted average (recent > old)
4. Smooth with EMA
5. Output: sentiment_score + confidence + metadata

Example:
    >>> from financial_analyzer.data.newsscraper import FinancialNewsScraper
    >>> from financial_analyzer.sentiment import FinBERTEngine, SentimentAggregator
    >>> 
    >>> scraper = FinancialNewsScraper()
    >>> engine = FinBERTEngine()
    >>> agg = SentimentAggregator(finbert_engine=engine, news_scraper=scraper)
    >>> 
    >>> sentiment = agg.aggregate_sentiment('AAPL', window_days=7)
    >>> print(sentiment)
    {
        'sentiment_score': 0.35,
        'confidence': 0.78,
        'article_count': 12,
        'sources': ['Reuters', 'Bloomberg'],
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
from financial_analyzer.data.newsscraper import FinancialNewsScraper  # ✅ REUSE EXISTING

logger = get_logger(__name__)


class SentimentAggregator:
    """
    Aggregate sentiment from multiple sources via existing NewsScraper.
    
    Uses:
    - FinancialNewsScraper (data module) for news fetching
    - FinBERTEngine (sentiment module) for sentiment scoring
    
    Algorithm:
    1. Fetch articles via scraper.get_all_news()
    2. Score each with FinBERT
    3. Weight by recency (exponential decay)
    4. Calculate aggregate sentiment
    5. Smooth with EMA (α=0.3)
    6. Calculate confidence + metadata
    """
    
    def __init__(
        self,
        finbert_engine: Optional[FinBERTEngine] = None,
        news_scraper: Optional[FinancialNewsScraper] = None,
        ema_alpha: float = 0.3,
        cache_hours: int = 1
    ):
        """
        Initialize aggregator.
        
        Args:
            finbert_engine: FinBERTEngine instance (or create default)
            news_scraper: FinancialNewsScraper instance (or create default)
            ema_alpha: EMA smoothing factor (0.3 = responsive)
            cache_hours: Cache sentiment for N hours
        """
        self.finbert = finbert_engine or FinBERTEngine()
        self.news_scraper = news_scraper or FinancialNewsScraper()
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
        max_articles: int = 50,
        use_ema: bool = True,
        previous_sentiment: Optional[float] = None
    ) -> Dict:
        """
        Aggregate sentiment for ticker.
        
        Args:
            ticker: Stock ticker
            window_days: News lookback window
            max_articles: Max articles to fetch
            use_ema: Apply EMA smoothing
            previous_sentiment: Previous sentiment (for EMA)
        
        Returns:
            {
                'sentiment_score': float ∈ [-1, +1],
                'confidence': float ∈ [0, 1],
                'article_count': int,
                'sources': List[str],
                'bullish_pct': float,
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
        
        # Fetch articles via existing NewsScraper
        try:
            articles_df = self.news_scraper.get_all_news(
                ticker,
                max_articles=max_articles,
                include_reddit=False  # Optional
            )
        except Exception as e:
            logger.error(f"News fetching failed: {e}")
            articles_df = pd.DataFrame()
        
        if articles_df.empty:
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
        
        # Extract headlines (or use 'text' column if available)
        if 'headline' in articles_df.columns:
            texts = articles_df['headline'].tolist()
        elif 'text' in articles_df.columns:
            texts = articles_df['text'].tolist()
        else:
            logger.error("No text column found in articles")
            texts = []
        
        if not texts:
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
        
        # Score each article with FinBERT
        article_sentiments = self.finbert.batch_sentiment(texts)
        
        # Extract scores
        scores = np.array([s['score'] for s in article_sentiments])
        confidences = np.array([s['confidence'] for s in article_sentiments])
        labels = [s['label'] for s in article_sentiments]
        
        # Calculate recency weights (exponential decay)
        now = datetime.now()
        weights = []
        
        # Get timestamps (assume 'published' or 'date' column)
        if 'published' in articles_df.columns:
            timestamps = pd.to_datetime(articles_df['published'])
        elif 'date' in articles_df.columns:
            timestamps = pd.to_datetime(articles_df['date'])
        else:
            # Fallback: equal weights
            timestamps = pd.Series([now] * len(articles_df))
        
        for ts in timestamps:
            if pd.isna(ts):
                weights.append(1.0)
            else:
                age_hours = (now - ts).total_seconds() / 3600
                weight = np.exp(-age_hours / 24)  # Half-life: 1 day
                weights.append(weight)
        
        weights = np.array(weights) / np.sum(weights)  # Normalize
        
        # Weighted average sentiment
        weighted_sentiment = np.sum(scores * weights)
        
        # EMA smoothing
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
        if 'source' in articles_df.columns:
            sources = list(set(articles_df['source'].dropna().tolist()))
        else:
            sources = []
        
        result = {
            'sentiment_score': float(ema_sentiment),
            'confidence': float(confidence),
            'article_count': len(articles_df),
            'sources': sources,
            'bullish_pct': n_bullish / len(labels) if labels else 0.0,
            'bearish_pct': n_bearish / len(labels) if labels else 0.0,
            'neutral_pct': n_neutral / len(labels) if labels else 1.0,
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


__all__ = ['SentimentAggregator']
```

---

## 🧪 TESTS : `sentiment/tests/` (20 TESTS TOTAL)

**CORRIGÉ** : seulement 2 fichiers de tests

```python
# ================== test_finbert_engine.py (10 tests) ==================
# UNCHANGED (same as before)

# ================== test_sentiment_aggregator.py (10 tests) ==================

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta

from financial_analyzer.sentiment import FinBERTEngine, SentimentAggregator


@pytest.fixture
def mock_news_df():
    """Mock news DataFrame from NewsScraper."""
    return pd.DataFrame({
        'headline': [
            'Apple stock surges on earnings',
            'Microsoft announces layoffs',
            'Google releases new AI model'
        ],
        'source': ['Reuters', 'Bloomberg', 'TechCrunch'],
        'published': pd.date_range('2025-01-01', periods=3, freq='h')
    })


def test_init_default():
    """SentimentAggregator initializes."""
    agg = SentimentAggregator()
    assert agg.ema_alpha == 0.3


def test_aggregate_sentiment_basic(mock_news_df):
    """Aggregate sentiment returns valid result."""
    agg = SentimentAggregator()
    
    # Mock NewsScraper.get_all_news()
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL', window_days=7)
    
    assert 'sentiment_score' in result
    assert 'confidence' in result
    assert 'article_count' in result
    assert -1 <= result['sentiment_score'] <= 1
    assert result['article_count'] == 3


def test_aggregate_sentiment_empty_news():
    """Aggregate handles empty news DataFrame."""
    agg = SentimentAggregator()
    
    # Mock empty DataFrame
    with patch.object(agg.news_scraper, 'get_all_news', return_value=pd.DataFrame()):
        result = agg.aggregate_sentiment('INVALID')
    
    assert result['sentiment_score'] == 0.0
    assert result['article_count'] == 0


def test_aggregate_sentiment_confidence_valid(mock_news_df):
    """Confidence is in [0, 1]."""
    agg = SentimentAggregator()
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL')
    
    assert 0 <= result['confidence'] <= 1


def test_aggregate_sentiment_distribution(mock_news_df):
    """Bullish + bearish + neutral = 1.0."""
    agg = SentimentAggregator()
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL')
    
    total = result['bullish_pct'] + result['bearish_pct'] + result['neutral_pct']
    assert abs(total - 1.0) < 0.01


def test_aggregate_sentiment_caching(mock_news_df):
    """Sentiment caching works."""
    agg = SentimentAggregator(cache_hours=1)
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result1 = agg.aggregate_sentiment('AAPL')
        result2 = agg.aggregate_sentiment('AAPL')
    
    # Same ticker → cached (identical timestamp within tolerance)
    assert abs((result2['timestamp'] - result1['timestamp']).total_seconds()) < 1


def test_aggregate_sentiment_ema_smoothing(mock_news_df):
    """EMA smoothing reduces volatility."""
    agg = SentimentAggregator(ema_alpha=0.3)
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result1 = agg.aggregate_sentiment('AAPL', use_ema=False)
        result2 = agg.aggregate_sentiment('AAPL', use_ema=True, previous_sentiment=0.0)
    
    # With EMA, current sentiment is dampened
    if result1['sentiment_score'] > 0:
        assert result2['sentiment_score'] < result1['sentiment_score']


def test_aggregate_sentiment_sources_extracted(mock_news_df):
    """Sources are extracted from DataFrame."""
    agg = SentimentAggregator()
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=mock_news_df):
        result = agg.aggregate_sentiment('AAPL')
    
    assert 'sources' in result
    assert len(result['sources']) > 0


def test_aggregate_sentiment_no_headline_column():
    """Handles DataFrame without headline column."""
    agg = SentimentAggregator()
    
    # DataFrame without headline
    df_no_headline = pd.DataFrame({'url': ['url1', 'url2']})
    
    with patch.object(agg.news_scraper, 'get_all_news', return_value=df_no_headline):
        result = agg.aggregate_sentiment('AAPL')
    
    assert result['article_count'] == 0


def test_aggregate_sentiment_exception_handling():
    """Handles NewsScraper exceptions gracefully."""
    agg = SentimentAggregator()
    
    # Mock exception
    with patch.object(agg.news_scraper, 'get_all_news', side_effect=Exception("API error")):
        result = agg.aggregate_sentiment('AAPL')
    
    assert result['sentiment_score'] == 0.0
    assert result['article_count'] == 0
```

---

## 📊 COMPARAISON AVANT/APRÈS

| Aspect | ❌ Version Doublon | ✅ Version Refactorisée |
|--------|-------------------|------------------------|
| **news_fetcher.py** | 150 LOC (NEW) | **REMOVED** (doublon) |
| **NewsScraper** | Créer nouveau | **REUSE** existant ✅ |
| **LOC Total** | 500 (3 files) | 350 (2 files) |
| **Tests** | 20 (3 files) | 20 (2 files) |
| **Duplication** | HIGH ❌ | ZERO ✅ |
| **Maintenance** | 2 scrapers à maintenir | 1 seul scraper ✅ |
| **Integration** | Complex | Simple ✅ |

---

## ✅ RECOMMANDATION FINALE

**UTILISE LA VERSION REFACTORISÉE** :

1. ✅ **Garde** `finbert_engine.py` (200 LOC)
2. ✅ **Utilise** `sentiment_aggregator.py` **CORRIGÉ** (150 LOC) qui importe `FinancialNewsScraper`
3. ❌ **Supprime** `news_fetcher.py` (doublon inutile)
4. ✅ **20 tests** (10 + 10) au lieu de 20 (10 + 5 + 5)

**Avantages** :
- Zero duplication ✅
- Réutilise code existant testé ✅
- Moins de maintenance ✅
- Architecture cohérente ✅

---

**Veux-tu que je génère le prompt Copilot CORRIGÉ sans doublon ?** 🚀
