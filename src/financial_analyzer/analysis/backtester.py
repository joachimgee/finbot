# 1. Stdlib
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

# 2. Données & Calculs
import pandas as pd
import numpy as np

# 3. Financier
from financetoolkit import Toolkit

# 6. Projet local
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.config import CONSTANTS, TRADING_CONFIG

# 7. (Optionnel) Plotting
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False


@dataclass
class Trade:
    """Structure d'un trade exécuté."""
    date: pd.Timestamp
    ticker: str
    signal: int  # -1, 0, +1
    qty: float
    price: float
    commission: float
    slippage: float
    cash_after: float
    position_after: float
    realized_pnl: float = 0.0


class BacktestEngine:
    """
    Framework complet de backtesting avec signaux de sentiment, momentum et mean-reversion.

    Args:
        initial_capital: Capital initial du portefeuille
        commission_rate: Commission par transaction (ex: 0.002 pour 0.2%)
        slippage_bps: Slippage en basis points (ex: 5 = 0.05%)
        strategy: 'sentiment' | 'momentum' | 'mean_reversion'
        period: 'D' (daily), 'W' (weekly), 'M' (monthly)
        sentiment_threshold: Seuil absolu pour signaux sentiment
        rebalance_freq: Fréquence de rebalancement ('D','W','M')
        target_leverage: Levier cible (1.0 = 100%)

    Example:
        >>> engine = BacktestEngine(initial_capital=10000, commission_rate=0.002)
        >>> engine.setup(df_prices, daily_sentiment)
        >>> results = engine.backtest()
        >>> metrics = engine.calculate_metrics()
    """

    def __init__(
        self,
        initial_capital: float,
        commission_rate: float = 0.002,
        slippage_bps: float = 5.0,
        strategy: str = "sentiment",
        period: str = "D",
        sentiment_threshold: float = 0.3,
        rebalance_freq: str = "W",
        target_leverage: float = 1.0,
        momentum_lookback: int = 20,
        meanrev_lookback: int = 20,
        zscore_threshold: float = 1.0,
    ) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital doit être > 0")
        if commission_rate < 0:
            raise ValueError("commission_rate doit être >= 0")
        if period not in {"D", "W", "M"}:
            raise ValueError("period doit être dans {'D','W','M'}")
        if rebalance_freq not in {"D", "W", "M"}:
            raise ValueError("rebalance_freq doit être dans {'D','W','M'}")
        if strategy not in {"sentiment", "momentum", "mean_reversion"}:
            raise ValueError("strategy invalide")

        self.initial_capital = float(initial_capital)
        self.commission_rate = float(commission_rate)
        self.slippage_bps = float(slippage_bps)
        self.strategy = strategy
        self.period = period
        self.sentiment_threshold = float(sentiment_threshold)
        self.rebalance_freq = rebalance_freq
        self.target_leverage = float(target_leverage)
        self.momentum_lookback = int(momentum_lookback)
        self.meanrev_lookback = int(meanrev_lookback)
        self.zscore_threshold = float(zscore_threshold)

        self.logger = get_logger(__name__)

        # État du portefeuille
        self.cash: float = self.initial_capital
        self.positions: Dict[str, float] = {}  # ticker -> qty
        self.avg_cost: Dict[str, float] = {}  # ticker -> prix moyen

        # Données alignées
        self._tickers: List[str] = []
        self.prices: pd.DataFrame = pd.DataFrame()
        self.sentiment: pd.DataFrame = pd.DataFrame()

        # Logs
        self.trades: List[Trade] = []
        self.equity_curve: pd.DataFrame = pd.DataFrame()

    # -------------- Préparation --------------
    def setup(
        self,
        df_prices: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        df_sentiment: pd.DataFrame,
        initial_capital: Optional[float] = None,
    ) -> None:
        """
        Initialise le backtest: valide les données, aligne prix et sentiment, reset l'état.

        Args:
            df_prices: DataFrame OHLCV (single) ou Dict[ticker, DataFrame] (multi)
            df_sentiment: DataFrame avec colonnes ['sentiment_score','ticker'] index DatetimeIndex
            initial_capital: Option pour écraser le capital initial

        Raises:
            ValueError: Si données invalides

        Example:
            >>> engine.setup(df_prices, daily_sentiment)
        """
        if initial_capital is not None:
            if initial_capital <= 0:
                raise ValueError("initial_capital doit être > 0")
            self.initial_capital = float(initial_capital)
            self.cash = float(initial_capital)

        # Normaliser prix
        prices_dict: Dict[str, pd.DataFrame]
        if isinstance(df_prices, dict):
            prices_dict = df_prices
        else:
            # Single ticker: essayer de déduire un symbole générique
            prices_dict = {"TICKER": df_prices}
        # Validation basique
        for tkr, df in prices_dict.items():
            required_cols = {"Open", "High", "Low", "Close", "Volume"}
            if not required_cols.issubset(df.columns):
                raise ValueError(f"OHLCV manquants pour {tkr}")
            if not isinstance(df.index, pd.DatetimeIndex):
                raise ValueError("df_prices index doit être DatetimeIndex")

        # Normaliser sentiment
        if "sentiment_score" not in df_sentiment.columns:
            raise ValueError("df_sentiment doit contenir 'sentiment_score'")
        if "ticker" not in df_sentiment.columns:
            # Single ticker fallback
            if len(prices_dict) == 1:
                only = next(iter(prices_dict.keys()))
                df_sentiment = df_sentiment.copy()
                df_sentiment["ticker"] = only
            else:
                raise ValueError("df_sentiment doit contenir 'ticker' en multi-ticker")
        if not isinstance(df_sentiment.index, pd.DatetimeIndex):
            raise ValueError("df_sentiment index doit être DatetimeIndex")

        # Resample sur self.period
        def _resample_prices(df: pd.DataFrame, period: str) -> pd.DataFrame:
            if period == "D":
                return df.sort_index()
            ohlc = {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
            return df.resample(period).agg(ohlc).dropna(how="any")

        def _resample_sent(df: pd.DataFrame, period: str) -> pd.DataFrame:
            if period == "D":
                return df.sort_index()
            agg = {
                "sentiment_score": "mean",
                "positive": "mean" if "positive" in df.columns else "mean",
                "negative": "mean" if "negative" in df.columns else "mean",
                "neutral": "mean" if "neutral" in df.columns else "mean",
                "label": lambda x: x.mode()[0] if len(x.mode()) > 0 else "neutral",
                "ticker": "last",
            }
            cols_in = [c for c in agg.keys() if c in df.columns]
            df_agged = df[cols_in].resample(period).agg({c: agg[c] for c in cols_in})
            return df_agged.dropna(subset=["sentiment_score"], how="any")

        prices_dict = {t: _resample_prices(df, self.period) for t, df in prices_dict.items()}
        df_sentiment = _resample_sent(df_sentiment, self.period)

        # Aligner dates
        all_index = None
        for df in prices_dict.values():
            all_index = df.index if all_index is None else all_index.union(df.index)
        all_index = all_index.union(df_sentiment.index)

        prices_dict = {t: df.reindex(all_index).ffill() for t, df in prices_dict.items()}
        df_sentiment = df_sentiment.reindex(all_index).ffill()

        self._tickers = list(prices_dict.keys())
        # Concat Close pour accès rapide
        close_cols = {t: prices_dict[t]["Close"] for t in self._tickers}
        self.prices = pd.DataFrame(close_cols, index=all_index)
        self._prices_full = prices_dict
        self.sentiment = df_sentiment

        # Validation NaN post-alignement
        n_price_nans = int(self.prices.isna().sum().sum())
        if n_price_nans > 0:
            self.logger.warning(
                f"Des valeurs prix NaN subsistent après alignement: {n_price_nans} cellules."
            )
        if "sentiment_score" in self.sentiment.columns:
            n_sent_nans = int(self.sentiment["sentiment_score"].isna().sum())
            if n_sent_nans > 0:
                self.logger.warning(
                    f"Des valeurs sentiment NaN subsistent après alignement: {n_sent_nans} lignes."
                )

        # Reset état
        self.positions = {t: 0.0 for t in self._tickers}
        self.avg_cost = {t: 0.0 for t in self._tickers}
        self.cash = float(self.initial_capital)
        self.trades = []
        self.equity_curve = pd.DataFrame(index=all_index, columns=["equity", "cash", "position_value"])  # filled in loop

        self.logger.info(
            f"Setup terminé: {len(self._tickers)} tickers, {len(all_index)} périodes, capital={self.initial_capital}"
        )

    # -------------- Génération des signaux --------------
    def generate_signals(self) -> pd.DataFrame:
        """
        Génère un DataFrame de signaux par date et par ticker (-1,0,1).

        Returns:
            DataFrame indexé par date, colonnes=tickers, valeurs dans {-1,0,1}
        """
        sig = pd.DataFrame(0, index=self.prices.index, columns=self._tickers)
        if self.strategy == "sentiment":
            for t in self._tickers:
                sent_series = self.sentiment[self.sentiment["ticker"] == t]["sentiment_score"].reindex(self.prices.index).ffill()
                sig[t] = np.where(sent_series > self.sentiment_threshold, 1, np.where(sent_series < -self.sentiment_threshold, -1, 0))
        elif self.strategy == "momentum":
            # momentum configurable
            lb = max(1, self.momentum_lookback)
            ret = self.prices.pct_change(lb)
            sig = np.where(ret > 0, 1, -1)
            sig = pd.DataFrame(sig, index=self.prices.index, columns=self._tickers)
        elif self.strategy == "mean_reversion":
            # mean-reversion configurable via z-score
            lb = max(2, self.meanrev_lookback)
            thr = self.zscore_threshold
            roll = self.prices.rolling(lb)
            z = (self.prices - roll.mean()) / (roll.std() + 1e-12)
            sig = np.where(z > thr, -1, np.where(z < -thr, 1, 0))
            sig = pd.DataFrame(sig, index=self.prices.index, columns=self._tickers)
        return sig.astype(int)

    # -------------- Exécution des trades --------------
    def _is_rebalance_date(self, date: pd.Timestamp) -> bool:
        if self.rebalance_freq == "D":
            return True
        if self.rebalance_freq == "W":
            # Rebalance le dernier jour ouvré de la semaine
            return date.weekday() == 4  # Vendredi
        if self.rebalance_freq == "M":
            # Rebalance le dernier jour du mois
            next_day = date + pd.Timedelta(days=1)
            return next_day.month != date.month
        return False

    def execute_trades(self, date: pd.Timestamp, signals: Dict[str, int]) -> None:
        """
        Exécute les trades pour atteindre les poids cibles basés sur les signaux.

        Args:
            date: Date d'exécution (utilise prix de clôture de cette date)
            signals: Dict[ticker, signal]
        """
        prices_today = {t: float(self._prices_full[t].loc[date, "Close"]) for t in self._tickers}
        equity_before = self._portfolio_value(prices_today)

        active = [t for t, s in signals.items() if s != 0 and not np.isnan(prices_today[t])]
        # Poids cibles égalitaires sur actifs actifs
        target_weights: Dict[str, float] = {t: 0.0 for t in self._tickers}
        if active:
            w = self.target_leverage / len(active)
            for t in active:
                target_weights[t] = w * (1 if signals[t] > 0 else -1)

        # Convertir poids en quantités
        for t in self._tickers:
            price = prices_today[t]
            if np.isnan(price) or price <= 0:
                continue
            current_qty = self.positions.get(t, 0.0)
            target_qty = (target_weights[t] * equity_before) / price
            delta_qty = target_qty - current_qty
            if abs(delta_qty) < 1e-8:
                continue

            exec_price = price * (1.0 + np.sign(delta_qty) * self.slippage_bps / 10000.0)
            commission = abs(delta_qty) * exec_price * self.commission_rate
            cost = delta_qty * exec_price + commission

            # Calcul PnL réalisé lors d'une réduction de position
            realized_pnl = 0.0
            if current_qty > 0 and delta_qty < 0:
                close_qty = min(abs(delta_qty), abs(current_qty))
                realized_pnl = close_qty * (exec_price - (self.avg_cost.get(t, exec_price)))
            elif current_qty < 0 and delta_qty > 0:
                close_qty = min(abs(delta_qty), abs(current_qty))
                realized_pnl = close_qty * ((self.avg_cost.get(t, exec_price)) - exec_price)

            # Vérifier cash si achat
            if delta_qty > 0 and (self.cash - cost) < -1e-8:
                # limiter à cash disponible
                affordable_qty = max((self.cash) / (exec_price * (1 + self.commission_rate)), 0.0)
                delta_qty = min(delta_qty, affordable_qty)
                commission = abs(delta_qty) * exec_price * self.commission_rate
                cost = delta_qty * exec_price + commission

            # Mettre à jour cash et positions
            self.cash -= cost
            new_qty = current_qty + delta_qty
            # Avg cost update
            if new_qty == 0:
                self.avg_cost[t] = 0.0
            elif delta_qty != 0:
                if current_qty == 0:
                    self.avg_cost[t] = exec_price
                else:
                    # moyenne pondérée simple côté position
                    self.avg_cost[t] = (
                        abs(current_qty) * self.avg_cost[t] + abs(delta_qty) * exec_price
                    ) / (abs(current_qty) + abs(delta_qty))
            self.positions[t] = new_qty

            self.trades.append(
                Trade(
                    date=date,
                    ticker=t,
                    signal=signals[t],
                    qty=float(delta_qty),
                    price=float(exec_price),
                    commission=float(commission),
                    slippage=float(self.slippage_bps),
                    cash_after=float(self.cash),
                    position_after=float(new_qty),
                    realized_pnl=float(realized_pnl - commission),
                )
            )
            self.logger.debug(
                f"{date.date()} Trade {t} qty={delta_qty:.4f} price={exec_price:.4f} comm={commission:.4f} cash={self.cash:.2f}"
            )

    def _portfolio_value(self, prices_today: Dict[str, float]) -> float:
        position_value = sum(self.positions[t] * prices_today.get(t, np.nan) for t in self._tickers)
        return float(self.cash + position_value)

    # -------------- Boucle de backtest --------------
    def backtest(self) -> Dict[str, pd.DataFrame]:
        """
        Exécute la simulation sur tout l'horizon.

        Returns:
            Dict avec 'trades' DataFrame et 'equity_curve' DataFrame
        """
        signals_df = self.generate_signals()
        for date in self.prices.index:
            signals = {t: int(signals_df.loc[date, t]) for t in self._tickers}
            if self._is_rebalance_date(date):
                self.execute_trades(date, signals)
            # Mise à jour equity curve (mark-to-market)
            prices_today = {t: float(self._prices_full[t].loc[date, "Close"]) for t in self._tickers}
            equity = self._portfolio_value(prices_today)
            position_value = sum(self.positions[t] * prices_today[t] for t in self._tickers)
            self.equity_curve.loc[date, "equity"] = equity
            self.equity_curve.loc[date, "cash"] = self.cash
            self.equity_curve.loc[date, "position_value"] = position_value

        # Construire DataFrames résultats
        trades_df = pd.DataFrame([t.__dict__ for t in self.trades])
        if not trades_df.empty:
            trades_df = trades_df.sort_values("date").reset_index(drop=True)
        self.equity_curve = self.equity_curve.astype(float).ffill().bfill()

        self.logger.info(
            f"Backtest terminé: {len(trades_df)} trades, equity finale={self.equity_curve['equity'].iloc[-1]:.2f}"
        )
        return {"trades": trades_df, "equity_curve": self.equity_curve.copy()}

    # -------------- Métriques --------------
    def calculate_metrics(self, risk_free_rate: Optional[float] = None) -> Dict[str, Any]:
        """
        Calcule les métriques de performance.

        Args:
            risk_free_rate: Taux sans risque annualisé (ex: 0.02)

        Returns:
            Dict avec métriques: total_return, annual_return, sharpe_ratio, sortino_ratio, max_drawdown,
            win_rate, profit_factor, total_trades, avg_trade
        """
        eq = self.equity_curve["equity"].astype(float)
        if eq.isna().all() or len(eq) < 2:
            raise ValueError("Equity curve insuffisante pour calculer les métriques.")

        total_return = (eq.iloc[-1] - self.initial_capital) / self.initial_capital
        returns = eq.pct_change().dropna()

        # Déterminer facteur d'annualisation d'après period (via TRADING_CONFIG)
        ann_map = {
            "D": TRADING_CONFIG.get("trading_days_per_year", 252),
            "W": TRADING_CONFIG.get("trading_weeks_per_year", 52),
            "M": TRADING_CONFIG.get("trading_months_per_year", 12),
        }
        ann_factor = ann_map[self.period]
        annual_return = (1 + returns.mean()) ** ann_factor - 1
        annual_vol = returns.std() * np.sqrt(ann_factor)
        rf = risk_free_rate if risk_free_rate is not None else TRADING_CONFIG.get("risk_free_rate", 0.0)
        sharpe = (annual_return - rf) / (annual_vol + 1e-12)

        # Sortino: std des rendements négatifs
        downside = returns[returns < 0]
        downside_vol = downside.std() * np.sqrt(ann_factor) if not downside.empty else 0.0
        sortino = (annual_return - rf) / (downside_vol + 1e-12)

        # Max drawdown
        cummax = eq.cummax()
        drawdown = (eq - cummax) / cummax
        max_dd = drawdown.min()

        # Trades stats
        trades_df = pd.DataFrame([t.__dict__ for t in self.trades])
        total_trades = len(trades_df)
        win_rate = 0.0
        profit_factor = np.nan
        avg_trade = np.nan
        if total_trades > 0 and "realized_pnl" in trades_df.columns:
            realized = trades_df["realized_pnl"].astype(float)
            realized_nonzero = realized[realized != 0]
            if not realized_nonzero.empty:
                avg_trade = realized_nonzero.mean()
                profits = realized_nonzero[realized_nonzero > 0].sum()
                losses = -realized_nonzero[realized_nonzero < 0].sum()
                profit_factor = (profits / losses) if losses > 0 else np.inf
                win_rate = (realized_nonzero > 0).mean()
            else:
                # Fallback: variations d'equity
                pnl_series = eq.diff().dropna()
                avg_trade = pnl_series.mean() if len(pnl_series) > 0 else 0.0
                profits = pnl_series[pnl_series > 0].sum()
                losses = -pnl_series[pnl_series < 0].sum()
                profit_factor = (profits / losses) if losses > 0 else np.inf
                win_rate = (pnl_series > 0).mean()

        metrics = {
            "total_return": float(total_return),
            "annual_return": float(annual_return),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": float(max_dd),
            "win_rate": float(win_rate),
            "profit_factor": float(profit_factor) if np.isfinite(profit_factor) else float("inf"),
            "total_trades": int(total_trades),
            "avg_trade": float(avg_trade) if not np.isnan(avg_trade) else 0.0,
        }
        self.logger.info(f"Metrics: {metrics}")
        return metrics

    # -------------- Résultats --------------
    def get_results(self) -> Dict[str, pd.DataFrame]:
        """
        Retourne les DataFrames de résultats (trades & equity curve).

        Returns:
            Dict avec 'trades' et 'equity_curve'
        """
        trades_df = pd.DataFrame([t.__dict__ for t in self.trades])
        if not trades_df.empty:
            trades_df = trades_df.sort_values("date").reset_index(drop=True)
        return {"trades": trades_df, "equity_curve": self.equity_curve.copy()}

    def plot_results(self) -> Optional[Any]:
        """Trace l'equity curve et les drawdowns. Retourne une Figure matplotlib si dispo."""
        try:
            if not HAS_MATPLOTLIB:
                raise ImportError("matplotlib indisponible")
            fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
            eq = self.equity_curve["equity"].astype(float)
            ax[0].plot(eq.index, eq.values, label="Equity")
            ax[0].set_title("Equity Curve")
            ax[0].legend()

            cummax = eq.cummax()
            drawdown = (eq - cummax) / cummax
            ax[1].plot(drawdown.index, drawdown.values, color="red", label="Drawdown")
            ax[1].axhline(0, color="black", linewidth=0.5)
            ax[1].legend()
            plt.tight_layout()
            return fig
        except Exception as e:
            self.logger.warning(f"Plot indisponible: {e}")
            return None

    def save_results(self, output_dir: str = "./backtest_results") -> None:
        """
        Sauvegarder les résultats en CSV.

        Args:
            output_dir: Répertoire de sortie
        """
        import os

        os.makedirs(output_dir, exist_ok=True)

        results = self.get_results()
        results["trades"].to_csv(f"{output_dir}/trades.csv", index=False)
        results["equity_curve"].to_csv(f"{output_dir}/equity_curve.csv")

        metrics = self.calculate_metrics()
        pd.Series(metrics).to_csv(f"{output_dir}/metrics.csv")

        self.logger.info(f"Résultats sauvegardés dans {output_dir}")
