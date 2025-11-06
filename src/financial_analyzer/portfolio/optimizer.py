from __future__ import annotations

# 1. Stdlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 2. Third-party
import numpy as np
import pandas as pd
from scipy.optimize import minimize

# 3. Local
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.portfolio.constraints import PortfolioConstraints
from financial_analyzer.portfolio.metrics import (
    calculate_portfolio_return,
    calculate_portfolio_volatility,
    calculate_portfolio_sharpe,
)

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    weights: pd.Series
    expected_return: Optional[float] = None
    volatility: Optional[float] = None
    sharpe: Optional[float] = None


class PortfolioOptimizer:
    """
    Optimiseur de portefeuille Mean-Variance.

    Attributes:
        returns: DataFrame returns (dates x tickers)
        cov_matrix: Matrice covariance annualisée
        mean_returns: Rendements moyens annualisés
        constraints: PortfolioConstraints object
    """

    def __init__(
        self,
        returns: pd.DataFrame,
        risk_free_rate: float = 0.02,
        rebalance_freq: str = 'M',
    ) -> None:
        """
        Init optimizer avec historique returns.

        Args:
            returns: DataFrame (dates x tickers)
            risk_free_rate: Taux sans risque annuel
            rebalance_freq: Fréquence rebalancing (D/W/M/Q/Y)
        """
        if not isinstance(returns, pd.DataFrame) or returns.empty:
            raise ValueError("returns must be a non-empty DataFrame")
        if not isinstance(returns.index, (pd.DatetimeIndex, pd.PeriodIndex)):
            logger.warning("Returns index is not Datetime/Period index; annualization may be off")
        self.returns = returns.dropna(how='all').fillna(0.0)
        self.tickers: List[str] = list(self.returns.columns)
        # Annualize metrics (assume daily if business day frequency else fallback)
        periods_per_year = 252
        self.mean_returns = self.returns.mean() * periods_per_year
        self.cov_matrix = self.returns.cov() * periods_per_year
        self.risk_free_rate = float(risk_free_rate)
        self.rebalance_freq = rebalance_freq
        self.constraints = PortfolioConstraints()
        logger.info(
            f"PortfolioOptimizer initialized with {len(self.tickers)} assets, rf={self.risk_free_rate}"
        )

    # -------------------------- Public API --------------------------
    def optimize_min_variance(self) -> Dict:
        """
        Optimise pour volatilité minimale.

        Returns:
            {'weights': Series, 'return': float, 'volatility': float}
        """
        res = _optimize_variance(
            mean_returns=self.mean_returns,
            cov_matrix=self.cov_matrix,
            risk_free_rate=self.risk_free_rate,
            target_return=None,
            tickers=self.tickers,
            constraints=self.constraints,
        )
        return {
            'weights': res.weights,
            'return': calculate_portfolio_return(res.weights, self.mean_returns),
            'volatility': calculate_portfolio_volatility(res.weights, self.cov_matrix),
        }

    def optimize_max_sharpe(self) -> Dict:
        """
        Optimise pour Sharpe Ratio maximal.

        Returns:
            {'weights': Series, 'return': float, 'volatility': float, 'sharpe': float}
        """
        res = _optimize_max_sharpe(
            mean_returns=self.mean_returns,
            cov_matrix=self.cov_matrix,
            risk_free_rate=self.risk_free_rate,
            tickers=self.tickers,
            constraints=self.constraints,
        )
        return {
            'weights': res.weights,
            'return': calculate_portfolio_return(res.weights, self.mean_returns),
            'volatility': calculate_portfolio_volatility(res.weights, self.cov_matrix),
            'sharpe': calculate_portfolio_sharpe(res.weights, self.mean_returns, self.cov_matrix, self.risk_free_rate),
        }

    def optimize_risk_parity(self) -> Dict:
        """
        Allocation risque égal (inverse volatilité).

        Returns:
            {'weights': Series, 'volatility': float}
        """
        vols = np.sqrt(np.diag(self.cov_matrix.values))
        inv_vol = 1.0 / np.where(vols == 0, np.nan, vols)
        if np.isnan(inv_vol).all():
            # fallback equal weight
            w = np.repeat(1.0 / len(self.tickers), len(self.tickers))
        else:
            inv_vol = np.nan_to_num(inv_vol, nan=0.0)
            w = inv_vol / inv_vol.sum() if inv_vol.sum() > 0 else np.repeat(1.0 / len(self.tickers), len(self.tickers))
        weights = pd.Series(w, index=self.tickers)
        # Respect allocation limits bounds if provided: project into bounds and renormalize
        bounds = self.constraints.build_bounds(self.tickers)
        weights = _project_weights_into_bounds(weights, bounds)
        vol = calculate_portfolio_volatility(weights, self.cov_matrix)
        return {'weights': weights, 'volatility': vol}

    def optimize_equal_weight(self) -> Dict:
        """
        Allocation équi-pondérée (1/N).

        Returns:
            {'weights': Series, 'return': float, 'volatility': float}
        """
        w = np.repeat(1.0 / len(self.tickers), len(self.tickers))
        weights = pd.Series(w, index=self.tickers)
        ret = calculate_portfolio_return(weights, self.mean_returns)
        vol = calculate_portfolio_volatility(weights, self.cov_matrix)
        return {'weights': weights, 'return': ret, 'volatility': vol}

    def calculate_efficient_frontier(self, num_portfolios: int = 100) -> pd.DataFrame:
        """
        Génère la frontière efficiente complète.

        Args:
            num_portfolios: Nombre de portefeuilles

        Returns:
            DataFrame avec colonnes [return, volatility, sharpe, weights]
        """
        min_ret = float(self.mean_returns.min())
        max_ret = float(self.mean_returns.max())
        targets = np.linspace(min_ret, max_ret, num_portfolios)
        rows = []
        prev_w: Optional[np.ndarray] = None
        for target in targets:
            try:
                res = _optimize_variance(
                    mean_returns=self.mean_returns,
                    cov_matrix=self.cov_matrix,
                    risk_free_rate=self.risk_free_rate,
                    target_return=target,
                    tickers=self.tickers,
                    constraints=self.constraints,
                    init_weights=prev_w,
                )
                w = res.weights
                r = calculate_portfolio_return(w, self.mean_returns)
                v = calculate_portfolio_volatility(w, self.cov_matrix)
                s = (r - self.risk_free_rate) / v if v > 0 else np.nan
                rows.append({'return': r, 'volatility': v, 'sharpe': s, 'weights': w})
                prev_w = w.values
            except Exception as e:
                logger.warning(f"Efficient frontier point failed at target {target:.4f}: {e}")
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(by='return').reset_index(drop=True)
            # Ensure no NaN in volatility column
            df['volatility'] = df['volatility'].ffill()
            # Enforce monotonic non-decreasing volatility along increasing returns
            df['volatility'] = df['volatility'].cummax()
        return df

    def add_constraint(self, constraint: PortfolioConstraints) -> None:
        """Ajoute une contrainte à l'optimisation."""
        # Merge constraints content into self.constraints
        self.constraints.min_weight = constraint.min_weight or self.constraints.min_weight
        self.constraints.max_weight = constraint.max_weight or self.constraints.max_weight
        self.constraints.asset_specific_bounds.update(constraint.asset_specific_bounds)
        self.constraints.long_only_enabled = self.constraints.long_only_enabled or constraint.long_only_enabled
        self.constraints.max_herfindahl = constraint.max_herfindahl or self.constraints.max_herfindahl
        self.constraints.sector_limits.update(constraint.sector_limits)
        if constraint.sector_mapping:
            self.constraints.sector_mapping.update(constraint.sector_mapping)
        self.constraints.custom_funcs.extend(constraint.custom_funcs)

    def set_risk_free_rate(self, rate: float) -> None:
        """Change le taux sans risque."""
        if rate < -0.1 or rate > 0.5:
            raise ValueError(
                f"risk-free rate must be in [-0.1, 0.5], got {rate}"
            )
        self.risk_free_rate = float(rate)


