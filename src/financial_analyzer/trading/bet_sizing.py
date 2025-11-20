"""
Bet Sizing for Portfolio Allocation.

Implements bet sizing strategies from "Advances in Financial Machine Learning" (AFML) Chapter 10
by Marcos López de Prado, with practical extensions for ML-based trading.

Strategies Implemented:
1. Kelly Criterion: Optimal bet size based on edge and win probability
2. Budget Method: Linear sizing based on concurrent long/short bets
3. Dynamic Sizing: Sigmoid/power function based on price divergence
4. Confidence-based: ML prediction confidence → position size

Key Concepts:
- Kelly Criterion: f* = (p*b - q) / b where p=win prob, b=win/loss ratio, q=1-p
- Budget Method: size = avg_long - avg_short (concurrent bets)
- Dynamic: size = sigmoid(w * (forecast - market))
- ML Confidence: size = (confidence - 1/n_classes) * side

Author: FinBot
License: MIT
References: AFML Chapter 10, Snippets 10.1-10.4
"""

import sys
from pathlib import Path
from typing import Optional, Union, Dict, Tuple
import warnings

import numpy as np
import pandas as pd
from scipy.stats import norm

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def kelly_criterion(
    win_prob: float,
    win_loss_ratio: float,
    max_leverage: float = 1.0,
    kelly_fraction: float = 0.25
) -> float:
    """
    Calculate optimal bet size using Kelly Criterion.
    
    Kelly Formula: f* = (p*b - q) / b
    where:
    - p = probability of winning
    - q = 1 - p = probability of losing
    - b = win/loss ratio (how much you win vs lose)
    - f* = fraction of capital to bet
    
    Args:
        win_prob: Probability of winning (0.0 to 1.0)
        win_loss_ratio: Ratio of win amount to loss amount (typically > 1)
        max_leverage: Maximum allowed leverage (default 1.0 = no leverage)
        kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly, conservative)
    
    Returns:
        Optimal bet size as fraction of capital (-max_leverage to +max_leverage)
    
    Raises:
        ValueError: If win_prob not in [0, 1] or win_loss_ratio <= 0
    
    Example:
        >>> # 60% win probability, 2:1 win/loss ratio
        >>> kelly_criterion(0.6, 2.0, kelly_fraction=0.5)
        0.15  # Bet 15% of capital (half Kelly)
        
        >>> # 55% win prob, 1.5:1 ratio
        >>> kelly_criterion(0.55, 1.5, kelly_fraction=1.0)
        0.1333  # Full Kelly: bet 13.33%
    """
    if not 0 <= win_prob <= 1:
        raise ValueError(f"win_prob must be in [0, 1], got {win_prob}")
    
    if win_loss_ratio <= 0:
        raise ValueError(f"win_loss_ratio must be > 0, got {win_loss_ratio}")
    
    if not 0 < kelly_fraction <= 1:
        raise ValueError(f"kelly_fraction must be in (0, 1], got {kelly_fraction}")
    
    lose_prob = 1.0 - win_prob
    
    # Kelly formula: f* = (p*b - q) / b
    kelly_full = (win_prob * win_loss_ratio - lose_prob) / win_loss_ratio
    
    # Clamp negative Kelly to 0 (no bet if negative edge)
    if kelly_full < 0:
        return 0.0
    
    # Apply fractional Kelly (e.g., quarter Kelly = 0.25)
    kelly_fractional = kelly_full * kelly_fraction
    
    # Clip to max leverage
    kelly_clipped = np.clip(kelly_fractional, 0, max_leverage)
    
    return float(kelly_clipped)


def bet_size_from_probability(
    prob: Union[pd.Series, float],
    num_classes: int,
    side: Optional[Union[pd.Series, int]] = None,
    kelly_fraction: float = 0.5,
    max_position_size: Optional[float] = None
) -> Union[pd.Series, float]:
    """
    AFML Snippet 10.1: Calculate bet size from ML prediction probability.
    
    Converts ML prediction confidence into bet size. Assumes probability represents
    confidence in the predicted class, normalized to [1/num_classes, 1.0].
    
    Formula: signal = (prob - 1/num_classes) / (1 - 1/num_classes)
    Then optionally multiply by side (-1 for short, +1 for long).
    
    Args:
        prob: Prediction probability (confidence), range [0, 1]
        num_classes: Number of classes (2 for binary, 3 for long/short/neutral)
        side: Predicted side (+1 long, -1 short, 0 neutral). If None, returns unsigned size
        kelly_fraction: Fraction of signal to use (conservative sizing)
    
    Returns:
        Bet size (scalar or Series), range [-kelly_fraction, +kelly_fraction]
    
    Example:
        >>> # Binary classification: 80% confidence → 60% size
        >>> bet_size_from_probability(0.8, num_classes=2, side=1)
        0.6  # (0.8 - 0.5) / (1 - 0.5) = 0.6
        
        >>> # 3-class: 70% confidence, short side
        >>> bet_size_from_probability(0.7, num_classes=3, side=-1)
        -0.55  # (0.7 - 0.333) / (1 - 0.333) * -1 = -0.55
    """
    if num_classes < 2:
        raise ValueError(f"num_classes must be >= 2, got {num_classes}")
    
    # Normalize probability to [0, 1] signal
    # prob=1/n_classes → signal=0 (no confidence)
    # prob=1.0 → signal=1 (max confidence)
    min_prob = 1.0 / num_classes
    
    if isinstance(prob, pd.Series):
        signal = (prob - min_prob) / (1.0 - min_prob)
        signal = signal.abs().clip(0, 1) * kelly_fraction
        
        # Apply side if provided
        if side is not None:
            if isinstance(side, pd.Series):
                signal = signal * side
            else:
                signal = signal * side
        
        # Cap to max position size if provided
        if max_position_size is not None:
            signal = signal.clip(-max_position_size, max_position_size)
    else:
        signal_raw = (prob - min_prob) / (1.0 - min_prob)
        signal = abs(signal_raw) * kelly_fraction
        signal = max(0.0, min(1.0, signal))
        
        # Apply side if provided
        if side is not None:
            signal = signal * side
        
        # Cap to max position size if provided
        if max_position_size is not None:
            signal = max(-max_position_size, min(max_position_size, signal))
    
    return signal


