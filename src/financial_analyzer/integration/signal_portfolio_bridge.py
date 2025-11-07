"""
Signal-to-portfolio bridge.

Converts ML/Sentiment signals (-2..2) into robust portfolio allocations using
external optimizers (Riskfolio-Lib NCO preferred) with safe fallbacks and
strict validations.

Audit references:
- AUDIT_RISKFOLIO_LIB.md pp. 12-18 (NCO algo)
- AUDIT_PYPORTFOLIOOPT.md pp. 8-15 (efficient frontier)

Example:
    >>> import pandas as pd
    >>> from financial_analyzer.integration.signal_portfolio_bridge import SignalPortfolioBridge
    >>> prices = pd.DataFrame({
    ...     'Open': [100, 101], 'High': [102, 103], 'Low': [99, 100],
    ...     'Close': [101, 102], 'Volume': [1_000_000, 1_100_000]
    ... }, index=pd.date_range('2024-01-01', periods=2, tz='UTC'))
    >>> bridge = SignalPortfolioBridge(portfolio_optimizer=None, sentiment_engine=None, feature_selector=None)
    >>> w = bridge.convert_signals_to_weights({'AAPL': 1.5, 'MSFT': -0.5}, prices)
    >>> isinstance(w, dict) and abs(sum(w.values()) - 1.0) < 1e-6
    True
"""

# 1. Stdlib
from typing import Dict, Optional, Any, List
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 3. Finance libs (imports deferred in methods if needed)
# 4. ML (not used directly here)

# 5. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


REQUIRED_OHLCV_COLS = ["Open", "High", "Low", "Close", "Volume"]


