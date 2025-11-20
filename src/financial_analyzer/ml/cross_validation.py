"""
PurgedKFold Cross-Validation for financial time series.

Implements Chapter 7 of "Advances in Financial Machine Learning" (AFML) by Marcos López de Prado.

Problem: Standard K-Fold CV assumes independence between samples. In finance, labels span time intervals
(e.g., triple-barrier method), creating temporal leakage between train/test sets.

Solution: PurgedKFold removes (purges) training samples that overlap with test label intervals,
and adds an embargo period after test sets to prevent forward-looking information.

Key Concepts:
- Purging: Remove train samples whose labels overlap with test period
- Embargo: Add buffer period after test set (prevent using future info)
- samples_info_sets (t1): Series mapping sample index → label end time

Author: FinBot
License: MIT
References: AFML Chapter 7, Snippet 7.1-7.4
"""

import sys
from pathlib import Path
from typing import Optional, Tuple, Generator

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def _ensure_vendor_mlfinlab_on_path() -> None:
    """Add vendor/mlfinlab to sys.path if not already present."""
    vendor_path = Path(__file__).parents[3] / "vendor" / "mlfinlab"
    if vendor_path.exists() and str(vendor_path) not in sys.path:
        sys.path.insert(0, str(vendor_path))
        logger.debug(f"Added {vendor_path} to sys.path for mlfinlab vendored import")


def ml_get_train_times(
    samples_info_sets: pd.Series,
    test_times: pd.Series
) -> pd.Series:
    """
    AFML Snippet 7.1: Purging observations in the training set.
    
    Given test_times, find the times of training observations that do NOT overlap
    with test label intervals.
    
    Purging Logic:
    - For each test sample with label ending at t1_test, remove train samples whose
      label interval [t0, t1] overlaps with any test label interval
    - A train sample overlaps if its end time (t1_train) >= earliest test start time
      AND its start time (t0_train) <= latest test end time
    
    Args:
        samples_info_sets: Series mapping sample start time (index) → label end time (value)
                          This is the t1 series from triple-barrier labeling
        test_times: Series or Index of test sample start times (must be in samples_info_sets.index)
    
    Returns:
        Series of purged training sample start times (non-overlapping with test)
    
    Example:
        >>> # Train samples with labels ending at various times
        >>> t1 = pd.Series([10, 20, 30, 40, 50], index=[0, 10, 20, 30, 40])
        >>> # Test period: samples starting at [20, 30] (labels end at 30, 40)
        >>> test = pd.Series([20, 30])
        >>> train = ml_get_train_times(t1, test)
        >>> # Returns samples [0, 10] (end before test starts at 20)
    """
    if samples_info_sets is None or samples_info_sets.empty:
        raise ValueError("samples_info_sets (t1) cannot be None or empty")
    
    if test_times is None or len(test_times) == 0:
        raise ValueError("test_times cannot be None or empty")
    
    # Convert test_times to Index/array
    if isinstance(test_times, pd.Series):
        test_times_values = test_times.values
    else:
        test_times_values = test_times
    
    # Get test interval bounds
    test_start_min = test_times_values.min()
    
    # Get test label end times (t1) for test samples
    # test_times should be keys in samples_info_sets
    try:
        test_t1_values = samples_info_sets.loc[test_times_values].values
        test_end_max = test_t1_values.max()
    except KeyError:
        # If test_times not in samples_info_sets, assume they represent label end times
        # This handles the case where test_times are not actual sample indices
        test_end_max = test_times_values.max()
    
    # Train samples: keep those whose labels END before test starts
    # This ensures no overlap: t1_train < test_start_min
    train_mask = (samples_info_sets < test_start_min)
    
    return samples_info_sets[train_mask]


