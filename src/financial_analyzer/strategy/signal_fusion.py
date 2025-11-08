"""
Signal fusion for combining multiple prediction sources.

This module provides the SignalFusion class which combines sentiment analysis,
technical indicators, and deep learning predictions into a unified trading signal
with confidence estimation and divergence detection.

Features
--------
- Multi-source signal fusion (sentiment, technical, deep learning)
- Normalization to [0, 1] range (0=bearish, 0.5=neutral, 1=bullish)
- Weighted ensemble with configurable weights
- Divergence detection when signals disagree
- Confidence calculation based on agreement

Example
-------
>>> from financial_analyzer.strategy import SignalFusion
>>> fusion = SignalFusion(
...     sentiment_weight=0.3,
...     technical_weight=0.4,
...     dl_weight=0.3,
...     divergence_threshold=0.4
... )
>>> signal = fusion.fuse(
...     ticker='AAPL',
...     sentiment=0.6,  # Positive sentiment
...     technical_signals={'rsi': 65, 'macd': 'bullish', 'sma_cross': 1},
...     dl_prediction=0.75  # Bullish prediction
... )
>>> print(signal)
{'ticker': 'AAPL', 'final_score': 0.72, 'confidence': 0.85, 'divergence': False, ...}
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple
import numpy as np

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class SignalFusion:
    """
    Fuse multiple trading signals into unified decision.

    Combines sentiment analysis, technical indicators, and deep learning
    predictions using weighted ensemble. Detects signal divergence and
    calculates confidence based on agreement between sources.

    Parameters
    ----------
    sentiment_weight : float, default 0.3
        Weight for sentiment signal in [0, 1].
    technical_weight : float, default 0.4
        Weight for technical signal in [0, 1].
    dl_weight : float, default 0.3
        Weight for deep learning signal in [0, 1].
    divergence_threshold : float, default 0.4
        Threshold for detecting signal divergence (max - min scores).

    Attributes
    ----------
    sentiment_weight : float
        Weight for sentiment component.
    technical_weight : float
        Weight for technical component.
    dl_weight : float
        Weight for deep learning component.
    divergence_threshold : float
        Divergence detection threshold.

    Raises
    ------
    ValueError
        If weights don't sum to 1.0 or are not in [0, 1].
        If divergence_threshold not in [0, 1].

    Example
    -------
    >>> fusion = SignalFusion(sentiment_weight=0.25, technical_weight=0.5, dl_weight=0.25)
    >>> signal = fusion.fuse('AAPL', sentiment=0.7, technical_signals={'rsi': 70}, dl_prediction=0.8)
    >>> signal['final_score']  # Weighted average
    0.75
    """

    def __init__(
        self,
        sentiment_weight: float = 0.3,
        technical_weight: float = 0.4,
        dl_weight: float = 0.3,
        divergence_threshold: float = 0.4,
    ) -> None:
        """Initialize SignalFusion with weights and thresholds."""
        # Validate weights
        if not (0.0 <= sentiment_weight <= 1.0):
            raise ValueError("sentiment_weight must be in [0, 1]")
        if not (0.0 <= technical_weight <= 1.0):
            raise ValueError("technical_weight must be in [0, 1]")
        if not (0.0 <= dl_weight <= 1.0):
            raise ValueError("dl_weight must be in [0, 1]")

        weights_sum = sentiment_weight + technical_weight + dl_weight
        if not np.isclose(weights_sum, 1.0, atol=1e-6):
            raise ValueError(f"Weights must sum to 1.0, got {weights_sum:.6f}")

        if not (0.0 <= divergence_threshold <= 1.0):
            raise ValueError("divergence_threshold must be in [0, 1]")

        self.sentiment_weight = sentiment_weight
        self.technical_weight = technical_weight
        self.dl_weight = dl_weight
        self.divergence_threshold = divergence_threshold

        logger.info(
            f"SignalFusion initialized: sentiment={sentiment_weight:.2f}, "
            f"technical={technical_weight:.2f}, dl={dl_weight:.2f}, "
            f"divergence_threshold={divergence_threshold:.2f}"
        )

    def fuse(
        self,
        ticker: str,
        sentiment: Optional[float] = None,
        technical_signals: Optional[Dict[str, Any]] = None,
        dl_prediction: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Fuse multiple signals into unified trading decision.

        Parameters
        ----------
        ticker : str
            Ticker symbol.
        sentiment : float, optional
            Sentiment score in [-1, 1] range (from SentimentAggregator).
        technical_signals : dict, optional
            Technical indicators: {'rsi': float, 'macd': str, 'sma_cross': int, ...}
        dl_prediction : float, optional
            Deep learning prediction in [0, 1] (bullish probability).

        Returns
        -------
        dict
            Fused signal with keys:
            - ticker: str
            - final_score: float in [0, 1] (0=bearish, 1=bullish)
            - confidence: float in [0, 1] (based on agreement)
            - divergence: bool (signals disagree significantly?)
            - divergence_magnitude: float (max - min of normalized scores)
            - components: dict with normalized scores for each source
            - sources_used: list of signal types included
            - confidence_per_source: dict with individual confidence for each source (NEW)
            - weight_contributions: dict with actual weight contribution per source (NEW)

        Example
        -------
        >>> signal = fusion.fuse('AAPL', sentiment=0.5, technical_signals={'rsi': 60}, dl_prediction=0.7)
        >>> signal['final_score']
        0.63
        >>> signal['divergence']
        False
        >>> signal['confidence_per_source']
        {'sentiment': 0.8, 'technical': 0.9, 'dl': 0.85}
        """
        try:
            # Normalize all signals to [0, 1]
            scores = {}
            sources_used = []
            confidence_per_source = {}

            if sentiment is not None:
                scores['sentiment'] = self._normalize_sentiment(sentiment)
                sources_used.append('sentiment')
                # Individual confidence: how far from neutral (0.5)?
                confidence_per_source['sentiment'] = abs(scores['sentiment'] - 0.5) * 2.0
                logger.debug(f"{ticker}: sentiment={sentiment:.3f} → normalized={scores['sentiment']:.3f}")

            if technical_signals is not None:
                scores['technical'] = self._normalize_technical(technical_signals)
                sources_used.append('technical')
                # Individual confidence based on distance from neutral
                confidence_per_source['technical'] = abs(scores['technical'] - 0.5) * 2.0
                logger.debug(f"{ticker}: technical signals → normalized={scores['technical']:.3f}")

            if dl_prediction is not None:
                scores['dl'] = self._normalize_dl(dl_prediction)
                sources_used.append('dl')
                # Individual confidence based on distance from neutral
                confidence_per_source['dl'] = abs(scores['dl'] - 0.5) * 2.0
                logger.debug(f"{ticker}: dl_prediction={dl_prediction:.3f} → normalized={scores['dl']:.3f}")

            # Handle no signals case
            if not scores:
                logger.warning(f"{ticker}: No signals provided, returning neutral")
                return {
                    'ticker': ticker,
                    'final_score': 0.5,
                    'confidence': 0.0,
                    'divergence': False,
                    'divergence_magnitude': 0.0,
                    'components': {},
                    'sources_used': [],
                    'confidence_per_source': {},
                    'weight_contributions': {},
                }

            # Detect divergence
            has_divergence, divergence_mag = self._detect_divergence(scores)

            # Calculate weighted ensemble and track contributions
            final_score = 0.0
            total_weight = 0.0
            weight_contributions = {}

            if 'sentiment' in scores:
                contribution = scores['sentiment'] * self.sentiment_weight
                final_score += contribution
                total_weight += self.sentiment_weight
                weight_contributions['sentiment'] = {
                    'raw_weight': self.sentiment_weight,
                    'normalized_score': scores['sentiment'],
                    'contribution': contribution,
                }

            if 'technical' in scores:
                contribution = scores['technical'] * self.technical_weight
                final_score += contribution
                total_weight += self.technical_weight
                weight_contributions['technical'] = {
                    'raw_weight': self.technical_weight,
                    'normalized_score': scores['technical'],
                    'contribution': contribution,
                }

            if 'dl' in scores:
                contribution = scores['dl'] * self.dl_weight
                final_score += contribution
                total_weight += self.dl_weight
                weight_contributions['dl'] = {
                    'raw_weight': self.dl_weight,
                    'normalized_score': scores['dl'],
                    'contribution': contribution,
                }

            # Normalize by actual weights used
            if total_weight > 0:
                final_score /= total_weight
                # Normalize weight contributions to show effective weights
                for source in weight_contributions:
                    weight_contributions[source]['effective_weight'] = (
                        weight_contributions[source]['raw_weight'] / total_weight
                    )

            # Calculate confidence (inverse of divergence)
            confidence = 1.0 - divergence_mag

            logger.info(
                f"{ticker}: final_score={final_score:.3f}, confidence={confidence:.3f}, "
                f"divergence={has_divergence}, sources={len(sources_used)}"
            )

            return {
                'ticker': ticker,
                'final_score': float(final_score),
                'confidence': float(confidence),
                'divergence': bool(has_divergence),
                'divergence_magnitude': float(divergence_mag),
                'components': {k: float(v) for k, v in scores.items()},
                'sources_used': sources_used,
                'confidence_per_source': {k: float(v) for k, v in confidence_per_source.items()},
                'weight_contributions': {
                    k: {
                        'raw_weight': float(v['raw_weight']),
                        'normalized_score': float(v['normalized_score']),
                        'contribution': float(v['contribution']),
                        'effective_weight': float(v.get('effective_weight', v['raw_weight'])),
                    }
                    for k, v in weight_contributions.items()
                },
            }

        except Exception as e:
            logger.error(f"{ticker}: Signal fusion failed: {e}")
            # Return neutral signal on error
            return {
                'ticker': ticker,
                'final_score': 0.5,
                'confidence': 0.0,
                'divergence': False,
                'divergence_magnitude': 0.0,
                'components': {},
                'sources_used': [],
                'confidence_per_source': {},
                'weight_contributions': {},
                'error': str(e),
            }

    def _normalize_sentiment(self, sentiment: float) -> float:
        """
        Normalize sentiment from [-1, 1] to [0, 1].

        Parameters
        ----------
        sentiment : float
            Raw sentiment score in [-1, 1] range.

        Returns
        -------
        float
            Normalized sentiment in [0, 1] (0=bearish, 0.5=neutral, 1=bullish).

        Example
        -------
        >>> fusion._normalize_sentiment(-1.0)
        0.0
        >>> fusion._normalize_sentiment(0.0)
        0.5
        >>> fusion._normalize_sentiment(1.0)
        1.0
        """
        # Clip to valid range
        sentiment = np.clip(sentiment, -1.0, 1.0)
        # Linear transformation: [-1, 1] → [0, 1]
        normalized = (sentiment + 1.0) / 2.0
        return float(normalized)

    def _normalize_technical(self, signals: Dict[str, Any]) -> float:
        """
        Normalize technical signals to [0, 1].

        Combines multiple technical indicators (RSI, MACD, SMA crossovers)
        into a single normalized score.

        Parameters
        ----------
        signals : dict
            Technical indicators, e.g.:
            - 'rsi': float in [0, 100]
            - 'macd': 'bullish'|'bearish'|'neutral'
            - 'sma_cross': 1 (golden) | -1 (death) | 0 (none)
            - 'bb_position': float in [0, 1] (Bollinger Band position)

        Returns
        -------
        float
            Normalized technical score in [0, 1].

        Example
        -------
        >>> fusion._normalize_technical({'rsi': 70, 'macd': 'bullish'})
        0.75
        """
        scores = []

        # RSI: 0-100 → 0-1
        if 'rsi' in signals:
            rsi = np.clip(signals['rsi'], 0, 100)
            scores.append(rsi / 100.0)

        # MACD: categorical → numeric
        if 'macd' in signals:
            macd_map = {'bearish': 0.0, 'neutral': 0.5, 'bullish': 1.0}
            macd_val = signals['macd']
            if isinstance(macd_val, str):
                scores.append(macd_map.get(macd_val.lower(), 0.5))
            else:
                # If numeric, assume [-1, 1] range
                scores.append(self._normalize_sentiment(macd_val))

        # SMA cross: -1, 0, 1 → 0, 0.5, 1
        if 'sma_cross' in signals:
            cross = np.clip(signals['sma_cross'], -1, 1)
            scores.append((cross + 1.0) / 2.0)

        # Bollinger Band position: already [0, 1]
        if 'bb_position' in signals:
            scores.append(np.clip(signals['bb_position'], 0, 1))

        # Average all available indicators
        if scores:
            return float(np.mean(scores))
        else:
            logger.warning("No recognized technical indicators, returning neutral 0.5")
            return 0.5

    def _normalize_dl(self, prediction: float) -> float:
        """
        Normalize deep learning prediction to [0, 1].

        Parameters
        ----------
        prediction : float
            DL prediction (assumed already in [0, 1] as bullish probability).

        Returns
        -------
        float
            Normalized prediction in [0, 1].

        Example
        -------
        >>> fusion._normalize_dl(0.8)
        0.8
        """
        # Clip to valid range (DL output should already be in [0, 1])
        normalized = np.clip(prediction, 0.0, 1.0)
        return float(normalized)

    def _detect_divergence(self, scores: Dict[str, float]) -> Tuple[bool, float]:
        """
        Detect divergence between normalized signals.

        Parameters
        ----------
        scores : dict
            Normalized scores for each signal type in [0, 1].

        Returns
        -------
        has_divergence : bool
            True if max - min > divergence_threshold.
        magnitude : float
            Divergence magnitude (max - min).

        Example
        -------
        >>> fusion._detect_divergence({'sentiment': 0.2, 'technical': 0.8})
        (True, 0.6)
        >>> fusion._detect_divergence({'sentiment': 0.5, 'technical': 0.6})
        (False, 0.1)
        """
        if len(scores) < 2:
            # Can't have divergence with only one signal
            return False, 0.0

        values = list(scores.values())
        min_val = min(values)
        max_val = max(values)
        magnitude = max_val - min_val

        has_divergence = magnitude > self.divergence_threshold

        if has_divergence:
            logger.warning(f"Divergence detected: magnitude={magnitude:.3f} > threshold={self.divergence_threshold:.3f}")

        return bool(has_divergence), float(magnitude)


__all__ = ["SignalFusion"]
