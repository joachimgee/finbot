# 🎯 PHASE 5.5 MODULE 6 - SIGNAL FUSION PROMPT

## CONTEXT

**Module 6** implémente **signal fusion & ensemble methods** pour combiner tous les signaux.

**Objectif** : Intégrer sentiments + technicals + deep learning + portfolio optimization en une stratégie unifiée.

**Workflow** :
- Sentiment signals (Module 2 : FinBERT)
- Technical signals (Module 1 : RSI, MACD, SMA)
- Deep learning signals (Module 5 : LSTM/Transformer predictions)
- Combine via weighted ensemble
- Generate portfolio allocation (Module 4 : Riskfolio)

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_ML4T_BOOK.md** (29 KB) :
   - Signal combination strategies
   - Ensemble weighting methods
   - Risk-adjusted position sizing

2. **AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md** (20 KB) :
   - Strategy implementation patterns
   - Multi-signal integration

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.5 MODULE 6 : SIGNAL FUSION & ENSEMBLE

Génère 2 fichiers + tests complets :

================================================================================
1. src/financial_analyzer/strategy/signal_fusion.py (350 LOC)
================================================================================

"""
Signal Fusion - Ensemble Signal Combination.

Combines multiple signal sources (sentiment, technical, deep learning)
into unified buy/sell scores and portfolio allocation.

Features:
- Sentiment fusion (from SentimentAggregator)
- Technical signal aggregation (from TechnicalFeatures)
- Deep learning fusion (from LSTMPredictor/TransformerPredictor)
- Weighted ensemble (configurable weights)
- Risk normalization (all signals 0-1 range)
- Divergence detection (signals disagreement warning)

Audit references:
- AUDIT_ML4T_BOOK.md pp.20-30 (multi-signal strategies)
- AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md pp.10-20 (strategy patterns)

Example:
    >>> from financial_analyzer.strategy import SignalFusion
    >>> from financial_analyzer.sentiment import SentimentAggregator
    >>> from financial_analyzer.deep_learning import LSTMPredictor
    >>> from financial_analyzer.features import TechnicalFeatures
    >>> 
    >>> # Initialize signals
    >>> sentiment_agg = SentimentAggregator()
    >>> lstm_pred = LSTMPredictor(lookback_window=60)
    >>> tech_feat = TechnicalFeatures()
    >>> 
    >>> # Initialize fusion
    >>> fusion = SignalFusion(
    ...     sentiment_weight=0.3,
    ...     technical_weight=0.3,
    ...     dl_weight=0.4
    ... )
    >>> 
    >>> # Get fused signal
    >>> signal = fusion.fuse(
    ...     ticker='AAPL',
    ...     sentiment=sentiment_agg.aggregate_sentiment('AAPL'),
    ...     technical_signals={'rsi': 65, 'macd': 0.5},
    ...     dl_prediction=lstm_predictions[0]
    ... )
    >>> print(signal)
    {
        'combined_score': 0.72,
        'bullish_prob': 0.75,
        'confidence': 0.68,
        'component_scores': {...},
        'divergence': False
    }
"""

Implement:

