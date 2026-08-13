"""Book cible du multi-stratégie (long/short combiné)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.trading.multi_strategy_book import combined_book


def _prices(n=340, k=20, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    mkt = rng.normal(0.0003, 0.01, n)
    cols = {f"S{j}": 100 * np.exp(np.cumsum(
        (0.5 + rng.random()) * mkt + rng.normal(rng.normal(0, 0.0005), 0.008, n)))
        for j in range(k)}
    return pd.DataFrame(cols, index=idx)


def test_combined_book_is_gross_normalized_long_short() -> None:
    px = _prices(seed=1)
    book = combined_book(px)
    assert book, "un book non vide est attendu sur un panel suffisant"
    gross = sum(abs(v) for v in book.values())
    assert gross == pytest.approx(1.0, abs=1e-6)          # brut normalisé
    assert any(v < 0 for v in book.values())              # long/short


def test_family_weights_shift_the_book() -> None:
    """Mettre tout le poids sur momentum ≠ tout sur pca_resid."""
    px = _prices(seed=2)
    only_mom = combined_book(px, family_weights={"momentum": 1.0})
    only_pca = combined_book(px, family_weights={"pca_resid": 1.0})
    assert only_mom and only_pca
    assert only_mom != only_pca


def test_insufficient_history_returns_empty() -> None:
    px = _prices(n=60)  # < 252 -> ni momentum ni pca ni paires
    assert combined_book(px) == {}


def test_symbols_are_subset_of_universe() -> None:
    px = _prices(seed=3)
    book = combined_book(px)
    assert set(book).issubset(set(px.columns))