class SignalPortfolioBridge:
    """
    Convertit signaux ML/Sentiment en allocations portfolio robustes.

    Pipeline:
    1. Réceptionne signaux (-2 à +2) de NewsSignalGenerator
    2. Filtre actifs par confidence + seuil sentiment
    3. Calcule expected returns (IC pondéré × signal strength)
    4. Optimise portfolio (Riskfolio NCO) avec contraintes
    5. Retourne poids optimaux (sum=1)
    
    **Expected Prices Format** (choose one):
    
    Format A - MultiIndex (PRODUCTION):
        >>> prices.columns = MultiIndex([('AAPL', 'Open'), ('AAPL', 'Close'), ...])
        >>> prices[('AAPL', 'Close')]  # Access AAPL close prices
    
    Format B - Wide format (ALTERNATIVE):
        >>> prices.columns = ['Open_AAPL', 'Close_AAPL', 'Open_MSFT', ...]
        >>> prices['Close_AAPL']  # Access AAPL close prices
    
    Format C - Single asset (TESTING ONLY):
        >>> prices.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        >>> prices['Close']  # Replicated for all tickers in covariance calculation

    Audit references:
    - AUDIT_RISKFOLIO_LIB.md pp. 12-18 (NCO algo)
    - AUDIT_PYPORTFOLIOOPT.md pp. 8-15 (efficient frontier)
    
    Example:
        >>> import pandas as pd
        >>> # Format C (testing)
        >>> prices = pd.DataFrame({
        ...     'Open': [100, 101], 'High': [102, 103], 'Low': [99, 100],
        ...     'Close': [101, 102], 'Volume': [1_000_000, 1_100_000]
        ... }, index=pd.date_range('2024-01-01', periods=2, tz='UTC'))
        >>> bridge = SignalPortfolioBridge(None, None, None)
        >>> weights = bridge.convert_signals_to_weights({'AAPL': 1.5, 'MSFT': 0.8}, prices)
        >>> sum(weights.values()) == 1.0
        True
    """

    def __init__(
        self,
        portfolio_optimizer: Optional[Any],
        sentiment_engine: Optional[Any],
        feature_selector: Optional[Any],
        max_weight: float = 0.20,
        min_weight: float = 0.01,
        long_only: bool = True
    ) -> None:
        """
        Initialise le bridge avec dépendances externes (mockables).

        Args:
            portfolio_optimizer: Optimiseur de portefeuille (Riskfolio wrapper),
                doit fournir preferablement `optimize_nco(expected_returns, cov, risk_measure)`
                et fallback `optimize_mean_variance(expected_returns, cov)`.
            sentiment_engine: Moteur sentiment (Phase 5.3), optionnel; si fourni, peut
                exposer des mesures d'IC historiques.
            feature_selector: Sélecteur de facteurs (Phase 5.2), optionnel; peut fournir
                informations de qualité factorielle.
            max_weight: Poids maximum par actif (par défaut 20%).
            min_weight: Poids minimum non-nul par actif (par défaut 1%).
            long_only: Si True, ignore les signaux négatifs (pas de short). Si False,
                autorise des expected returns négatifs (requiert un optimiseur supportant le short).

        Raises:
            ValueError: Si contraintes invalides.
        """
        logger.debug("Initializing SignalPortfolioBridge ...")
        if not (0 < min_weight <= max_weight <= 1):
            raise ValueError("Constraints invalid: require 0 < min_weight <= max_weight <= 1")
        self.portfolio_optimizer = portfolio_optimizer
        self.sentiment_engine = sentiment_engine
        self.feature_selector = feature_selector
        self.max_weight = float(max_weight)
        self.min_weight = float(min_weight)
        self.long_only = bool(long_only)
        logger.info(
            f"Bridge initialized with max_weight={self.max_weight:.2f}, min_weight={self.min_weight:.2f}"
        )

    def convert_signals_to_weights(
        self,
        signals: Dict[str, float],
        prices: pd.DataFrame,
        lookback_days: int = 252,
        risk_measure: str = 'CVaR'
    ) -> Dict[str, float]:
        """
        Convertit signaux en poids portfolio via Riskfolio NCO.

        Args:
            signals: Dict[ticker, signal_strength (-2 to +2)]
            prices: OHLCV DataFrame capitalisées + DatetimeIndex UTC
            lookback_days: Fenêtre historique (252 = 1 an)
            risk_measure: 'MV'|'CVaR'|'CDaR'|'EVaR' (Riskfolio)

        Returns:
            Dict[ticker, weight] optimisé, sum=1.0

        Raises:
            ValueError: Si signals invalides
            TypeError: Si prices pas DataFrame OHLCV

        Process:
        1. Filter long_candidates (signal >= 1.0)
        2. Calculate expected_returns = IC_historical × signal_strength
        3. Call optimizer.optimize_nco(expected_returns, risk_measure)
        4. Apply constraints (max/min weight, sector limits)
        5. Normalize weights (sum=1)

        Audit:
        - AUDIT_RISKFOLIO_LIB.md p.14 (NCO step-by-step)
        - AUDIT_PYPORTFOLIOOPT.md p.10 (efficient frontier constraints)

        Example:
            >>> import pandas as pd
            >>> prices = pd.DataFrame({
            ...     'Open': [100, 101], 'High': [102, 103], 'Low': [99, 100],
            ...     'Close': [101, 102], 'Volume': [1_000_000, 1_100_000]
            ... }, index=pd.date_range('2024-01-01', periods=2, tz='UTC'))
            >>> bridge = SignalPortfolioBridge(None, None, None)
            >>> w = bridge.convert_signals_to_weights({'AAPL': 1.2, 'MSFT': 0.5}, prices)
            >>> 0.99 < sum(w.values()) <= 1.01
            True
        """
        logger.debug("Starting convert_signals_to_weights ...")
        self._validate_inputs(signals, prices)

        # Select tickers from signals that are present in prices columns if prices are multi-asset
        tickers = list(signals.keys())

        # Compute expected returns proxy from signals and optional ICs
        exp_returns = self._compute_expected_returns(signals)
        logger.debug(f"Expected returns computed for {len(exp_returns)} tickers")

        # Covariance matrix from price returns if multi-asset prices provided
        cov = self._compute_covariance(prices, tickers, lookback_days)

        # Optimize using provided optimizer, with layered fallbacks
        weights = self._optimize_with_fallbacks(exp_returns, cov, risk_measure)

        # Apply constraints and normalization
        weights = self._apply_constraints_and_normalize(weights)

        logger.info(
            f"Optimization finished: {len(weights)} assets, sum={sum(weights.values()):.4f}"
        )
        return weights

    # --------------------------- internal helpers ---------------------------------

    def _validate_inputs(self, signals: Dict[str, float], prices: pd.DataFrame) -> None:
        """Validate types, ranges, OHLCV presence, and handle NaNs (forward-fill)."""
        logger.debug("Validating inputs ...")
        if not isinstance(signals, dict):
            raise TypeError(f"signals must be dict, got {type(signals)}")
        if not signals:
            raise ValueError("signals dict is empty")
        if not all(isinstance(v, (int, float)) for v in signals.values()):
            raise ValueError("All signal values must be numeric")
        if not all(-2.0 <= float(v) <= 2.0 for v in signals.values()):
            raise ValueError("All signals must be in [-2, 2]")

        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be DataFrame, got {type(prices)}")
        missing = [c for c in REQUIRED_OHLCV_COLS if c not in prices.columns]
        if missing:
            raise ValueError(f"prices missing OHLCV columns: {missing}")
        if prices.empty:
            raise ValueError("prices DataFrame is empty")
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise ValueError("prices index must be DatetimeIndex")
        if prices.index.tz is None:
            logger.warning("prices DatetimeIndex has no timezone; assuming UTC")
            prices.index = prices.index.tz_localize('UTC')

        if pd.isna(prices).any().any():
            logger.warning("NaN values in prices, forward-filling ...")
            prices.ffill(inplace=True)

    def _compute_expected_returns(self, signals: Dict[str, float]) -> Dict[str, float]:
        """
        Compute expected returns from signal strengths and optional IC inputs.

        If a sentiment engine provides historical IC per ticker via a method like
        `get_ic(tickers: List[str]) -> Dict[str, float]`, it will be used. Otherwise
        a conservative constant IC=0.05 is applied.
        """
        # Try to query ICs from engines if available
        ic_by_ticker: Dict[str, float] = {}
        try:
            if self.sentiment_engine and hasattr(self.sentiment_engine, 'get_ic'):
                ic_by_ticker = dict(self.sentiment_engine.get_ic(list(signals.keys())))  # type: ignore[arg-type]
                logger.info("Using ICs from sentiment_engine")
                logger.debug(f"IC values: {ic_by_ticker}")
        except Exception as e:
            logger.warning(f"Failed to fetch IC from sentiment_engine: {e}")

        default_ic = 0.05
        exp_returns: Dict[str, float] = {}
        for t, s in signals.items():
            # Long-only: ignore negative signals entirely
            if self.long_only and float(s) < 0:
                continue
            ic = float(ic_by_ticker.get(t, default_ic))
            # Scale: expected return proportional to signal and IC
            exp_returns[t] = float(ic * float(s))

        if not exp_returns:
            logger.warning(
                f"No valid signals after filtering (long_only={self.long_only}). Using flat expected returns."
            )
            return {t: default_ic for t in signals.keys()}
        return exp_returns

    def _compute_covariance(self, prices: pd.DataFrame, tickers: list, lookback_days: int) -> pd.DataFrame:
        """Compute covariance matrix using Close prices of provided tickers.

        Expected prices format:
        - Option A: MultiIndex columns (ticker, OHLCV) → prices[ticker]['Close']
        - Option B: Wide format with Close_{TICKER}
        - Option C: Single Close column (replicate for all tickers - testing only)
        
        Args:
            prices: OHLCV DataFrame (format A/B/C)
            tickers: Liste des tickers à inclure
            lookback_days: Nombre de jours historiques (252 = 1 an)
        
        Returns:
            Matrice de covariance (n_tickers × n_tickers)
        
        Notes:
            - Si données insuffisantes (<2 jours) → matrice identité
            - Si variance nulle → matrice identité
            - Log condition number pour détecter singularité
        
        Example:
            >>> prices = pd.DataFrame(...)  # MultiIndex format
            >>> cov = self._compute_covariance(prices, ['AAPL', 'MSFT'], 252)
            >>> cov.shape == (2, 2)
            True
        """
        logger.debug("Computing covariance matrix ...")

        close_df: pd.DataFrame
        # A) MultiIndex columns
        if isinstance(prices.columns, pd.MultiIndex):
            top = prices.columns.get_level_values(0)
            avail = [t for t in tickers if t in top]
            close_df = pd.DataFrame({t: prices[(t, 'Close')] for t in avail}) if avail else pd.DataFrame()
        # B) Wide format: Close_TICKER
        elif any(f'Close_{t}' in prices.columns for t in tickers):
            present = [t for t in tickers if f'Close_{t}' in prices.columns]
            close_df = pd.DataFrame({t: prices[f'Close_{t}'] for t in present}) if present else pd.DataFrame()
        # C) Fallback: single Close column replicated
        else:
            if 'Close' not in prices.columns:
                raise ValueError("Cannot find Close prices for covariance calculation")
            logger.warning("Using single Close column replicated for all tickers (testing mode)")
            close_df = pd.DataFrame({t: prices['Close'] for t in tickers})

        close_df = close_df.tail(lookback_days).dropna(how='all')
        if close_df.empty or len(close_df) < 2:
            logger.warning("Insufficient data for covariance, using identity matrix")
            return pd.DataFrame(np.eye(len(tickers)), index=tickers, columns=tickers)

        returns = close_df.pct_change().dropna(how='all')
        if returns.empty or (returns.std().sum() == 0):
            logger.warning("Zero variance detected, using identity covariance")
            return pd.DataFrame(np.eye(len(tickers)), index=tickers, columns=tickers)

        cov = returns.cov().reindex(index=tickers, columns=tickers).fillna(0.0)
        try:
            cond = float(np.linalg.cond(cov.values))
            logger.debug(f"Covariance shape: {cov.shape}, condition number: {cond:.2e}")
        except Exception:
            logger.debug(f"Covariance shape: {cov.shape}")
        return cov

    def _optimize_with_fallbacks(
        self,
        exp_returns: Dict[str, float],
        cov: pd.DataFrame,
        risk_measure: str
    ) -> Dict[str, float]:
        """Attempt layered optimizations: NCO → Mean-Variance → Equal-Weight."""
        tickers = list(exp_returns.keys())
        # 1) Preferred: external optimizer NCO
        if self.portfolio_optimizer is not None:
            try:
                if hasattr(self.portfolio_optimizer, 'optimize_nco'):
                    logger.info("Optimizing with NCO ...")
                    logger.debug(f"Expected returns: {exp_returns}")
                    w = self.portfolio_optimizer.optimize_nco(exp_returns, cov, risk_measure)  # type: ignore[misc]
                    if isinstance(w, dict) and w:
                        return {k: float(w[k]) for k in tickers if k in w}
            except ValueError as e:
                logger.warning(f"NCO failed, fallback to mean-variance: {e}")
            except Exception as e:
                logger.error(f"NCO optimization error: {e}", exc_info=True)

            # 2) Fallback: mean-variance
            try:
                if hasattr(self.portfolio_optimizer, 'optimize_mean_variance'):
                    logger.info("Optimizing with mean-variance ...")
                    w = self.portfolio_optimizer.optimize_mean_variance(exp_returns, cov)  # type: ignore[misc]
                    if isinstance(w, dict) and w:
                        return {k: float(w.get(k, 0.0)) for k in tickers}
            except Exception as e:
                logger.warning(f"Mean-variance failed: {e}")

        # 3) Final fallback: proportional to positive expected returns, else equal-weight among positives
        logger.info("Falling back to proportional positive expected returns")
        pos = {k: (0.0 if (self.long_only and v < 0) else max(0.0, v)) for k, v in exp_returns.items()}
        s = sum(pos.values())
        if s > 0:
            return {k: (v / s) for k, v in pos.items()}
        # if no positive, equal weight across all (long-only policy)
        return {k: 1.0 / len(tickers) for k in tickers}

    def _apply_constraints_and_normalize(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Clip to [0, max_weight], enforce min/max constraints, and normalize to sum=1.

        Algorithm:
        1) Clip negatives to 0, cap at self.max_weight
        2) Check feasibility: n*max_weight >= 1.0; n*min_weight <= 1.0
        3) If min infeasible, reduce effective min to 1/n
        4) Apply effective min to non-zero weights, re-cap at max
        5) If total < 1, distribute remaining proportionally to headroom up to max
        6) Ensure final sum ≈ 1. If n*max < 1 raise ValueError (impossible)
        """
        logger.debug("Applying constraints and normalization ...")
        if not weights:
            raise ValueError("Optimizer returned empty weights")

        # Replace NaNs with 0.0 then clip negatives to 0 (long-only policy in constraints) and cap at max
        clean = {k: (0.0 if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v)) for k, v in weights.items()}
        w = {k: float(np.clip(v, 0.0, self.max_weight)) for k, v in clean.items()}
        n_assets = len(w)
        max_possible = self.max_weight * n_assets
        min_required = self.min_weight * n_assets

        if max_possible < 1.0:
            raise ValueError(
                f"Impossible constraints: {n_assets} assets with max_weight={self.max_weight:.3f} "
                f"can only reach {max_possible:.3f} < 1.0. Increase max_weight or reduce n_assets."
            )

        # Adjust effective minimum if sum of mins would exceed 1
        effective_min = self.min_weight
        if min_required > 1.0:
            effective_min = 1.0 / n_assets
            logger.warning(
                f"min_weight={self.min_weight:.3f} too high for {n_assets} assets, adjusting to {effective_min:.3f}"
            )

        # Enforce effective min for positive positions
        w = {k: (0.0 if v == 0.0 else min(max(v, effective_min), self.max_weight)) for k, v in w.items()}

        total = sum(w.values())
        if total <= 0:
            # Fallback to equal-weight across all assets
            return {k: 1.0 / max(1, n_assets) for k in w}

        if abs(total - 1.0) < 1e-9:
            return w

        if total > 1.0:
            # Scale down proportionally; cannot violate max since we're decreasing
            w = {k: (v / total) for k, v in w.items()}
            return w

        # total < 1.0 → distribute remaining based on headroom without exceeding caps
        remaining = 1.0 - total
        headroom = {k: max(0.0, self.max_weight - v) for k, v in w.items()}
        headroom_sum = sum(headroom.values())
        if headroom_sum <= 0:
            return w
        w = {k: (v + (headroom[k] / headroom_sum) * remaining) for k, v in w.items()}
        
        # Final validation (production-safe, not using assert)
        max_violation = max(v - self.max_weight for v in w.values())
        if max_violation > 1e-9:
            raise ValueError(f"max_weight violated: max={max(w.values()):.6f} > {self.max_weight:.6f}")

        sum_weights = sum(w.values())
        if abs(sum_weights - 1.0) >= 1e-6:
            raise ValueError(f"Weights sum != 1.0: {sum_weights:.6f}")

        return w

    def convert_signals_to_weights_batch(
        self,
        signals_list: List[Dict[str, float]],
        prices: pd.DataFrame,
        lookback_days: int = 252,
        risk_measure: str = 'CVaR',
        n_jobs: int = -1
    ) -> List[Dict[str, float]]:
        """Batch processing for multiple signal dictionaries (e.g., walk-forward rebalances).

        Args:
            signals_list: Liste de dicts signaux (ex: un par date de rebalancement)
            prices: DataFrame OHLCV complet
            lookback_days: Fenêtre pour covariance
            risk_measure: Mesure de risque Riskfolio
            n_jobs: Nombre de jobs parallèles (-1 = tous les CPUs)

        Returns:
            Liste de dicts de poids, même ordre que `signals_list`.
        """
        from joblib import Parallel, delayed

        logger.info(f"Batch processing {len(signals_list)} signal sets with n_jobs={n_jobs}")
        if n_jobs == 1 or len(signals_list) < 10:
            return [
                self.convert_signals_to_weights(s, prices, lookback_days, risk_measure)
                for s in signals_list
            ]

        results = Parallel(n_jobs=n_jobs, backend='loky')(
            delayed(self.convert_signals_to_weights)(s, prices, lookback_days, risk_measure)
            for s in signals_list
        )
        logger.info(f"Batch processing completed: {len(results)} weights computed")
        return results
