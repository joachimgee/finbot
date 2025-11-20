"""Redis-backed cache manager with graceful in-memory fallback.

Provides high-level API for caching JSON-serializable objects with TTL support,
metrics (hit/miss), namespacing, bulk invalidation, and optional async helpers.

Design Goals:
    - Transparence: same interface whether Redis available or not.
    - Safety: swallow transient Redis errors and log; never break core flow.
    - Observability: expose CacheMetrics dataclass with counters + last reset.
    - Extensibility: pluggable serialization (default JSON) & key prefixing.

Example:
    >>> manager = CacheManager(url="redis://localhost:6379/0")
    >>> manager.set("prices:BTC", {"close": 45000}, ttl=300)
    >>> data = manager.get("prices:BTC")
    >>> assert data["close"] == 45000

Thread-Safety:
    - In-memory fallback uses a simple dict protected by RLock for atomic ops.

Limitations:
    - Not optimized for extremely high concurrency (for that use aioredis).
    - Objects must be JSON-serializable by default encoder.
"""
from __future__ import annotations

import json
import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple, Union

try:  # Optional dependency
    import redis  # type: ignore
except Exception:  # pragma: no cover - absence path
    redis = None  # type: ignore

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

JsonSerializable = Union[dict, list, str, int, float, bool, None]
Serializer = Callable[[JsonSerializable], str]
Deserializer = Callable[[str], JsonSerializable]


@dataclass
class CacheMetrics:
    """Metrics structure for cache operations.

    Attributes:
        hits: Total number of successful key retrievals.
        misses: Total number of failed retrievals (key absent or expired).
        sets: Total number of set operations.
        deletes: Total number of delete operations.
        last_reset: Epoch timestamp of last metrics reset.
    """
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    last_reset: float = field(default_factory=lambda: time.time())

    def reset(self) -> None:
        """Reset all counters to zero and update last_reset."""
        logger.debug("Resetting cache metrics")
        self.hits = self.misses = self.sets = self.deletes = 0
        self.last_reset = time.time()

    def to_dict(self) -> Dict[str, Union[int, float]]:
        """Return metrics as a dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "last_reset": self.last_reset,
        }


class _InMemoryStore:
    """Simple in-memory store with TTL support used as fallback.

    Uses a dict mapping key -> (value, expiry_timestamp|None).
    All operations are thread-safe via an RLock.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Tuple[str, Optional[float]]] = {}
        self._lock = threading.RLock()

    def set(self, key: str, value: str, ttl: Optional[int]) -> None:
        expiry = time.time() + ttl if ttl else None
        with self._lock:
            self._data[key] = (value, expiry)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            value, expiry = entry
            if expiry and expiry < time.time():
                del self._data[key]
                return None
            return value

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def keys(self, prefix: Optional[str] = None) -> Dict[str, Tuple[str, Optional[float]]]:
        with self._lock:
            if prefix:
                return {k: v for k, v in self._data.items() if k.startswith(prefix)}
            return dict(self._data)

    def clear_prefix(self, prefix: str) -> int:
        with self._lock:
            to_delete = [k for k in self._data if k.startswith(prefix)]
            for k in to_delete:
                del self._data[k]
            return len(to_delete)


