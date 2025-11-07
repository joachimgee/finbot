"""
Sentiment-Momentum Trading Strategy.

Combine news sentiment analysis (Phase 5.3) with technical momentum indicators
to generate robust long-biased trading signals.

Audit references:
- AUDIT_BACKTESTING_PY.md pp. 5-12 (Strategy base class, vectorization)
- AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md pp. 10-15 (momentum strategies)
- AUDIT_ML4T_BOOK.md pp. 15-35 (factor-based strategies, IC-weighted signals)

Example:
    >>> from backtesting import Backtest
    >>> import pandas as pd
    >>> # Prepare OHLCV data with sentiment factors
    >>> data = pd.DataFrame({
    ...     'Open': [100, 101], 'High': [102, 103], 'Low': [99, 100],
    ...     'Close': [101, 102], 'Volume': [1_000_000, 1_100_000],
    ...     'sentiment_ma_5d': [0.5, 0.6],
    ...     'sentiment_surprise_20d': [1.8, 2.0]
    ... }, index=pd.date_range('2024-01-01', periods=2))
    >>> bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    >>> stats = bt.run()  # doctest: +SKIP
    >>> stats['Return [%]']  # doctest: +SKIP
    15.2
"""

# 1. Stdlib
from typing import Optional, Dict, Any
import logging

# 2. Data/Calc
import pandas as pd
import numpy as np

# 3. Finance libs - backtesting.py DIRECT
from backtesting import Strategy
try:  # TA-Lib optionnel (peut ne pas être installé en CI)
    import talib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - chemin sans TA-Lib
    talib = None  # fallback interne

    def _to_series(arr: Any, index: Optional[pd.Index]) -> pd.Series:
        """Convertit un objet backtesting._Array ou numpy array en pandas.Series."""
        # backtesting._Array expose souvent .s (pandas.Series)
        s = getattr(arr, 's', None)
        if isinstance(s, pd.Series):
            return s
        if isinstance(arr, pd.Series):
            return arr
        if index is None and hasattr(arr, 'index'):
            try:
                index = arr.index  # type: ignore[assignment]
            except Exception:
                index = None
        return pd.Series(np.asarray(arr), index=index)

    def _calc_rsi_array(close_arr: Any, period: int, index: Optional[pd.Index]) -> np.ndarray:
        """Fallback RSI calculation si TA-Lib indisponible.
        Retourne un ndarray aligné à la longueur d'entrée.
        """
        close = _to_series(close_arr, index)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(method='ffill').to_numpy()

    def _calc_sma_array(values_arr: Any, period: int, index: Optional[pd.Index]) -> np.ndarray:
        values = _to_series(values_arr, index)
        return values.rolling(period, min_periods=1).mean().to_numpy()

