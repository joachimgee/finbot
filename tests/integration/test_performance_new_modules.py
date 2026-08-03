"""Smoke tests for newly added performance optimization modules.

Validates import, basic functionality without external services:
    - CacheManager in-memory fallback operations
    - AsyncFetcher price fetch (monkeypatch to avoid real network)
    - Database init and simple ORM operations using SQLite fallback
"""
from __future__ import annotations

import asyncio
import os
import pandas as pd
import pytest

from financial_analyzer.caching.cache_manager import CacheManager
from financial_analyzer.async_pipeline.async_fetcher import AsyncFetcher
from financial_analyzer.database.db import init_db, SessionLocal, close_db
from financial_analyzer.database.models import Trade, Allocation, PerformanceMetric, CacheStat


def test_cache_manager_in_memory_basic(monkeypatch):
    # Ce test cible le backend mémoire : neutraliser REDIS_URL, sinon
    # CacheManager(url=None) le récupère via l'env (auto-détection prod) et
    # bascule sur redis quand un service Redis tourne (comme en CI).
    monkeypatch.delenv("REDIS_URL", raising=False)
    cm = CacheManager(url=None)
    cm.set("foo", {"a": 1}, ttl=1)
    assert cm.get("foo") == {"a": 1}
    assert cm.backend_type() == "memory"
    cm.delete("foo")
    assert cm.get("foo") is None
    metrics = cm.get_metrics().to_dict()
    assert metrics["hits"] >= 1 and metrics["misses"] >= 1


def test_async_fetcher_prices_mock(monkeypatch):
    async def fake_request_json(self, url, params=None):
        return {"chart": {"result": [{"timestamp": [1, 2], "indicators": {"quote": [{"close": [10.0, 11.0]}]}}]}}
    monkeypatch.setattr(AsyncFetcher, "_request_json", fake_request_json)
    async def run_case():
        af = AsyncFetcher(concurrency=2)
        prices = await af.fetch_prices(["AAA"], start=None, end=None)
        assert "AAA" in prices and not prices["AAA"].empty
        await af.aclose()
    import asyncio
    asyncio.run(run_case())


def test_database_models_sqlite(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    init_db()
    with SessionLocal() as s:
        trade = Trade(ticker="AAA", action="BUY", quantity=5, price=100.0, notional=500.0)
        s.add(trade)
        alloc = Allocation(as_of_date=pd.Timestamp("2025-11-07").date(), weights={"AAA": 0.5}, meta=None)
        s.add(alloc)
        perf = PerformanceMetric(day=pd.Timestamp("2025-11-07").date(), returns=0.01, volatility=0.02, drawdown=0.0, sharpe=1.5, sortino=2.0)
        s.add(perf)
        stat = CacheStat(backend="memory", hits=1, misses=0, sets=1, deletes=0, last_reset=123456.0)
        s.add(stat)
        s.commit()
        assert trade.id is not None and alloc.id is not None and perf.id is not None and stat.id is not None
    close_db()
