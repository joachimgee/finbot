"""Performance Analytics Module (Module 8).

Provides comprehensive post-backtest analytics:
- Return metrics (total, annualized, cumulative)
- Risk metrics (volatility, VaR, CVaR, max drawdown)
- Risk-adjusted ratios (Sharpe, Sortino, Calmar)
- Benchmark comparison (alpha, beta, tracking error)
- Trade statistics (win rate, profit factor, average gain/loss)
- Rolling window metrics

Integration: Complementary to PerformanceAttributor (do NOT duplicate attribution).

Example
-------
>>> import pandas as pd, numpy as np
>>> from financial_analyzer.analytics.performance_analyzer import PerformanceAnalyzer
>>> analyzer = PerformanceAnalyzer(risk_free_rate=0.02, periods_per_year=252)
>>> dates = pd.date_range('2024-01-01', periods=100, freq='D')
>>> port = pd.Series(np.random.randn(100)/100, index=dates)
>>> bench = pd.Series(np.random.randn(100)/120, index=dates)
>>> trades = pd.DataFrame({
...     'EntryTime': dates[:5], 'ExitTime': dates[5:10], 'PnL': [120, -50, 80, -20, 30]
... })
>>> result = analyzer.analyze_returns(port, bench, trades)
>>> result['risk']['max_drawdown_pct'] < 0
True
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class TradeStats:
    """Aggregated trade statistics.

    Attributes
    ----------
    trades_count : int
        Number of trades.
    wins : int
        Number of profitable trades.
    losses : int
        Number of losing trades.
    win_rate_pct : float
        Win rate percentage [0, 100].
    avg_win : float
        Average profit of winning trades.
    avg_loss : float
        Average loss (absolute) of losing trades.
    profit_factor : float
        Sum wins / |sum losses| (>=0). 0 if no losses.
    total_pnl : float
        Sum of trade PnL.

    Example
    -------
    >>> stats = TradeStats(trades_count=10, wins=6, losses=4, win_rate_pct=60.0,
    ...                    avg_win=120.0, avg_loss=80.0, profit_factor=1.5, total_pnl=400.0)
    >>> stats.win_rate_pct
    60.0
    """
    trades_count: int
    wins: int
    losses: int
    win_rate_pct: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_pnl: float


class PerformanceAnalyzer:
    """Compute portfolio performance analytics.

    Parameters
    ----------
    risk_free_rate : float, default 0.02
        Annualized risk-free rate used for Sharpe/Sortino.
    periods_per_year : int, default 252
        Number of periods per year (e.g., trading days).

    Raises
    ------
    ValueError
        If risk_free_rate < 0 or periods_per_year <= 0.
    """
    def __init__(self, risk_free_rate: float = 0.02, periods_per_year: int = 252) -> None:
        if risk_free_rate < 0:
            raise ValueError("risk_free_rate must be >= 0")
        if periods_per_year <= 0:
            raise ValueError("periods_per_year must be > 0")
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year
        logger.info(
            f"PerformanceAnalyzer initialized: rf={risk_free_rate:.2%}, periods_per_year={periods_per_year}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze_returns(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series | None,
        trades: pd.DataFrame | None,
    ) -> Dict[str, Any]:
        """Analyze portfolio performance relative to optional benchmark.

        Parameters
        ----------
        portfolio_returns : pd.Series
            Periodic portfolio returns (index datetime-like). Values decimal e.g., 0.01.
        benchmark_returns : pd.Series, optional
            Benchmark returns aligned on index.
        trades : pd.DataFrame, optional
            Trades with at least 'PnL' column.

        Returns
        -------
        dict
            Structured analytics: {'returns': {...}, 'risk': {...}, 'ratios': {...}, 'benchmark': {...}, 'trades': {...}}
        """
        if portfolio_returns is None or portfolio_returns.empty:
            logger.warning("Empty portfolio_returns passed to analyze_returns")
            return {
                'returns': {}, 'risk': {}, 'ratios': {}, 'benchmark': {}, 'trades': {}
            }

        # Ensure alignment
        port = portfolio_returns.dropna().copy()
        bench = benchmark_returns.dropna().reindex(port.index) if benchmark_returns is not None else None

        # Return metrics
        returns_metrics = self._compute_return_metrics(port)
        # Risk metrics
        risk_metrics = self._compute_risk_metrics(port)
        # Ratios
        ratios_metrics = self._compute_risk_adjusted_ratios(port, risk_metrics)
        # Benchmark comparison
        benchmark_metrics = self.compare_to_benchmark(port, bench) if bench is not None else {}
        # Trade stats
        trade_metrics = self._compute_trade_stats(trades) if trades is not None else {}

        return {
            'returns': returns_metrics,
            'risk': risk_metrics,
            'ratios': ratios_metrics,
            'benchmark': benchmark_metrics,
            'trades': trade_metrics,
        }

    def calculate_drawdown(
        self, returns: pd.Series
    ) -> Tuple[pd.Series, float, pd.Timestamp | None, pd.Timestamp | None]:
        """Calculate drawdown series and max drawdown.

        Returns
        -------
        drawdown_series : pd.Series
            Drawdown values (0 to negative numbers).
        max_dd : float
            Maximum drawdown (negative number, e.g., -0.25 for -25%).
        peak : Timestamp | None
            Peak date before max drawdown.
        trough : Timestamp | None
            Trough date at drawdown bottom.
        """
        if returns.empty:
            return pd.Series(dtype=float), 0.0, None, None
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdown = (cumulative / rolling_max) - 1.0
        max_dd = float(drawdown.min())
        trough_date = drawdown.idxmin() if not drawdown.empty else None
        peak_date = cumulative.loc[:trough_date].idxmax() if trough_date else None
        return drawdown, max_dd, peak_date, trough_date

    def calculate_var_cvar(
        self, returns: pd.Series, confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Compute Value-at-Risk and Conditional VaR (expected shortfall).

        Parameters
        ----------
        returns : pd.Series
            Periodic returns.
        confidence : float, default 0.95
            Confidence level for VaR.

        Returns
        -------
        var : float
            VaR as negative threshold (e.g., -0.03 for 3% loss).
        cvar : float
            Expected shortfall beyond VaR.
        """
        if returns.empty:
            return 0.0, 0.0
        if not 0.8 < confidence < 0.999:
            raise ValueError("confidence must be in (0.8, 0.999)")
        sorted_ret = np.sort(returns.values)
        idx = int((1 - confidence) * len(sorted_ret))
        idx = max(0, min(idx, len(sorted_ret) - 1))
        var = float(sorted_ret[idx])
        tail = sorted_ret[: idx + 1]
        cvar = float(tail.mean()) if len(tail) > 0 else var
        return var, cvar

    def calculate_rolling_metrics(
        self, returns: pd.Series, window: int = 20
    ) -> pd.DataFrame:
        """Compute rolling return & volatility metrics.

        Returns
        -------
        DataFrame with columns: ['rolling_return', 'rolling_volatility']
        """
        if returns.empty:
            return pd.DataFrame(columns=['rolling_return', 'rolling_volatility'])
        roll_ret = returns.rolling(window).mean()
        roll_vol = returns.rolling(window).std()
        return pd.DataFrame({'rolling_return': roll_ret, 'rolling_volatility': roll_vol})

    def compare_to_benchmark(
        self, portfolio: pd.Series, benchmark: pd.Series | None
    ) -> Dict[str, float]:
        """Compare portfolio returns to benchmark: alpha, beta, tracking error.

        Returns empty dict si benchmark None ou vide.
        """
        if benchmark is None or benchmark.empty:
            return {}
        aligned = pd.DataFrame({'p': portfolio, 'b': benchmark}).dropna()
        if aligned.empty:
            return {}
        p = aligned['p']
        b = aligned['b']
        # Beta via covariance / variance
        var_b = b.var()
        cov_pb = p.cov(b)
        beta = cov_pb / var_b if var_b > 0 else 0.0
        alpha = (p.mean() - beta * b.mean()) * self.periods_per_year
        tracking_error = np.sqrt(((p - b) ** 2).mean())
        return {
            'alpha_annual': float(alpha),
            'beta': float(beta),
            'tracking_error': float(tracking_error),
        }

    # ------------------------------------------------------------------
    # Internal computations
    # ------------------------------------------------------------------
    def _compute_return_metrics(self, returns: pd.Series) -> Dict[str, float]:
        cumulative = (1 + returns).cumprod() - 1.0
        total_return = float(cumulative.iloc[-1]) if not cumulative.empty else 0.0
        periods = len(returns)
        annualized_return = (1 + total_return) ** (self.periods_per_year / periods) - 1 if periods > 0 else 0.0
        avg_period_return = float(returns.mean())
        return {
            'total_return_pct': total_return * 100,
            'annualized_return_pct': annualized_return * 100,
            'cumulative_return_series': cumulative,
            'average_period_return_pct': avg_period_return * 100,
        }

    def _compute_risk_metrics(self, returns: pd.Series) -> Dict[str, float]:
        volatility = float(returns.std()) * np.sqrt(self.periods_per_year)
        drawdown_series, max_dd, peak, trough = self.calculate_drawdown(returns)
        var_95, cvar_95 = self.calculate_var_cvar(returns, confidence=0.95)
        return {
            'volatility_annual_pct': volatility * 100,
            'max_drawdown_pct': max_dd * 100,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'drawdown_series': drawdown_series,
            'peak_date': peak,
            'trough_date': trough,
        }

    def _compute_risk_adjusted_ratios(
        self, returns: pd.Series, risk_metrics: Dict[str, Any]
    ) -> Dict[str, float]:
        avg_return = returns.mean() * self.periods_per_year
        vol = returns.std() * np.sqrt(self.periods_per_year)
        downside = returns[returns < 0].std() * np.sqrt(self.periods_per_year)
        rf = self.risk_free_rate
        sharpe = (avg_return - rf) / vol if vol > 0 else 0.0
        sortino = (avg_return - rf) / downside if downside > 0 else 0.0
        max_dd = abs(risk_metrics.get('max_drawdown_pct', 0.0) / 100.0)
        calmar = (avg_return - rf) / max_dd if max_dd > 0 else 0.0
        return {
            'sharpe_ratio': float(sharpe),
            'sortino_ratio': float(sortino),
            'calmar_ratio': float(calmar),
        }

    def _compute_trade_stats(self, trades: pd.DataFrame) -> Dict[str, Any]:
        if trades is None or trades.empty or 'PnL' not in trades.columns:
            return {}
        pnl = trades['PnL'].astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        wins_count = int((pnl > 0).sum())
        losses_count = int((pnl < 0).sum())
        win_rate = (wins_count / len(pnl)) * 100 if len(pnl) > 0 else 0.0
        avg_win = float(wins.mean()) if not wins.empty else 0.0
        avg_loss = float(abs(losses.mean())) if not losses.empty else 0.0
        profit_factor = float(wins.sum() / abs(losses.sum())) if not losses.empty else float('inf')
        return {
            'trades_count': len(pnl),
            'wins': wins_count,
            'losses': losses_count,
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_pnl': float(pnl.sum()),
        }

__all__ = ["PerformanceAnalyzer", "TradeStats"]
