"""Tests for SignalFusion."""

import pytest
import numpy as np

from financial_analyzer.strategy import SignalFusion


@pytest.fixture
def fusion():
    """Create SignalFusion instance with default weights."""
    return SignalFusion(
        sentiment_weight=0.3,
        technical_weight=0.4,
        dl_weight=0.3,
        divergence_threshold=0.4,
    )


def test_init_defaults():
    """Test initialization with default parameters."""
    fusion = SignalFusion()
    assert fusion.sentiment_weight == 0.3
    assert fusion.technical_weight == 0.4
    assert fusion.dl_weight == 0.3
    assert fusion.divergence_threshold == 0.4


def test_init_custom_weights():
    """Test initialization with custom weights."""
    fusion = SignalFusion(
        sentiment_weight=0.25,
        technical_weight=0.5,
        dl_weight=0.25,
        divergence_threshold=0.3,
    )
    assert fusion.sentiment_weight == 0.25
    assert fusion.technical_weight == 0.5
    assert fusion.dl_weight == 0.25
    assert fusion.divergence_threshold == 0.3


def test_init_invalid_weights_sum():
    """Test that weights must sum to 1.0."""
    with pytest.raises(ValueError, match="must sum to 1.0"):
        SignalFusion(sentiment_weight=0.5, technical_weight=0.5, dl_weight=0.5)


def test_init_invalid_weight_range():
    """Test that weights must be in [0, 1]."""
    with pytest.raises(ValueError, match="must be in"):
        SignalFusion(sentiment_weight=-0.1, technical_weight=0.6, dl_weight=0.5)


def test_init_invalid_divergence_threshold():
    """Test that divergence_threshold must be in [0, 1]."""
    with pytest.raises(ValueError, match="divergence_threshold"):
        SignalFusion(divergence_threshold=1.5)


def test_fuse_all_bullish(fusion):
    """Test fusion with all bullish signals."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.8,  # 0.8 → normalized 0.9
        technical_signals={'rsi': 80, 'macd': 'bullish'},  # 0.8 + 1.0 → avg 0.9
        dl_prediction=0.9,
    )

    assert signal['ticker'] == 'AAPL'
    assert signal['final_score'] > 0.8  # All signals bullish
    assert signal['confidence'] > 0.9  # High agreement
    assert signal['divergence'] is False
    assert len(signal['sources_used']) == 3
    assert 'sentiment' in signal['components']
    assert 'technical' in signal['components']
    assert 'dl' in signal['components']


def test_fuse_all_bearish(fusion):
    """Test fusion with all bearish signals."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=-0.8,  # -0.8 → normalized 0.1
        technical_signals={'rsi': 20, 'macd': 'bearish'},  # 0.2 + 0.0 → avg 0.1
        dl_prediction=0.1,
    )

    assert signal['ticker'] == 'AAPL'
    assert signal['final_score'] < 0.2  # All signals bearish
    assert signal['confidence'] > 0.9  # High agreement
    assert signal['divergence'] is False


