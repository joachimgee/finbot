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


# ============================================================================
# POLISH TESTS: Confidence-per-source & Weight Breakdown
# ============================================================================


def test_confidence_per_source_all_sources(fusion):
    """Test confidence_per_source tracks individual source confidence."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.6,  # In [-1, 1] → normalized to 0.8
        technical_signals={'rsi': 70, 'macd': 5, 'sma_cross': 1, 'bb_position': 0.9},
        dl_prediction=0.75,
    )

    # Should have confidence for all 3 sources
    assert 'confidence_per_source' in signal
    assert set(signal['confidence_per_source'].keys()) == {'sentiment', 'technical', 'dl'}

    # Confidence based on distance from neutral (0.5)
    # sentiment 0.6 → normalized (0.6+1)/2=0.8 → confidence = abs(0.8-0.5)*2 = 0.6
    # dl 0.75 → confidence = abs(0.75-0.5)*2 = 0.5
    assert signal['confidence_per_source']['sentiment'] == pytest.approx(0.6, abs=0.01)
    assert signal['confidence_per_source']['technical'] > 0.5
    assert signal['confidence_per_source']['dl'] == pytest.approx(0.5, abs=0.01)


def test_confidence_per_source_partial_sources(fusion):
    """Test confidence_per_source with only some sources."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.0,  # Neutral in [-1, 1]
        technical_signals=None,
        dl_prediction=None,
    )

    # Should only have sentiment
    assert 'confidence_per_source' in signal
    assert list(signal['confidence_per_source'].keys()) == ['sentiment']

    # Neutral sentiment (0.0) → normalized to 0.5 → confidence = abs(0.5-0.5)*2 = 0.0
    assert signal['confidence_per_source']['sentiment'] == pytest.approx(0.0, abs=0.01)


def test_confidence_per_source_extreme_values(fusion):
    """Test confidence_per_source with extreme signal values."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=1.0,  # Extreme bullish
        technical_signals={'rsi': 100},  # Extreme
        dl_prediction=1.0,  # Max
    )

    # All should show high confidence
    assert signal['confidence_per_source']['sentiment'] == pytest.approx(1.0, abs=0.01)
    assert signal['confidence_per_source']['technical'] >= 0.8
    assert signal['confidence_per_source']['dl'] == pytest.approx(1.0, abs=0.01)


def test_weight_contributions_structure(fusion):
    """Test weight_contributions has correct structure."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.6,
        technical_signals={'rsi': 60},
        dl_prediction=0.7,
    )

    # Should have weight_contributions
    assert 'weight_contributions' in signal
    assert set(signal['weight_contributions'].keys()) == {'sentiment', 'technical', 'dl'}

    # Each source should have complete metadata
    for source in ['sentiment', 'technical', 'dl']:
        contrib = signal['weight_contributions'][source]
        assert 'raw_weight' in contrib
        assert 'normalized_score' in contrib
        assert 'contribution' in contrib
        assert 'effective_weight' in contrib

        # Validate types
        assert isinstance(contrib['raw_weight'], float)
        assert isinstance(contrib['normalized_score'], float)
        assert isinstance(contrib['contribution'], float)
        assert isinstance(contrib['effective_weight'], float)


def test_weight_contributions_sum_to_one(fusion):
    """Test effective_weight values sum to 1.0."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.6,
        technical_signals={'rsi': 60},
        dl_prediction=0.7,
    )

    # Effective weights should sum to 1.0
    total_weight = sum(
        contrib['effective_weight']
        for contrib in signal['weight_contributions'].values()
    )
    assert total_weight == pytest.approx(1.0, abs=0.0001)


def test_weight_contributions_match_fusion_weights(fusion):
    """Test effective_weight matches fusion configuration."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.6,
        technical_signals={'rsi': 60},
        dl_prediction=0.7,
    )

    # Should match configured weights
    assert signal['weight_contributions']['sentiment']['raw_weight'] == 0.3
    assert signal['weight_contributions']['technical']['raw_weight'] == 0.4
    assert signal['weight_contributions']['dl']['raw_weight'] == 0.3

    # Effective weights should also match (all sources present)
    assert signal['weight_contributions']['sentiment']['effective_weight'] == pytest.approx(0.3, abs=0.0001)
    assert signal['weight_contributions']['technical']['effective_weight'] == pytest.approx(0.4, abs=0.0001)
    assert signal['weight_contributions']['dl']['effective_weight'] == pytest.approx(0.3, abs=0.0001)


def test_weight_contributions_partial_sources(fusion):
    """Test weight_contributions with only some sources."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.6,
        technical_signals=None,
        dl_prediction=0.7,
    )

    # Should only have sentiment and dl
    assert set(signal['weight_contributions'].keys()) == {'sentiment', 'dl'}

    # Effective weights should be renormalized
    total_effective = sum(
        contrib['effective_weight']
        for contrib in signal['weight_contributions'].values()
    )
    assert total_effective == pytest.approx(1.0, abs=0.0001)

    # Effective weights should be proportional: sentiment=0.3, dl=0.3 → 0.5 each
    assert signal['weight_contributions']['sentiment']['effective_weight'] == pytest.approx(0.5, abs=0.0001)
    assert signal['weight_contributions']['dl']['effective_weight'] == pytest.approx(0.5, abs=0.0001)


def test_weight_contributions_manual_calculation(fusion):
    """Test weight_contributions against manual calculation."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=0.0,  # Normalized to 0.5 (neutral)
        technical_signals={'rsi': 50},  # Normalized ~0.5
        dl_prediction=1.0,  # Max bullish
    )

    # Manual calculation:
    # sentiment_norm = (0.0 + 1) / 2 = 0.5
    # technical_norm = 50/100 = 0.5
    # dl_norm = 1.0
    # final = (0.5*0.3 + 0.5*0.4 + 1.0*0.3) / 1.0 = 0.15 + 0.2 + 0.3 = 0.65

    assert signal['final_score'] == pytest.approx(0.65, abs=0.01)

    # Check individual contributions
    assert signal['weight_contributions']['sentiment']['contribution'] == pytest.approx(0.15, abs=0.01)
    assert signal['weight_contributions']['technical']['contribution'] == pytest.approx(0.20, abs=0.01)
    assert signal['weight_contributions']['dl']['contribution'] == pytest.approx(0.30, abs=0.01)


def test_polishes_no_signals_case(fusion):
    """Test polishes return empty dicts when no signals provided."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment=None,
        technical_signals=None,
        dl_prediction=None,
    )

    # Should have empty polishes
    assert signal['confidence_per_source'] == {}
    assert signal['weight_contributions'] == {}


def test_polishes_error_case(fusion):
    """Test polishes are empty in error cases."""
    signal = fusion.fuse(
        ticker='AAPL',
        sentiment='invalid',  # type: ignore
        technical_signals=None,
        dl_prediction=None,
    )

    # Should have empty polishes
    assert signal['confidence_per_source'] == {}
    assert signal['weight_contributions'] == {}

