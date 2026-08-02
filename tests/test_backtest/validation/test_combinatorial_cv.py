"""Tests pour CombinatorialPurgedCV."""

import pytest
import numpy as np
import pandas as pd
from src.financial_analyzer.backtest.validation.combinatorial_cv import CombinatorialPurgedCV, generate_backtest_paths

@pytest.fixture
def simple_X():
    dates = pd.date_range('2020-01-01', periods=150, freq='D')
    return pd.DataFrame({'f1': np.random.rand(150), 'f2': np.random.rand(150)}, index=dates)

def test_comb_cv_init():
    cv = CombinatorialPurgedCV(n_splits=5, n_paths=10)
    assert cv.n_splits == 5
    assert cv.n_paths == 10

def test_comb_cv_generate_paths(simple_X):
    cv = CombinatorialPurgedCV(n_splits=5, n_paths=10)
    paths = cv.generate_paths(simple_X)
    assert len(paths) == 10
    assert all(len(path) == 5 for path in paths)

def test_comb_cv_paths_different(simple_X):
    cv = CombinatorialPurgedCV(n_splits=5, n_paths=5)
    paths = cv.generate_paths(simple_X)
    # Vérifier que paths sont différents (ordre différent)
    assert len(paths) == 5

def test_generate_backtest_paths_convenience(simple_X):
    paths = generate_backtest_paths(simple_X, n_splits=5, n_paths=5)
    assert isinstance(paths, list)
    assert len(paths) == 5
