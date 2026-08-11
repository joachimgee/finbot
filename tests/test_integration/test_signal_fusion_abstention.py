"""Tests P0 : les sources stub du SignalFusionEngine s'abstiennent réellement.

Le daemon canonique (``scripts/professional_analysis_daemon.py``) produit ses
signaux via ``SignalFusionEngine``. Historiquement, quatre sources sans vrai
modèle (fundamental, ml_lstm, ml_factor, rl) injectaient un score constant 0.5
pondéré — soit ~55 % du poids nominal de bruit neutre tirant le score composite
vers l'indécision. Ces tests verrouillent le correctif : ces sources retournent
None (abstention) et la fusion renormalise sur les seules sources réelles.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.integration.signal_fusion_engine import (
    SignalComponent,
    SignalFusionEngine,
)


@pytest.fixture()
def price_data() -> pd.DataFrame:
    """OHLCV synthétique suffisant pour tout calcul technique/LSTM."""
    n = 120
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(100 + np.cumsum(np.random.default_rng(0).normal(0, 1, n)), index=idx)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=idx,
    )


# --- Abstention directe des sources stub ------------------------------------

def test_stub_sources_abstain_regardless_of_input(price_data: pd.DataFrame) -> None:
    """Les quatre sources sans modèle validé retournent None, quoi qu'on passe."""
    engine = SignalFusionEngine()

    assert engine._get_fundamental_signal("AAPL", {"pe": 10, "roe": 0.3}) is None
    assert engine._get_lstm_signal("AAPL", price_data) is None
    assert engine._get_ml_factor_signal("AAPL") is None
    assert engine._get_rl_signal("AAPL", price_data) is None


def test_abstaining_sources_declared() -> None:
    """Le contrat d'abstention est explicite et couvre exactement les 4 stubs."""
    assert set(SignalFusionEngine.ABSTAINING_SOURCES) == {
        "fundamental",
        "ml_lstm",
        "ml_factor",
        "rl",
    }


def test_abstention_logged_once(price_data: pd.DataFrame) -> None:
    """Une source abstentionniste n'est journalisée qu'une fois (pas de spam)."""
    engine = SignalFusionEngine()
    assert "rl" not in engine._abstained_logged
    engine._get_rl_signal("AAPL", price_data)
    assert "rl" in engine._abstained_logged
    # Deuxième appel : toujours None, sans ré-ajout / erreur.
    assert engine._get_rl_signal("MSFT", price_data) is None


# --- La fusion renormalise sur les sources réelles --------------------------

def _force_real_sources(
    engine: SignalFusionEngine, tech_score: float, sent_score: float
) -> None:
    """Injecte deux vraies sources déterministes ; laisse les stubs s'abstenir."""
    engine._get_technical_signal = lambda symbol, pdata: SignalComponent(  # type: ignore[assignment]
        source="technical", score=tech_score, confidence=0.75,
        weight=engine.source_weights["technical"],
    )
    engine._get_sentiment_signal = lambda symbol, **kw: SignalComponent(  # type: ignore[assignment]
        source="sentiment", score=sent_score, confidence=0.60,
        weight=engine.source_weights["sentiment"],
    )


def test_composite_excludes_stub_sources(price_data: pd.DataFrame) -> None:
    """Le signal fusionné ne contient QUE des sources réelles."""
    engine = SignalFusionEngine(min_sources=2)
    _force_real_sources(engine, tech_score=0.9, sent_score=0.8)

    fused = engine.generate_signal("AAPL", price_data, use_cache=False)
    assert fused is not None
    sources = {c.source for c in fused.components}
    assert sources == {"technical", "sentiment"}
    assert sources.isdisjoint(SignalFusionEngine.ABSTAINING_SOURCES)


def test_composite_not_diluted_to_neutral(price_data: pd.DataFrame) -> None:
    """Un signal fortement haussier n'est plus tiré vers 0.5 par les constantes.

    Avec l'ancien comportement, quatre constantes 0.5 (fundamental/ml_lstm/
    ml_factor/rl) diluaient un technical=0.9 vers ~0.6. Après abstention, le
    composite est la moyenne pondérée par confiance des seules sources réelles.
    """
    engine = SignalFusionEngine(min_sources=2)
    _force_real_sources(engine, tech_score=0.9, sent_score=0.8)

    fused = engine.generate_signal("AAPL", price_data, use_cache=False)
    assert fused is not None

    # Calcul de référence : renormalisation sur technical + sentiment seulement.
    w_t = engine.source_weights["technical"] * 0.75
    w_s = engine.source_weights["sentiment"] * 0.60
    expected = (0.9 * w_t + 0.8 * w_s) / (w_t + w_s)
    assert fused.composite_score == pytest.approx(expected, rel=1e-9)
    # Strictement au-dessus du neutre pré-correctif (aucune constante 0.5).
    assert fused.composite_score > 0.75


def test_single_real_source_below_min_sources_abstains(price_data: pd.DataFrame) -> None:
    """Sans fallback, une seule source réelle (< min_sources) ne trade pas."""
    engine = SignalFusionEngine(min_sources=2, fallback_mode=False)
    # Seul technical est réel ; sentiment renvoie None ; les 4 stubs s'abstiennent.
    engine._get_technical_signal = lambda symbol, pdata: SignalComponent(  # type: ignore[assignment]
        source="technical", score=0.9, confidence=0.75,
        weight=engine.source_weights["technical"],
    )
    engine._get_sentiment_signal = lambda symbol, **kw: None  # type: ignore[assignment]

    fused = engine.generate_signal("AAPL", price_data, use_cache=False)
    assert fused is None