class SignalFusion:
    """
    Ensemble signal combination for trading decisions.
    
    Workflow:
    1. Normalize each signal to [0, 1] (0=bearish, 0.5=neutral, 1=bullish)
    2. Calculate component scores
    3. Combine via weighted average
    4. Detect divergence (signals disagree)
    5. Calculate confidence from agreement
    
    Signals:
    - Sentiment: sentiment_score from SentimentAggregator (-1 to 1) → normalize to [0, 1]
    - Technical: RSI, MACD, SMA signals (multiple indicators)
    - Deep Learning: LSTM prediction (returns) → map to bullish/bearish
    """
    
    def __init__(
        self,
        sentiment_weight: float = 0.3,
        technical_weight: float = 0.3,
        dl_weight: float = 0.4,
        divergence_threshold: float = 0.3
    ):
        """
        Initialize signal fusion.
        
        Args:
            sentiment_weight: Weight for sentiment signals (default 0.3)
            technical_weight: Weight for technical signals (default 0.3)
            dl_weight: Weight for deep learning signals (default 0.4)
            divergence_threshold: Signal disagreement threshold (default 0.3)
        
        Notes:
            - Weights should sum to 1.0 (normalized automatically)
            - divergence_threshold: if max(scores) - min(scores) > threshold → divergence
        """
        # Validate weights sum
        # Normalize weights to 1.0
        # Store threshold
        pass
    
    def fuse(
        self,
        ticker: str,
        sentiment: Optional[Dict] = None,
        technical_signals: Optional[Dict] = None,
        dl_prediction: Optional[float] = None
    ) -> Dict:
        """
        Fuse multiple signals into unified score.
        
        Args:
            ticker: Asset ticker
            sentiment: Dict from SentimentAggregator with keys:
                - 'sentiment_score': float in [-1, +1]
                - 'confidence': float in [0, 1]
            technical_signals: Dict with indicator scores:
                - 'rsi': RSI value (0-100, 70+ overbought, 30- oversold)
                - 'macd': MACD histogram (-1 to +1 normalized)
                - 'sma_200': price relative to SMA200 (-1 to +1)
            dl_prediction: LSTM/Transformer prediction (next period return)
        
        Returns:
            Dict with keys:
            - 'combined_score': float in [0, 1] (fused signal)
            - 'bullish_prob': probability of positive return
            - 'confidence': confidence in signal (0-1)
            - 'component_scores': Dict with individual signal scores
            - 'divergence': bool (signals disagree?)
            - 'divergence_level': float (measure of disagreement)
        
        Example:
            >>> signal = fusion.fuse(
            ...     ticker='AAPL',
            ...     sentiment={'sentiment_score': 0.5, 'confidence': 0.8},
            ...     technical_signals={'rsi': 65, 'macd': 0.3},
            ...     dl_prediction=0.02  # 2% expected return
            ... )
            >>> signal['combined_score']
            0.72
        """
        # Normalize each signal to [0, 1]
        # Calculate component scores
        # Weighted average
        # Detect divergence
        # Calculate confidence
        # Return full dict
        pass
    
    def _normalize_sentiment(self, sentiment: Dict) -> float:
        """
        Normalize sentiment score to [0, 1].
        
        Input: {'sentiment_score': float in [-1, +1], ...}
        Output: float in [0, 1]
        
        Mapping: -1 → 0, 0 → 0.5, +1 → 1
        """
        # sentiment_score from SentimentAggregator
        # Return (sentiment_score + 1) / 2  → [0, 1]
        pass
    
    def _normalize_technical(self, signals: Dict) -> float:
        """
        Normalize technical signals (RSI, MACD, SMA) to [0, 1].
        
        Process:
        1. RSI: 0-100 scale → normalize to [0, 1]
        2. MACD: -1 to +1 → normalize to [0, 1] via (x+1)/2
        3. SMA: -1 to +1 → normalize to [0, 1] via (x+1)/2
        4. Average: (rsi_norm + macd_norm + sma_norm) / 3
        
        Returns:
            float in [0, 1]
        """
        # Extract RSI (30-70 is healthy, extremes dangerous)
        # RSI normalize: rsi / 100
        # Extract MACD, SMA (already -1 to +1)
        # Average all
        # Return
        pass
    
    def _normalize_dl(self, prediction: float) -> float:
        """
        Normalize deep learning prediction to [0, 1].
        
        Input: Expected return (e.g., 0.02 = 2%)
        Output: Bullish probability [0, 1]
        
        Mapping:
        - Negative return → < 0.5
        - Zero return → 0.5
        - Positive return → > 0.5
        
        Use sigmoid or linear mapping based on threshold.
        """
        # If prediction > 0 (bullish), map to [0.5, 1]
        # If prediction < 0 (bearish), map to [0, 0.5]
        # Consider magnitude of prediction
        pass
    
    def _detect_divergence(self, scores: Dict) -> Tuple[bool, float]:
        """
        Detect divergence (signals disagree).
        
        Args:
            scores: Dict with 'sentiment', 'technical', 'dl' scores in [0, 1]
        
        Returns:
            Tuple[is_divergent, divergence_level]
            - is_divergent: bool (max - min > threshold)
            - divergence_level: float in [0, 1] (how much disagreement)
        """
        # Get all scores as list
        # max_score - min_score = divergence
        # is_divergent = divergence > threshold
        # Return
        pass


