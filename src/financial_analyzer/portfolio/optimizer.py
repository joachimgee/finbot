from __future__ import annotations

# 1. Stdlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

# 2. Third-party
import numpy as np
import pandas as pd
from scipy.optimize import minimize

# 3. Local
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.portfolio.constraints import (
    PortfolioConstraints,
    Constraints as HardConstraints,
)
from financial_analyzer.portfolio.metrics import (
    calculate_portfolio_return,
    calculate_portfolio_volatility,
    calculate_portfolio_sharpe,
)

logger = get_logger(__name__)


def _regularize_covariance(cov_matrix: pd.DataFrame, shrinkage: float = 0.01) -> pd.DataFrame:
    """
    Regularize covariance matrix to ensure positive definiteness.
    
    Applies shrinkage towards diagonal matrix (Ledoit-Wolf style) and adds
    jitter if necessary to guarantee numerical stability.
    
    Args:
        cov_matrix: Raw covariance matrix (DataFrame)
        shrinkage: Shrinkage parameter [0, 1], default 0.01
    
    Returns:
        Regularized covariance matrix (DataFrame with same index/columns)
    
    Example:
        >>> cov_raw = returns.cov()
        >>> cov_reg = _regularize_covariance(cov_raw, shrinkage=0.02)
    """
    if not isinstance(cov_matrix, pd.DataFrame):
        raise TypeError(f"cov_matrix must be DataFrame, got {type(cov_matrix)}")
    
    if cov_matrix.empty:
        return cov_matrix
    
    # Convert to numpy for computation
    cov_np = cov_matrix.values
    n = len(cov_np)
    
    # Shrinkage: blend sample cov with diagonal target
    trace = np.trace(cov_np)
    target = np.eye(n) * (trace / n) if n > 0 else np.eye(n)
    cov_shrunk = (1 - shrinkage) * cov_np + shrinkage * target
    
    # Check if positive definite
    def is_positive_definite(matrix: np.ndarray) -> bool:
        """Check if matrix is positive definite via Cholesky decomposition."""
        try:
            np.linalg.cholesky(matrix)
            return True
        except np.linalg.LinAlgError:
            return False
    
    # Add jitter if not PD
    if not is_positive_definite(cov_shrunk):
        jitter = 1e-6
        logger.warning(
            f"Covariance matrix not positive definite after shrinkage={shrinkage:.4f}, "
            f"adding jitter={jitter}"
        )
        cov_shrunk += np.eye(n) * jitter
    
    # Return as DataFrame with original index/columns
    return pd.DataFrame(cov_shrunk, index=cov_matrix.index, columns=cov_matrix.columns)


@dataclass(frozen=True)
class OptimizationResult:
    """Conteneur de résultat d'optimisation."""
    weights: pd.Series
    expected_return: Optional[float] = None
    volatility: Optional[float] = None
    sharpe: Optional[float] = None


