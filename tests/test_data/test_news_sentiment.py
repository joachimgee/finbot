"""Sentiment de presse point-in-time (inscription sentiment) — anti look-ahead."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.data.pit_loader import RealDataUnavailableError
from financial_analyzer.data.polygon_news_sentiment import (
    NewsSentimentLoader,
    article_text,
    build_sentiment_panel,
)


def test_article_text_combines_title_and_description() -> None:
    assert article_text(
        {"title": "Apple beats", "description": "Revenue up 10% on iPhone"}
    ) == "Apple beats. Revenue up 10% on iPhone"


def test_article_text_dedupes_and_handles_missing() -> None:
    # Description répétant le titre -> pas de duplication.
    assert article_text({"title": "Apple beats", "description": "apple beats"}) == "Apple beats"
    assert article_text({"title": "Only title"}) == "Only title"
    assert article_text({"description": "Only desc"}) == "Only desc"
    assert article_text({}) == ""


def _articles():
    return pd.DataFrame([
        {"ticker": "AAA", "published_utc": pd.Timestamp("2024-01-10"), "sentiment": 1.0},
        {"ticker": "AAA", "published_utc": pd.Timestamp("2024-02-20"), "sentiment": -1.0},
    ])


def test_panel_has_no_lookahead() -> None:
    dates = pd.date_range("2024-01-01", "2024-03-01", freq="D")
    p = build_sentiment_panel(_articles(), dates, window_days=30)["AAA"]
    # Rien de connu avant le premier article publié.
    assert p.loc[p.index < "2024-01-10"].isna().all()
    # Dans les 30 j de l'article +1 -> sentiment +1.
    assert p.loc["2024-01-15"] == pytest.approx(1.0)
    # Après 30 j sans article -> NaN (article de janv. sorti de la fenêtre).
    assert np.isnan(p.loc["2024-02-15"])


def test_panel_tz_aware_dates() -> None:
    dates = pd.date_range("2024-01-01", "2024-03-01", freq="D", tz="UTC")
    p = build_sentiment_panel(_articles(), dates, window_days=30)
    assert str(p.index.tz) == "UTC"
    assert p.loc[p.index < pd.Timestamp("2024-01-10", tz="UTC"), "AAA"].isna().all()


def test_window_averages_multiple_articles() -> None:
    long = pd.DataFrame([
        {"ticker": "Z", "published_utc": pd.Timestamp("2024-01-05"), "sentiment": 1.0},
        {"ticker": "Z", "published_utc": pd.Timestamp("2024-01-06"), "sentiment": -1.0},
    ])
    p = build_sentiment_panel(long, pd.date_range("2024-01-01", "2024-01-20"), window_days=30)
    assert p.loc["2024-01-10", "Z"] == pytest.approx(0.0)  # moyenne(+1, -1)


def test_empty_is_safe() -> None:
    p = build_sentiment_panel(pd.DataFrame(), pd.date_range("2024-01-01", periods=3), 30)
    assert p.empty or p.isna().all().all()


def test_fail_safe_abstains(monkeypatch) -> None:
    monkeypatch.setattr(
        "financial_analyzer.data.polygon_news_sentiment.fetch_news_sentiment",
        lambda *a, **k: pd.DataFrame(columns=["ticker", "published_utc", "sentiment"]),
    )
    with pytest.raises(RealDataUnavailableError):
        NewsSentimentLoader(source="polygon", allow_synthetic_fallback=False).load(
            ["AAA"], "2024-01-01", "2024-06-30")


def test_synthetic_deterministic() -> None:
    a = NewsSentimentLoader(source="synthetic").load(["AAA", "BBB"], "2024-01-01", "2024-06-30")
    b = NewsSentimentLoader(source="synthetic").load(["AAA", "BBB"], "2024-01-01", "2024-06-30")
    pd.testing.assert_frame_equal(a, b)
    assert set(a["sentiment"].unique()).issubset({-1.0, 0.0, 1.0})
