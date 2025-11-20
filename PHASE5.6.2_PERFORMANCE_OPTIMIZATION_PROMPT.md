# 🎯 PHASE 5.6.2 - PERFORMANCE OPTIMIZATION PROMPT

## 📍 STATUS ACTUEL

✅ Phase 5.5 : Core modules (9.88/10) - DONE
✅ Phase 5.6.1 : Integration tests (9.1/10) - DONE
🚀 **Phase 5.6.2** : Performance Optimization - **NOW**

---

## CONTEXT

**Phase 5.6.2** implémente **Performance Optimization** pour production :
- Redis Caching (market data, sentiment results, universe selection)
- Async Pipeline (parallel API calls)
- Database Layer (PostgreSQL + SQLAlchemy)

**Objectif** : Rendre le pipeline RAPIDE et SCALABLE avant backtesting (5.6.3).

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_BACKTESTING_PY.md** (45 KB) :
   - Performance patterns
   - Caching strategies

2. **AUDIT_FINANCE_PARTIE_1_OVERVIEW.md** (21 KB) :
   - System architecture
   - Performance considerations

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.6.2 : PERFORMANCE OPTIMIZATION

Génère 4 fichiers pour optimisation production :

================================================================================
1. src/financial_analyzer/caching/cache_manager.py (300 LOC)
================================================================================

"""
Cache Manager - Redis Integration.

Centralized caching layer for:
- Market data (OHLCV)
- Sentiment analysis results
- Universe selections
- Technical indicators

Features:
- Configurable TTL per data type
- Automatic expiration
- Cache invalidation
- Hit/miss metrics

Example:
    >>> from financial_analyzer.caching import CacheManager
    >>> 
    >>> cache = CacheManager(redis_host='localhost', redis_port=6379)
    >>> 
    >>> # Cache market data (1h TTL)
    >>> cache.set('market_data:AAPL:2025-11-08', returns_df, ttl=3600)
    >>> data = cache.get('market_data:AAPL:2025-11-08')
    >>> 
    >>> # Cache sentiment (4h TTL)
    >>> cache.set('sentiment:AAPL', sentiment_scores, ttl=14400)
    >>> 
    >>> # Clear cache on date change
    >>> cache.invalidate('market_data:*')
"""

from typing import Any, Dict, Optional, List
import redis
import pickle
import logging
from datetime import timedelta