__all__ = ['SignalFusion']

================================================================================
2. src/financial_analyzer/strategy/ensemble_allocator.py (250 LOC)
================================================================================

"""
Ensemble Allocator - Convert Signals to Portfolio Positions.

Translates fused signals (bullish probability) into portfolio weights
using risk-aware position sizing.

Features:
- Signal-to-weight conversion
- Risk normalization (VaR-based sizing)
- Dynamic position sizing
- Concentration limits
- Multi-asset coordination

Example:
    >>> from financial_analyzer.strategy import EnsembleAllocator
    >>> from financial_analyzer.portfolio_optimization import RiskfolioOptimizer
    >>> 
    >>> allocator = EnsembleAllocator(
    ...     max_position_size=0.15,
    ...     min_position_size=0.01
    ... )
    >>> 
    >>> # Get signals for universe
    >>> signals = {
    ...     'AAPL': {'combined_score': 0.8, 'confidence': 0.85},
    ...     'MSFT': {'combined_score': 0.6, 'confidence': 0.70},
    ...     'GOOGL': {'combined_score': 0.3, 'confidence': 0.60},
    ... }
    >>> 
    >>> # Allocate
    >>> allocation = allocator.allocate(
    ...     signals=signals,
    ...     total_capital=1_000_000,
    ...     risk_model='inverse_variance'  # or 'equal_weight', 'signal_based'
    ... )
    >>> print(allocation)
    {
        'AAPL': 0.45,    # 45% allocation
        'MSFT': 0.30,    # 30% allocation
        'GOOGL': 0.15,   # 15% allocation
        'CASH': 0.10     # 10% cash buffer
    }
"""

Implement:

class EnsembleAllocator:
    """
    Convert multi-asset signals to portfolio allocation.
    
    Process:
    1. Get signal scores per asset (0-1 range)
    2. Apply confidence weighting
    3. Convert to gross notional (long only)
    4. Apply position limits (min/max)
    5. Normalize to sum = 1.0
    6. Return final weights
    
    Models:
    - 'equal_weight': All bullish assets get equal weight
    - 'signal_based': Weight by signal strength
    - 'inverse_variance': Weight by 1/volatility
    """
    
    def __init__(
        self,
        max_position_size: float = 0.20,
        min_position_size: float = 0.00,
        cash_reserve: float = 0.05,
        confidence_threshold: float = 0.50
    ):
        """
        Initialize allocator.
        
        Args:
            max_position_size: Max weight per asset (default 0.20 = 20%)
            min_position_size: Min weight per asset (default 0.00 = 0%)
            cash_reserve: Reserve cash % (default 0.05 = 5%)
            confidence_threshold: Min confidence to include (default 0.50)
        """
        pass
    
    def allocate(
        self,
        signals: Dict[str, Dict],
        total_capital: float = 1_000_000,
        risk_model: str = 'signal_based'
    ) -> Dict[str, float]:
        """
        Allocate capital based on signals.
        
        Args:
            signals: Dict[ticker, signal_dict] where signal_dict has:
                - 'combined_score': float [0, 1]
                - 'confidence': float [0, 1]
            total_capital: Total capital to deploy
            risk_model: 'equal_weight', 'signal_based', 'inverse_variance'
        
        Returns:
            Dict[ticker, weight] where weights sum to 1.0
        
        Example:
            >>> signals = {
            ...     'AAPL': {'combined_score': 0.8, 'confidence': 0.9},
            ...     'MSFT': {'combined_score': 0.6, 'confidence': 0.8},
            ... }
            >>> weights = allocator.allocate(signals, total_capital=1M)
            >>> weights
            {'AAPL': 0.45, 'MSFT': 0.30, 'CASH': 0.25}
        """
        # Filter by confidence_threshold
        # Apply risk_model
        # Apply position limits (max/min)
        # Add cash reserve
        # Normalize to 1.0
        # Return
        pass
    
    def _apply_signal_weights(self, signals: Dict) -> Dict:
        """
        Convert signal scores to raw weights.
        
        Process:
        1. Bullish score = combined_score > 0.5
        2. Confidence-weight the score
        3. Normalize across assets
        """
        # For each asset, weight = combined_score * confidence
        # Sum weights
        # Normalize: weight / sum
        # Return
        pass
    
    def _apply_position_limits(self, weights: Dict) -> Dict:
        """
        Apply min/max position size constraints.
        
        Process:
        1. Clip each weight to [min_position_size, max_position_size]
        2. Re-normalize to sum = 1.0
        """
        # Clip weights
        # Normalize
        # Return
        pass


