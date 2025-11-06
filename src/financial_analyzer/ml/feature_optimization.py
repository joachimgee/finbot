"""Factor computation optimization module.

Provides caching and parallel execution utilities for efficient alpha factor computation.

Example:
    >>> from financial_analyzer.ml.feature_optimization import FactorCache, FactorBatchComputer
    >>> cache = FactorCache(maxsize=100)
    >>> computer = FactorBatchComputer(ohlcv_df, max_workers=4)
    >>> factors = computer.compute_batch(['ROC_10', 'RSI_14', 'MACD'])
"""

from __future__ import annotations

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from financial_analyzer.ml.feature_engineering import AlphaFactorEngine, FactorResult

logger = logging.getLogger(__name__)


class FactorCache:
    """LRU cache for computed alpha factors with TTL support.

    Stores factor results in memory to avoid redundant computations. Uses LRU
    eviction policy and optional time-to-live (TTL) for cached entries.

    Attributes:
        maxsize: Maximum number of cached entries
        ttl_seconds: Time-to-live for cache entries (None = no expiry)
        hits: Number of cache hits
        misses: Number of cache misses

    Example:
        >>> cache = FactorCache(maxsize=100, ttl_seconds=3600)
        >>> key = cache.make_key("AAPL", "ROC_10", "2024-01-01", "2024-12-31")
        >>> cache.set(key, factor_result)
        >>> result = cache.get(key)
    """

    def __init__(self, maxsize: int = 128, ttl_seconds: Optional[float] = None) -> None:
        """Initialize the factor cache.

        Args:
            maxsize: Maximum number of entries (LRU eviction)
            ttl_seconds: Time-to-live in seconds (None = no expiry)
        """
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.hits = 0
        self.misses = 0

        logger.info(
            "FactorCache initialized (maxsize=%d, ttl=%s)",
            maxsize,
            f"{ttl_seconds}s" if ttl_seconds else "None",
        )

    def make_key(self, ticker: str, factor_name: str, start_date: str, end_date: str) -> str:
        """Generate cache key from parameters.

        Args:
            ticker: Asset ticker symbol
            factor_name: Name of the alpha factor
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            MD5 hash of concatenated parameters
        """
        key_str = f"{ticker}|{factor_name}|{start_date}|{end_date}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached factor result.

        Args:
            key: Cache key (from make_key)

        Returns:
            Cached FactorResult or None if not found/expired
        """
        if key not in self._cache:
            self.misses += 1
            return None

        value, timestamp = self._cache[key]

        # Check TTL expiry
        if self.ttl_seconds is not None:
            age = time.time() - timestamp
            if age > self.ttl_seconds:
                logger.debug("Cache entry expired (key=%s, age=%.1fs)", key[:8], age)
                del self._cache[key]
                self.misses += 1
                return None

        # Move to end (LRU)
        self._cache[key] = self._cache.pop(key)
        self.hits += 1
        logger.debug("Cache hit (key=%s)", key[:8])
        return value

    def set(self, key: str, value: Any) -> None:
        """Store factor result in cache.

        Args:
            key: Cache key (from make_key)
            value: FactorResult object to cache
        """
        # Evict oldest if at capacity
        if len(self._cache) >= self.maxsize and key not in self._cache:
            oldest_key = next(iter(self._cache))
            logger.debug("Cache eviction (key=%s)", oldest_key[:8])
            del self._cache[oldest_key]

        self._cache[key] = (value, time.time())
        logger.debug("Cache set (key=%s)", key[:8])

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("Cache cleared")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate, size
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "maxsize": self.maxsize,
        }


class FactorBatchComputer:
    """Parallel batch computation of alpha factors.

    Computes multiple factors concurrently using ThreadPoolExecutor for I/O-bound
    operations (e.g., reading cached data) and CPU-bound vectorized computations.

    Attributes:
        engine: AlphaFactorEngine instance
        max_workers: Number of parallel workers (default: 4)
        cache: Optional FactorCache for memoization

    Example:
        >>> computer = FactorBatchComputer(ohlcv_df, max_workers=4)
        >>> factors = computer.compute_batch(['ROC_10', 'RSI_14', 'MACD'])
        >>> print(f"Computed {len(factors)} factors")
    """

    def __init__(
        self,
        ohlcv: pd.DataFrame,
        max_workers: int = 4,
        cache: Optional[FactorCache] = None,
        risk_free_rate: float = 0.03,
    ) -> None:
        """Initialize the batch computer.

        Args:
            ohlcv: OHLCV DataFrame
            max_workers: Number of parallel workers
            cache: Optional FactorCache instance
            risk_free_rate: Annual risk-free rate

        Raises:
            ValueError: If ohlcv is invalid or max_workers < 1
        """
        if ohlcv is None or ohlcv.empty:
            raise ValueError("ohlcv must be a non-empty DataFrame")
        if max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {max_workers}")

        self.engine = AlphaFactorEngine(ohlcv, risk_free_rate=risk_free_rate)
        self.max_workers = max_workers
        self.cache = cache

        logger.info(
            "FactorBatchComputer initialized (workers=%d, cache=%s)",
            max_workers,
            "enabled" if cache else "disabled",
        )

    def compute_single(self, factor_name: str) -> Optional[FactorResult]:
        """Compute a single factor (with optional caching).

        Args:
            factor_name: Name of the factor to compute

        Returns:
            FactorResult or None if computation fails

        Raises:
            ValueError: If factor_name is unknown
        """
        # Check cache
        if self.cache:
            cache_key = self.cache.make_key(
                ticker="default",
                factor_name=factor_name,
                start_date=str(self.engine.ohlcv.index[0]),
                end_date=str(self.engine.ohlcv.index[-1]),
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Compute factor
        try:
            all_factors = self.engine.compute_all_factors()
            if factor_name not in all_factors:
                logger.warning("Unknown factor: %s", factor_name)
                return None

            result = all_factors[factor_name]

            # Store in cache
            if self.cache:
                self.cache.set(cache_key, result)

            return result

        except Exception as e:
            logger.error("Error computing factor %s: %s", factor_name, e)
            return None

    def compute_batch(
        self, factor_names: List[str], progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, FactorResult]:
        """Compute multiple factors in parallel.

        Args:
            factor_names: List of factor names to compute
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary of factor_name -> FactorResult

        Example:
            >>> def progress(name):
            ...     print(f"Computed {name}")
            >>> factors = computer.compute_batch(['ROC_10', 'RSI_14'], progress)
        """
        if not factor_names:
            logger.warning("Empty factor_names list")
            return {}

        logger.info("Computing %d factors in parallel (workers=%d)", len(factor_names), self.max_workers)
        start_time = time.time()

        results: Dict[str, FactorResult] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_name = {executor.submit(self.compute_single, name): name for name in factor_names}

            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    if result is not None:
                        results[name] = result
                        if progress_callback:
                            progress_callback(name)
                except Exception as e:
                    logger.error("Exception computing %s: %s", name, e)

        elapsed = time.time() - start_time
        logger.info(
            "Batch computation completed: %d/%d factors in %.2fs",
            len(results),
            len(factor_names),
            elapsed,
        )

        return results

    def benchmark(self, n_runs: int = 3) -> Dict[str, float]:
        """Benchmark factor computation performance.

        Args:
            n_runs: Number of benchmark runs (default: 3)

        Returns:
            Dictionary with timing statistics (mean, std, min, max)

        Example:
            >>> stats = computer.benchmark(n_runs=5)
            >>> print(f"Mean time: {stats['mean']:.2f}s")
        """
        logger.info("Running benchmark (%d runs)...", n_runs)
        timings = []

        for i in range(n_runs):
            start = time.time()
            all_factors = self.engine.compute_all_factors()
            elapsed = time.time() - start
            timings.append(elapsed)
            logger.info("Run %d/%d: %.3fs (%d factors)", i + 1, n_runs, elapsed, len(all_factors))

        stats = {
            "mean": float(np.mean(timings)),
            "std": float(np.std(timings)),
            "min": float(np.min(timings)),
            "max": float(np.max(timings)),
            "n_runs": n_runs,
            "n_factors": len(all_factors),
        }

        logger.info(
            "Benchmark results: mean=%.3fs, std=%.3fs, min=%.3fs, max=%.3fs",
            stats["mean"],
            stats["std"],
            stats["min"],
            stats["max"],
        )

        return stats


# --------------- Performance Utilities ------------------


def profile_factor_computation(
    ohlcv: pd.DataFrame, factor_names: Optional[List[str]] = None, n_runs: int = 1
) -> pd.DataFrame:
    """Profile individual factor computation times.

    Args:
        ohlcv: OHLCV DataFrame
        factor_names: List of factors to profile (None = all)
        n_runs: Number of runs per factor (for averaging)

    Returns:
        DataFrame with columns: factor_name, mean_time, std_time, category

    Example:
        >>> profile_df = profile_factor_computation(ohlcv_df, n_runs=3)
        >>> print(profile_df.sort_values('mean_time', ascending=False).head())
    """
    engine = AlphaFactorEngine(ohlcv)
    all_factors = engine.compute_all_factors()

    if factor_names is None:
        factor_names = list(all_factors.keys())

    logger.info("Profiling %d factors (%d runs each)", len(factor_names), n_runs)

    results = []
    for name in factor_names:
        timings = []
        for _ in range(n_runs):
            start = time.time()
            _ = engine.compute_all_factors()[name]
            elapsed = time.time() - start
            timings.append(elapsed)

        factor_result = all_factors.get(name)
        results.append(
            {
                "factor_name": name,
                "mean_time": float(np.mean(timings)),
                "std_time": float(np.std(timings)),
                "category": factor_result.category if factor_result else "Unknown",
            }
        )

    profile_df = pd.DataFrame(results)
    logger.info("Profiling completed")
    return profile_df


def compute_factor_correlation_matrix(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Compute correlation matrix of all factors.

    Note: No caching applied here due to DataFrame unhashability.
    Caller should implement caching if needed.

    Args:
        ohlcv: OHLCV DataFrame

    Returns:
        Correlation matrix (90+ x 90+)

    Note:
        Removed @lru_cache decorator as DataFrame is unhashable.
        Caller should implement caching if needed.

    Example:
        >>> ohlcv_hash = str(ohlcv_df.index[0])[:10]  # Simple hash
        >>> corr_matrix = compute_factor_correlation_matrix(ohlcv_hash, ohlcv_df)
        >>> print(f"Correlation shape: {corr_matrix.shape}")
    """
    logger.info("Computing factor correlation matrix...")
    engine = AlphaFactorEngine(ohlcv)
    factors_df = engine.get_factors_dataframe()
    corr_matrix = factors_df.corr()
    logger.info("Correlation matrix computed: %s", corr_matrix.shape)
    return corr_matrix
