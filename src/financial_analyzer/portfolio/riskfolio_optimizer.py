"""
Riskfolio-based Portfolio Optimization utilities.

This module wraps riskfolio-lib's Portfolio and HCPortfolio to provide
production-ready optimization workflows with robust logging and error handling.

Features
--------
- Classic mean-risk optimization with CVaR/CDaR/EVaR/etc.
- NCO (Nested Clustered Optimization) via HCPortfolio
- HRP (Hierarchical Risk Parity) via HCPortfolio
- Covariance shrinkage (Ledoit-Wolf, Oracle Approximating Shrinkage)
- Risk decomposition by asset (variance-based approximation)

Notes
-----
Tests mock riskfolio objects; no network or heavy compute is performed here.
"""

from __future__ import annotations

from typing import Dict, Optional
import sys
from pathlib import Path
import logging

import numpy as np
import pandas as pd
from sklearn.covariance import ledoit_wolf, OAS

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

def _ensure_vendor_riskfolio_on_path() -> None:
    """Ensure vendored Riskfolio-Lib is importable.

    Adds `vendor/riskfolio-lib` (or `vendor/Riskfolio-Lib`) to `sys.path` when running
    from the project workspace so that `import riskfolio` succeeds without pip install.
    """
    try:
        root = Path(__file__).resolve().parents[3]
        candidates = [
            root / "vendor" / "riskfolio-lib",
            root / "vendor" / "Riskfolio-Lib",
        ]
        for p in candidates:
            if p.exists() and str(p) not in sys.path:
                sys.path.insert(0, str(p))
    except Exception:
        # Best-effort only
        pass


try:
    from riskfolio import Portfolio, HCPortfolio  # type: ignore
except Exception:
    _ensure_vendor_riskfolio_on_path()
    try:
        from riskfolio import Portfolio, HCPortfolio  # type: ignore
    except Exception as e:  # pragma: no cover - tests will mock these classes
        Portfolio = None  # type: ignore
        HCPortfolio = None  # type: ignore
        logger.warning(
            "riskfolio-lib not available; Portfolio/HCPortfolio will be mocked in tests"
        )


