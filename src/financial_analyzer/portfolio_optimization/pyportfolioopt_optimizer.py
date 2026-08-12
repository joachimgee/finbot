"""
PyPortfolioOpt integration for FinBot.

Provides classical mean-variance optimization using PyPortfolioOpt library
as an alternative backend to the internal MV optimizer and Riskfolio-Lib.

Features:
- Max Sharpe optimization
- Min Volatility optimization
- Efficient Frontier calculation
- Black-Litterman views
- Discrete allocation
- Integration with PortfolioConstraints

References:
- PyPortfolioOpt docs: https://pyportfolioopt.readthedocs.io/
- archive/FORKS_INTEGRATION_PLAN.md section PyPortfolioOpt

Example:
    >>> import pandas as pd
    >>> from financial_analyzer.portfolio_optimization.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
    >>> prices = pd.DataFrame(...)  # Historical prices
    >>> opt = PyPortfolioOptOptimizer(prices)
    >>> weights = opt.optimize_max_sharpe()
    >>> print(weights)
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, Union, List
import logging

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.portfolio.constraints import PortfolioConstraints

logger = get_logger(__name__)

try:
    from pypfopt import expected_returns, risk_models, EfficientFrontier, BlackLittermanModel
    from pypfopt import objective_functions
    from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices
except ImportError:  # pragma: no cover
    expected_returns = None  # type: ignore
    risk_models = None  # type: ignore
    EfficientFrontier = None  # type: ignore
    BlackLittermanModel = None  # type: ignore
    DiscreteAllocation = None  # type: ignore
    get_latest_prices = None  # type: ignore
    logger.warning(
        "PyPortfolioOpt not available at import time; install with: pip install PyPortfolioOpt"
    )


class PyPortfolioOptOptimizer:
    """
    PyPortfolioOpt-based portfolio optimizer.

    Provides classical mean-variance optimization with PyPortfolioOpt as backend.
    Interfaces are compatible with FinBot's PortfolioConstraints and return
    normalized weights as pd.Series.

    Parameters
    ----------
    prices : pd.DataFrame
        Historical prices with DatetimeIndex and tickers as columns.
    risk_free_rate : float, default 0.02
        Annual risk-free rate for Sharpe calculation.
    frequency : int, default 252
        Number of periods per year for annualization.
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        risk_free_rate: float = 0.02,
        frequency: int = 252,
    ) -> None:
        if prices is None or prices.empty:
            raise ValueError("prices must be a non-empty DataFrame")
        if not isinstance(prices.index, pd.DatetimeIndex):
            logger.warning("prices index is not DatetimeIndex; annualization may be incorrect")

        self.prices = prices.copy()
        self.tickers = list(prices.columns)
        self.risk_free_rate = float(risk_free_rate)
        self.frequency = int(frequency)

        logger.info(
            f"PyPortfolioOptOptimizer initialized with {len(self.tickers)} assets, "
            f"rf={self.risk_free_rate:.4f}"
        )

    # ======================== Optimization Methods ========================

    def optimize_max_sharpe(
        self,
        method: str = "mean_historical_return",
        cov_method: str = "sample_cov",
        constraints: Optional[PortfolioConstraints] = None,
    ) -> pd.Series:
        """
        Maximize Sharpe ratio.

        Parameters
        ----------
        method : str, default 'mean_historical_return'
            Expected returns method: 'mean_historical_return', 'ema_historical_return', 'capm_return'.
        cov_method : str, default 'sample_cov'
            Covariance method: 'sample_cov', 'semicovariance', 'exp_cov', 'ledoit_wolf', 'oracle_approximating'.
        constraints : PortfolioConstraints, optional
            Constraints to apply (bounds, sector limits, etc.)

        Returns
        -------
        pd.Series
            Optimal weights indexed by ticker, sum=1.0.
        """
        mu = self._expected_returns(method)
        S = self._covariance_matrix(cov_method)
        bounds = self._get_bounds(constraints)

        ef = EfficientFrontier(mu, S, weight_bounds=bounds)

        # Apply sector constraints if provided
        if constraints and constraints.sector_limits:
            self._apply_sector_constraints(ef, constraints)

        # Optimize
        weights = ef.max_sharpe(risk_free_rate=self.risk_free_rate)
        clean_weights = ef.clean_weights()

        return self._series_from_dict(clean_weights)

    def optimize_min_volatility(
        self,
        cov_method: str = "sample_cov",
        constraints: Optional[PortfolioConstraints] = None,
    ) -> pd.Series:
        """
        Minimize portfolio volatility.

        Parameters
        ----------
        cov_method : str, default 'sample_cov'
            Covariance method.
        constraints : PortfolioConstraints, optional
            Constraints to apply.

        Returns
        -------
        pd.Series
            Optimal weights, sum=1.0.
        """
        # Min vol doesn't need expected returns
        S = self._covariance_matrix(cov_method)
        bounds = self._get_bounds(constraints)

        # Dummy mu (PyPortfolioOpt requires it even for min_vol)
        mu = pd.Series(np.ones(len(self.tickers)), index=self.tickers)

        ef = EfficientFrontier(mu, S, weight_bounds=bounds)

        if constraints and constraints.sector_limits:
            self._apply_sector_constraints(ef, constraints)

        weights = ef.min_volatility()
        clean_weights = ef.clean_weights()

        return self._series_from_dict(clean_weights)

    def optimize_efficient_return(
        self,
        target_return: float,
        method: str = "mean_historical_return",
        cov_method: str = "sample_cov",
        constraints: Optional[PortfolioConstraints] = None,
        l2_reg: float = 0.0,
    ) -> pd.Series:
        """
        Optimize for minimum volatility given a target expected return.

        Args:
            target_return: Target annualized expected return (e.g., 0.10 for 10%).
            method: Expected returns method.
            cov_method: Covariance method.
            constraints: PortfolioConstraints to apply.
            l2_reg: Non-negative L2 regularization strength.

        Returns:
            Optimal weights as pd.Series.
        """
        mu = self._expected_returns(method)
        S = self._covariance_matrix(cov_method)
        bounds = self._get_bounds(constraints)

        ef = EfficientFrontier(mu, S, weight_bounds=bounds)
        if l2_reg and l2_reg > 0:
            ef.add_objective(objective_functions.L2_reg, gamma=float(l2_reg))
        if constraints and constraints.sector_limits:
            self._apply_sector_constraints(ef, constraints)

        ef.efficient_return(target_return=float(target_return), market_neutral=False)
        clean_weights = ef.clean_weights()
        return self._series_from_dict(clean_weights)

    def optimize_efficient_risk(
        self,
        target_volatility: float,
        method: str = "mean_historical_return",
        cov_method: str = "sample_cov",
        constraints: Optional[PortfolioConstraints] = None,
        l2_reg: float = 0.0,
    ) -> pd.Series:
        """
        Optimize for maximum return given a target volatility.

        Args:
            target_volatility: Target annualized volatility (e.g., 0.15 for 15%).
            method: Expected returns method.
            cov_method: Covariance method.
            constraints: PortfolioConstraints to apply.
            l2_reg: Non-negative L2 regularization strength.

        Returns:
            Optimal weights as pd.Series.
        """
        mu = self._expected_returns(method)
        S = self._covariance_matrix(cov_method)
        bounds = self._get_bounds(constraints)

        ef = EfficientFrontier(mu, S, weight_bounds=bounds)
        if l2_reg and l2_reg > 0:
            ef.add_objective(objective_functions.L2_reg, gamma=float(l2_reg))
        if constraints and constraints.sector_limits:
            self._apply_sector_constraints(ef, constraints)

        ef.efficient_risk(target_volatility=float(target_volatility), market_neutral=False)
        clean_weights = ef.clean_weights()
        return self._series_from_dict(clean_weights)

    def optimize_max_quadratic_utility(
        self,
        method: str = "mean_historical_return",
        cov_method: str = "sample_cov",
        risk_aversion: float = 1.0,
        constraints: Optional[PortfolioConstraints] = None,
        l2_reg: float = 0.0,
    ) -> pd.Series:
        """
        Maximize mean-variance (quadratic) utility: mu^T w - (risk_aversion/2) * w^T S w.

        Useful alternative to max Sharpe, especially when RF is ambiguous.
        """
        mu = self._expected_returns(method)
        S = self._covariance_matrix(cov_method)
        bounds = self._get_bounds(constraints)

        ef = EfficientFrontier(mu, S, weight_bounds=bounds)
        if l2_reg and l2_reg > 0:
            ef.add_objective(objective_functions.L2_reg, gamma=float(l2_reg))
        if constraints and constraints.sector_limits:
            self._apply_sector_constraints(ef, constraints)

        ef.max_quadratic_utility(risk_aversion=float(risk_aversion))
        clean_weights = ef.clean_weights()
        return self._series_from_dict(clean_weights)

    def optimize_black_litterman(
        self,
        views: Dict[str, float],
        view_confidences: Optional[Dict[str, float]] = None,
        cov_method: str = "sample_cov",
        market_caps: Optional[Dict[str, float]] = None,
        risk_aversion: float = 1.0,
        constraints: Optional[PortfolioConstraints] = None,
    ) -> pd.Series:
        """
        Black-Litterman optimization with investor views.

        Parameters
        ----------
        views : dict
            Absolute views: {ticker: expected_return}.
        view_confidences : dict, optional
            Confidence in each view (0 to 1). If None, equal confidence.
        cov_method : str, default 'sample_cov'
            Covariance method.
        market_caps : dict, optional
            Market capitalizations for prior. If None, equal-weighted prior.
        risk_aversion : float, default 1.0
            Risk aversion parameter.
        constraints : PortfolioConstraints, optional
            Constraints to apply.

        Returns
        -------
        pd.Series
            Posterior optimal weights, sum=1.0.
        """
        S = self._covariance_matrix(cov_method)

        # Market caps for prior
        if market_caps is None:
            market_caps = {t: 1.0 for t in self.tickers}

        # Build BL model
        bl = BlackLittermanModel(
            cov_matrix=S,
            absolute_views=views,
            pi="market",
            market_caps=market_caps,
            risk_aversion=risk_aversion,
        )

        if view_confidences:
            # Construct omega (view uncertainty) from confidences
            # PyPortfolioOpt expects omega to be set before bl_returns()
            # Omega must be a diagonal matrix or scalar
            omega_dict = {}
            for ticker, conf in view_confidences.items():
                if ticker in views:
                    # Lower confidence → higher uncertainty
                    omega_dict[ticker] = (1.0 - conf) * S.loc[ticker, ticker]
            
            # Convert to DataFrame for diagonal matrix
            omega_df = pd.DataFrame(0.0, index=list(views.keys()), columns=list(views.keys()))
            for ticker, val in omega_dict.items():
                omega_df.loc[ticker, ticker] = val
            
            bl.omega = omega_df

        # Get posterior estimates
        mu_bl = bl.bl_returns()
        S_bl = bl.bl_cov()

        bounds = self._get_bounds(constraints)
        ef = EfficientFrontier(mu_bl, S_bl, weight_bounds=bounds)

        if constraints and constraints.sector_limits:
            self._apply_sector_constraints(ef, constraints)

        weights = ef.max_sharpe(risk_free_rate=self.risk_free_rate)
        clean_weights = ef.clean_weights()

        return self._series_from_dict(clean_weights)

    def calculate_efficient_frontier(
        self,
        num_portfolios: int = 100,
        method: str = "mean_historical_return",
        cov_method: str = "sample_cov",
        constraints: Optional[PortfolioConstraints] = None,
    ) -> pd.DataFrame:
        """
        Compute efficient frontier portfolios.

        Parameters
        ----------
        num_portfolios : int, default 100
            Number of portfolios on the frontier.
        method : str
            Expected returns method.
        cov_method : str
            Covariance method.
        constraints : PortfolioConstraints, optional
            Constraints to apply.

        Returns
        -------
        pd.DataFrame
            Columns: ['return', 'volatility', 'sharpe', 'weights'].
        """
        mu = self._expected_returns(method)
        S = self._covariance_matrix(cov_method)
        bounds = self._get_bounds(constraints)

        min_ret = float(mu.min())
        max_ret = float(mu.max())
        target_returns = np.linspace(min_ret, max_ret, num_portfolios)

        results = []
        for target in target_returns:
            try:
                ef = EfficientFrontier(mu, S, weight_bounds=bounds)

                if constraints and constraints.sector_limits:
                    self._apply_sector_constraints(ef, constraints)

                # Efficient return for target
                ef.efficient_return(target_return=target, market_neutral=False)
                clean_weights = ef.clean_weights()
                w = self._series_from_dict(clean_weights)

                perf = ef.portfolio_performance(verbose=False, risk_free_rate=self.risk_free_rate)
                exp_return, volatility, sharpe = perf

                results.append({
                    'return': float(exp_return),
                    'volatility': float(volatility),
                    'sharpe': float(sharpe),
                    'weights': w,
                })

            except Exception as e:
                logger.debug(f"Efficient frontier point failed at target {target:.4f}: {e}")

        df = pd.DataFrame(results)
        if not df.empty:
            df = df.sort_values(by='return').reset_index(drop=True)
            # Enforce monotonic volatility
            df['volatility'] = df['volatility'].cummax()

        return df

    def discrete_allocation(
        self,
        weights: pd.Series,
        total_portfolio_value: float,
    ) -> Tuple[Dict[str, int], float]:
        """
        Compute discrete share allocation from continuous weights.

        Parameters
        ----------
        weights : pd.Series
            Continuous portfolio weights (sum=1).
        total_portfolio_value : float
            Total portfolio value in currency.

        Returns
        -------
        allocation : dict
            {ticker: number_of_shares}.
        leftover : float
            Leftover cash after allocation.
        """
        latest_prices = get_latest_prices(self.prices)
        da = DiscreteAllocation(weights.to_dict(), latest_prices, total_portfolio_value=total_portfolio_value)
        allocation, leftover = da.lp_portfolio()

        logger.info(f"Discrete allocation: {allocation}, leftover={leftover:.2f}")
        return allocation, leftover

    def portfolio_performance(
        self,
        weights: pd.Series,
        method: str = "mean_historical_return",
        cov_method: str = "sample_cov",
    ) -> Tuple[float, float, float]:
        """
        Compute portfolio performance (expected return, volatility, Sharpe) for given weights.
        Returns annualized metrics based on the optimizer frequency and risk-free rate.
        """
        w = self._align_weights(weights)
        mu = self._expected_returns(method)
        S = self._covariance_matrix(cov_method)
        exp_return = float(np.dot(w.values, mu.values))
        variance = float(np.dot(w.values, S.values @ w.values))
        volatility = float(np.sqrt(max(variance, 0.0)))
        sharpe = (exp_return - self.risk_free_rate) / volatility if volatility > 0 else np.nan
        return exp_return, volatility, sharpe

    def risk_contributions(
        self,
        weights: pd.Series,
        cov_method: str = "sample_cov",
    ) -> pd.DataFrame:
        """
        Compute marginal and percentage risk contributions of each asset.
        Returns a DataFrame with columns: ['marginal', 'contribution', 'percentage'].
        """
        w = self._align_weights(weights)
        S = self._covariance_matrix(cov_method)
        port_var = float(np.dot(w.values, S.values @ w.values))
        if port_var <= 0:
            marginal = S @ w
            rc = w * 0.0
            pct = w * 0.0
        else:
            sigma = float(np.sqrt(port_var))
            marginal = pd.Series(S.values @ w.values, index=w.index) / sigma
            rc = w * marginal
            pct = rc / rc.sum() if rc.sum() != 0 else rc * 0.0
        df = pd.DataFrame({
            'marginal': marginal.astype(float),
            'contribution': rc.astype(float),
            'percentage': pct.astype(float),
        })
        return df

    def turnover(
        self,
        prev_weights: pd.Series,
        new_weights: pd.Series,
        one_way: bool = True,
    ) -> float:
        """
        Compute turnover between two weight vectors.
        If one_way=True, returns 0.5 * sum(|delta|) (one-way turnover); else full sum(|delta|).
        """
        pw = self._align_weights(prev_weights).fillna(0.0)
        nw = self._align_weights(new_weights).fillna(0.0)
        delta = (nw - pw).abs().sum()
        return float(0.5 * delta) if one_way else float(delta)

    # ======================== Internal Helpers ========================

    def _expected_returns(self, method: str) -> pd.Series:
        """Compute expected returns via PyPortfolioOpt methods."""
        if method == "mean_historical_return":
            mu = expected_returns.mean_historical_return(self.prices, frequency=self.frequency)
        elif method == "ema_historical_return":
            mu = expected_returns.ema_historical_return(self.prices, frequency=self.frequency)
        elif method == "capm_return":
            # Requires market prices; default to mean if unavailable
            logger.warning("capm_return requires market prices; falling back to mean_historical_return")
            mu = expected_returns.mean_historical_return(self.prices, frequency=self.frequency)
        else:
            raise ValueError(f"Unknown expected returns method: {method}")

        return mu

    def _covariance_matrix(self, method: str) -> pd.DataFrame:
        """Compute covariance via PyPortfolioOpt methods."""
        if method == "sample_cov":
            S = risk_models.sample_cov(self.prices, frequency=self.frequency)
        elif method == "semicovariance":
            S = risk_models.semicovariance(self.prices, frequency=self.frequency)
        elif method == "exp_cov":
            S = risk_models.exp_cov(self.prices, frequency=self.frequency)
        elif method == "ledoit_wolf":
            S = risk_models.CovarianceShrinkage(self.prices, frequency=self.frequency).ledoit_wolf()
        elif method == "oracle_approximating":
            S = risk_models.CovarianceShrinkage(self.prices, frequency=self.frequency).oracle_approximating()
        else:
            raise ValueError(f"Unknown covariance method: {method}")

        return S

    def _get_bounds(
        self, constraints: Optional[PortfolioConstraints]
    ) -> Union[Tuple[float, float], List[Tuple[float, float]]]:
        """Extract weight bounds from PortfolioConstraints.

        Returns either a global tuple (lb, ub) or a list of per-asset (lb, ub) bounds.
        """
        if constraints is None:
            return (0.0, 1.0)

        # If any asset-specific bound or explicit min bounds exist, build per-asset bounds
        has_asset_bounds = bool(constraints.asset_specific_bounds)
        has_global_min = constraints.min_weight is not None
        if has_asset_bounds or has_global_min:
            return constraints.build_bounds(self.tickers)

        # Fallback to global bounds
        if getattr(constraints, 'long_only_enabled', True):
            lb = 0.0
        else:
            lb = -1.0
        ub = constraints.max_weight if constraints.max_weight is not None else 1.0
        return (lb, ub)

    def _apply_sector_constraints(
        self,
        ef: EfficientFrontier,
        constraints: PortfolioConstraints,
    ) -> None:
        """Apply sector constraints to EfficientFrontier object."""
        if not constraints.sector_limits or not constraints.sector_mapping:
            return

        # Build sector_mapper and sector_upper for PyPortfolioOpt
        sector_mapper = constraints.sector_mapping
        sector_upper = constraints.sector_limits
        
        # PyPortfolioOpt requires sector_lower as well (dict or None)
        # Default: no lower bounds per sector
        sector_lower = {k: 0.0 for k in sector_upper.keys()}

        ef.add_sector_constraints(sector_mapper, sector_lower, sector_upper)
        logger.debug(f"Applied sector constraints: {sector_upper}")

    def _series_from_dict(self, weights_dict: Dict[str, float]) -> pd.Series:
        """Convert PyPortfolioOpt weights dict to normalized pd.Series."""
        w = pd.Series(weights_dict)
        # Ensure sum=1 (PyPortfolioOpt clean_weights already does this, but be safe)
        total = w.sum()
        if total > 0:
            w = w / total
        return w.astype(float)

    def _align_weights(self, weights: pd.Series) -> pd.Series:
        """Align a weights Series to internal ticker order and normalize to sum=1 if needed."""
        w = weights.reindex(self.tickers).fillna(0.0).astype(float)
        s = w.sum()
        if s != 0 and not np.isclose(s, 1.0):
            w = w / s
        return w


__all__ = ["PyPortfolioOptOptimizer"]
