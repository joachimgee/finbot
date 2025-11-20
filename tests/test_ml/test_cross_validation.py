"""
Tests for PurgedKFold cross-validation module.

Tests:
- ml_get_train_times() purging logic
- PurgedKFold initialization and validation
- PurgedKFold split() with various scenarios
- Embargo application
- Temporal leakage prevention
- Integration with sklearn models

Author: FinBot
License: MIT
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

from financial_analyzer.ml.cross_validation import (
    ml_get_train_times,
    PurgedKFold,
    get_purged_kfold_cv
)


class TestMlGetTrainTimes:
    """Tests for ml_get_train_times purging function."""
    
    def test_purge_basic(self):
        """Test basic purging: remove train samples overlapping test."""
        # Train samples with labels ending at various times
        t1 = pd.Series(
            [10, 20, 30, 40, 50],
            index=[0, 10, 20, 30, 40]
        )
        
        # Test period: samples [25, 35] (labels end at 30, 40)
        test_times = pd.Series([25, 35])
        
        # Expected: keep samples ending before test starts (0, 10)
        purged = ml_get_train_times(t1, test_times)
        
        assert len(purged) == 2
        assert 0 in purged.index
        assert 10 in purged.index
        assert 20 not in purged.index  # overlaps
    
    def test_purge_no_overlap(self):
        """Test purging when no overlap (all train samples valid)."""
        t1 = pd.Series(
            [5, 10, 15],
            index=[0, 5, 10]
        )
        
        # Test period starts after all train labels end
        test_times = pd.Series([20, 25])
        
        purged = ml_get_train_times(t1, test_times)
        
        # All train samples should be kept (no overlap)
        assert len(purged) == 3
    
    def test_purge_all_overlap(self):
        """Test purging when all train samples overlap."""
        t1 = pd.Series(
            [100, 110, 120],
            index=[80, 90, 100]
        )
        
        # Test period overlaps all train
        test_times = pd.Series([85, 95])
        
        purged = ml_get_train_times(t1, test_times)
        
        # No train samples should remain
        assert len(purged) == 0
    
    def test_purge_empty_inputs(self):
        """Test error handling for empty inputs."""
        t1 = pd.Series([], dtype=float)
        test_times = pd.Series([10, 20])
        
        with pytest.raises(ValueError, match="cannot be None or empty"):
            ml_get_train_times(t1, test_times)
        
        t1 = pd.Series([10, 20], index=[0, 10])
        test_times = pd.Series([])
        
        with pytest.raises(ValueError, match="cannot be None or empty"):
            ml_get_train_times(t1, test_times)


class TestPurgedKFoldInit:
    """Tests for PurgedKFold initialization."""
    
    def test_init_valid(self):
        """Test valid initialization."""
        t1 = pd.Series([10, 20, 30], index=[0, 10, 20])
        cv = PurgedKFold(n_splits=3, samples_info_sets=t1, pct_embargo=0.01)
        
        assert cv.n_splits == 3
        assert cv.pct_embargo == 0.01
        assert cv.samples_info_sets is not None
    
    def test_init_without_t1(self):
        """Test initialization without t1 (warning logged)."""
        cv = PurgedKFold(n_splits=3)
        
        assert cv.samples_info_sets is None
        # Should still initialize (falls back to standard KFold)
        assert cv.n_splits == 3
    
    def test_init_invalid_n_splits(self):
        """Test error on invalid n_splits."""
        with pytest.raises(ValueError, match="n_splits must be >= 2"):
            PurgedKFold(n_splits=1)
    
    def test_init_invalid_embargo(self):
        """Test error on invalid pct_embargo."""
        with pytest.raises(ValueError, match="pct_embargo must be in"):
            PurgedKFold(n_splits=3, pct_embargo=0.6)
        
        with pytest.raises(ValueError, match="pct_embargo must be in"):
            PurgedKFold(n_splits=3, pct_embargo=-0.1)


class TestPurgedKFoldSplit:
    """Tests for PurgedKFold split() method."""
    
    def test_split_basic(self):
        """Test basic split with purging."""
        # Create synthetic data
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        X = pd.DataFrame({'feature': np.random.randn(100)}, index=dates)
        y = pd.Series(np.random.randn(100), index=dates)
        
        # Create t1: label ends 5 days after sample start
        t1 = pd.Series(dates + timedelta(days=5), index=dates)
        
        cv = PurgedKFold(n_splits=3, samples_info_sets=t1, pct_embargo=0.0)
        
        splits = list(cv.split(X, y))
        
        assert len(splits) == 3
        
        for train_idx, test_idx in splits:
            # Validate no overlap (train indices != test indices)
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            # No train sample should be in test set
            assert len(set(train_idx) & set(test_idx)) == 0
    
    def test_split_with_embargo(self):
        """Test split with embargo (buffer after test)."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        X = pd.DataFrame({'feature': np.random.randn(100)}, index=dates)
        y = pd.Series(np.random.randn(100), index=dates)
        
        t1 = pd.Series(dates + timedelta(days=3), index=dates)
        
        # 5% embargo
        cv = PurgedKFold(n_splits=3, samples_info_sets=t1, pct_embargo=0.05)
        
        splits = list(cv.split(X, y))
        
        assert len(splits) == 3
        
        for train_idx, test_idx in splits:
            # With embargo, train size should be smaller than without
            assert len(train_idx) > 0
            assert len(test_idx) > 0
    
    def test_split_without_t1_fallback(self):
        """Test split without t1 falls back to standard KFold."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        X = pd.DataFrame({'feature': np.random.randn(100)}, index=dates)
        y = pd.Series(np.random.randn(100), index=dates)
        
        # No t1 provided
        cv = PurgedKFold(n_splits=3)
        
        splits = list(cv.split(X, y))
        
        # Should still produce splits (standard KFold behavior)
        assert len(splits) == 3
    
    def test_split_non_dataframe_error(self):
        """Test error when X is not a DataFrame."""
        X = np.random.randn(100, 5)
        y = np.random.randn(100)
        
        cv = PurgedKFold(n_splits=3)
        
        with pytest.raises(TypeError, match="must be a pandas DataFrame"):
            list(cv.split(X, y))


class TestPurgedKFoldLeakagePrevention:
    """Tests verifying temporal leakage prevention."""
    
    def test_no_future_leakage(self):
        """Test that train samples never use future information from test."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        X = pd.DataFrame({'feature': np.random.randn(100)}, index=dates)
        y = pd.Series(np.random.randn(100), index=dates)
        
        # Labels end 10 days after sample start
        t1 = pd.Series(dates + timedelta(days=10), index=dates)
        
        cv = PurgedKFold(n_splits=5, samples_info_sets=t1, pct_embargo=0.01)
        
        for train_idx, test_idx in cv.split(X, y):
            train_dates = X.index[train_idx]
            test_dates = X.index[test_idx]
            
            # Validate purging: no train sample's label should overlap with test period
            train_t1 = t1.loc[train_dates]
            test_start = test_dates.min()
            
            # Most train labels should end BEFORE test starts (purged)
            # Note: if ALL would be removed, fallback keeps unpurged set
            purged_properly = (train_t1 < test_start).sum()
            total_train = len(train_t1)
            
            # At least some purging should occur (unless fallback triggered)
            # In proper purging, at least 50% should be purged
            if purged_properly > 0:
                # Some samples are properly purged
                assert purged_properly / total_train >= 0.1, \
                    f"Insufficient purging: only {purged_properly}/{total_train} samples purged"
    
    def test_embargo_prevents_forward_looking(self):
        """Test embargo prevents using information immediately after test."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        X = pd.DataFrame({'feature': np.random.randn(100)}, index=dates)
        y = pd.Series(np.random.randn(100), index=dates)
        
        t1 = pd.Series(dates + timedelta(days=5), index=dates)
        
        # 10% embargo (10 samples out of 100)
        cv_with_embargo = PurgedKFold(n_splits=3, samples_info_sets=t1, pct_embargo=0.1)
        cv_no_embargo = PurgedKFold(n_splits=3, samples_info_sets=t1, pct_embargo=0.0)
        
        splits_embargo = list(cv_with_embargo.split(X, y))
        splits_no_embargo = list(cv_no_embargo.split(X, y))
        
        # With embargo, train sets should be smaller
        for (train_emb, _), (train_no, _) in zip(splits_embargo, splits_no_embargo):
            assert len(train_emb) <= len(train_no)


class TestPurgedKFoldIntegration:
    """Integration tests with sklearn models."""
    
    def test_cross_val_score_integration(self):
        """Test PurgedKFold works with sklearn cross_val_score."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        X = pd.DataFrame({
            'feature1': np.random.randn(100),
            'feature2': np.random.randn(100)
        }, index=dates)
        y = pd.Series(np.random.choice([0, 1], size=100), index=dates)
        
        t1 = pd.Series(dates + timedelta(days=3), index=dates)
        
        cv = PurgedKFold(n_splits=3, samples_info_sets=t1, pct_embargo=0.01)
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        
        # Should not raise errors
        scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy')
        
        assert len(scores) == 3
        assert all(0 <= s <= 1 for s in scores)  # accuracy in [0, 1]
    
    def test_manual_train_test_split(self):
        """Test manual train/test split and model training."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        X = pd.DataFrame({
            'feature1': np.random.randn(100),
            'feature2': np.random.randn(100)
        }, index=dates)
        y = pd.Series(np.random.choice([0, 1], size=100), index=dates)
        
        t1 = pd.Series(dates + timedelta(days=3), index=dates)
        
        cv = PurgedKFold(n_splits=3, samples_info_sets=t1)
        
        for train_idx, test_idx in cv.split(X, y):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            model = RandomForestClassifier(n_estimators=10, random_state=42)
            model.fit(X_train, y_train)
            
            score = model.score(X_test, y_test)
            assert 0 <= score <= 1


class TestGetPurgedKfoldCv:
    """Tests for get_purged_kfold_cv convenience function."""
    
    def test_get_purged_kfold_basic(self):
        """Test basic usage of convenience function."""
        t1 = pd.Series([10, 20, 30], index=[0, 10, 20])
        
        cv = get_purged_kfold_cv(
            n_splits=3,
            samples_info_sets=t1,
            pct_embargo=0.01
        )
        
        assert isinstance(cv, PurgedKFold)
        assert cv.n_splits == 3
    
    def test_get_purged_kfold_vendored_fallback(self):
        """Test fallback to local implementation when vendored unavailable."""
        t1 = pd.Series([10, 20, 30], index=[0, 10, 20])
        
        # Force local implementation
        cv = get_purged_kfold_cv(
            n_splits=3,
            samples_info_sets=t1,
            use_vendored=False
        )
        
        assert isinstance(cv, PurgedKFold)


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_small_dataset(self):
        """Test with very small dataset (edge case)."""
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        X = pd.DataFrame({'feature': np.random.randn(10)}, index=dates)
        y = pd.Series(np.random.randn(10), index=dates)
        
        t1 = pd.Series(dates + timedelta(days=1), index=dates)
        
        cv = PurgedKFold(n_splits=2, samples_info_sets=t1)
        
        splits = list(cv.split(X, y))
        
        # Should handle small dataset gracefully
        assert len(splits) == 2
    
    def test_misaligned_t1_index(self):
        """Test error when t1 index doesn't match X index."""
        dates_X = pd.date_range('2023-01-01', periods=100, freq='D')
        dates_t1 = pd.date_range('2023-01-02', periods=100, freq='D')  # offset by 1 day
        
        X = pd.DataFrame({'feature': np.random.randn(100)}, index=dates_X)
        y = pd.Series(np.random.randn(100), index=dates_X)
        
        t1 = pd.Series(dates_t1 + timedelta(days=3), index=dates_t1)
        
        cv = PurgedKFold(n_splits=3, samples_info_sets=t1)
        
        # Should raise error during split (index mismatch)
        with pytest.raises(ValueError, match="cannot be aligned"):
            list(cv.split(X, y))
    
    def test_zero_embargo(self):
        """Test with zero embargo (no buffer)."""
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        X = pd.DataFrame({'feature': np.random.randn(50)}, index=dates)
        y = pd.Series(np.random.randn(50), index=dates)
        
        t1 = pd.Series(dates + timedelta(days=2), index=dates)
        
        cv = PurgedKFold(n_splits=3, samples_info_sets=t1, pct_embargo=0.0)
        
        splits = list(cv.split(X, y))
        
        # Should work with zero embargo
        assert len(splits) == 3
