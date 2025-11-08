"""
Ensemble portfolio allocation from fused signals.

This module provides the EnsembleAllocator class which converts fused trading
signals into portfolio allocations with position sizing, cash reserves, and
risk management constraints.

Features
--------
- Signal-to-weight conversion
- Position sizing with min/max limits
- Cash reserve management
- Multiple risk models (equal weight, signal-based, inverse variance)
- Confidence-weighted allocation
- Automatic re-normalization

Example
-------
>>> from financial_analyzer.strategy import EnsembleAllocator
>>> allocator = EnsembleAllocator(
...     max_position_size=0.20,
...     min_position_size=0.02,
...     cash_reserve=0.10,
...     confidence_threshold=0.5
... )
>>> signals = {
...     'AAPL': {'final_score': 0.8, 'confidence': 0.9},
...     'MSFT': {'final_score': 0.7, 'confidence': 0.8},
...     'GOOGL': {'final_score': 0.3, 'confidence': 0.6}
... }
>>> weights = allocator.allocate(signals, total_capital=100000, risk_model='signal_based')
>>> print(weights)
{'AAPL': 0.20, 'MSFT': 0.18, 'GOOGL': 0.0, 'cash': 0.62}
"""

from __future__ import annotations

from typing import Dict, Optional, Literal
import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

RiskModel = Literal["equal_weight", "signal_based", "inverse_variance"]