__all__ = ['EnsembleAllocator']

================================================================================
3. TESTS (15 TOTAL)
================================================================================

tests/test_strategy/test_signal_fusion.py (8 tests)
- test_init_default()
- test_fuse_all_bullish()
- test_fuse_all_bearish()
- test_fuse_mixed_signals()
- test_normalize_sentiment()
- test_normalize_technical()
- test_normalize_dl()
- test_divergence_detection()

tests/test_strategy/test_ensemble_allocator.py (7 tests)
- test_init_default()
- test_allocate_equal_weight()
- test_allocate_signal_based()
- test_allocate_position_limits()
- test_allocate_cash_reserve()
- test_allocate_normalizes_to_one()
- test_allocate_empty_signals()

================================================================================
REQUIREMENTS
================================================================================

✅ Type hints 100%
✅ Google/NumPy docstrings 100%
✅ 15 tests passing 100%
✅ Logging (info/warning/error)
✅ Error handling with try/except
✅ Zero Pylance errors
✅ Production-ready

CRITICAL:
- Normalize ALL signals to [0, 1] (0=bearish, 0.5=neutral, 1=bullish)
- Weighted ensemble: combine by weights (sum=1.0)
- Divergence detection: max(scores) - min(scores) > threshold
- Position sizing: clip to [min_pos, max_pos], re-normalize
- All tests mock dependencies (Sentiment, LSTM, Technical)

Refs: AUDIT_ML4T_BOOK.md, AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `signal_fusion.py` (350 LOC) - Multi-signal ensemble
2. ✅ `ensemble_allocator.py` (250 LOC) - Position sizing
3. ✅ 2 test files (15 tests total: 8 + 7)

**Key features:**
- Sentiment + Technical + Deep Learning combination
- Normalization to [0, 1] scale
- Divergence detection
- Confidence weighting
- Position limits + risk control
- Multiple allocation strategies

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ signal_fusion.py (350 LOC)
✅ ensemble_allocator.py (250 LOC)
✅ test_signal_fusion.py (8 tests)
✅ test_ensemble_allocator.py (7 tests)

Total: 600 LOC + 15 tests
All passing: 15/15 ✅
```

---

## 🎯 MODULE 6 COMPLEXITY

**Module 6 est la COUCHE D'INTÉGRATION** :
- Combine tous les modules précédents
- Signal normalization
- Ensemble methods
- Position sizing

**Attendu** : 1.5-2h par Copilot

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

This is the **integration layer** - combining everything into one unified strategy! 🎯