class CacheManager:
    """
    Redis cache manager with TTL and metrics.
    
    Features:
    - Automatic serialization (pickle)
    - Configurable TTL per key type
    - Cache invalidation patterns
    - Hit/miss tracking
    """
    
    def __init__(
        self,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_db: int = 0,
        enable_metrics: bool = True
    ):
        """
        Initialize cache manager.
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            enable_metrics: Enable hit/miss tracking
        """
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False
        )
        self.enable_metrics = enable_metrics
        self.logger = logging.getLogger(__name__)
        
        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600
    ) -> bool:
        """
        Set cached value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (auto-serialized)
            ttl: Time-to-live in seconds
        
        Returns:
            True if set successfully
        """
        try:
            serialized = pickle.dumps(value)
            self.redis_client.setex(key, ttl, serialized)
            self.logger.debug(f"Cache SET: {key} (ttl={ttl}s)")
            return True
        except Exception as e:
            self.logger.error(f"Cache SET failed: {key} - {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found/expired
        """
        try:
            data = self.redis_client.get(key)
            if data is None:
                self.cache_misses += 1
                self.logger.debug(f"Cache MISS: {key}")
                return None
            
            self.cache_hits += 1
            self.logger.debug(f"Cache HIT: {key}")
            return pickle.loads(data)
        except Exception as e:
            self.logger.error(f"Cache GET failed: {key} - {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete cached value."""
        try:
            self.redis_client.delete(key)
            self.logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            self.logger.error(f"Cache DELETE failed: {key} - {e}")
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.
        
        Args:
            pattern: Pattern (e.g., 'market_data:*')
        
        Returns:
            Number of keys deleted
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                self.logger.info(f"Cache INVALIDATE: {pattern} ({deleted} keys)")
                return deleted
            return 0
        except Exception as e:
            self.logger.error(f"Cache INVALIDATE failed: {pattern} - {e}")
            return 0
    
    def get_metrics(self) -> Dict[str, float]:
        """Get cache hit/miss metrics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0.0
        
        return {
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'total': total,
            'hit_rate': hit_rate
        }


# Standard TTLs
CACHE_TTLS = {
    'market_data': 3600,      # 1 hour
    'sentiment': 14400,        # 4 hours
    'universe': 86400,         # 1 day
    'technical': 3600,         # 1 hour
    'ml_predictions': 7200,    # 2 hours
}


__all__ = ['CacheManager', 'CACHE_TTLS']

================================================================================
2. src/financial_analyzer/async_pipeline/async_fetcher.py (300 LOC)
================================================================================

"""
Async Market Data & News Fetcher.

Parallel fetching for:
- Historical OHLCV data (yfinance)
- News/sentiment data (NewsAPI)
- Technical indicators
- Multi-asset support

Features:
- Concurrent API calls
- Automatic retries
- Error handling
- Rate limiting

Example:
    >>> import asyncio
    >>> from financial_analyzer.async_pipeline import AsyncFetcher
    >>> 
    >>> async def fetch_data():
    ...     fetcher = AsyncFetcher(max_concurrent=5)
    ...     
    ...     tickers = ['AAPL', 'MSFT', 'GOOGL']
    ...     data = await fetcher.fetch_market_data(
    ...         tickers=tickers,
    ...         start_date='2023-01-01',
    ...         end_date='2024-01-01'
    ...     )
    ...     
    ...     sentiment = await fetcher.fetch_sentiment(tickers)
    ...     return data, sentiment
    >>> 
    >>> data, sentiment = asyncio.run(fetch_data())
"""

import asyncio
from typing import Dict, List, Optional, Any
import aiohttp
import yfinance as yf
import logging


class AsyncFetcher:
    """
    Async data fetcher with concurrency control.
    
    Features:
    - Concurrent market data fetching
    - Concurrent sentiment fetching
    - Automatic retries
    - Rate limiting
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        retry_attempts: int = 3,
        timeout_seconds: int = 30
    ):
        """
        Initialize async fetcher.
        
        Args:
            max_concurrent: Max concurrent requests
            retry_attempts: Retry attempts per request
            timeout_seconds: Request timeout
        """
        self.max_concurrent = max_concurrent
        self.retry_attempts = retry_attempts
        self.timeout_seconds = timeout_seconds
        self.logger = logging.getLogger(__name__)
        
        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_market_data(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Fetch market data for multiple tickers concurrently.
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dict[ticker, DataFrame with OHLCV]
        """
        tasks = [
            self._fetch_ticker_data(ticker, start_date, end_date)
            for ticker in tickers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            ticker: data
            for ticker, data in zip(tickers, results)
            if not isinstance(data, Exception)
        }
    
    async def _fetch_ticker_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> Optional[Any]:
        """Fetch single ticker with retries."""
        for attempt in range(self.retry_attempts):
            try:
                async with self.semaphore:
                    # yfinance doesn't support async natively, run in executor
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(
                        None,
                        lambda: yf.download(ticker, start_date, end_date)
                    )
                    self.logger.info(f"Fetched {ticker}: {len(data)} rows")
                    return data
            except Exception as e:
                self.logger.warning(f"Fetch {ticker} attempt {attempt+1} failed: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        self.logger.error(f"Failed to fetch {ticker} after {self.retry_attempts} attempts")
        return None
    
    async def fetch_sentiment(
        self,
        tickers: List[str],
        api_key: str
    ) -> Dict[str, float]:
        """
        Fetch sentiment scores concurrently.
        
        Args:
            tickers: List of tickers
            api_key: NewsAPI key
        
        Returns:
            Dict[ticker, sentiment_score]
        """
        tasks = [
            self._fetch_ticker_sentiment(ticker, api_key)
            for ticker in tickers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            ticker: score
            for ticker, score in zip(tickers, results)
            if isinstance(score, (int, float))
        }
    
    async def _fetch_ticker_sentiment(
        self,
        ticker: str,
        api_key: str
    ) -> Optional[float]:
        """Fetch sentiment for single ticker."""
        try:
            async with aiohttp.ClientSession() as session:
                # Example: NewsAPI integration
                # (implement according to your sentiment fetcher)
                pass
        except Exception as e:
            self.logger.error(f"Sentiment fetch failed for {ticker}: {e}")
            return None


__all__ = ['AsyncFetcher']

================================================================================
3. src/financial_analyzer/database/models.py (400 LOC)
================================================================================

"""
Database Models - SQLAlchemy.

Tables for:
- Trades (executed orders)
- Allocations (portfolio weights)
- Performance metrics
- Cache statistics

Example:
    >>> from financial_analyzer.database import SessionLocal, Trade, Allocation
    >>> 
    >>> # Create trade
    >>> trade = Trade(
    ...     ticker='AAPL',
    ...     order_type='BUY',
    ...     quantity=100,
    ...     price=150.25,
    ...     timestamp='2025-11-08 10:30:00'
    ... )
    >>> session = SessionLocal()
    >>> session.add(trade)
    >>> session.commit()
    >>> 
    >>> # Query trades
    >>> trades = session.query(Trade).filter(Trade.ticker == 'AAPL').all()
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum


Base = declarative_base()


class OrderType(enum.Enum):
    """Order type enumeration."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Trade(Base):
    """
    Trade model - Executed orders.
    
    Columns:
    - id: Primary key
    - ticker: Stock ticker
    - order_type: BUY/SELL/HOLD
    - quantity: Number of shares
    - price: Execution price
    - timestamp: Execution time
    - pnl: Profit/loss (calculated)
    """
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), nullable=False, index=True)
    order_type = Column(Enum(OrderType), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    pnl = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_ticker_timestamp', 'ticker', 'timestamp'),
    )


class Allocation(Base):
    """
    Portfolio allocation model.
    
    Columns:
    - id: Primary key
    - date: Allocation date
    - ticker: Stock ticker
    - weight: Portfolio weight %
    - confidence: Signal confidence
    - reason: Allocation reason (sentiment/technical/ml)
    """
    __tablename__ = "allocations"
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    weight = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    reason = Column(String(50), nullable=True)
    
    __table_args__ = (
        Index('idx_date_ticker', 'date', 'ticker'),
    )


class PerformanceMetric(Base):
    """
    Daily performance metrics.
    
    Columns:
    - id: Primary key
    - date: Date
    - portfolio_value: Total portfolio value
    - daily_return: Daily return %
    - sharpe_ratio: Running Sharpe ratio
    - max_drawdown: Max drawdown %
    """
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, index=True, unique=True)
    portfolio_value = Column(Float, nullable=False)
    daily_return = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)


class CacheStat(Base):
    """
    Cache statistics - Track hit/miss rates.
    """
    __tablename__ = "cache_stats"
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, index=True)
    cache_hits = Column(Integer, nullable=False)
    cache_misses = Column(Integer, nullable=False)
    hit_rate = Column(Float, nullable=False)


__all__ = ['Base', 'Trade', 'Allocation', 'PerformanceMetric', 'CacheStat']

================================================================================
4. src/financial_analyzer/database/db.py (200 LOC)
================================================================================

"""
Database Connection & Session Management.

Features:
- SQLAlchemy session factory
- Connection pooling
- Migration support (Alembic ready)
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging


# Database URL (configure via env vars)
DATABASE_URL = "postgresql://user:password@localhost/finbot"

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger(__name__)


def get_db() -> Session:
    """
    Get database session (for dependency injection).
    
    Usage in FastAPI:
        @app.get("/trades")
        def get_trades(db: Session = Depends(get_db)):
            return db.query(Trade).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database (create all tables)."""
    from financial_analyzer.database.models import Base
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


def close_db():
    """Close database connection."""
    engine.dispose()
    logger.info("Database closed")


__all__ = ['engine', 'SessionLocal', 'get_db', 'init_db', 'close_db']

================================================================================
REQUIREMENTS
================================================================================

✅ Redis integration (python-redis)
✅ Async support (asyncio, aiohttp)
✅ SQLAlchemy ORM
✅ PostgreSQL compatibility
✅ Type hints 100%
✅ Google docstrings 100%
✅ Logging throughout
✅ Connection pooling
✅ Error handling

CRITICAL:
- Redis optional (graceful fallback if unavailable)
- Async doesn't block pipeline (true concurrency)
- Database migrations ready (Alembic compatible)
- No real DB calls in tests (use fixtures)

New requirements.txt entries:
redis>=4.0
aiohttp>=3.8
SQLAlchemy>=2.0
psycopg2-binary>=2.9  (PostgreSQL driver)
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `cache_manager.py` (300 LOC) - Redis caching
2. ✅ `async_fetcher.py` (300 LOC) - Async data fetching
3. ✅ `database/models.py` (400 LOC) - SQLAlchemy models
4. ✅ `database/db.py` (200 LOC) - DB connection

**Total** : 1,200 LOC

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ cache_manager.py (300 LOC)
✅ async_fetcher.py (300 LOC)
✅ database/models.py (400 LOC)
✅ database/db.py (200 LOC)

Total: 1,200 LOC
Ready: YES
```

---

## 🎯 PURPOSE

**Phase 5.6.2 implémente** :
- ✅ Redis caching (1h market data, 4h sentiment, 1d universe)
- ✅ Async pipeline (5x speedup via concurrent API calls)
- ✅ Database persistence (trades, allocations, metrics)

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

**C'est Phase 5.6.2 - Performance Optimization !** 🎯

**Temps estimé par Copilot : 2-3 heures** ⏱️

**Livraison cible** : Samedi 8 novembre, ~23h
