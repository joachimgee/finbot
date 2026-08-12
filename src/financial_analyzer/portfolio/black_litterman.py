"""
Black-Litterman Model utilities.

This module implements a practical Black-Litterman blend of market equilibrium
returns with investor views (absolute and relative) and confidence weighting.

References
----------
- He, G., and Litterman, R. (1999). The Intuition Behind Black-Litterman Model Portfolios.
- Idzorek, T. (2004). A Step-By-Step Guide to the Black-Litterman Model.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class BlackLittermanModel:
    """Black-Litterman posterior returns blending prior and views.

    Parameters
    ----------
    cov_matrix : pd.DataFrame
        Covariance matrix (assets x assets).
    market_caps : pd.Series
        Market capitalization per asset (used to infer market-cap weights).
    risk_free_rate : float, default 0.02
        Annual risk-free rate used to shift prior/posterior to absolute returns.
    tau : float, default 0.05
        Scalar controlling prior uncertainty.
    """

    def __init__(self, cov_matrix: pd.DataFrame, market_caps: pd.Series, risk_free_rate: float = 0.02, tau: float = 0.05) -> None:
        self.cov = cov_matrix.copy()
        self.market_caps = market_caps.copy()
        self.rf = float(risk_free_rate)
        self.tau = float(tau)
        self._views: List[Tuple[pd.Series, float]] = []  # (P row as Series, Q scalar)
        self._conf: List[float] = []  # confidence per view in [0,1]

        # Align indices
        self.cov = self.cov.loc[self.cov.index, self.cov.columns]
        self.market_caps = self.market_caps.reindex(self.cov.columns).fillna(0.0)

        # Compute market weights
        mc_sum = float(self.market_caps.sum())
        if mc_sum <= 0:
            logger.warning("Market caps sum to zero; using equal weights for equilibrium.")
            self.market_weights = pd.Series(np.ones(len(self.cov.columns)) / len(self.cov.columns), index=self.cov.columns)
        else:
            self.market_weights = self.market_caps / mc_sum

        logger.info(
            f"BlackLittermanModel initialized with {len(self.cov.columns)} assets, tau={self.tau}, rf={self.rf}"
        )

    # ------------------------ Views API ------------------------ #

    def add_absolute_view(self, asset: str, expected_return: float, confidence: float = 1.0) -> None:
        """Add an absolute view: asset expected return equals X.

        Parameters
        ----------
        asset : str
            Asset identifier (must be in covariance columns).
        expected_return : float
            Expected return for the asset.
        confidence : float, default 1.0
            Confidence weight in (0,1]. Higher means stronger view.
        """
        self._validate_asset(asset)
        p = pd.Series(0.0, index=self.cov.columns)
        p[asset] = 1.0
        self._views.append((p, float(expected_return)))
        self._conf.append(float(np.clip(confidence, 1e-3, 1.0)))

    def add_relative_view(self, asset1: str, asset2: str, outperformance: float, confidence: float = 1.0) -> None:
        """Add a relative view: asset1 outperforms asset2 by a margin.

        Parameters
        ----------
        asset1 : str
            First asset (positive coefficient).
        asset2 : str
            Second asset (negative coefficient).
        outperformance : float
            Expected (asset1 - asset2) return.
        confidence : float, default 1.0
            Confidence in (0,1].
        """
        self._validate_asset(asset1)
        self._validate_asset(asset2)
        p = pd.Series(0.0, index=self.cov.columns)
        p[asset1] = 1.0
        p[asset2] = -1.0
        self._views.append((p, float(outperformance)))
        self._conf.append(float(np.clip(confidence, 1e-3, 1.0)))

    # ------------------------ Posterior ------------------------ #

    def get_posterior_returns(self) -> pd.Series:
        """Compute posterior expected returns (annualized absolute returns).

        Returns
        -------
        pd.Series
            Posterior expected returns indexed by asset, same order as cov.
        """
        # Prior (equilibrium) excess returns via reverse optimization.
        # We adopt a practical delta=1 for implied returns: pi = Σ w_mkt.
        pi_excess = self.cov.values @ self.market_weights.values  # shape (n,)
        pi_excess = pd.Series(pi_excess, index=self.cov.columns)

        if len(self._views) == 0:
            # Return rf + equilibrium excess
            return (pi_excess + self.rf).astype(float)

        # Build P (k x n) and Q (k,) and Omega (k x k)
        P = np.vstack([p.values for (p, _) in self._views])
        Q = np.array([q for (_, q) in self._views], dtype=float)
        tauSigma = self.tau * self.cov.values
        # Confidence-weighted Omega: diag(diag(P τΣ Pᵀ) / conf)
        diag_base = np.diag(P @ tauSigma @ P.T)
        conf = np.array(self._conf, dtype=float)
        Omega = np.diag(diag_base / np.clip(conf, 1e-3, 1.0))

        # Posterior mean of excess returns
        # μ = pi + τΣ Pᵀ (P τΣ Pᵀ + Ω)^{-1} (Q - P pi)
        try:
            middle = np.linalg.inv(P @ tauSigma @ P.T + Omega)
        except np.linalg.LinAlgError:
            middle = np.linalg.pinv(P @ tauSigma @ P.T + Omega)
        adjust = tauSigma @ P.T @ (middle @ (Q - (P @ pi_excess.values)))
        mu_excess_post = pi_excess.values + adjust
        mu_post = pd.Series(mu_excess_post + self.rf, index=self.cov.columns)
        return mu_post.astype(float)

    # ------------------------ Helpers ------------------------ #

    def _validate_asset(self, asset: str) -> None:
        if asset not in self.cov.columns:
            raise ValueError(f"Invalid asset in view: {asset}")


__all__ = ["BlackLittermanModel"]
