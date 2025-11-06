"""Feature importance utilities for ML models.

This module provides a simple permutation importance implementation that works
with any sklearn-compatible estimator exposing .score(X, y).
"""
from __future__ import annotations

from typing import Dict
import numpy as np
import pandas as pd


class FeatureImportance:
    """Analyze feature importance via permutation importance.

    Example:
        >>> fi = FeatureImportance(model, X, y)
        >>> importances = fi.permutation_importance()
    """

    def __init__(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        random_state: int | np.random.Generator | None = 42,
    ) -> None:
        """Initialize with trained model and data.

        Args:
            model: Estimator implementing .score(X, y)
            X: Feature matrix (n_samples, n_features)
            y: Target values (n_samples,)
            random_state: Seed or Generator for reproducible shuffles
        """
        if X.ndim != 2:
            raise ValueError("X must be 2D array [n_samples, n_features]")
        if y.ndim != 1:
            raise ValueError("y must be 1D array [n_samples]")
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y must have the same number of samples")
        self.model = model
        self.X = X
        self.y = y
        # Initialize RNG
        if isinstance(random_state, np.random.Generator):
            self.rng = random_state
        else:
            self.rng = np.random.default_rng(random_state if random_state is not None else None)

    def permutation_importance(self, n_repeats: int = 10) -> Dict[str, float]:
        """Calculate permutation importance for each feature.

        Args:
            n_repeats: Number of permutations per feature

        Returns:
            Mapping feature_name -> importance score
        """
        baseline = float(self.model.score(self.X, self.y))
        importances: Dict[str, float] = {}
        n_features = self.X.shape[1]
        for col_idx in range(n_features):
            scores = []
            for _ in range(n_repeats):
                X_perm = self.X.copy()
                self.rng.shuffle(X_perm[:, col_idx])
                score = float(self.model.score(X_perm, self.y))
                scores.append(baseline - score)
            importances[f"Feature_{col_idx}"] = float(np.mean(scores))
        return importances
