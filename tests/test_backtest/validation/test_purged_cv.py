"""Tests pour PurgedKFold."""

import pytest
import numpy as np
import pandas as pd
from src.financial_analyzer.backtest.validation.purged_cv import PurgedKFold, purged_kfold_split

@pytest.fixture
def simple_X():
    dates = pd.date_range('2020-01-01', periods=200, freq='D')
    return pd.DataFrame({'feature1': np.random.rand(200), 'feature2': np.random.rand(200)}, index=dates)

@pytest.fixture
def timestamps():
    dates = pd.date_range('2020-01-01', periods=200, freq='D')
    return pd.Series(dates, index=dates)

def test_purged_kfold_init():
    cv = PurgedKFold(n_splits=5, pct_embargo=0.01)
    assert cv.n_splits == 5
    assert cv.pct_embargo == 0.01

def test_purged_kfold_invalid_n_splits():
    with pytest.raises(ValueError, match="n_splits"):
        PurgedKFold(n_splits=1)

def test_purged_kfold_invalid_embargo():
    with pytest.raises(ValueError, match="pct_embargo"):
        PurgedKFold(n_splits=5, pct_embargo=1.5)

def test_purged_kfold_split_basic(simple_X):
    cv = PurgedKFold(n_splits=5)
    splits = list(cv.split(simple_X))
    assert len(splits) == 5

def test_purged_kfold_split_lengths(simple_X):
    cv = PurgedKFold(n_splits=5, pct_embargo=0.01)
    train_idx, test_idx = next(cv.split(simple_X))
    # Train + test peuvent égaler total si embargo est petit
    assert len(train_idx) > 0 and len(test_idx) > 0

def test_purged_kfold_no_overlap(simple_X):
    cv = PurgedKFold(n_splits=5)
    for train_idx, test_idx in cv.split(simple_X):
        assert len(set(train_idx) & set(test_idx)) == 0  # No overlap

def test_purged_kfold_with_timestamps(simple_X, timestamps):
    cv = PurgedKFold(n_splits=5, purge_method='timestamps')
    splits = list(cv.split(simple_X, timestamps))
    assert len(splits) == 5

def test_purged_kfold_get_n_splits():
    cv = PurgedKFold(n_splits=5)
    assert cv.get_n_splits() == 5

def test_purged_kfold_split_convenience(simple_X):
    splits = purged_kfold_split(simple_X, n_splits=5, pct_embargo=0.02)
    assert isinstance(splits, list)
    assert len(splits) == 5