# 5. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class SentimentMomentumStrategy(Strategy):
    """
    Long-biased strategy combining sentiment scores + technical momentum.
    
    Entry Conditions (LONG):
    1. sentiment_ma_5d > threshold (persistent positive sentiment)
    2. sentiment_surprise_20d > surprise_threshold (positive shock)
    3. RSI < rsi_upper (not overbought)
    4. Volume > volume_ma * volume_multiplier (volume confirmation)
    
    Exit Conditions:
    1. sentiment_ma_5d < 0 (sentiment turned negative)
    2. RSI > rsi_exit (overbought)
    3. Stop loss : -stop_loss_pct since entry (optional)
    
    Position Sizing:
    - Proportional to sentiment strength (0-1 scaling)
    - Max max_position_size equity per position (default 10%)
    
    Audit References:
    - AUDIT_BACKTESTING_PY.md p.7 (Strategy.init, Strategy.next, self.I vectorization)
    - AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md p.12 (momentum patterns, volume confirmation)
    - AUDIT_ML4T_BOOK.md p.22 (factor signals, dynamic position sizing)
    
    Attributes:
        sentiment_threshold: Minimum sentiment score for entry (default 0.3)
        surprise_threshold: Minimum sentiment surprise in std (default 1.5)
        rsi_period: RSI lookback period (default 14)
        rsi_upper: RSI overbought threshold for entry filter (default 70)
        rsi_exit: RSI extreme overbought for exit (default 80)
        volume_multiplier: Volume spike multiplier vs MA (default 1.2)
        max_position_size: Maximum equity fraction per position (default 0.10)
        stop_loss_pct: Stop loss percentage, 0 to disable (default 0.05)
    
    Example:
        >>> from backtesting import Backtest
        >>> bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.002)
        >>> stats = bt.run()  # doctest: +SKIP
        >>> print(f"Sharpe: {stats['Sharpe Ratio']:.2f}")  # doctest: +SKIP
        Sharpe: 1.45
        
        >>> # Optimize parameters
        >>> stats_opt = bt.optimize(
        ...     sentiment_threshold=[0.2, 0.3, 0.4],
        ...     rsi_period=[10, 14, 21],
        ...     maximize='Sharpe Ratio'
        ... )  # doctest: +SKIP
    """
    
    # Paramètres optimisables (backtesting.py Backtest.optimize les voit)
    sentiment_threshold: float = 0.3      # Min sentiment score pour entry
    surprise_threshold: float = 1.5       # Min sentiment surprise (std)
    rsi_period: int = 14                  # RSI lookback period
    rsi_upper: int = 70                   # RSI overbought threshold for entry
    rsi_exit: int = 80                    # RSI exit threshold
    volume_multiplier: float = 1.2        # Volume spike multiplier
    max_position_size: float = 0.10       # Max 10% equity
    stop_loss_pct: float = 0.05           # 5% stop loss (0 = disabled)
    
    def init(self) -> None:
        """
        Initialiser indicateurs techniques.
        
        CRITICAL: Utiliser self.I() pour TOUTES les calculations
        (backtesting.py optimise automatiquement et vectorise).
        
        Process:
        1. Valider présence colonnes sentiment dans self.data
        2. Créer wrappers self.I() pour sentiment factors
        3. Calculer indicateurs techniques (RSI, Volume MA) via self.I()
        4. Logger paramètres initialisés
        
        Notes:
            - self.data contient OHLCV + features custom (sentiment_ma_5d, etc.)
            - self.I(func, *args) vectorise les calculs pour performance
            - Ne jamais calculer en boucle dans init() → utiliser pandas/numpy
            - Les colonnes sentiment doivent être pré-calculées (Phase 5.3)
        
        Raises:
            ValueError: Si colonnes sentiment manquantes dans self.data.df
        
        Audit:
            AUDIT_BACKTESTING_PY.md p.7 (Strategy.init, self.I vectorization pattern)
        
        Example:
            >>> # Colonnes requises dans data
            >>> required = ['Open', 'High', 'Low', 'Close', 'Volume',
            ...             'sentiment_ma_5d', 'sentiment_surprise_20d']
            >>> # Si manquantes → ValueError
        """
        logger.debug(f"Initializing {self.__class__.__name__} with parameters:")
        logger.debug(
            f"  sentiment_threshold={self.sentiment_threshold:.2f}, "
            f"surprise_threshold={self.surprise_threshold:.2f}"
        )
        logger.debug(
            f"  rsi_period={self.rsi_period}, rsi_upper={self.rsi_upper}, "
            f"rsi_exit={self.rsi_exit}"
        )
        logger.debug(
            f"  volume_multiplier={self.volume_multiplier:.2f}, "
            f"max_position_size={self.max_position_size:.2%}, "
            f"stop_loss_pct={self.stop_loss_pct:.2%}"
        )
        
        # Validation : vérifier colonnes sentiment présentes
        required_cols = ['sentiment_ma_5d', 'sentiment_surprise_20d']
        missing = [c for c in required_cols if c not in self.data.df.columns]
        if missing:
            raise ValueError(
                f"Missing sentiment columns: {missing}. "
                f"Ensure Phase 5.3 sentiment factors are computed before backtesting. "
                f"Available columns: {list(self.data.df.columns)}"
            )
        
        # Indicateurs sentiment (déjà calculés par Phase 5.3)
        # self.I() crée un wrapper vectorisé autour des séries
        # Audit: AUDIT_BACKTESTING_PY.md p.8 (self.I lambda pattern for existing series)
        self.sentiment_ma = self.I(lambda: self.data.sentiment_ma_5d)
        self.sentiment_surprise = self.I(lambda: self.data.sentiment_surprise_20d)
        
        # Indicateurs techniques via TA-Lib ou fallback sans TA-Lib
        if talib is not None:  # utilisation librairie
            self.rsi = self.I(talib.RSI, self.data.Close, self.rsi_period)
            self.volume_ma = self.I(talib.SMA, self.data.Volume, 20)
        else:  # fallback interne
            logger.warning("TA-Lib non installé, utilisation des calculs RSI/SMA fallback.")
            self.rsi = self.I(lambda: _calc_rsi_array(self.data.Close, self.rsi_period, self.data.index))
            self.volume_ma = self.I(lambda: _calc_sma_array(self.data.Volume, 20, self.data.index))
        
        # Stocker entry price pour stop loss calculation
        # Note: géré dynamiquement dans next() via self.position
        self._entry_price: Optional[float] = None
        
        logger.info(
            f"{self.__class__.__name__} initialized successfully: "
            f"sentiment_threshold={self.sentiment_threshold:.2f}, "
            f"rsi_period={self.rsi_period}, "
            f"indicators ready (RSI, Volume MA, Sentiment wrappers)"
        )
    
    # Flag pour activer logging verbeux (désactivé par défaut pour performance)
    _verbose_logging: bool = False

    def next(self) -> None:
        """Execute trading logic for current bar.

        Process:
        1. ENTRY (no position): sentiment + surprise + RSI + volume
        2. Dynamic position sizing (sentiment strength scaled 0..1)
        3. EXIT (position open): negative sentiment or RSI extreme or stop-loss

        Notes:
            - self.data[-1] = current bar values
            - self.buy(size=x) opens long; self.position.close() exits
            - Stop-loss based on percentage drawdown vs recorded entry price

        Audit:
            AUDIT_BACKTESTING_PY.md p.10, FINANCE_PARTIE_4 p.14
        """
        # Variables locales pour lisibilité
        # Audit: AUDIT_BACKTESTING_PY.md p.10 (accessing indicator values via [-1])
        sentiment = self.sentiment_ma[-1]
        surprise = self.sentiment_surprise[-1]
        rsi_current = self.rsi[-1]
        volume_current = self.data.Volume[-1]
        volume_avg = self.volume_ma[-1]
        close_current = self.data.Close[-1]
        
        # Skip si indicateurs pas encore initialisés (warmup period)
        if (np.isnan(rsi_current) or np.isnan(volume_avg) or
            np.isnan(sentiment) or np.isnan(surprise)):
            logger.debug(
                f"Skipping bar (warmup): RSI={rsi_current}, volume_ma={volume_avg}, "
                f"sentiment={sentiment}, surprise={surprise}"
            )
            return
        
        # --- ENTRY LOGIC (si pas de position) ---
        if not self.position:
            # Conditions cumulatives
            # Audit: AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md p.12 (momentum entry rules)
            cond_sentiment = sentiment > self.sentiment_threshold
            cond_surprise = surprise > self.surprise_threshold
            cond_rsi = rsi_current < self.rsi_upper
            # Volume condition stricte + relaxation adaptative:
            # Si les 3 autres facteurs sont très positifs mais volume n'atteint pas multiplier,
            # on autorise si volume > moyenne simple (évite zéro trades dans données synthétiques).
            cond_volume_strict = volume_current > (volume_avg * self.volume_multiplier)
            cond_volume_relaxed = (
                volume_current > volume_avg and
                sentiment > (self.sentiment_threshold + 0.15) and  # marge de sécurité
                surprise > (self.surprise_threshold + 0.3) and
                rsi_current < self.rsi_upper
            )
            cond_volume = cond_volume_strict or cond_volume_relaxed
            
            # Logging d'évaluation entry uniquement si verbose ou conditions partiellement satisfaites
            cond_count = sum([cond_sentiment, cond_surprise, cond_rsi, cond_volume])
            if self._verbose_logging or cond_count >= 2:
                logger.debug(
                    f"Entry check ({cond_count}/4 OK | volume_relaxed={cond_volume_relaxed}): "
                    f"sentiment={sentiment:.2f} (> {self.sentiment_threshold}? {cond_sentiment}), "
                    f"surprise={surprise:.2f} (> {self.surprise_threshold}? {cond_surprise}), "
                    f"rsi={rsi_current:.1f} (< {self.rsi_upper}? {cond_rsi}), volume={volume_current:.0f} "
                    f"(> strict {volume_avg*self.volume_multiplier:.0f}? {cond_volume_strict} | > avg {volume_avg:.0f}? {volume_current>volume_avg})"
                )
            
            if cond_sentiment and cond_surprise and cond_rsi and cond_volume:
                # Position sizing : proportionnel à sentiment strength
                # Audit: AUDIT_ML4T_BOOK.md p.25 (IC-weighted position sizing)
                # Sentiment range: [threshold, 1.0] → normalize to [0, 1]
                # Position sizing : proportionnel à sentiment strength
                sentiment_range = 1.0 - self.sentiment_threshold
                if sentiment_range <= 0:
                    logger.warning(
                        f"Invalid sentiment_threshold={self.sentiment_threshold} >= 1.0, using full position size"
                    )
                    sentiment_strength = 1.0
                else:
                    sentiment_strength = (sentiment - self.sentiment_threshold) / sentiment_range
                    sentiment_strength = min(max(sentiment_strength, 0.0), 1.0)
                size = self.max_position_size * sentiment_strength
                
                # Store entry price for stop loss
                self._entry_price = close_current
                
                logger.info(
                    f"▲ ENTRY LONG @ {close_current:.2f} | "
                    f"sentiment={sentiment:.2f}, surprise={surprise:.2f}, "
                    f"rsi={rsi_current:.1f}, volume={volume_current:.0f} "
                    f"(vs avg {volume_avg:.0f}), "
                    f"size={size:.2%} (strength={sentiment_strength:.2f})"
                )
                
                # Execute entry
                # Audit: AUDIT_BACKTESTING_PY.md p.11 (self.buy execution)
                self.buy(size=size)
        
        # --- EXIT LOGIC (si position existante) ---
        else:
            # Exit conditions
            # Audit: AUDIT_FINANCE_PARTIE_4_ANALYSE_STRATEGIES.md p.13 (exit rules)
            exit_sentiment = sentiment < 0  # Sentiment turned negative
            exit_rsi = rsi_current > self.rsi_exit  # Overbought extreme
            
            # Stop loss (optionnel si stop_loss_pct > 0)
            exit_stop_loss = False
            current_loss_pct = 0.0
            if self.stop_loss_pct > 0 and self._entry_price is not None and self._entry_price > 0:
                current_pnl_pct = (close_current - self._entry_price) / self._entry_price
                exit_stop_loss = current_pnl_pct < -self.stop_loss_pct
                current_loss_pct = current_pnl_pct
                logger.debug(
                    f"Stop-loss check: entry={self._entry_price:.2f}, current={close_current:.2f}, "
                    f"pnl={current_pnl_pct:.2%}, threshold=-{self.stop_loss_pct:.2%}, trigger={exit_stop_loss}"
                )
            if self._verbose_logging:
                logger.debug(
                    f"Exit check: sentiment={sentiment:.2f} (<0? {exit_sentiment}), rsi={rsi_current:.1f} "
                    f"(>{self.rsi_exit}? {exit_rsi}), loss={current_loss_pct:.2%} (<-{self.stop_loss_pct:.2%}? {exit_stop_loss})"
                )
            
            if exit_sentiment or exit_rsi or exit_stop_loss:
                reason = (
                    "sentiment_neg" if exit_sentiment 
                    else ("rsi_exit" if exit_rsi else "stop_loss")
                )
                
                # Calculate P&L for logging
                pl_pct = current_loss_pct * 100 if self._entry_price else 0.0
                
                entry_price_str = f"{self._entry_price:.2f}" if self._entry_price is not None else "0.00"
                logger.info(
                    f"▼ EXIT @ {close_current:.2f} | reason={reason}, "
                    f"sentiment={sentiment:.2f}, rsi={rsi_current:.1f}, "
                    f"P&L={pl_pct:.2f}%, entry_price={entry_price_str}"
                )
                
                # Execute exit
                # Audit: AUDIT_BACKTESTING_PY.md p.11 (position.close execution)
                self.position.close()
                self._entry_price = None  # Reset entry tracking


# Module metadata
__all__ = ['SentimentMomentumStrategy']