class PortfolioOptimizer:
    """
    Optimiseur de portefeuille unifié.

    Deux modes d'usage supportés pour compatibilité des tests:
    1) Mode "Mean-Variance" (scipy): initialiser avec `returns` DataFrame puis appeler
       optimize_min_variance(), optimize_max_sharpe(), etc. Utilise PortfolioConstraints.
    2) Mode "Monte Carlo": instancier sans returns mais avec `random_seed`; appeler
       optimize_max_sharpe(daily_returns=..., constraints=..., n_trials=...). Utilise HardConstraints.
    """

    def __init__(
        self,
        returns: Optional[pd.DataFrame] = None,
        risk_free_rate: float = 0.02,
        rebalance_freq: str = 'M',
        random_seed: Optional[int] = None,
    ) -> None:
        self.risk_free_rate = float(risk_free_rate)
        self.rebalance_freq = rebalance_freq
        self._rng = np.random.default_rng(random_seed if random_seed is not None else 42)

        # Mean-Variance state (when returns provided)
        self.returns: Optional[pd.DataFrame] = None
        self.tickers: List[str] = []
        self.mean_returns: Optional[pd.Series] = None
        self.cov_matrix: Optional[pd.DataFrame] = None
        self.constraints = PortfolioConstraints()

        if returns is not None:
            if not isinstance(returns, pd.DataFrame) or returns.empty:
                raise ValueError("returns must be a non-empty DataFrame")
            if not isinstance(returns.index, (pd.DatetimeIndex, pd.PeriodIndex)):
                logger.warning(
                    "Returns index is not Datetime/Period index; annualization may be off"
                )
            self.returns = returns.dropna(how='all').fillna(0.0)
            self.tickers = list(self.returns.columns)
            periods_per_year = 252
            self.mean_returns = self.returns.mean() * periods_per_year
            cov_raw = self.returns.cov() * periods_per_year
            self.cov_matrix = _regularize_covariance(cov_raw)
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
        if self.returns is None or self.mean_returns is None or self.cov_matrix is None:
            raise ValueError("Optimizer not initialized with returns for mean-variance mode")
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

    def _optimize_max_sharpe_mv(self) -> Dict:
        """
        Optimise pour Sharpe Ratio maximal.

        Returns:
            {'weights': Series, 'return': float, 'volatility': float, 'sharpe': float}
        """
        if self.returns is None or self.mean_returns is None or self.cov_matrix is None:
            raise ValueError("Optimizer not initialized with returns for mean-variance mode")
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

    def optimize_black_litterman(
        self,
        views: Dict[str, float],
        confidences: Optional[Dict[str, float]] = None,
        tau: float = 0.05,
        market_weights: Optional[pd.Series] = None,
        delta: Optional[float] = None,
    ) -> Dict:
        """
        Optimisation Black-Litterman simple: calcule un postérieur des rendements attendus
        à partir d'un prior (marché ou moyenne) et de vues sur certains actifs.

        Args:
            views: mapping asset -> vue (rendement annuel attendu)
            confidences: mapping asset -> confiance (0..1), par défaut 0.5
            tau: intensité d'incertitude du prior (typ. 0.025–0.1)
            market_weights: poids de marché (prior via reverse optimization si delta fourni)
            delta: aversion au risque (nécessaire pour prior = delta * Σ * w_mkt)

        Returns:
            Dict avec 'weights', 'return', 'volatility', 'sharpe'
        """
        if self.mean_returns is None or self.cov_matrix is None:
            raise ValueError("Optimizer not initialized with returns for mean-variance mode")
        tickers = self.tickers
        mu_prior: pd.Series
        if market_weights is not None and delta is not None and delta > 0:
            w_mkt = market_weights.reindex(tickers).fillna(0.0).values.astype(float)
            mu_prior = pd.Series(self.cov_matrix.values @ w_mkt * float(delta), index=tickers)
        else:
            mu_prior = self.mean_returns.copy()

        # Build P and Q for asset-level views (identity rows for specified assets)
        assets = list(views.keys())
        if not assets:
            # No views: fallback to max sharpe with prior
            tmp = self.mean_returns
            self.mean_returns = mu_prior
            res = self._optimize_max_sharpe_mv()
            self.mean_returns = tmp
            return res
        P = np.zeros((len(assets), len(tickers)), dtype=float)
        for i, a in enumerate(assets):
            if a in tickers:
                P[i, tickers.index(a)] = 1.0
        Q = np.array([float(views[a]) for a in assets], dtype=float)

        # Ω diagonal basée sur la variance des vues P Σ P^T ajustée par confiance
        Sigma = self.cov_matrix.values.astype(float)
        PS = P @ Sigma
        Omega_diag = np.maximum(np.diag(PS @ P.T), 1e-12)
        conf = np.array([float(confidences.get(a, 0.5)) if confidences else 0.5 for a in assets], dtype=float)
        conf = np.clip(conf, 1e-6, 1.0)
        Omega_diag = Omega_diag * (1.0 / conf)
        Omega = np.diag(Omega_diag)

        # Posterior mean (simple form): μ_bl = μ_prior + τ Σ P^T (P τ Σ P^T + Ω)^-1 (Q - P μ_prior)
        tauSigma = float(tau) * Sigma
        middle = np.linalg.inv(P @ tauSigma @ P.T + Omega)
        adj = tauSigma @ P.T @ middle @ (Q - P @ mu_prior.values.astype(float))
        mu_post = mu_prior.values.astype(float) + adj
        mu_post = pd.Series(mu_post, index=tickers)

        # Option: on garde Σ inchangée pour la stabilité
        tmp = self.mean_returns
        self.mean_returns = mu_post
        res = self._optimize_max_sharpe_mv()
        self.mean_returns = tmp
        return res

    def optimize_risk_parity(self) -> Dict:
        """
        Allocation risque égal (inverse volatilité).

        Returns:
            {'weights': Series, 'volatility': float}
        """
        if self.cov_matrix is None:
            raise ValueError("Optimizer not initialized with returns for mean-variance mode")
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
        if self.mean_returns is None or self.cov_matrix is None:
            raise ValueError("Optimizer not initialized with returns for mean-variance mode")
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
        if self.mean_returns is None or self.cov_matrix is None:
            raise ValueError("Optimizer not initialized with returns for mean-variance mode")
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

    # ---------------- Monte Carlo mode API (compatibilité tests) ----------------
    @staticmethod
    def _annualize_returns(daily_returns: pd.DataFrame) -> pd.Series:
        mu = daily_returns.mean().astype(float)
        return (1 + mu) ** 252 - 1

    @staticmethod
    def _covariance(daily_returns: pd.DataFrame) -> pd.DataFrame:
        return daily_returns.cov() * 252.0

    def _random_weights(
        self,
        tickers: pd.Index,
        bounds: Optional[Dict[str, Tuple[float, float]]] = None,
        max_positions: Optional[int] = None,
    ) -> pd.Series:
        n = len(tickers)
        k = n if max_positions is None or max_positions >= n else int(max_positions)
        active = np.zeros(n, dtype=bool)
        active[:k] = True
        self._rng.shuffle(active)
        lo = np.zeros(n, dtype=float)
        hi = np.ones(n, dtype=float)
        if bounds:
            for i, t in enumerate(tickers):
                if t in bounds:
                    lo[i], hi[i] = bounds[t]
        # Inactive assets must be zero
        lo[~active] = 0.0
        hi[~active] = 0.0
        # Feasibility checks
        total_lo = float(lo.sum())
        total_hi = float(hi.sum())
        if total_lo > 1.0 - 1e-12 or total_hi < 1.0 - 1e-12:
            # Infeasible selection; return zeros to skip
            return pd.Series(np.zeros(n, dtype=float), index=tickers)
        slack = 1.0 - total_lo
        cap = hi - lo
        cap[cap < 0] = 0.0
        if float(cap.sum()) <= 1e-12:
            return pd.Series(np.zeros(n, dtype=float), index=tickers)
        # Sample Dirichlet weighted by capacities
        alpha = np.where(cap > 0, cap, 0.0) + 1e-3
        y = self._rng.dirichlet(alpha)
        add = y * slack
        w = lo + add
        # Numerical stability: adjust add proportionally to hit exact sum 1 without violating caps
        s = float(w.sum())
        if abs(s - 1.0) > 1e-12 and slack > 0:
            scale = (1.0 - float(lo.sum())) / slack
            add = add * scale
            w = lo + add
        # Final clamp to [lo, hi] (should be redundant)
        w = np.minimum(np.maximum(w, lo), hi)
        return pd.Series(w, index=tickers)

    @staticmethod
    def _portfolio_stats(
        weights: pd.Series, exp_ret: pd.Series, cov: pd.DataFrame
    ) -> Tuple[float, float, float]:
        w = weights.values.astype(float)
        mu = exp_ret.reindex(weights.index).values.astype(float)
        cov_m = cov.reindex(index=weights.index, columns=weights.index).values.astype(float)
        port_ret = float(w @ mu)
        port_vol = float(np.sqrt(w @ cov_m @ w))
        sharpe = port_ret / port_vol if port_vol > 1e-12 else 0.0
        return port_ret, port_vol, sharpe

    def optimize_max_sharpe_monte_carlo(
        self,
        daily_returns: pd.DataFrame,
        constraints: Optional[HardConstraints] = None,
        n_trials: int = 5000,
    ) -> OptimizationResult:
        if not isinstance(daily_returns, pd.DataFrame) or daily_returns.empty:
            raise ValueError("daily_returns invalide")
        daily_returns = daily_returns.replace([np.inf, -np.inf], np.nan).dropna(how='all').fillna(0.0)

        tickers = daily_returns.columns
        exp_ret = self._annualize_returns(daily_returns)
        cov = self._covariance(daily_returns)

        bounds_dict: Optional[Dict[str, Tuple[float, float]]] = None
        max_pos: Optional[int] = None
        if constraints is not None and constraints.bounds is not None:
            bounds_dict = {t: (constraints.bounds.get_lower(t), constraints.bounds.get_upper(t)) for t in tickers}
        if constraints is not None and constraints.max_positions is not None:
            max_pos = int(constraints.max_positions.max_positions)

        best: Optional[OptimizationResult] = None
        for _ in range(int(n_trials)):
            w = self._random_weights(tickers, bounds=bounds_dict, max_positions=max_pos)
            if float(w.sum()) <= 0:
                continue
            feasible = True
            if constraints is not None:
                if not constraints.is_feasible(w, cov=cov):
                    feasible = False
            if not feasible:
                continue
            port_ret, port_vol, sharpe = self._portfolio_stats(w, exp_ret, cov)
            cand = OptimizationResult(weights=w, expected_return=port_ret, volatility=port_vol, sharpe=sharpe)
            if best is None or (cand.sharpe or -1) > (best.sharpe or -1):
                best = cand
        if best is None:
            raise ValueError("Aucun portefeuille faisable n'a été trouvé avec les contraintes fournies.")
        return best

    # Backward-compat signature wrapper
    def optimize_max_sharpe(
        self,
        daily_returns: Optional[pd.DataFrame] = None,
        constraints: Optional[Union[HardConstraints, PortfolioConstraints]] = None,
        n_trials: int = 5000,
        allow_short: bool = False,
    ) -> Union[OptimizationResult, Dict]:
        # If returns provided at init (mean-variance mode), ignore monte-carlo params and use scipy path
        if self.returns is not None:
            return self._optimize_max_sharpe_mv()
        # Else use Monte Carlo path
        if daily_returns is None:
            raise ValueError("daily_returns requis pour le mode Monte Carlo")
        hc = constraints if isinstance(constraints, HardConstraints) else None
        return self.optimize_max_sharpe_monte_carlo(daily_returns, constraints=hc, n_trials=n_trials)


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

    # Custom constraints (must return >= 0 when satisfied)
    for cf in constraints.custom_funcs:
        cons.append({'type': 'ineq', 'fun': lambda w, func=cf, names=tickers: float(func(w, names))})

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

    # Custom constraints (must return >= 0 when satisfied)
    for cf in constraints.custom_funcs:
        cons.append({'type': 'ineq', 'fun': lambda w, func=cf, names=tickers: float(func(w, names))})

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
    return opt._optimize_max_sharpe_mv()


def calculate_risk_parity(returns: pd.DataFrame) -> Dict:
    """Allocation risque égal (inverse vol)."""
    opt = PortfolioOptimizer(returns)
    return opt.optimize_risk_parity()


def calculate_equal_weight(returns: pd.DataFrame) -> Dict:
    """Allocation équi-pondérée (1/N)."""
    opt = PortfolioOptimizer(returns)
    return opt.optimize_equal_weight()
