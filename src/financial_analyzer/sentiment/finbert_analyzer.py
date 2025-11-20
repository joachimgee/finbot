"""
FinBERT analyzer adapter module.

This module exposes the exact symbols tests patch against:
- AutoModelForSequenceClassification
- AutoTokenizer
- torch

It does not implement the full pipeline itself; the higher-level
FinancialSentimentAnalyzer imports these and uses them directly. Keeping
these imports at module scope allows tests to monkeypatch them predictably.
"""

from __future__ import annotations

# 1) Third-party
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline  # noqa: F401
import torch  # noqa: F401

__all__ = [
	"AutoModelForSequenceClassification",
	"AutoTokenizer",
	"torch",
]