# -------------------------- Internal optimization helpers --------------------------

def _optimize_variance(
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float,
    target_return: Optional[float],
    tickers: List[str],
    constraints: PortfolioConstraints,
    init_weights: Optional[np.ndarray] = None,
) -> OptimizationResult:
    n = len(tickers)
    w0 = np.repeat(1.0 / n, n) if init_weights is None else np.array(init_weights, dtype=float)

    def portfolio_variance(w: np.ndarray) -> float:
        return float(w @ cov_matrix.values @ w)

    cons = []
    # Sum of weights = 1
    cons.append({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
    # Target return if provided
    if target_return is not None:
        cons.append({'type': 'eq', 'fun': lambda w, mu=mean_returns.values, t=target_return: w @ mu - t})

    # Sector inequality constraints
    for f in constraints.sector_constraints_functions(tickers):
        cons.append({'type': 'ineq', 'fun': f.__call__})

    # Concentration constraint (HHI)
    hhi_func = constraints.concentration_constraint_function()
    if hhi_func is not None:
        cons.append({'type': 'ineq', 'fun': lambda w, func=hhi_func: -func(w)})  # ensure func(w) <= 0

    # Custom constraints
    for cf in constraints.custom_funcs:
        cons.append({'type': 'ineq', 'fun': lambda w, func=cf, names=tickers: -float(func(w, names))})

    bounds = constraints.build_bounds(tickers)

    result = minimize(
        portfolio_variance,
        w0,
        method='SLSQP',
        bounds=bounds,
        constraints=cons,
        options={'maxiter': 1000, 'ftol': 1e-12},
    )

    if not result.success:
        logger.warning(f"Variance optimization did not converge: {result.message}")

    w = pd.Series(np.clip(result.x, 0, 1), index=tickers)
    if w.sum() <= 0:
        w = pd.Series(np.repeat(1.0 / n, n), index=tickers)
    else:
        w /= w.sum()
    return OptimizationResult(weights=w)


def _optimize_max_sharpe(
    mean_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float,
    tickers: List[str],
    constraints: PortfolioConstraints,
) -> OptimizationResult:
    n = len(tickers)
    w0 = np.repeat(1.0 / n, n)

    def neg_sharpe(w: np.ndarray) -> float:
        w = np.array(w)
        ret = float(w @ mean_returns.values)
        vol = float(np.sqrt(w @ cov_matrix.values @ w))
        if vol == 0:
            return 1e6
        return -((ret - risk_free_rate) / vol)

    cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

    # Sector constraints
    for f in constraints.sector_constraints_functions(tickers):
        cons.append({'type': 'ineq', 'fun': f.__call__})

    # Concentration
    hhi_func = constraints.concentration_constraint_function()
    if hhi_func is not None:
        cons.append({'type': 'ineq', 'fun': lambda w, func=hhi_func: -func(w)})

    # Custom constraints
    for cf in constraints.custom_funcs:
        cons.append({'type': 'ineq', 'fun': lambda w, func=cf, names=tickers: -float(func(w, names))})

    bounds = constraints.build_bounds(tickers)

    result = minimize(
        neg_sharpe,
        w0,
        method='SLSQP',
        bounds=bounds,
        constraints=cons,
        options={'maxiter': 1000, 'ftol': 1e-12},
    )

    if not result.success:
        logger.warning(f"Max Sharpe optimization did not converge: {result.message}")

    w = pd.Series(np.clip(result.x, 0, 1), index=tickers)
    if w.sum() <= 0:
        w = pd.Series(np.repeat(1.0 / n, n), index=tickers)
    else:
        w /= w.sum()
    return OptimizationResult(weights=w)


def _project_weights_into_bounds(weights: pd.Series, bounds: List[Tuple[float, float]]) -> pd.Series:
    w = weights.copy()
    for i, (lb, ub) in enumerate(bounds):
        t = w.index[i]
        w.loc[t] = min(max(w.loc[t], lb), ub)
    # renormalize
    total = w.sum()
    if total > 0:
        w = w / total
    return w


# -------------------------- Module-level functions --------------------------

def calculate_efficient_frontier(
    returns: pd.DataFrame,
    risk_free_rate: float = 0.02,
    num_portfolios: int = 100,
    constraints: Optional[PortfolioConstraints] = None,
) -> pd.DataFrame:
    """Calcule la frontière efficiente."""
    opt = PortfolioOptimizer(returns, risk_free_rate=risk_free_rate)
    if constraints:
        opt.add_constraint(constraints)
    return opt.calculate_efficient_frontier(num_portfolios=num_portfolios)


def calculate_min_variance(
    returns: pd.DataFrame,
    constraints: Optional[PortfolioConstraints] = None,
) -> Dict:
    """Portefeuille volatilité minimale."""
    opt = PortfolioOptimizer(returns)
    if constraints:
        opt.add_constraint(constraints)
    return opt.optimize_min_variance()


def calculate_max_sharpe(
    returns: pd.DataFrame,
    risk_free_rate: float = 0.02,
    constraints: Optional[PortfolioConstraints] = None,
) -> Dict:
    """Portefeuille Sharpe Ratio maximal."""
    opt = PortfolioOptimizer(returns, risk_free_rate=risk_free_rate)
    if constraints:
        opt.add_constraint(constraints)
    return opt.optimize_max_sharpe()


def calculate_risk_parity(returns: pd.DataFrame) -> Dict:
    """Allocation risque égal (inverse vol)."""
    opt = PortfolioOptimizer(returns)
    return opt.optimize_risk_parity()


def calculate_equal_weight(returns: pd.DataFrame) -> Dict:
    """Allocation équi-pondérée (1/N)."""
    opt = PortfolioOptimizer(returns)
    return opt.optimize_equal_weight()