class RiskfolioOptimizer:
    """Riskfolio optimizer wrapper.

    Parameters
    ----------
    returns : pd.DataFrame
        Historical returns with columns as assets and rows as dates.
    covariance_method : str, default 'ledoit_wolf'
        Covariance estimation method ('ledoit_wolf', 'oracle', 'sample').
    frequency : int, default 252
        Number of periods per year (used only for documentation/consistency).
    """

    def __init__(self, returns: pd.DataFrame, covariance_method: str = 'ledoit_wolf', frequency: int = 252) -> None:
        self.returns = returns.copy() if returns is not None else pd.DataFrame()
        self.covariance_method = covariance_method
        self.frequency = frequency

        if self.returns is None or self.returns.empty:
            logger.warning("RiskfolioOptimizer initialized with empty returns DataFrame")
        else:
            logger.info(
                f"RiskfolioOptimizer initialized with {self.returns.shape[0]} rows, "
                f"{self.returns.shape[1]} assets"
            )

    # ------------------------ Optimization Methods ------------------------ #

    def optimize_mean_cvar(
        self,
        expected_returns: Optional[pd.Series] = None,
        risk_aversion: float = 1.0,
        cvar_alpha: float = 0.05,
    ) -> pd.Series:
        """Mean-CVaR optimization using riskfolio Portfolio.

        Returns weights that sum to 1.0. On errors, returns equal-weight portfolio.

        Parameters
        ----------
        expected_returns : pd.Series, optional
            Expected returns per asset. If None, historical mean is used.
        risk_aversion : float, default 1.0
            Risk aversion parameter 'l' used in Utility objective (higher → more risk averse).
        cvar_alpha : float, default 0.05
            Significance level for CVaR risk measure.

        Returns
        -------
        pd.Series
            Optimal weights indexed by asset.
        """
        return self._classic_optimization(rm='CVaR', alpha=cvar_alpha, expected_returns=expected_returns, risk_aversion=risk_aversion)

    def optimize_mean_cdar(
        self,
        expected_returns: Optional[pd.Series] = None,
        risk_aversion: float = 1.0,
        cdar_alpha: float = 0.05,
    ) -> pd.Series:
        """Mean-CDaR optimization using riskfolio Portfolio.

        Parameters are analogous to :meth:`optimize_mean_cvar` but using CDaR.
        """
        return self._classic_optimization(rm='CDaR', alpha=cdar_alpha, expected_returns=expected_returns, risk_aversion=risk_aversion)

    def optimize_nco(
        self,
        expected_returns: Optional[pd.Series] = None,
        risk_measure: str = 'CVaR',
        linkage: str = 'ward',
    ) -> pd.Series:
        """Nested Clustered Optimization (NCO) via HCPortfolio.

        Parameters
        ----------
        expected_returns : pd.Series, optional
            Expected returns per asset; if None, historical means are used.
        risk_measure : str, default 'CVaR'
            Risk measure (e.g., 'MV', 'CVaR', 'CDaR', 'EVaR', 'RLVaR').
        linkage : str, default 'ward'
            Linkage method for hierarchical clustering.
        """
        if self.returns.empty:
            return pd.Series(dtype=float)
        try:
            hcp = HCPortfolio(returns=self.returns)  # type: ignore
            # Estimate stats
            rm = risk_measure
            cov_method = self.covariance_method
            # riskfolio calculates stats internally; we pass method strings
            hcp.assets_stats(method_mu='hist', method_cov=cov_method)
            # Optimization
            w = hcp.optimization(model='NCO', codependence='pearson', rm=rm, linkage=linkage)
            w = self._ensure_weights_series(w)
            return self._normalize_weights(w)
        except Exception as e:
            logger.error(f"NCO optimization failed: {e}")
            return self._equal_weights()

    def optimize_hrp(
        self,
        linkage: str = 'ward',
        rm: str = 'MV',
    ) -> pd.Series:
        """Hierarchical Risk Parity (HRP) via HCPortfolio.

        Parameters
        ----------
        linkage : str, default 'ward'
            Linkage method.
        rm : str, default 'MV'
            Risk measure for cluster allocation.
        """
        if self.returns.empty:
            return pd.Series(dtype=float)
        try:
            hcp = HCPortfolio(returns=self.returns)  # type: ignore
            hcp.assets_stats(method_mu='hist', method_cov=self.covariance_method)
            w = hcp.optimization(model='HRP', codependence='pearson', rm=rm, linkage=linkage)
            w = self._ensure_weights_series(w)
            return self._normalize_weights(w)
        except Exception as e:
            logger.error(f"HRP optimization failed: {e}")
            return self._equal_weights()

    # ------------------------ Analytics ------------------------ #

    def risk_decomposition(self, weights: pd.Series) -> pd.DataFrame:
        """Compute variance-based risk decomposition (MRC/RC/%).

        Uses the covariance matrix estimated with the configured method.

        Parameters
        ----------
        weights : pd.Series
            Portfolio weights indexed by asset.

        Returns
        -------
        pd.DataFrame
            Columns: 'mrc' (marginal), 'rc' (absolute), 'pct' (% of total risk).
        """
        if weights is None or len(weights) == 0:
            return pd.DataFrame(columns=['mrc', 'rc', 'pct'])

        cov = self._estimate_covariance(self.covariance_method)
        # Align to weights order
        cov = cov.loc[weights.index, weights.index]
        w = weights.values.reshape(-1, 1)
        # Marginal risk contribution for variance: Σ w
        mrc = cov.values @ w  # (n,1)
        rc = w * mrc  # (n,1)
        rc_flat = rc.flatten()
        total = float(rc_flat.sum())
        if total == 0:
            pct = np.zeros_like(rc_flat)
        else:
            pct = rc_flat / total
        df = pd.DataFrame({'mrc': mrc.flatten(), 'rc': rc_flat, 'pct': pct}, index=weights.index)
        return df

    # ------------------------ Internals ------------------------ #

    def _classic_optimization(
        self,
        rm: str,
        alpha: float,
        expected_returns: Optional[pd.Series],
        risk_aversion: float,
    ) -> pd.Series:
        if self.returns.empty:
            return pd.Series(dtype=float)
        try:
            port = Portfolio(returns=self.returns)  # type: ignore
            method_cov = self.covariance_method
            mu = expected_returns if expected_returns is not None else self.returns.mean()
            # assets_stats sets internal moments; we pass means via series overriding attr if available
            port.assets_stats(method_mu='hist', method_cov=method_cov)
            # Some versions allow setting mu directly
            try:
                setattr(port, 'mu', mu.values.reshape(-1, 1))  # type: ignore
                setattr(port, 'assets', list(mu.index))  # type: ignore
            except Exception:
                pass
            w = port.optimization(
                model='Classic',
                rm=rm,
                obj='Utility',
                rf=0.0,
                l=risk_aversion,
                a=alpha,
            )
            w = self._ensure_weights_series(w)
            return self._normalize_weights(w)
        except Exception as e:
            logger.error(f"Classic optimization ({rm}) failed: {e}")
            return self._equal_weights()

    def _estimate_covariance(self, method: str = 'ledoit_wolf') -> pd.DataFrame:
        """Estimate covariance matrix using shrinkage or sample.

        Parameters
        ----------
        method : str
            'ledoit_wolf', 'oracle' (OAS), or 'sample'.

        Returns
        -------
        pd.DataFrame
            Covariance matrix aligned to returns columns.
        """
        if self.returns.empty:
            return pd.DataFrame()

        X = self.returns.values
        cols = list(self.returns.columns)
        try:
            if method == 'ledoit_wolf':
                cov, _ = ledoit_wolf(X)
                return pd.DataFrame(cov, index=cols, columns=cols)
            if method in ('oracle', 'oas'):
                oas = OAS().fit(X)
                cov = oas.covariance_
                return pd.DataFrame(cov, index=cols, columns=cols)
            # sample
            cov = np.cov(X, rowvar=False)
            return pd.DataFrame(cov, index=cols, columns=cols)
        except Exception as e:
            logger.error(f"Covariance estimation failed (method={method}): {e}")
            # Fallback to pandas cov
            try:
                cov = self.returns.cov().values
                return pd.DataFrame(cov, index=cols, columns=cols)
            except Exception:
                return pd.DataFrame()

    def _equal_weights(self) -> pd.Series:
        if self.returns.empty:
            return pd.Series(dtype=float)
        n = self.returns.shape[1]
        w = np.ones(n) / n
        return pd.Series(w, index=self.returns.columns)

    @staticmethod
    def _ensure_weights_series(w: object) -> pd.Series:
        if isinstance(w, pd.Series):
            return w.astype(float)
        if isinstance(w, pd.DataFrame) and w.shape[1] == 1:
            return w.iloc[:, 0].astype(float)
        if isinstance(w, np.ndarray):
            if w.ndim == 2 and w.shape[1] == 1:
                w = w.ravel()
            # No index info; return generic series
            return pd.Series(w.astype(float))
        # Unknown type -> empty
        return pd.Series(dtype=float)

    @staticmethod
    def _normalize_weights(w: pd.Series) -> pd.Series:
        s = float(w.sum()) if len(w) else 0.0
        if s == 0.0:
            return w
        return (w / s).astype(float)


__all__ = ["RiskfolioOptimizer"]