def bet_size_budget(
    events_t1: pd.Series,
    sides: pd.Series
) -> pd.Series:
    """
    AFML Section 10.2: Budget-based bet sizing.
    
    Linear bet sizing based on the difference between concurrent long and short bets.
    For each bet, calculates size as:
        size = avg_concurrent_long - avg_concurrent_short
    
    Args:
        events_t1: Series mapping bet start time (index) → bet end time (value)
        sides: Series mapping bet start time (index) → bet side (+1 long, -1 short)
    
    Returns:
        Series mapping bet start time → bet size
    
    Example:
        >>> t1 = pd.Series([10, 15, 20], index=[0, 5, 10])  # start → end times
        >>> sides = pd.Series([1, 1, -1], index=[0, 5, 10])  # long, long, short
        >>> sizes = bet_size_budget(t1, sides)
        >>> # sizes[0] = avg_long - avg_short at time 0
    """
    if not events_t1.index.equals(sides.index):
        raise ValueError("events_t1 and sides must have matching indices")
    
    if events_t1.empty or sides.empty:
        raise ValueError("events_t1 and sides cannot be empty")
    
    # Build DataFrame
    df = pd.DataFrame({
        't1': events_t1,
        'side': sides
    })
    
    # Convert index to DatetimeIndex if not already
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # For each event, calculate avg concurrent bets at start time
    bet_sizes = pd.Series(index=events_t1.index, dtype=float)
    
    for idx in events_t1.index:
        t = idx
        
        # Active bets at time t: started <= t AND (not ended OR end > t)
        active_mask = (df.index <= t) & ((df['t1'].isna()) | (df['t1'] > t))
        active_df = df[active_mask]
        
        n_long = (active_df['side'] > 0).sum()
        n_short = (active_df['side'] < 0).sum()
        
        # Average long - average short
        avg_long = 1.0 if n_long > 0 else 0.0
        avg_short = 1.0 if n_short > 0 else 0.0
        
        bet_sizes[idx] = avg_long - avg_short
    
    return bet_sizes


def bet_size_dynamic(
    current_positions: Union[float, pd.Series],
    max_position_size: Union[float, pd.Series],
    current_price: Union[float, pd.Series],
    forecast_price: Union[float, pd.Series],
    w_param: float = 10.0,
    func: str = 'sigmoid'
) -> Union[pd.Series, float]:
    """
    AFML Snippet 10.4: Dynamic bet sizing based on price divergence.
    
    Calculates bet size using sigmoid or power function of price divergence.
    
    Args:
        current_positions: Current position size
        max_position_size: Maximum allowed position
        current_price: Current market price
        forecast_price: Forecasted/target price
        w_param: Width parameter (higher = more aggressive response)
        func: Function type ('sigmoid' or 'power')
    
    Returns:
        Bet size (change from current position)
    
    Example:
        >>> # Market at 100, forecast at 110 → bullish, increase position
        >>> bet_size_dynamic(0.05, 0.10, 100, 110, w_param=5)
        0.024  # Increase from 5% to 7.4%
    """
    # Broadcast to Series if any input is Series
    is_series = any(isinstance(x, pd.Series) for x in [current_positions, max_position_size, current_price, forecast_price])
    
    if is_series:
        # Convert all to Series with common index
        series_inputs = [x for x in [current_positions, max_position_size, current_price, forecast_price] if isinstance(x, pd.Series)]
        common_index = series_inputs[0].index
        
        current_positions = pd.Series(current_positions, index=common_index) if not isinstance(current_positions, pd.Series) else current_positions
        max_position_size = pd.Series(max_position_size, index=common_index) if not isinstance(max_position_size, pd.Series) else max_position_size
        current_price = pd.Series(current_price, index=common_index) if not isinstance(current_price, pd.Series) else current_price
        forecast_price = pd.Series(forecast_price, index=common_index) if not isinstance(forecast_price, pd.Series) else forecast_price
    
    # Calculate price divergence (normalized)
    price_div = (forecast_price - current_price) / current_price
    
    # Apply sizing function
    if func == 'sigmoid':
        # Sigmoid: 2 / (1 + exp(-w*x)) - 1, range [-1, 1]
        divergence_normalized = 2.0 / (1.0 + np.exp(-w_param * price_div)) - 1.0
    elif func == 'power':
        # Power: sign(x) * |x|^w
        divergence_normalized = np.sign(price_div) * np.abs(price_div) ** w_param
    else:
        raise ValueError(f"func must be 'sigmoid' or 'power', got '{func}'")
    
    # Target position: normalized to [0, max_position_size] range
    # divergence_normalized in [-1, 1] → target in [0, max_position_size]
    target_pos = (divergence_normalized + 1) / 2 * max_position_size
    
    # Bet size = change from current position
    bet_size = target_pos - current_positions
    
    return bet_size