class EnsembleAllocator:
    """
    Allocate portfolio based on ensemble signals.

    Converts fused trading signals into portfolio weights with proper
    position sizing, cash reserves, and risk management.

    Parameters
    ----------
    max_position_size : float, default 0.20
        Maximum weight for a single position (20%).
    min_position_size : float, default 0.02
        Minimum weight for a position (2%). Below this, position is excluded.
    cash_reserve : float, default 0.10
        Minimum cash reserve as fraction of portfolio (10%).
    confidence_threshold : float, default 0.5
        Minimum confidence to include signal in allocation.

    Attributes
    ----------
    max_position_size : float
        Maximum position weight.
    min_position_size : float
        Minimum position weight.
    cash_reserve : float
        Cash reserve fraction.
    confidence_threshold : float
        Confidence threshold.

    Raises
    ------
    ValueError
        If position sizes or cash reserve not in [0, 1].
        If max_position_size < min_position_size.

    Example
    -------
    >>> allocator = EnsembleAllocator(max_position_size=0.15, cash_reserve=0.05)
    >>> signals = {'AAPL': {'final_score': 0.8, 'confidence': 0.9}}
    >>> weights = allocator.allocate(signals, total_capital=10000)
    >>> sum(weights.values())
    1.0
    """

    def __init__(
        self,
        max_position_size: float = 0.20,
        min_position_size: float = 0.02,
        cash_reserve: float = 0.10,
        confidence_threshold: float = 0.5,
    ) -> None:
        """Initialize EnsembleAllocator with constraints."""
        # Validate parameters
        if not (0.0 < max_position_size <= 1.0):
            raise ValueError("max_position_size must be in (0, 1]")
        if not (0.0 <= min_position_size < max_position_size):
            raise ValueError("min_position_size must be in [0, max_position_size)")
        if not (0.0 <= cash_reserve < 1.0):
            raise ValueError("cash_reserve must be in [0, 1)")
        if not (0.0 <= confidence_threshold <= 1.0):
            raise ValueError("confidence_threshold must be in [0, 1]")

        self.max_position_size = max_position_size
        self.min_position_size = min_position_size
        self.cash_reserve = cash_reserve
        self.confidence_threshold = confidence_threshold

        logger.info(
            f"EnsembleAllocator initialized: max_pos={max_position_size:.2%}, "
            f"min_pos={min_position_size:.2%}, cash_reserve={cash_reserve:.2%}, "
            f"conf_threshold={confidence_threshold:.2f}"
        )

    def allocate(
        self,
        signals: Dict[str, Dict[str, float]],
        total_capital: float,
        risk_model: RiskModel = "signal_based",
        covariance_matrix: Optional[pd.DataFrame] = None,
    ) -> Dict[str, float]:
        """
        Allocate portfolio weights based on signals.

        Parameters
        ----------
        signals : dict
            Fused signals per ticker: {ticker: {'final_score': float, 'confidence': float}}
        total_capital : float
            Total portfolio capital (for logging, not used in calculation).
        risk_model : {'equal_weight', 'signal_based', 'inverse_variance'}, default 'signal_based'
            Risk model to use:
            - equal_weight: Equal allocation to all signals
            - signal_based: Weight by final_score * confidence
            - inverse_variance: Weight by inverse variance (requires covariance_matrix)
        covariance_matrix : pd.DataFrame, optional
            Covariance matrix for inverse_variance model. Index/columns must match tickers.

        Returns
        -------
        dict
            Portfolio weights: {ticker: weight, 'cash': weight}
            All weights sum to 1.0.

        Example
        -------
        >>> signals = {
        ...     'AAPL': {'final_score': 0.8, 'confidence': 0.9},
        ...     'MSFT': {'final_score': 0.7, 'confidence': 0.8}
        ... }
        >>> weights = allocator.allocate(signals, 100000, risk_model='signal_based')
        >>> weights['AAPL'] + weights['MSFT'] + weights['cash']
        1.0
        """
        try:
            # Filter signals by confidence threshold
            filtered_signals = {
                ticker: sig
                for ticker, sig in signals.items()
                if sig.get('confidence', 0.0) >= self.confidence_threshold
            }

            if not filtered_signals:
                logger.warning("No signals meet confidence threshold, allocating 100% to cash")
                return {'cash': 1.0}

            logger.info(
                f"Allocating with {risk_model} model: {len(filtered_signals)} signals "
                f"(filtered from {len(signals)}), capital=${total_capital:,.0f}"
            )

            # Apply risk model to get raw weights
            if risk_model == "equal_weight":
                raw_weights = self._equal_weight_allocation(filtered_signals)
            elif risk_model == "signal_based":
                raw_weights = self._signal_based_allocation(filtered_signals)
            elif risk_model == "inverse_variance":
                raw_weights = self._inverse_variance_allocation(filtered_signals, covariance_matrix)
            else:
                raise ValueError(f"Unknown risk_model: {risk_model}")

            # Apply position limits
            clipped_weights = self._apply_position_limits(raw_weights)

            # Apply cash reserve
            final_weights = self._apply_cash_reserve(clipped_weights)

            # Validate and log
            total = sum(final_weights.values())
            if not np.isclose(total, 1.0, atol=1e-6):
                logger.warning(f"Weights sum to {total:.6f}, re-normalizing")
                final_weights = {k: v / total for k, v in final_weights.items()}

            n_positions = len([w for k, w in final_weights.items() if k != 'cash' and w > 0])
            cash_pct = final_weights.get('cash', 0.0)
            logger.info(f"Allocation complete: {n_positions} positions, {cash_pct:.1%} cash")

            return final_weights

        except Exception as e:
            logger.error(f"Allocation failed: {e}")
            # Return 100% cash on error
            return {'cash': 1.0}

    def _equal_weight_allocation(self, signals: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """
        Equal weight allocation.

        Parameters
        ----------
        signals : dict
            Filtered signals.

        Returns
        -------
        dict
            Equal weights for all tickers.
        """
        n = len(signals)
        weight = 1.0 / n
        return {ticker: weight for ticker in signals.keys()}

    def _signal_based_allocation(self, signals: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """
        Signal-based allocation: weight = final_score * confidence.

        Parameters
        ----------
        signals : dict
            Filtered signals with final_score and confidence.

        Returns
        -------
        dict
            Weights proportional to score * confidence.
        """
        weights = {}
        for ticker, sig in signals.items():
            score = sig.get('final_score', 0.5)
            confidence = sig.get('confidence', 1.0)
            # Weight by score * confidence
            # Score in [0, 1]: 0=bearish, 1=bullish
            # Only allocate to bullish signals (score > 0.5)
            if score > 0.5:
                weights[ticker] = (score - 0.5) * 2.0 * confidence  # Normalize [0.5, 1] → [0, 1]
            else:
                weights[ticker] = 0.0

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        else:
            # All bearish, return empty
            logger.warning("All signals bearish, no positions")
            return {}

        return weights

    def _inverse_variance_allocation(
        self,
        signals: Dict[str, Dict[str, float]],
        covariance_matrix: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """
        Inverse variance allocation (minimum variance).

        Parameters
        ----------
        signals : dict
            Filtered signals.
        covariance_matrix : pd.DataFrame, optional
            Covariance matrix. If None, falls back to equal weight.

        Returns
        -------
        dict
            Weights inversely proportional to variance.
        """
        if covariance_matrix is None:
            logger.warning("No covariance matrix provided, falling back to equal weight")
            return self._equal_weight_allocation(signals)

        tickers = list(signals.keys())

        # Filter covariance matrix to available tickers
        available_tickers = [t for t in tickers if t in covariance_matrix.index]
        if not available_tickers:
            logger.warning("No tickers in covariance matrix, falling back to equal weight")
            return self._equal_weight_allocation(signals)

        cov = covariance_matrix.loc[available_tickers, available_tickers]
        variances = np.diag(cov.values)

        # Inverse variance weights
        inv_var = 1.0 / (variances + 1e-8)  # Add epsilon to avoid division by zero
        weights_array = inv_var / inv_var.sum()

        weights = {ticker: float(w) for ticker, w in zip(available_tickers, weights_array)}

        # Add zero weights for tickers not in covariance matrix
        for ticker in tickers:
            if ticker not in weights:
                weights[ticker] = 0.0

        return weights

    def _apply_position_limits(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        Clip weights to [min_position_size, max_position_size].

        Iteratively applies limits and re-normalizes until convergence.

        Parameters
        ----------
        weights : dict
            Raw weights (should already sum to 1.0).

        Returns
        -------
        dict
            Clipped and re-normalized weights.
        """
        if not weights:
            return {}
        
        # Iterative clipping to handle re-normalization correctly
        max_iterations = 10
        current_weights = weights.copy()
        
        for iteration in range(max_iterations):
            clipped = {}
            needs_renormalization = False
            
            for ticker, weight in current_weights.items():
                if weight < self.min_position_size:
                    if weight > 0:
                        logger.debug(f"Iter {iteration}: {ticker} weight {weight:.4f} < min {self.min_position_size:.4f}, excluded")
                        needs_renormalization = True
                    # Exclude by not adding to clipped
                elif weight > self.max_position_size + 1e-6:  # Small tolerance for float comparison
                    clipped[ticker] = self.max_position_size
                    logger.debug(f"Iter {iteration}: {ticker} weight {weight:.4f} > max {self.max_position_size:.4f}, clipped")
                    needs_renormalization = True
                else:
                    clipped[ticker] = weight

            if not clipped:
                return {}

            # Re-normalize to sum to 1.0
            total = sum(clipped.values())
            if total > 0:
                clipped = {k: v / total for k, v in clipped.items()}
            
            # Check if any weight violates limits after normalization
            converged = True
            for ticker, weight in clipped.items():
                if weight > self.max_position_size + 1e-6 or weight < self.min_position_size - 1e-6:
                    converged = False
                    break
            
            if converged:
                break
            
            current_weights = clipped
        
        return clipped

    def _apply_cash_reserve(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        Apply cash reserve constraint.

        Parameters
        ----------
        weights : dict
            Weights before cash reserve.

        Returns
        -------
        dict
            Weights with cash reserve included.
        """
        # Scale down all weights to leave room for cash
        available = 1.0 - self.cash_reserve
        scaled = {k: v * available for k, v in weights.items()}
        scaled['cash'] = self.cash_reserve

        return scaled


__all__ = ["EnsembleAllocator"]