class CacheManager:
    """High-level cache manager with Redis optional backend.

    Methods:
        set(key, value, ttl): Store value.
        get(key): Retrieve value or None.
        delete(key): Remove key returning success flag.
        invalidate(prefix): Remove all keys with prefix.
        get_metrics(): Return metrics dataclass.

    Fallback semantics:
        - If Redis unreachable OR not installed -> uses _InMemoryStore.
        - All Redis errors are logged at WARNING level.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        namespace: str = "finbot",
        serializer: Serializer = lambda obj: json.dumps(obj, separators=(",", ":")),
        deserializer: Deserializer = lambda s: json.loads(s),
        default_ttl: Optional[int] = None,
        health_check_interval: int = 30,
    ) -> None:
        """Initialize cache manager.

        Args:
            url: Redis connection URL (e.g. redis://localhost:6379/0). If None uses fallback.
            namespace: Key namespace prefix for isolation.
            serializer: Function converting object -> string.
            deserializer: Function converting string -> object.
            default_ttl: Default TTL (seconds) if none provided on set.
            health_check_interval: Seconds between backend health checks.
        """
        self._url = url or os.getenv("REDIS_URL")
        self._namespace = namespace.rstrip(":")
        self._serializer = serializer
        self._deserializer = deserializer
        self._default_ttl = default_ttl
        self._health_check_interval = health_check_interval
        self._metrics = CacheMetrics()
        self._last_health_check = 0.0
        self._backend: Any = None
        self._in_memory = _InMemoryStore()
        self._lock = threading.RLock()
        self._connect()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _namespaced(self, key: str) -> str:
        return f"{self._namespace}:{key}" if self._namespace else key

    def _connect(self) -> None:
        if redis is None or not self._url:
            logger.info("Redis unavailable or URL missing; using in-memory fallback")
            self._backend = None
            return
        try:
            self._backend = redis.Redis.from_url(self._url, decode_responses=True)
            # Cheap ping validation
            self._backend.ping()
            logger.info("Connected to Redis backend for CacheManager")
        except Exception as e:  # pragma: no cover - network dependent
            logger.warning(f"Redis connection failed; fallback to memory: {e}")
            self._backend = None

    def _check_health(self) -> None:
        if self._backend is None:
            return
        now = time.time()
        if (now - self._last_health_check) < self._health_check_interval:
            return
        try:
            self._backend.ping()
            self._last_health_check = now
        except Exception as e:  # pragma: no cover - network
            logger.warning(f"Redis health check failed: {e}; switching to fallback")
            self._backend = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set(self, key: str, value: JsonSerializable, ttl: Optional[int] = None) -> None:
        """Store a JSON-serializable value under key.

        Args:
            key: Cache key without namespace.
            value: Value to store (JSON-serializable).
            ttl: TTL in seconds. If None uses default_ttl; if still None -> no expiration.
        """
        namespaced = self._namespaced(key)
        ttl_final = ttl if ttl is not None else self._default_ttl
        payload = self._serializer(value)
        with self._lock:
            if self._backend is not None:
                try:
                    if ttl_final:
                        self._backend.set(namespaced, payload, ex=ttl_final)
                    else:
                        self._backend.set(namespaced, payload)
                except Exception as e:  # pragma: no cover - network
                    logger.warning(f"Redis set failed: {e}; using fallback")
                    self._in_memory.set(namespaced, payload, ttl_final)
            else:
                self._in_memory.set(namespaced, payload, ttl_final)
            self._metrics.sets += 1

    def get(self, key: str) -> Optional[JsonSerializable]:
        """Retrieve a value by key.

        Returns None on miss or expiry.
        """
        namespaced = self._namespaced(key)
        self._check_health()
        with self._lock:
            raw: Optional[str] = None
            if self._backend is not None:
                try:
                    raw = self._backend.get(namespaced)
                except Exception as e:  # pragma: no cover - network
                    logger.warning(f"Redis get failed: {e}; falling back")
                    raw = self._in_memory.get(namespaced)
            else:
                raw = self._in_memory.get(namespaced)
            if raw is None:
                self._metrics.misses += 1
                return None
            self._metrics.hits += 1
            try:
                return self._deserializer(raw)
            except Exception as e:
                logger.error(f"Deserialization failed for key {namespaced}: {e}")
                return None

    def delete(self, key: str) -> bool:
        """Delete a single key.

        Returns:
            True if deletion succeeded (key existed), False otherwise.
        """
        namespaced = self._namespaced(key)
        with self._lock:
            success = False
            if self._backend is not None:
                try:
                    success = bool(self._backend.delete(namespaced))
                except Exception as e:  # pragma: no cover - network
                    logger.warning(f"Redis delete failed: {e}; fallback")
                    success = self._in_memory.delete(namespaced)
            else:
                success = self._in_memory.delete(namespaced)
            if success:
                self._metrics.deletes += 1
            return success

    def invalidate(self, prefix: str) -> int:
        """Invalidate all keys sharing prefix (namespace aware).

        Args:
            prefix: Prefix relative to namespace.
        Returns:
            Number of keys removed.
        """
        namespaced_prefix = self._namespaced(prefix)
        removed = 0
        with self._lock:
            if self._backend is not None:
                try:
                    # Use scan for efficiency on large keyspace.
                    cursor = 0
                    while True:  # pragma: no cover - requires real Redis
                        cursor, keys = self._backend.scan(cursor=cursor, match=f"{namespaced_prefix}*")
                        if keys:
                            self._backend.delete(*keys)
                            removed += len(keys)
                        if cursor == 0:
                            break
                except Exception as e:  # pragma: no cover
                    logger.warning(f"Redis invalidate scan failed: {e}; fallback to memory")
                    removed += self._in_memory.clear_prefix(namespaced_prefix)
            else:
                removed += self._in_memory.clear_prefix(namespaced_prefix)
        if removed:
            self._metrics.deletes += removed
        return removed

    # ------------------------------------------------------------------
    # Metrics & utility
    # ------------------------------------------------------------------
    def get_metrics(self) -> CacheMetrics:
        """Return a snapshot of current metrics."""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset internal metrics counters."""
        self._metrics.reset()

    def backend_type(self) -> str:
        """Return backend type string ('redis' or 'memory')."""
        return 'redis' if self._backend is not None else 'memory'

    def available_keys(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """List available keys for inspection (memory backend only).

        NOTE: For Redis we avoid full key scans unless explicitly needed.
        """
        if self._backend is not None:
            logger.warning("available_keys() on redis backend is discouraged")
            return {}
        return self._in_memory.keys(self._namespaced(prefix) if prefix else None)

    # ------------------------------------------------------------------
    # Async convenience wrappers (still sync backend interaction)
    # ------------------------------------------------------------------
    async def aget(self, key: str) -> Optional[JsonSerializable]:
        """Async wrapper around get for integration in async flows."""
        return self.get(key)

    async def aset(self, key: str, value: JsonSerializable, ttl: Optional[int] = None) -> None:
        """Async wrapper around set."""
        self.set(key, value, ttl)

    async def adelete(self, key: str) -> bool:
        """Async wrapper around delete."""
        return self.delete(key)

    async def ainvalidate(self, prefix: str) -> int:
        """Async wrapper around invalidate."""
        return self.invalidate(prefix)


__all__ = [
    "CacheManager",
    "CacheMetrics",
]