def test_fuse_mixed_signals_divergence(fusion):
    """Test fusion with mixed signals triggering divergence."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.8,  # 0.8 → normalized 0.9 (bullish)
        technical_signals={'rsi': 30, 'macd': 'bearish'},  # 0.3 + 0.0 → avg 0.15 (bearish)
        dl_prediction=0.2,  # bearish
    )

    assert signal['ticker'] == 'AAPL'
    assert signal['divergence'] is True  # Signals disagree
    assert signal['divergence_magnitude'] > 0.4
    assert signal['confidence'] < 0.6  # Low confidence due to divergence
    assert 0.2 < signal['final_score'] < 0.6  # Somewhere in the middle


def test_fuse_partial_signals(fusion):
    """Test fusion with only some signals provided."""
    # Only sentiment and technical
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.5,
        technical_signals={'rsi': 60},
        dl_prediction=None,
    )

    assert signal['ticker'] == 'AAPL'
    assert len(signal['sources_used']) == 2
    assert 'sentiment' in signal['sources_used']
    assert 'technical' in signal['sources_used']
    assert 'dl' not in signal['sources_used']


def test_fuse_no_signals(fusion):
    """Test fusion with no signals returns neutral."""
    signal = fusion.fuse(ticker='AAPL')

    assert signal['ticker'] == 'AAPL'
    assert signal['final_score'] == 0.5  # Neutral
    assert signal['confidence'] == 0.0
    assert signal['divergence'] is False
    assert len(signal['sources_used']) == 0


def test_normalize_sentiment(fusion):
    """Test sentiment normalization from [-1, 1] to [0, 1]."""
    assert fusion._normalize_sentiment(-1.0) == pytest.approx(0.0)
    assert fusion._normalize_sentiment(0.0) == pytest.approx(0.5)
    assert fusion._normalize_sentiment(1.0) == pytest.approx(1.0)
    assert fusion._normalize_sentiment(0.5) == pytest.approx(0.75)
    assert fusion._normalize_sentiment(-0.5) == pytest.approx(0.25)


def test_normalize_technical_rsi(fusion):
    """Test technical normalization with RSI."""
    score = fusion._normalize_technical({'rsi': 50})
    assert score == pytest.approx(0.5)

    score = fusion._normalize_technical({'rsi': 100})
    assert score == pytest.approx(1.0)

    score = fusion._normalize_technical({'rsi': 0})
    assert score == pytest.approx(0.0)


def test_normalize_technical_macd(fusion):
    """Test technical normalization with MACD."""
    score = fusion._normalize_technical({'macd': 'bullish'})
    assert score == pytest.approx(1.0)

    score = fusion._normalize_technical({'macd': 'bearish'})
    assert score == pytest.approx(0.0)

    score = fusion._normalize_technical({'macd': 'neutral'})
    assert score == pytest.approx(0.5)


def test_normalize_technical_multiple_indicators(fusion):
    """Test technical normalization with multiple indicators."""
    score = fusion._normalize_technical({
        'rsi': 60,
        'macd': 'bullish',
        'sma_cross': 1,
    })
    # rsi: 0.6, macd: 1.0, sma_cross: 1.0 → avg = 0.867
    assert 0.85 < score < 0.90


def test_normalize_technical_empty(fusion):
    """Test technical normalization with no recognized indicators."""
    score = fusion._normalize_technical({})
    assert score == pytest.approx(0.5)  # Neutral fallback


def test_normalize_dl(fusion):
    """Test DL prediction normalization (already in [0, 1])."""
    assert fusion._normalize_dl(0.0) == pytest.approx(0.0)
    assert fusion._normalize_dl(0.5) == pytest.approx(0.5)
    assert fusion._normalize_dl(1.0) == pytest.approx(1.0)
    assert fusion._normalize_dl(1.5) == pytest.approx(1.0)  # Clipped


def test_detect_divergence_high(fusion):
    """Test divergence detection with high divergence."""
    scores = {'sentiment': 0.2, 'technical': 0.8, 'dl': 0.3}
    has_div, magnitude = fusion._detect_divergence(scores)

    assert has_div is True
    assert magnitude == pytest.approx(0.6)  # 0.8 - 0.2


def test_detect_divergence_low(fusion):
    """Test divergence detection with low divergence."""
    scores = {'sentiment': 0.5, 'technical': 0.6, 'dl': 0.55}
    has_div, magnitude = fusion._detect_divergence(scores)

    assert has_div is False
    assert magnitude == pytest.approx(0.1)  # 0.6 - 0.5


def test_detect_divergence_single_signal(fusion):
    """Test divergence detection with only one signal."""
    scores = {'sentiment': 0.7}
    has_div, magnitude = fusion._detect_divergence(scores)

    assert has_div is False
    assert magnitude == pytest.approx(0.0)


def test_fuse_with_error_handling(fusion):
    """Test fusion handles errors gracefully."""
    # Pass invalid technical signals that might cause errors
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment='invalid',  # type: ignore
        technical_signals=None,
        dl_prediction=None,
    )

    # Should return neutral signal with error
    assert 'error' in signal
    assert signal['final_score'] == 0.5
    assert signal['confidence'] == 0.0
