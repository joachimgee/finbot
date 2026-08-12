"""Robustesse statistique (Tier 3) — PSR / DSR / purged K-fold."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.robustness import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
    purged_kfold_indices,
    sharpe_per_period,
)


def _returns(mean: float, sd: float, n: int = 500, seed: int = 0) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(mean, sd, n))


# --- PSR ---------------------------------------------------------------------

def test_psr_high_for_strong_edge_long_sample() -> None:
    """Un Sharpe positif net sur un long échantillon -> PSR proche de 1."""
    r = _returns(0.001, 0.01, n=2000, seed=1)  # SR/j ≈ 0.1
    assert probabilistic_sharpe_ratio(r, sr_benchmark=0.0) > 0.99


def test_psr_below_half_when_sr_under_benchmark() -> None:
    """PSR < 0.5 quand le Sharpe observé est sous le repère."""
    r = _returns(0.0005, 0.01, n=800, seed=2)
    sr = sharpe_per_period(r)
    assert probabilistic_sharpe_ratio(r, sr_benchmark=sr + 0.05) < 0.5


def test_psr_degenerate_returns_zero() -> None:
    assert probabilistic_sharpe_ratio(pd.Series([0.01, 0.01])) == 0.0
    assert probabilistic_sharpe_ratio(pd.Series([0.01])) == 0.0


def test_psr_shorter_sample_less_confident() -> None:
    """Même edge par période, moins d'observations -> PSR plus faible."""
    long = probabilistic_sharpe_ratio(_returns(0.0007, 0.01, n=2000, seed=3))
    short = probabilistic_sharpe_ratio(_returns(0.0007, 0.01, n=120, seed=3))
    assert long > short


# --- Expected max Sharpe (sélection) -----------------------------------------

def test_expected_max_sharpe_grows_with_trials() -> None:
    """Plus on essaie de configs, plus le Sharpe max attendu (sous H0) est élevé."""
    e10 = expected_max_sharpe(10, sr_std=0.05)
    e1000 = expected_max_sharpe(1000, sr_std=0.05)
    assert 0 < e10 < e1000


def test_expected_max_sharpe_single_trial_is_zero() -> None:
    assert expected_max_sharpe(1, sr_std=0.05) == 0.0
    assert expected_max_sharpe(50, sr_std=0.0) == 0.0


# --- DSR ----------------------------------------------------------------------

def test_dsr_deflates_with_more_trials() -> None:
    """À Sharpe observé fixe, le DSR baisse quand le nombre d'essais augmente."""
    r = _returns(0.0006, 0.01, n=1500, seed=4)
    dsr_few, _ = deflated_sharpe_ratio(r, n_trials=5, sr_std=0.05)
    dsr_many, _ = deflated_sharpe_ratio(r, n_trials=5000, sr_std=0.05)
    assert dsr_few > dsr_many


def test_dsr_diag_exposes_benchmark_and_moments() -> None:
    r = _returns(0.0006, 0.01, n=1000, seed=5)
    dsr, diag = deflated_sharpe_ratio(r, n_trials=100, sr_std=0.05)
    assert 0.0 <= dsr <= 1.0
    assert diag["sr_benchmark"] > 0.0
    assert diag["n_trials"] == 100.0
    assert diag["n_obs"] == float(len(r))


# --- Purged & embargoed K-fold ------------------------------------------------

def test_purged_kfold_covers_all_test_indices_disjointly() -> None:
    folds = purged_kfold_indices(100, n_splits=5)
    covered = np.concatenate([test for _, test in folds])
    assert sorted(covered.tolist()) == list(range(100))  # partition exacte


def test_purged_kfold_train_excludes_purge_and_embargo() -> None:
    """L'entraînement ne contient ni le bloc test, ni sa bande de purge/embargo."""
    folds = purged_kfold_indices(100, n_splits=5, embargo=3, purge=2)
    train, test = folds[2]  # bloc test au milieu -> purge des deux côtés
    t0, t1 = test.min(), test.max()
    train_set = set(train.tolist())
    assert train_set.isdisjoint(set(test.tolist()))
    # purge à gauche/droite + embargo à droite retirés de l'entraînement.
    for i in range(t0 - 2, t1 + 1 + 2 + 3):
        assert i not in train_set


def test_purged_kfold_rejects_bad_params() -> None:
    with pytest.raises(ValueError):
        purged_kfold_indices(100, n_splits=1)
    with pytest.raises(ValueError):
        purged_kfold_indices(3, n_splits=5)
