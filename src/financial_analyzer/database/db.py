"""Database engine and session management for FinBot.

PostgreSQL-ready SQLAlchemy setup with QueuePool connection pooling.

Environment variables:
    DATABASE_URL: SQLAlchemy URL (e.g., postgresql+psycopg2://user:pass@host:5432/db)
                   Fallback: sqlite:///./finbot.db
    DB_POOL_SIZE: Pool size (default 5)
    DB_MAX_OVERFLOW: Max overflow connections (default 10)

Helpers:
    get_engine(): Create or return singleton Engine
    SessionLocal: sessionmaker factory bound to engine
    init_db(): Create tables for all models
    close_db(): Dispose engine/pool
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from financial_analyzer.database.models import Base
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

_ENGINE: Optional[Engine] = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)  # bind set in init


def _build_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # Fallback to SQLite for local dev
    return os.getenv("SQLITE_URL", "sqlite:///./finbot.db")


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy Engine with QueuePool."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    url = _build_url()
    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    logger.info(f"Creating SQLAlchemy engine for {url} (pool_size={pool_size}, max_overflow={max_overflow})")
    _ENGINE = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        future=True,
    )
    SessionLocal.configure(bind=_ENGINE)
    return _ENGINE


def init_db() -> None:
    """Create all database tables if not present."""
    engine = get_engine()
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized (tables created if missing)")
    except Exception as e:  # pragma: no cover - depends on environment
        logger.error(f"init_db failed: {e}")
        raise


def close_db() -> None:
    """Dispose engine and release connections."""
    global _ENGINE
    if _ENGINE is not None:
        try:
            _ENGINE.dispose()
            logger.info("SQLAlchemy engine disposed")
        finally:
            _ENGINE = None


__all__ = ["get_engine", "SessionLocal", "init_db", "close_db"]
