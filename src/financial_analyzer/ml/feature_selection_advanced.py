"""Advanced factor selection module using Information Coefficient (IC) analysis.

Provides tools for selecting high-quality alpha factors based on IC metrics,
stability analysis, and redundancy removal.

Example:
    >>> from financial_analyzer.ml.feature_selection_advanced import AdvancedFactorSelector
    >>> selector = AdvancedFactorSelector(factors_df, returns_series)
    >>> ic_scores = selector.ic_analysis()
    >>> best_factors = selector.select_factors_by_ic_threshold(threshold=0.05)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)


class AdvancedFactorSelector:
    """Advanced factor selection using IC analysis and stability metrics.

    Selects alpha factors based on:
    - Information Coefficient (IC): Correlation with forward returns
    - IC Stability: Consistency of IC over time (rolling windows)
    - Redundancy: Removes highly correlated factors

    Attributes:
        factors: DataFrame of factor values (index=dates, columns=factor_names)
        returns: Series of forward returns (aligned with factors)
        min_periods: Minimum periods for rolling IC calculation

    Example:
        >>> selector = AdvancedFactorSelector(factors_df, returns_1d)
        >>> ic_df = selector.ic_analysis()
        >>> stable_factors = selector.select_factors_by_ic_threshold(
        ...     ic_threshold=0.05,
        ...     stability_threshold=0.3
        ... )
    """

    def __init__(
        self,
        factors: pd.DataFrame,
        returns: pd.Series,
        min_periods: int = 60,
    ) -> None:
        """Initialize the factor selector.

        Args:
            factors: DataFrame of factor values (index=dates, columns=factors)
            returns: Forward returns series (same index as factors)
            min_periods: Minimum periods for rolling calculations

        Raises:
            ValueError: If factors or returns are invalid
        """
        if factors is None or factors.empty:
            raise ValueError("factors must be a non-empty DataFrame")
        if returns is None or returns.empty:
            raise ValueError("returns must be a non-empty Series")
        if len(factors) != len(returns):
            raise ValueError(
                f"factors and returns must have same length: {len(factors)} != {len(returns)}"
            )

        self.factors = factors.copy()
        self.returns = returns.copy()
        self.min_periods = min_periods

        # Align indices
        common_idx = self.factors.index.intersection(self.returns.index)
        self.factors = self.factors.loc[common_idx]
        self.returns = self.returns.loc[common_idx]

        logger.info(
            "AdvancedFactorSelector initialized: %d factors, %d periods",
            len(self.factors.columns),
            len(self.factors),
        )

    def ic_analysis(
        self, method: str = "spearman", forward_periods: int = 1
    ) -> pd.DataFrame:
        """Compute Information Coefficient (IC) for all factors.

        Args:
            method: Correlation method ('spearman' or 'pearson')
            forward_periods: Periods ahead for forward returns

        Returns:
            DataFrame with columns: factor_name, ic_mean, ic_std, ic_ir, abs_ic_mean

        Example:
            >>> ic_df = selector.ic_analysis(method='spearman')
            >>> print(ic_df.sort_values('abs_ic_mean', ascending=False).head())
        """
        logger.info("Computing IC analysis (method=%s, forward=%d)", method, forward_periods)

        # Shift returns forward
        forward_returns = self.returns.shift(-forward_periods)

        results = []
        for factor_name in self.factors.columns:
            factor_values = self.factors[factor_name]

            # Remove NaNs
            valid_mask = factor_values.notna() & forward_returns.notna()
            factor_clean = factor_values[valid_mask]
            returns_clean = forward_returns[valid_mask]

            if len(factor_clean) < self.min_periods:
                logger.warning("Insufficient data for %s (%d < %d)", factor_name, len(factor_clean), self.min_periods)
                continue

            # Compute IC
            if method == "spearman":
                ic, _ = spearmanr(factor_clean, returns_clean)
            elif method == "pearson":
                ic = np.corrcoef(factor_clean, returns_clean)[0, 1]
            else:
                raise ValueError(f"Unknown method: {method}")

            # Rolling IC for std calculation
            rolling_ic = self._rolling_ic(factor_clean, returns_clean, window=60, method=method)
            ic_std = rolling_ic.std()
            ic_ir = ic / (ic_std + 1e-9)  # Information Ratio

            results.append(
                {
                    "factor_name": factor_name,
                    "ic_mean": float(ic),
                    "ic_std": float(ic_std),
                    "ic_ir": float(ic_ir),
                    "abs_ic_mean": float(abs(ic)),
                }
            )

        ic_df = pd.DataFrame(results)
        ic_df = ic_df.sort_values("abs_ic_mean", ascending=False).reset_index(drop=True)

        logger.info(
            "IC analysis completed: %d factors (mean |IC|: %.4f)",
            len(ic_df),
            ic_df["abs_ic_mean"].mean() if not ic_df.empty else 0.0,
        )

        return ic_df

    def rolling_ic_stability(
        self,
        factor_name: str,
        window: int = 60,
        method: str = "spearman",
    ) -> pd.Series:
        """Compute rolling IC over time for a single factor.

        Args:
            factor_name: Name of the factor
            window: Rolling window size
            method: Correlation method ('spearman' or 'pearson')

        Returns:
            Series of rolling IC values (index=dates)

        Example:
            >>> rolling_ic = selector.rolling_ic_stability('ROC_10', window=60)
            >>> print(f"IC stability: {rolling_ic.std():.4f}")
        """
        if factor_name not in self.factors.columns:
            raise ValueError(f"Unknown factor: {factor_name}")

        logger.debug("Computing rolling IC for %s (window=%d)", factor_name, window)

        factor_values = self.factors[factor_name]
        forward_returns = self.returns.shift(-1)

        rolling_ic = self._rolling_ic(factor_values, forward_returns, window=window, method=method)

        logger.debug(
            "Rolling IC computed for %s: mean=%.4f, std=%.4f",
            factor_name,
            rolling_ic.mean(),
            rolling_ic.std(),
        )

        return rolling_ic

    def select_factors_by_ic_threshold(
        self,
        ic_threshold: float = 0.05,
        stability_threshold: Optional[float] = None,
        max_factors: Optional[int] = None,
    ) -> List[str]:
        """Select factors with IC above threshold and optional stability constraint.

        Args:
            ic_threshold: Minimum absolute IC (e.g., 0.05)
            stability_threshold: Maximum IC std (e.g., 0.3) - None to skip
            max_factors: Maximum number of factors to return (top-N by |IC|)

        Returns:
            List of selected factor names (sorted by |IC| descending)

        Example:
            >>> factors = selector.select_factors_by_ic_threshold(
            ...     ic_threshold=0.05,
            ...     stability_threshold=0.3,
            ...     max_factors=20
            ... )
            >>> print(f"Selected {len(factors)} high-quality factors")
        """
        logger.info(
            "Selecting factors (ic_threshold=%.4f, stability_threshold=%s, max_factors=%s)",
            ic_threshold,
            stability_threshold,
            max_factors,
        )

        ic_df = self.ic_analysis()

        # Filter by IC threshold
        selected = ic_df[ic_df["abs_ic_mean"] >= ic_threshold].copy()

        # Filter by stability (if specified)
        if stability_threshold is not None:
            selected = selected[selected["ic_std"] <= stability_threshold]

        # Limit to top-N
        if max_factors is not None and len(selected) > max_factors:
            selected = selected.head(max_factors)

        factor_names = selected["factor_name"].tolist()

        logger.info(
            "Selected %d factors (from %d total): %s",
            len(factor_names),
            len(ic_df),
            factor_names[:5] if len(factor_names) > 5 else factor_names,
        )

        return factor_names

    def factor_redundancy_analysis(
        self,
        factor_names: Optional[List[str]] = None,
        corr_threshold: float = 0.8,
    ) -> Dict[str, List[str]]:
        """Identify redundant factors (highly correlated pairs).

        Args:
            factor_names: List of factors to analyze (None = all)
            corr_threshold: Correlation threshold for redundancy (e.g., 0.8)

        Returns:
            Dictionary mapping factor_name -> list of redundant factors

        Example:
            >>> redundant = selector.factor_redundancy_analysis(corr_threshold=0.85)
            >>> for factor, similar in redundant.items():
            ...     print(f"{factor} similar to: {similar}")
        """
        if factor_names is None:
            factor_names = self.factors.columns.tolist()

        logger.info(
            "Analyzing redundancy for %d factors (threshold=%.2f)",
            len(factor_names),
            corr_threshold,
        )

        # Compute correlation matrix
        factors_subset = self.factors[factor_names]
        corr_matrix = factors_subset.corr()

        # Find redundant pairs
        redundant_map: Dict[str, List[str]] = {}
        seen_pairs = set()

        for i, factor_i in enumerate(factor_names):
            redundant_list = []
            for j, factor_j in enumerate(factor_names):
                if i >= j:  # Skip diagonal and duplicates
                    continue

                pair = tuple(sorted([factor_i, factor_j]))
                if pair in seen_pairs:
                    continue

                corr_val = corr_matrix.loc[factor_i, factor_j]
                if abs(corr_val) >= corr_threshold:
                    redundant_list.append(factor_j)
                    seen_pairs.add(pair)

            if redundant_list:
                redundant_map[factor_i] = redundant_list

        logger.info("Found %d factors with redundant pairs", len(redundant_map))
        return redundant_map

    def remove_redundant_factors(
        self,
        factor_names: List[str],
        corr_threshold: float = 0.8,
        keep_strategy: str = "ic",
    ) -> List[str]:
        """Remove redundant factors, keeping best by IC or first occurrence.

        Args:
            factor_names: List of factors to prune
            corr_threshold: Correlation threshold for redundancy
            keep_strategy: 'ic' (keep higher |IC|) or 'first' (keep first)

        Returns:
            List of non-redundant factors

        Example:
            >>> pruned = selector.remove_redundant_factors(
            ...     all_factors,
            ...     corr_threshold=0.85,
            ...     keep_strategy='ic'
            ... )
            >>> print(f"Pruned from {len(all_factors)} to {len(pruned)} factors")
        """
        logger.info(
            "Removing redundant factors (threshold=%.2f, strategy=%s)",
            corr_threshold,
            keep_strategy,
        )

        # Precompute IC if needed
        ic_map = {}
        if keep_strategy == "ic":
            ic_df = self.ic_analysis()
            ic_map = dict(zip(ic_df["factor_name"], ic_df["abs_ic_mean"]))

        # Compute correlation matrix
        factors_subset = self.factors[factor_names]
        corr_matrix = factors_subset.corr()

        # Greedy removal: iterate and remove redundant
        kept_factors = []
        removed_factors = set()

        for factor in factor_names:
            if factor in removed_factors:
                continue

            kept_factors.append(factor)

            # Check for redundant factors
            for other in factor_names:
                if other == factor or other in removed_factors or other in kept_factors:
                    continue

                corr_val = corr_matrix.loc[factor, other]
                if abs(corr_val) >= corr_threshold:
                    # Decide which to keep
                    if keep_strategy == "ic":
                        ic_factor = ic_map.get(factor, 0.0)
                        ic_other = ic_map.get(other, 0.0)
                        if ic_other > ic_factor:
                            # Keep other, remove factor (undo append)
                            kept_factors.pop()
                            removed_factors.add(factor)
                            break
                        else:
                            removed_factors.add(other)
                    else:  # keep_strategy == 'first'
                        removed_factors.add(other)

        logger.info(
            "Redundancy removal: %d -> %d factors (%d removed)",
            len(factor_names),
            len(kept_factors),
            len(removed_factors),
        )

        return kept_factors

    # -------------------- Private Helpers --------------------

    def _rolling_ic(
        self,
        factor_values: pd.Series,
        returns: pd.Series,
        window: int,
        method: str = "spearman",
    ) -> pd.Series:
        """Compute rolling IC between factor and returns.

        Args:
            factor_values: Factor time series
            returns: Returns time series
            window: Rolling window size
            method: Correlation method

        Returns:
            Series of rolling IC values
        """
        # Align series
        valid_mask = factor_values.notna() & returns.notna()
        factor_clean = factor_values[valid_mask]
        returns_clean = returns[valid_mask]

        if len(factor_clean) < window:
            logger.warning("Insufficient data for rolling IC (%d < %d)", len(factor_clean), window)
            return pd.Series(dtype=float)

        # Compute rolling correlation
        if method == "spearman":
            # Spearman requires rank transformation
            def rolling_spearman(x, y):
                if len(x) < window or x.isna().any() or y.isna().any():
                    return np.nan
                corr, _ = spearmanr(x, y)
                return corr

            rolling_ic = pd.Series(
                [
                    rolling_spearman(
                        factor_clean.iloc[max(0, i - window + 1) : i + 1],
                        returns_clean.iloc[max(0, i - window + 1) : i + 1],
                    )
                    for i in range(len(factor_clean))
                ],
                index=factor_clean.index,
            )
        else:  # pearson
            factor_roll = factor_clean.rolling(window=window, min_periods=window)
            returns_roll = returns_clean.rolling(window=window, min_periods=window)
            rolling_ic = factor_roll.corr(returns_roll)

        return rolling_ic


# --------------- Utility Functions ------------------


def select_top_factors_by_category(
    ic_df: pd.DataFrame,
    factors_metadata: Dict[str, str],
    n_per_category: int = 5,
) -> List[str]:
    """Select top N factors per category based on IC.

    Args:
        ic_df: IC analysis DataFrame (from ic_analysis)
        factors_metadata: Mapping factor_name -> category
        n_per_category: Number of factors per category

    Returns:
        List of selected factor names

    Example:
        >>> metadata = {f.name: f.category for f in all_factors.values()}
        >>> top_factors = select_top_factors_by_category(ic_df, metadata, n_per_category=3)
    """
    # Add category column
    ic_df = ic_df.copy()
    ic_df["category"] = ic_df["factor_name"].map(factors_metadata)

    # Group by category and take top N
    selected = []
    for category, group in ic_df.groupby("category"):
        top_n = group.nlargest(n_per_category, "abs_ic_mean")
        selected.extend(top_n["factor_name"].tolist())

    logger.info(
        "Selected %d factors (%d per category)",
        len(selected),
        n_per_category,
    )

    return selected


def compute_ic_decay(
    factors: pd.DataFrame,
    returns: pd.Series,
    max_lag: int = 10,
    method: str = "spearman",
) -> pd.DataFrame:
    """Compute IC decay (IC at different forward lags).

    Args:
        factors: DataFrame of factor values
        returns: Returns series
        max_lag: Maximum forward lag to compute
        method: Correlation method

    Returns:
        DataFrame with columns: factor_name, lag, ic

    Example:
        >>> decay_df = compute_ic_decay(factors_df, returns, max_lag=5)
        >>> pivot = decay_df.pivot(index='factor_name', columns='lag', values='ic')
        >>> print(pivot.head())
    """
    logger.info("Computing IC decay (max_lag=%d, method=%s)", max_lag, method)

    results = []
    for factor_name in factors.columns:
        factor_values = factors[factor_name]

        for lag in range(1, max_lag + 1):
            forward_returns = returns.shift(-lag)

            # Remove NaNs
            valid_mask = factor_values.notna() & forward_returns.notna()
            factor_clean = factor_values[valid_mask]
            returns_clean = forward_returns[valid_mask]

            if len(factor_clean) < 20:
                continue

            # Compute IC
            if method == "spearman":
                ic, _ = spearmanr(factor_clean, returns_clean)
            else:  # pearson
                ic = np.corrcoef(factor_clean, returns_clean)[0, 1]

            results.append({"factor_name": factor_name, "lag": lag, "ic": float(ic)})

    decay_df = pd.DataFrame(results)
    logger.info("IC decay computed: %d entries", len(decay_df))
    return decay_df
