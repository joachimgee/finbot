"""SQLAlchemy ORM models for FinBot persistent entities.

Models:
    Trade: Executed trade/order record.
    Allocation: Portfolio allocation snapshot.
    PerformanceMetric: Daily performance & risk metrics snapshot.
    CacheStat: Cache system statistics (hit/miss) persistence.

Conventions:
    - UTC timestamps.
    - snake_case columns; explicit indexes for common queries.
    - Postgres friendly types (JSONB if available else TEXT fallback).

Example:
    >>> from financial_analyzer.database.db import init_db, SessionLocal
    >>> init_db()
    >>> with SessionLocal() as s:
    ...     trade = Trade(ticker="AAPL", action="BUY", quantity=10, price=180.0, notional=1800.0)
    ...     s.add(trade); s.commit()

Note: Alembic migrations recommended for schema evolution beyond initial deploy.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    JSON,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Type JSON portable, résolu au moment de la compilation du DDL selon le
# dialecte réellement utilisé : JSONB sous PostgreSQL, JSON générique ailleurs
# (SQLite). Contrairement à une détection basée sur DATABASE_URL à l'import, la
# même définition de colonne rend correctement quel que soit le moteur ciblé —
# donc les tests SQLite ne cassent pas quand DATABASE_URL pointe vers Postgres.
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402

JSONType = JSON().with_variant(JSONB(), "postgresql")

# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):  # pragma: no cover - SQLA internals
    pass


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class TimestampMixin:
    """Mixin adding created_at/updated_at UTC timestamps."""

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc), onupdate=lambda: dt.datetime.now(dt.timezone.utc)
    )


class IDMixin:
    """Mixin for primary key id."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


# ---------------------------------------------------------------------------
# Trade model
# ---------------------------------------------------------------------------


class Trade(TimestampMixin, IDMixin, Base):
    """Executed order/trade record.

    Attributes:
        ticker: Symbol traded.
        action: BUY/SELL.
        quantity: Number of units.
        price: Executed price.
        notional: Monetary value (quantity * price), may include sign.
        meta: Additional metadata (broker, strategy id, etc.).
    """

    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_ticker", "ticker"),
        Index("ix_trades_created_at", "created_at"),
    )

    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    notional: Mapped[float] = mapped_column(Float, nullable=False)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)


# ---------------------------------------------------------------------------
# Allocation model
# ---------------------------------------------------------------------------


class Allocation(TimestampMixin, IDMixin, Base):
    """Portfolio allocation snapshot."""

    __tablename__ = "allocations"
    __table_args__ = (
        Index("ix_allocations_created_at", "created_at"),
        UniqueConstraint("as_of_date", name="uq_allocations_as_of_date"),
    )

    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    weights: Mapped[Dict[str, float]] = mapped_column(JSONType, nullable=False)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)


# ---------------------------------------------------------------------------
# PerformanceMetric model
# ---------------------------------------------------------------------------


class PerformanceMetric(TimestampMixin, IDMixin, Base):
    """Daily performance & risk metrics snapshot."""

    __tablename__ = "performance_metrics"
    __table_args__ = (
        Index("ix_perf_metrics_day", "day"),
        UniqueConstraint("day", name="uq_perf_metrics_day"),
    )

    day: Mapped[dt.date] = mapped_column(Date, nullable=False)
    returns: Mapped[float] = mapped_column(Float, nullable=False)
    volatility: Mapped[float] = mapped_column(Float, nullable=True)
    drawdown: Mapped[float] = mapped_column(Float, nullable=True)
    sharpe: Mapped[float] = mapped_column(Float, nullable=True)
    sortino: Mapped[float] = mapped_column(Float, nullable=True)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)


# ---------------------------------------------------------------------------
# CacheStat model
# ---------------------------------------------------------------------------


class CacheStat(TimestampMixin, IDMixin, Base):
    """Cache system statistics snapshot (persisted)."""

    __tablename__ = "cache_stats"
    __table_args__ = (
        Index("ix_cache_stats_created_at", "created_at"),
    )

    backend: Mapped[str] = mapped_column(String(16), nullable=False)
    hits: Mapped[int] = mapped_column(Integer, nullable=False)
    misses: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    deletes: Mapped[int] = mapped_column(Integer, nullable=False)
    last_reset: Mapped[float] = mapped_column(Float, nullable=False)


__all__ = [
    "Base",
    "Trade",
    "Allocation",
    "PerformanceMetric",
    "CacheStat",
]
