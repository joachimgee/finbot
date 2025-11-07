"""Centralized logging utilities for FinBot.

Provides a helper to obtain module-specific loggers with consistent formatting.
"""
from __future__ import annotations

import logging
from typing import Optional

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger.

    Ensures a single configuration point for log formatting. All modules should
    obtain their logger via this function to maintain consistency.

    Args:
        name: Optional module name. If None root logger is returned.

    Returns:
        Configured ``logging.Logger`` instance.
    """
    global _configured
    if not _configured:
        logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, datefmt=_DATE_FORMAT)
        _configured = True
    return logging.getLogger(name if name else __name__)