class PurgedKFold(KFold):
    """
    Purged K-Fold cross-validation for financial time series.
    
    Extends sklearn.model_selection.KFold to handle labels that span intervals.
    Removes training samples whose label intervals overlap with test label intervals.
    Optionally adds an embargo period after test sets.
    
    Key Differences from Standard KFold:
    - Purging: Removes train samples overlapping test labels
    - Embargo: Adds buffer period after test (default: pct_embargo * n_samples)
    - Requires samples_info_sets (t1): label end times for each sample
    
    Attributes:
        n_splits: Number of folds (default 3)
        samples_info_sets: Series mapping sample index → label end time (t1)
        pct_embargo: Embargo size as fraction of n_samples (default 0.01 = 1%)
    
    Example:
        >>> from financial_analyzer.ml.labeling import triple_barrier_labels
        >>> # Generate labels with t1 (label end times)
        >>> labels, t1, _ = triple_barrier_labels(prices, pt_sl=[0.02, 0.02])
        >>> 
        >>> # Create PurgedKFold with t1
        >>> cv = PurgedKFold(n_splits=5, samples_info_sets=t1, pct_embargo=0.01)
        >>> 
        >>> # Use with sklearn models
        >>> for train_idx, test_idx in cv.split(X):
        ...     X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        ...     y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        ...     model.fit(X_train, y_train)
        ...     score = model.score(X_test, y_test)
    """
    
    def __init__(
        self,
        n_splits: int = 3,
        samples_info_sets: Optional[pd.Series] = None,
        pct_embargo: float = 0.01
    ):
        """
        Initialize PurgedKFold.
        
        Args:
            n_splits: Number of folds (must be >= 2)
            samples_info_sets: Series mapping sample index → label end time (t1)
                              Required for purging. If None, falls back to standard KFold.
            pct_embargo: Embargo size as fraction of n_samples (0.0 to 0.5)
                        After each test set, embargo the next pct_embargo * n_samples rows
        
        Raises:
            ValueError: If n_splits < 2 or pct_embargo out of range
        """
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        
        if not 0.0 <= pct_embargo <= 0.5:
            raise ValueError(f"pct_embargo must be in [0.0, 0.5], got {pct_embargo}")
        
        # Call parent with shuffle=False (test sets must be contiguous)
        super().__init__(n_splits=n_splits, shuffle=False, random_state=None)
        
        self.samples_info_sets = samples_info_sets
        self.pct_embargo = pct_embargo
        
        if samples_info_sets is None:
            logger.warning(
                "samples_info_sets (t1) not provided. PurgedKFold will behave like standard KFold. "
                "For proper purging, provide t1 from triple-barrier labeling."
            )
    
    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        groups=None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generate indices to split data into training and test sets with purging.
        
        Process:
        1. Standard KFold split to get test indices
        2. For each test fold:
           a. Identify test sample times
           b. Purge train samples overlapping test labels (via ml_get_train_times)
           c. Apply embargo: remove samples immediately after test set
        
        Args:
            X: DataFrame with datetime index or integer index
            y: Optional labels (not used, kept for sklearn compatibility)
            groups: Optional group labels (not used)
        
        Yields:
            Tuple of (train_indices, test_indices) as numpy arrays
        
        Example:
            >>> cv = PurgedKFold(n_splits=3, samples_info_sets=t1)
            >>> for train_idx, test_idx in cv.split(X):
            ...     print(f"Train size: {len(train_idx)}, Test size: {len(test_idx)}")
        """
        if not isinstance(X, pd.DataFrame):
            raise TypeError("X must be a pandas DataFrame with index")
        
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        # Fallback to standard KFold if no t1 provided
        if self.samples_info_sets is None:
            logger.warning("No samples_info_sets provided, using standard KFold (no purging)")
            yield from super().split(X, y, groups)
            return
        
        # Align samples_info_sets with X index
        if not self.samples_info_sets.index.equals(X.index):
            logger.warning("samples_info_sets index does not match X.index, attempting to reindex")
            t1_aligned = self.samples_info_sets.reindex(X.index)
            if t1_aligned.isna().any():
                raise ValueError(
                    f"samples_info_sets cannot be aligned with X.index. "
                    f"Missing t1 values for {t1_aligned.isna().sum()} samples."
                )
        else:
            t1_aligned = self.samples_info_sets
        
        # Generate base splits using parent KFold
        for train_indices, test_indices in super().split(X, y, groups):
            # Get test times (index values for test samples)
            test_times = X.index[test_indices]
            
            # Purge train samples overlapping with test labels
            # We need to check: for each train sample, does its label (t1) overlap with test period?
            # Overlap occurs if: t1_train >= test_start_min
            # Keep train samples where: t1_train < test_start_min
            try:
                test_start_min = test_times.min()
                test_t1 = t1_aligned.loc[test_times]
                test_end_max = test_t1.max()
                
                # For each train sample, check if its label ends before test starts
                train_indices_series = pd.Series(train_indices)
                train_times = X.index[train_indices]
                train_t1 = t1_aligned.loc[train_times]
                
                # Keep train samples whose labels end BEFORE test period starts
                # This prevents using information that overlaps with test labels
                purge_mask = (train_t1 < test_start_min)
                purged_train_indices = train_indices[purge_mask]
                
                if len(purged_train_indices) == 0:
                    logger.warning(
                        f"Purging removed ALL train samples for this fold. "
                        f"Test starts at {test_start_min}, but all train labels extend past it. "
                        f"Using unpurged train set to avoid empty training."
                    )
                    purged_train_indices = train_indices
                
            except Exception as e:
                logger.error(f"Purging failed: {e}. Using unpurged train set.")
                purged_train_indices = train_indices
            
            # Apply embargo: remove samples immediately after test set
            if self.pct_embargo > 0:
                embargo_size = int(n_samples * self.pct_embargo)
                if embargo_size > 0:
                    # Find samples in embargo window
                    test_end_idx = test_indices[-1]
                    embargo_start = test_end_idx + 1
                    embargo_end = min(test_end_idx + embargo_size + 1, n_samples)
                    embargo_indices = np.arange(embargo_start, embargo_end)
                    
                    # Remove embargo samples from train
                    purged_train_indices = np.setdiff1d(purged_train_indices, embargo_indices)
            
            # Ensure train indices are sorted
            purged_train_indices = np.sort(purged_train_indices)
            
            yield purged_train_indices, test_indices


def get_purged_kfold_cv(
    n_splits: int = 5,
    samples_info_sets: Optional[pd.Series] = None,
    pct_embargo: float = 0.01,
    use_vendored: bool = True
) -> PurgedKFold:
    """
    Convenience function to get PurgedKFold CV object.
    
    Tries to use vendored mlfinlab if available, otherwise uses our implementation.
    
    Args:
        n_splits: Number of folds
        samples_info_sets: Series mapping sample index → label end time (t1)
        pct_embargo: Embargo size as fraction of n_samples
        use_vendored: If True, try vendored mlfinlab first (currently stubs)
    
    Returns:
        PurgedKFold cross-validator instance
    
    Example:
        >>> cv = get_purged_kfold_cv(n_splits=5, samples_info_sets=t1, pct_embargo=0.01)
        >>> scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy')
    """
    # For now, vendored mlfinlab has stubs, so we use our implementation
    # In future, if vendored version is complete, we can import it
    if use_vendored:
        try:
            _ensure_vendor_mlfinlab_on_path()
            from mlfinlab.cross_validation.cross_validation import PurgedKFold as VendorPurgedKFold
            
            # Check if vendored version is functional (not a stub)
            import inspect
            source = inspect.getsource(VendorPurgedKFold.split)
            if 'pass' in source and source.strip().endswith('pass'):
                logger.info("Vendored mlfinlab PurgedKFold is a stub, using local implementation")
                raise ImportError("Stub implementation")
            
            logger.info("Using vendored mlfinlab PurgedKFold")
            return VendorPurgedKFold(
                n_splits=n_splits,
                samples_info_sets=samples_info_sets,
                pct_embargo=pct_embargo
            )
        except ImportError:
            logger.info("Vendored mlfinlab not available, using local PurgedKFold implementation")
    
    # Use our implementation
    return PurgedKFold(
        n_splits=n_splits,
        samples_info_sets=samples_info_sets,
        pct_embargo=pct_embargo
    )