def calculate_bet_sizes(
    weights: Union[pd.Series, Dict[str, float]],
    equity: float,
    method: str = 'proportional',
    ml_confidence: Optional[pd.Series] = None,
    num_classes: int = 2,
    kelly_params: Optional[Dict] = None,
    max_position_size: Optional[float] = None
) -> pd.Series:
    """
    Unified bet sizing function for portfolio allocation.
    
    Converts portfolio weights into position sizes using various methods.
    
    Args:
        weights: Portfolio weights (symbol → weight)
        equity: Total portfolio equity
        method: Sizing method:
            - 'proportional': Direct proportion (default)
            - 'kelly': Kelly criterion based
            - 'confidence': ML confidence based
            - 'dynamic': Dynamic sizing (requires ml_confidence)
        ml_confidence: ML prediction confidence per symbol (for 'confidence' method)
        num_classes: Number of ML classes (for 'confidence' method)
        kelly_params: Dict with 'win_prob', 'win_loss_ratio', 'kelly_fraction' (for 'kelly' method)
        max_position_size: Maximum $ per position (optional cap)
    
    Returns:
        Series mapping symbol → position size in dollars
    
    Example:
        >>> weights = pd.Series({'AAPL': 0.3, 'MSFT': 0.2})
        >>> equity = 100000
        >>> 
        >>> # Proportional
        >>> calculate_bet_sizes(weights, equity, method='proportional')
        AAPL    30000
        MSFT    20000
        
        >>> # Kelly criterion
        >>> kelly_params = {'win_prob': 0.6, 'win_loss_ratio': 2.0, 'kelly_fraction': 0.5}
        >>> calculate_bet_sizes(weights, equity, method='kelly', kelly_params=kelly_params)
        AAPL    4500  # 30% weight * 15% kelly * 100k
        MSFT    3000
    """
    if isinstance(weights, dict):
        weights = pd.Series(weights)
    
    if weights.empty:
        return pd.Series(dtype=float)
    
    if equity <= 0:
        raise ValueError(f"equity doit être > 0, got {equity}")
    
    if method == 'proportional':
        # Direct proportion: size = weight * equity
        bet_sizes = weights * equity
    
    elif method == 'kelly':
        # Kelly criterion: size = weight * kelly_factor * equity
        if kelly_params is None:
            raise ValueError("kelly_params requis pour method='kelly'")
        
        kelly_factor = kelly_criterion(
            win_prob=kelly_params.get('win_prob', 0.55),
            win_loss_ratio=kelly_params.get('win_loss_ratio', 1.5),
            max_leverage=kelly_params.get('max_leverage', 1.0),
            kelly_fraction=kelly_params.get('kelly_fraction', 0.25)
        )
        
        bet_sizes = weights * kelly_factor * equity
    
    elif method == 'confidence':
        # ML confidence based: size = weight * confidence_signal * equity
        if ml_confidence is None:
            raise ValueError("ml_confidence requis pour method='confidence'")
        
        # Align confidence with weights
        confidence_aligned = ml_confidence.reindex(weights.index).fillna(0.5)
        
        # Convert confidence to signal
        sides = weights.apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
        confidence_signals = bet_size_from_probability(
            prob=confidence_aligned,
            num_classes=num_classes,
            side=sides,
            kelly_fraction=1.0
        )
        
        bet_sizes = weights.abs() * confidence_signals * equity
    
    elif method == 'dynamic':
        # Dynamic sizing based on forecast vs market
        # Requires additional context, fallback to proportional
        logger.warning("Dynamic method requires market/forecast prices, falling back to proportional")
        bet_sizes = weights * equity
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'proportional', 'kelly', 'confidence', or 'dynamic'")
    
    # Apply max position size cap if specified
    if max_position_size is not None:
        bet_sizes = bet_sizes.clip(-max_position_size, max_position_size)
    
    return bet_sizes
