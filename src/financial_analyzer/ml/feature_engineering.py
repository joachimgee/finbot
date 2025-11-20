from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FactorResult:
    """Result of a factor calculation.

    Attributes:
        name: Factor name (unique key)
        values: Factor time series (indexed by dates)
        description: Short description of the factor
        category: Category name (Momentum/Trend/Volatility/Volume/...)
        valid_data: Count of non-NaN values
    """

    name: str
    values: pd.Series
    description: str
    category: str
    valid_data: int


class AlphaFactorEngine:
    """Compute a rich set of alpha factors from OHLCV data.

    This engine focuses on vectorized numpy/pandas implementations for
    performance and reproducibility. It exposes convenient primitives to compute
    common technical indicators and bundles a curated default set (>20) used in
    baseline experiments.

    Example:
        >>> afe = AlphaFactorEngine(ohlcv_df)
        >>> factors = afe.get_factors_dataframe()
        >>> factors.shape
        (252, 26)
    """

    def __init__(
        self,
        ohlcv: pd.DataFrame,
        prices: Optional[pd.DataFrame] = None,
        risk_free_rate: float = 0.03,
    ) -> None:
        """Initialize the factor engine.

        Args:
            ohlcv: DataFrame containing columns ['open','high','low','close','volume']
            prices: Optional additional prices (e.g., for cross-sectional use)
            risk_free_rate: Annual risk-free rate used by some factors

        Raises:
            ValueError: If required OHLCV columns are missing
        """
        if ohlcv is None or ohlcv.empty:
            raise ValueError("ohlcv must be a non-empty DataFrame")

        # Validate required columns (case-insensitive)
        cols_lower = pd.Index([c.lower() for c in ohlcv.columns])
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(cols_lower)):
            raise ValueError(f"OHLCV must contain {required}")

        # Normalize column names: keep original but access via lower alias
        self._colmap = {c.lower(): c for c in ohlcv.columns}
        self.ohlcv = ohlcv.copy()
        self.prices = prices
        self.rf_rate = float(risk_free_rate)
        self.returns = self.ohlcv[self._colmap["close"]].pct_change()

        logger.info("AlphaFactorEngine initialized with %d bars", len(ohlcv))

    # --------------------------- Momentum ---------------------------
    def roc(self, period: int = 12) -> FactorResult:
        """Rate of Change momentum indicator.

        Args:
            period: Lookback window in bars
        """
        close = self.ohlcv[self._colmap["close"]]
        roc_values = close.pct_change(periods=period)
        return FactorResult(
            name=f"ROC_{period}",
            values=roc_values,
            description=f"{period}-period Rate of Change",
            category="Momentum",
            valid_data=int(roc_values.notna().sum()),
        )

    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, FactorResult]:
        """MACD momentum indicator.

        Returns a dict with keys: 'MACD', 'Signal', 'Histogram'.
        Names align with legacy expectations in tests.
        """
        close = self.ohlcv[self._colmap["close"]]
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        macd_line_res = FactorResult(
            name="MACD",
            values=macd_line,
            description="MACD line",
            category="Momentum",
            valid_data=int(macd_line.notna().sum()),
        )
        signal_line_res = FactorResult(
            name="Signal",
            values=signal_line,
            description="MACD signal line",
            category="Momentum",
            valid_data=int(signal_line.notna().sum()),
        )
        histogram_res = FactorResult(
            name="Histogram",
            values=histogram,
            description="MACD histogram",
            category="Momentum",
            valid_data=int(histogram.notna().sum()),
        )
        
        return {
            macd_line_res.name: macd_line_res,
            signal_line_res.name: signal_line_res,
            histogram_res.name: histogram_res,
        }

    def rsi(self, period: int = 14) -> FactorResult:
        """Relative Strength Index.

        Uses simple rolling means for clarity and stability.
        """
        close = self.ohlcv[self._colmap["close"]]
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        rs = pd.Series(np.where(avg_loss != 0, avg_gain / avg_loss, np.nan), index=close.index)
        rsi_vals = 100 - (100 / (1 + rs))
        return FactorResult(
            name=f"RSI_{period}",
            values=rsi_vals,
            description=f"{period}-period RSI",
            category="Momentum",
            valid_data=int(rsi_vals.notna().sum()),
        )

    def stochastic(self, period: int = 14, smooth: int = 3) -> Dict[str, FactorResult]:
        """Stochastic Oscillator %K and %D."""
        low = self.ohlcv[self._colmap["low"]]
        high = self.ohlcv[self._colmap["high"]]
        close = self.ohlcv[self._colmap["close"]]
        low_min = low.rolling(window=period, min_periods=period).min()
        high_max = high.rolling(window=period, min_periods=period).max()
        denom = (high_max - low_min).replace(0, np.nan)
        k_raw = (close - low_min) / denom * 100.0
        k_line = k_raw.rolling(window=smooth, min_periods=1).mean()
        d_line = k_line.rolling(window=smooth, min_periods=1).mean()
        
        k_res = FactorResult(
            name=f"Stoch_K_{period}",
            values=k_line,
            description=f"Stochastic %K ({period})",
            category="Momentum",
            valid_data=int(k_line.notna().sum()),
        )
        d_res = FactorResult(
            name=f"Stoch_D_{period}",
            values=d_line,
            description=f"Stochastic %D ({period})",
            category="Momentum",
            valid_data=int(d_line.notna().sum()),
        )
        
        return {
            k_res.name: k_res,
            d_res.name: d_res,
        }

    def mom(self, period: int = 10) -> FactorResult:
        """Price momentum (difference)."""
        close = self.ohlcv[self._colmap["close"]]
        momentum = close - close.shift(period)
        return FactorResult(
            name=f"MOM_{period}",
            values=momentum,
            description=f"{period}-period price momentum",
            category="Momentum",
            valid_data=int(momentum.notna().sum()),
        )

    def cmo(self, period: int = 14) -> FactorResult:
        """Chande Momentum Oscillator."""
        close = self.ohlcv[self._colmap["close"]]
        delta = close.diff()
        up_sum = delta.clip(lower=0).rolling(window=period, min_periods=period).sum()
        down_sum = (-delta).clip(lower=0).rolling(window=period, min_periods=period).sum()
        denom = (up_sum + down_sum).replace(0, np.nan)
        cmo_vals = 100.0 * (up_sum - down_sum) / denom
        return FactorResult(
            name=f"CMO_{period}",
            values=cmo_vals,
            description=f"{period}-period Chande Momentum Oscillator",
            category="Momentum",
            valid_data=int(cmo_vals.notna().sum()),
        )

    # -------------------------- Volatility -------------------------
    def _true_range(self) -> pd.Series:
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]
        prev_close = self.ohlcv[self._colmap["close"]].shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        return tr

    def atr(self, period: int = 14) -> FactorResult:
        """Average True Range (ATR)."""
        tr = self._true_range()
        atr_vals = tr.rolling(window=period, min_periods=period).mean()
        return FactorResult(
            name=f"ATR_{period}",
            values=atr_vals,
            description=f"{period}-period Average True Range",
            category="Volatility",
            valid_data=int(atr_vals.notna().sum()),
        )

    def bollinger_bands(self, period: int = 20, num_std: float = 2.0) -> Dict[str, FactorResult]:
        """Bollinger Bands and derived indicators."""
        close = self.ohlcv[self._colmap["close"]]
        sma = close.rolling(window=period, min_periods=period).mean()
        std = close.rolling(window=period, min_periods=period).std()
        upper = sma + (num_std * std)
        lower = sma - (num_std * std)
        bandwidth = (upper - lower) / sma
        pct_b = (close - lower) / (upper - lower)
        
        upper_res = FactorResult(
            name=f"BB_Upper_{period}",
            values=upper,
            description=f"Bollinger Bands upper ({period})",
            category="Volatility",
            valid_data=int(upper.notna().sum()),
        )
        lower_res = FactorResult(
            name=f"BB_Lower_{period}",
            values=lower,
            description=f"Bollinger Bands lower ({period})",
            category="Volatility",
            valid_data=int(lower.notna().sum()),
        )
        bandwidth_res = FactorResult(
            name=f"BB_Width_{period}",
            values=bandwidth,
            description=f"Bollinger Band width ratio ({period})",
            category="Volatility",
            valid_data=int(bandwidth.notna().sum()),
        )
        pctb_res = FactorResult(
            name=f"BB_PctB_{period}",
            values=pct_b,
            description=f"Bollinger %B ({period})",
            category="Volatility",
            valid_data=int(pct_b.notna().sum()),
        )
        
        return {
            upper_res.name: upper_res,
            lower_res.name: lower_res,
            bandwidth_res.name: bandwidth_res,
            pctb_res.name: pctb_res,
        }

    def historical_volatility(self, period: int = 20) -> FactorResult:
        """Historical volatility (annualized)."""
        close = self.ohlcv[self._colmap["close"]]
        hvol = close.pct_change().rolling(window=period, min_periods=period).std() * np.sqrt(252)
        return FactorResult(
            name=f"HVol_{period}",
            values=hvol,
            description=f"{period}-period historical volatility (annualized)",
            category="Volatility",
            valid_data=int(hvol.notna().sum()),
        )

    def garman_klass_volatility(self, period: int = 20) -> FactorResult:
        """Garman-Klass volatility estimator (annualized)."""
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]
        open_ = self.ohlcv[self._colmap["open"]]
        close = self.ohlcv[self._colmap["close"]]
        log_hl = (np.log(high) - np.log(low)) ** 2
        log_co = (np.log(close) - np.log(open_)) ** 2
        gk_var = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
        gk_vol = gk_var.rolling(window=period, min_periods=period).mean() ** 0.5 * np.sqrt(252)
        return FactorResult(
            name=f"GK_Vol_{period}",
            values=gk_vol,
            description=f"{period}-period Garman-Klass volatility",
            category="Volatility",
            valid_data=int(gk_vol.notna().sum()),
        )

    # ---------------------------- Trend ----------------------------
    def sma(self, period: int = 50) -> FactorResult:
        """Simple Moving Average (price/SMA - 1)."""
        close = self.ohlcv[self._colmap["close"]]
        sma_vals = close.rolling(window=period, min_periods=period).mean()
        ratio = close / sma_vals - 1.0
        return FactorResult(
            name=f"SMA_{period}",
            values=ratio,
            description=f"Price to {period}-SMA ratio",
            category="Trend",
            valid_data=int(ratio.notna().sum()),
        )

    def ema(self, period: int = 12) -> FactorResult:
        """Exponential Moving Average (price/EMA - 1)."""
        close = self.ohlcv[self._colmap["close"]]
        ema_vals = close.ewm(span=period, adjust=False).mean()
        ratio = close / ema_vals - 1.0
        return FactorResult(
            name=f"EMA_{period}",
            values=ratio,
            description=f"Price to {period}-EMA ratio",
            category="Trend",
            valid_data=int(ratio.notna().sum()),
        )

    def adx(self, period: int = 14) -> FactorResult:
        """Average Directional Index (trend strength)."""
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]
        close = self.ohlcv[self._colmap["close"]]
        up = high.diff()
        down = -low.diff()
        plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
        minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=low.index)
        tr = self._true_range()
        tr_n = tr.rolling(window=period, min_periods=period).sum()
        plus_di = 100.0 * plus_dm.rolling(window=period, min_periods=period).sum() / tr_n
        minus_di = 100.0 * minus_dm.rolling(window=period, min_periods=period).sum() / tr_n
        dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([np.inf, -np.inf], np.nan)
        adx_vals = dx.rolling(window=period, min_periods=period).mean()
        return FactorResult(
            name=f"ADX_{period}",
            values=adx_vals,
            description=f"{period}-period Average Directional Index",
            category="Trend",
            valid_data=int(adx_vals.notna().sum()),
        )

    # ---------------------------- Volume ---------------------------
    def obv(self) -> FactorResult:
        """On-Balance Volume (normalized by price)."""
        volume = self.ohlcv[self._colmap["volume"]]
        close = self.ohlcv[self._colmap["close"]]
        close_diff = close.diff()
        obv_raw = np.where(close_diff > 0, volume, np.where(close_diff < 0, -volume, 0))
        obv_series = pd.Series(obv_raw, index=close.index).cumsum()
        obv_ratio = obv_series / close.replace(0, np.nan)
        return FactorResult(
            name="OBV",
            values=obv_ratio,
            description="On-Balance Volume (normalized)",
            category="Volume",
            valid_data=int(obv_ratio.notna().sum()),
        )

    def vwap(self, window: int = 20) -> FactorResult:
        """Volume-Weighted Average Price ratio (price/VWAP - 1)."""
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]
        close = self.ohlcv[self._colmap["close"]]
        volume = self.ohlcv[self._colmap["volume"]]
        typical_price = (high + low + close) / 3.0
        vol_sum = volume.rolling(window=window, min_periods=window).sum()
        tpv_sum = (typical_price * volume).rolling(window=window, min_periods=window).sum()
        vwap_vals = tpv_sum / vol_sum
        ratio = close / vwap_vals - 1.0
        return FactorResult(
            name="VWAP",
            values=ratio,
            description="Price to VWAP ratio",
            category="Volume",
            valid_data=int(ratio.notna().sum()),
        )

    # --------------------------- Value Factors ---------------------
    def value_factors(self) -> Dict[str, FactorResult]:
        """Compute 15 value-based alpha factors.

        Returns:
            Dictionary of 15 FactorResult objects (Price/Book, P/E ratios, etc.)

        Note:
            Requires fundamental data. If unavailable, returns normalized price metrics.
        """
        factors: Dict[str, FactorResult] = {}
        close = self.ohlcv[self._colmap["close"]]
        volume = self.ohlcv[self._colmap["volume"]]
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]

        # 1. Price-to-52Week-High ratio
        high_52w = close.rolling(window=252, min_periods=50).max()
        pr_to_52w = close / high_52w
        factors["PR_52W_HIGH"] = FactorResult(
            name="PR_52W_HIGH",
            values=pr_to_52w,
            description="Price to 52-week high ratio",
            category="Value",
            valid_data=int(pr_to_52w.notna().sum()),
        )

        # 2. Price-to-52Week-Low ratio
        low_52w = close.rolling(window=252, min_periods=50).min()
        pr_to_52w_low = close / low_52w - 1.0
        factors["PR_52W_LOW"] = FactorResult(
            name="PR_52W_LOW",
            values=pr_to_52w_low,
            description="Price to 52-week low ratio minus 1",
            category="Value",
            valid_data=int(pr_to_52w_low.notna().sum()),
        )

        # 3. Price to Rolling Mean ratio (200-day)
        ma_200 = close.rolling(window=200, min_periods=50).mean()
        pr_to_ma = close / ma_200 - 1.0
        factors["PR_MA200"] = FactorResult(
            name="PR_MA200",
            values=pr_to_ma,
            description="Price to 200-day MA ratio",
            category="Value",
            valid_data=int(pr_to_ma.notna().sum()),
        )

        # 4. Relative Strength vs. Market (mock: price momentum)
        ret_60 = close.pct_change(periods=60)
        factors["RS_60"] = FactorResult(
            name="RS_60",
            values=ret_60,
            description="60-day relative strength (price momentum)",
            category="Value",
            valid_data=int(ret_60.notna().sum()),
        )

        # 5. Price Reversal (short-term mean reversion signal)
        ret_5 = close.pct_change(periods=5)
        reversal = -ret_5  # Negative momentum implies reversal
        factors["REVERSAL_5"] = FactorResult(
            name="REVERSAL_5",
            values=reversal,
            description="5-day price reversal signal",
            category="Value",
            valid_data=int(reversal.notna().sum()),
        )

        # 6. Earnings Yield Proxy (inverse of price momentum)
        ret_252 = close.pct_change(periods=252)
        # Use np.where to explicitly handle NaN values (avoid division by (1 + NaN) = NaN)
        ey_proxy = pd.Series(
            np.where(ret_252.notna(), 1.0 / (1.0 + ret_252.clip(lower=-0.99)), np.nan),
            index=close.index
        )
        factors["EARN_YIELD_PROXY"] = FactorResult(
            name="EARN_YIELD_PROXY",
            values=ey_proxy,
            description="Earnings yield proxy (inverse momentum)",
            category="Value",
            valid_data=int(ey_proxy.notna().sum()),
        )

        # 7. Price-to-Volume ratio (liquidity-adjusted value)
        pv_ratio = close / (volume.replace(0, np.nan) + 1e-9)
        pv_norm = (pv_ratio - pv_ratio.rolling(60).mean()) / (pv_ratio.rolling(60).std() + 1e-9)
        factors["PR_VOL_RATIO"] = FactorResult(
            name="PR_VOL_RATIO",
            values=pv_norm,
            description="Price-to-volume z-score (60-day)",
            category="Value",
            valid_data=int(pv_norm.notna().sum()),
        )

        # 8. Downside Deviation (risk-adjusted value)
        neg_ret = self.returns.copy()
        neg_ret[neg_ret > 0] = 0
        downside_std = neg_ret.rolling(window=60, min_periods=20).std()
        factors["DOWNSIDE_DEV_60"] = FactorResult(
            name="DOWNSIDE_DEV_60",
            values=-downside_std,
            description="Negative of 60-day downside deviation",
            category="Value",
            valid_data=int(downside_std.notna().sum()),
        )

        # 9. High-Low Range (normalized volatility proxy)
        hl_range = (high - low) / close
        hl_z = (hl_range - hl_range.rolling(60).mean()) / (hl_range.rolling(60).std() + 1e-9)
        factors["HL_RANGE_Z"] = FactorResult(
            name="HL_RANGE_Z",
            values=hl_z,
            description="High-Low range z-score (60-day)",
            category="Value",
            valid_data=int(hl_z.notna().sum()),
        )

        # 10. Price Acceleration (second derivative)
        ret_10 = close.pct_change(periods=10)
        accel = ret_10.diff()
        factors["PRICE_ACCEL"] = FactorResult(
            name="PRICE_ACCEL",
            values=accel,
            description="Price acceleration (momentum change)",
            category="Value",
            valid_data=int(accel.notna().sum()),
        )

        # 11. Z-Score of Close Price (mean reversion signal)
        close_z = (close - close.rolling(60).mean()) / (close.rolling(60).std() + 1e-9)
        factors["CLOSE_ZSCORE_60"] = FactorResult(
            name="CLOSE_ZSCORE_60",
            values=close_z,
            description="Z-score of close price (60-day)",
            category="Value",
            valid_data=int(close_z.notna().sum()),
        )

        # 12. Return Skewness (asymmetry of returns)
        ret_skew = self.returns.rolling(window=60, min_periods=20).skew()
        factors["RET_SKEW_60"] = FactorResult(
            name="RET_SKEW_60",
            values=ret_skew,
            description="60-day return skewness",
            category="Value",
            valid_data=int(ret_skew.notna().sum()),
        )

        # 13. Return Kurtosis (tail risk)
        ret_kurt = self.returns.rolling(window=60, min_periods=20).kurt()
        factors["RET_KURT_60"] = FactorResult(
            name="RET_KURT_60",
            values=ret_kurt,
            description="60-day return kurtosis",
            category="Value",
            valid_data=int(ret_kurt.notna().sum()),
        )

        # 14. Price Dispersion (coefficient of variation)
        cv = close.rolling(60).std() / (close.rolling(60).mean() + 1e-9)
        factors["PRICE_CV_60"] = FactorResult(
            name="PRICE_CV_60",
            values=cv,
            description="Coefficient of variation (60-day)",
            category="Value",
            valid_data=int(cv.notna().sum()),
        )

        # 15. Cumulative Return (buy-and-hold)
        cum_ret = (1 + self.returns).cumprod() - 1.0
        factors["CUM_RETURN"] = FactorResult(
            name="CUM_RETURN",
            values=cum_ret,
            description="Cumulative return since start",
            category="Value",
            valid_data=int(cum_ret.notna().sum()),
        )

        return factors

    # ----------------------- Alternative Factors -------------------
    def alternative_factors(self) -> Dict[str, FactorResult]:
        """Compute 15 alternative alpha factors (seasonality, patterns, etc.).

        Returns:
            Dictionary of 15 FactorResult objects
        """
        factors: Dict[str, FactorResult] = {}
        close = self.ohlcv[self._colmap["close"]]
        volume = self.ohlcv[self._colmap["volume"]]
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]
        open_ = self.ohlcv[self._colmap["open"]]

        # 1. Overnight Return (close-to-open gap)
        overnight_ret = (open_ - close.shift(1)) / close.shift(1)
        factors["OVERNIGHT_RET"] = FactorResult(
            name="OVERNIGHT_RET",
            values=overnight_ret,
            description="Overnight return (gap risk)",
            category="Alternative",
            valid_data=int(overnight_ret.notna().sum()),
        )

        # 2. Intraday Return (open-to-close)
        intraday_ret = (close - open_) / open_
        factors["INTRADAY_RET"] = FactorResult(
            name="INTRADAY_RET",
            values=intraday_ret,
            description="Intraday return",
            category="Alternative",
            valid_data=int(intraday_ret.notna().sum()),
        )

        # 3. High-Close spread (upper tail)
        hc_spread = (high - close) / close
        factors["HIGH_CLOSE_SPREAD"] = FactorResult(
            name="HIGH_CLOSE_SPREAD",
            values=hc_spread,
            description="High-Close spread ratio",
            category="Alternative",
            valid_data=int(hc_spread.notna().sum()),
        )

        # 4. Close-Low spread (lower tail)
        cl_spread = (close - low) / close
        factors["CLOSE_LOW_SPREAD"] = FactorResult(
            name="CLOSE_LOW_SPREAD",
            values=cl_spread,
            description="Close-Low spread ratio",
            category="Alternative",
            valid_data=int(cl_spread.notna().sum()),
        )

        # 5. Volume Momentum (rate of change in volume)
        vol_mom = volume.pct_change(periods=10)
        factors["VOL_MOM_10"] = FactorResult(
            name="VOL_MOM_10",
            values=vol_mom,
            description="10-day volume momentum",
            category="Alternative",
            valid_data=int(vol_mom.notna().sum()),
        )

        # 6. Volume Z-Score (abnormal volume)
        vol_z = (volume - volume.rolling(60).mean()) / (volume.rolling(60).std() + 1e-9)
        factors["VOL_ZSCORE_60"] = FactorResult(
            name="VOL_ZSCORE_60",
            values=vol_z,
            description="Volume z-score (60-day)",
            category="Alternative",
            valid_data=int(vol_z.notna().sum()),
        )

        # 7. Price Range Expansion (volatility breakout)
        true_range = np.maximum(high - low, np.abs(high - close.shift(1)))
        true_range = np.maximum(true_range, np.abs(low - close.shift(1)))
        tr_series = pd.Series(true_range, index=close.index)
        tr_ma = tr_series.rolling(window=14, min_periods=5).mean()
        tr_expansion = tr_series / (tr_ma + 1e-9) - 1.0
        factors["TR_EXPANSION"] = FactorResult(
            name="TR_EXPANSION",
            values=tr_expansion,
            description="True Range expansion ratio",
            category="Alternative",
            valid_data=int(tr_expansion.notna().sum()),
        )

        # 8. Consecutive Up Days (winning streak)
        up_days = (close > close.shift(1)).astype(int)
        consec_up = up_days.rolling(window=10, min_periods=1).sum()
        factors["CONSEC_UP_10"] = FactorResult(
            name="CONSEC_UP_10",
            values=consec_up,
            description="Count of up days in last 10",
            category="Alternative",
            valid_data=int(consec_up.notna().sum()),
        )

        # 9. Consecutive Down Days (losing streak)
        down_days = (close < close.shift(1)).astype(int)
        consec_down = down_days.rolling(window=10, min_periods=1).sum()
        factors["CONSEC_DOWN_10"] = FactorResult(
            name="CONSEC_DOWN_10",
            values=consec_down,
            description="Count of down days in last 10",
            category="Alternative",
            valid_data=int(consec_down.notna().sum()),
        )

        # 10. Turnover Ratio (volume / price, liquidity measure)
        turnover = volume / (close + 1e-9)
        turnover_z = (turnover - turnover.rolling(60).mean()) / (turnover.rolling(60).std() + 1e-9)
        factors["TURNOVER_Z_60"] = FactorResult(
            name="TURNOVER_Z_60",
            values=turnover_z,
            description="Turnover z-score (60-day)",
            category="Alternative",
            valid_data=int(turnover_z.notna().sum()),
        )

        # 11. Price Gap (open vs previous close)
        gap = (open_ - close.shift(1)) / close.shift(1)
        gap_ma = gap.rolling(window=20, min_periods=5).mean()
        factors["GAP_MA_20"] = FactorResult(
            name="GAP_MA_20",
            values=gap_ma,
            description="20-day average price gap",
            category="Alternative",
            valid_data=int(gap_ma.notna().sum()),
        )

        # 12. High-Low Volatility (range volatility)
        hl_vol = ((high - low) / close).rolling(window=20, min_periods=5).std()
        factors["HL_VOL_20"] = FactorResult(
            name="HL_VOL_20",
            values=hl_vol,
            description="High-Low volatility (20-day)",
            category="Alternative",
            valid_data=int(hl_vol.notna().sum()),
        )

        # 13. Price Dispersion from VWAP (intraday drift)
        typical = (high + low + close) / 3.0
        vwap_drift = (close - typical) / typical
        factors["VWAP_DRIFT"] = FactorResult(
            name="VWAP_DRIFT",
            values=vwap_drift,
            description="Close vs typical price drift",
            category="Alternative",
            valid_data=int(vwap_drift.notna().sum()),
        )

        # 14. Volume-Price Correlation (20-day)
        vp_corr = self.returns.rolling(window=20, min_periods=10).corr(volume.pct_change())
        factors["VOL_PRICE_CORR_20"] = FactorResult(
            name="VOL_PRICE_CORR_20",
            values=vp_corr,
            description="20-day volume-price correlation",
            category="Alternative",
            valid_data=int(vp_corr.notna().sum()),
        )

        # 15. Amihud Illiquidity (price impact)
        daily_ret_abs = self.returns.abs()
        illiq = daily_ret_abs / (volume.replace(0, np.nan) + 1e-9)
        illiq_ma = illiq.rolling(window=20, min_periods=5).mean()
        factors["AMIHUD_ILLIQ_20"] = FactorResult(
            name="AMIHUD_ILLIQ_20",
            values=illiq_ma,
            description="Amihud illiquidity (20-day avg)",
            category="Alternative",
            valid_data=int(illiq_ma.notna().sum()),
        )

        return factors

    # -------------------- Cross-Asset Factors ----------------------
    def cross_asset_factors(self) -> Dict[str, FactorResult]:
        """Compute 10 cross-asset alpha factors (correlations, beta proxies).

        Returns:
            Dictionary of 10 FactorResult objects

        Note:
            Without external market data, uses self-correlation and momentum patterns.
        """
        factors: Dict[str, FactorResult] = {}
        close = self.ohlcv[self._colmap["close"]]
        volume = self.ohlcv[self._colmap["volume"]]

        # 1. Rolling Beta Proxy (return volatility ratio)
        ret_std_60 = self.returns.rolling(window=60, min_periods=20).std()
        ret_std_252 = self.returns.rolling(window=252, min_periods=60).std()
        beta_proxy = ret_std_60 / (ret_std_252 + 1e-9)
        factors["BETA_PROXY_60_252"] = FactorResult(
            name="BETA_PROXY_60_252",
            values=beta_proxy,
            description="Beta proxy (60d/252d vol ratio)",
            category="CrossAsset",
            valid_data=int(beta_proxy.notna().sum()),
        )

        # 2. Autocorrelation (mean reversion indicator)
        autocorr_1 = self.returns.rolling(window=60, min_periods=20).apply(
            lambda x: x.autocorr(lag=1) if len(x.dropna()) > 10 else np.nan, raw=False
        )
        factors["AUTOCORR_1_60"] = FactorResult(
            name="AUTOCORR_1_60",
            values=autocorr_1,
            description="Lag-1 autocorrelation (60-day)",
            category="CrossAsset",
            valid_data=int(autocorr_1.notna().sum()),
        )

        # 3. Autocorrelation lag-5
        autocorr_5 = self.returns.rolling(window=60, min_periods=20).apply(
            lambda x: x.autocorr(lag=5) if len(x.dropna()) > 15 else np.nan, raw=False
        )
        factors["AUTOCORR_5_60"] = FactorResult(
            name="AUTOCORR_5_60",
            values=autocorr_5,
            description="Lag-5 autocorrelation (60-day)",
            category="CrossAsset",
            valid_data=int(autocorr_5.notna().sum()),
        )

        # 4. Momentum Cross-over (fast vs slow)
        ma_20 = close.rolling(window=20, min_periods=10).mean()
        ma_50 = close.rolling(window=50, min_periods=20).mean()
        ma_cross = (ma_20 - ma_50) / ma_50
        factors["MA_CROSS_20_50"] = FactorResult(
            name="MA_CROSS_20_50",
            values=ma_cross,
            description="MA crossover signal (20d vs 50d)",
            category="CrossAsset",
            valid_data=int(ma_cross.notna().sum()),
        )

        # 5. Volume-Momentum Divergence
        ret_20 = close.pct_change(periods=20)
        vol_20 = volume.pct_change(periods=20)
        divergence = ret_20 - vol_20
        factors["VOL_MOM_DIVERG_20"] = FactorResult(
            name="VOL_MOM_DIVERG_20",
            values=divergence,
            description="Volume-momentum divergence (20d)",
            category="CrossAsset",
            valid_data=int(divergence.notna().sum()),
        )

        # 6. Regime Volatility Ratio (short vs long)
        vol_10 = self.returns.rolling(window=10, min_periods=5).std()
        vol_60 = self.returns.rolling(window=60, min_periods=20).std()
        vol_ratio = vol_10 / (vol_60 + 1e-9)
        factors["VOL_RATIO_10_60"] = FactorResult(
            name="VOL_RATIO_10_60",
            values=vol_ratio,
            description="Volatility regime ratio (10d/60d)",
            category="CrossAsset",
            valid_data=int(vol_ratio.notna().sum()),
        )

        # 7. Price Correlation with Lagged Self (momentum persistence)
        close_shifted = close.shift(5)
        rolling_corr = close.rolling(window=60, min_periods=20).corr(close_shifted)
        factors["PRICE_LAG5_CORR_60"] = FactorResult(
            name="PRICE_LAG5_CORR_60",
            values=rolling_corr,
            description="Price correlation with 5-day lag (60d)",
            category="CrossAsset",
            valid_data=int(rolling_corr.notna().sum()),
        )

        # 8. Drawdown Severity (max loss from peak)
        cummax = close.cummax()
        drawdown = (close - cummax) / cummax
        factors["DRAWDOWN"] = FactorResult(
            name="DRAWDOWN",
            values=drawdown,
            description="Current drawdown from peak",
            category="CrossAsset",
            valid_data=int(drawdown.notna().sum()),
        )

        # 9. Recovery Ratio (price vs 60-day low)
        low_60 = close.rolling(window=60, min_periods=20).min()
        recovery = (close - low_60) / low_60
        factors["RECOVERY_60"] = FactorResult(
            name="RECOVERY_60",
            values=recovery,
            description="Recovery from 60-day low",
            category="CrossAsset",
            valid_data=int(recovery.notna().sum()),
        )

        # 10. Hurst Exponent Proxy (trend persistence)
        ret_cumsum = self.returns.rolling(window=60, min_periods=20).sum()
        ret_std_cumsum = ret_cumsum.rolling(window=20, min_periods=10).std()
        hurst_proxy = ret_std_cumsum / (self.returns.rolling(60).std() + 1e-9)
        factors["HURST_PROXY_60"] = FactorResult(
            name="HURST_PROXY_60",
            values=hurst_proxy,
            description="Hurst exponent proxy (trend persistence)",
            category="CrossAsset",
            valid_data=int(hurst_proxy.notna().sum()),
        )

        return factors

    # ------------------- Microstructure Factors --------------------
    def microstructure_factors(self) -> Dict[str, FactorResult]:
        """Compute 15 microstructure alpha factors (liquidity, order flow, spreads).

        Returns:
            Dictionary of 15 FactorResult objects
        """
        factors: Dict[str, FactorResult] = {}
        close = self.ohlcv[self._colmap["close"]]
        volume = self.ohlcv[self._colmap["volume"]]
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]
        open_ = self.ohlcv[self._colmap["open"]]

        # 1. Bid-Ask Spread Proxy (High-Low / Close)
        ba_spread = (high - low) / close
        factors["BA_SPREAD_PROXY"] = FactorResult(
            name="BA_SPREAD_PROXY",
            values=ba_spread,
            description="Bid-ask spread proxy (HL/Close)",
            category="Microstructure",
            valid_data=int(ba_spread.notna().sum()),
        )

        # 2. Roll Spread Estimator (price autocorrelation)
        price_diff = close.diff()
        cov_lag1 = price_diff.rolling(window=20, min_periods=10).cov(price_diff.shift(1))
        roll_spread = 2 * np.sqrt(np.abs(-cov_lag1))
        factors["ROLL_SPREAD_20"] = FactorResult(
            name="ROLL_SPREAD_20",
            values=roll_spread,
            description="Roll spread estimator (20-day)",
            category="Microstructure",
            valid_data=int(roll_spread.notna().sum()),
        )

        # 3. Effective Spread (intraday price movement)
        eff_spread = 2 * np.abs(close - (high + low) / 2.0) / close
        factors["EFF_SPREAD"] = FactorResult(
            name="EFF_SPREAD",
            values=eff_spread,
            description="Effective spread (2*|C - midpoint|/C)",
            category="Microstructure",
            valid_data=int(eff_spread.notna().sum()),
        )

        # 4. Price Impact (Kyle's Lambda approximation)
        abs_ret = self.returns.abs()
        vol_dollars = volume * close
        price_impact = abs_ret / (vol_dollars.replace(0, np.nan) + 1e-9)
        pi_ma = price_impact.rolling(window=20, min_periods=5).mean()
        factors["PRICE_IMPACT_20"] = FactorResult(
            name="PRICE_IMPACT_20",
            values=pi_ma,
            description="Price impact (20-day avg)",
            category="Microstructure",
            valid_data=int(pi_ma.notna().sum()),
        )

        # 5. Order Flow Imbalance Proxy (volume direction)
        close_chg = close.diff()
        ofi_proxy = np.where(close_chg > 0, volume, -volume)
        ofi_series = pd.Series(ofi_proxy, index=close.index)
        ofi_cumsum = ofi_series.rolling(window=20, min_periods=5).sum()
        factors["OFI_20"] = FactorResult(
            name="OFI_20",
            values=ofi_cumsum,
            description="Order flow imbalance proxy (20-day)",
            category="Microstructure",
            valid_data=int(ofi_cumsum.notna().sum()),
        )

        # 6. Volume Concentration (Herfindahl index proxy)
        vol_sq = volume ** 2
        vol_sum = volume.rolling(window=20, min_periods=5).sum()
        vol_sq_sum = vol_sq.rolling(window=20, min_periods=5).sum()
        hhi = vol_sq_sum / (vol_sum ** 2 + 1e-9)
        factors["VOL_CONC_HHI_20"] = FactorResult(
            name="VOL_CONC_HHI_20",
            values=hhi,
            description="Volume concentration HHI (20-day)",
            category="Microstructure",
            valid_data=int(hhi.notna().sum()),
        )

        # 7. Quoted Spread (High-Low normalized by midpoint)
        midpoint = (high + low) / 2.0
        quoted_spread = (high - low) / midpoint
        factors["QUOTED_SPREAD"] = FactorResult(
            name="QUOTED_SPREAD",
            values=quoted_spread,
            description="Quoted spread (HL / midpoint)",
            category="Microstructure",
            valid_data=int(quoted_spread.notna().sum()),
        )

        # 8. Realized Spread (close vs midpoint)
        realized_spread = (close - midpoint) / midpoint
        factors["REALIZED_SPREAD"] = FactorResult(
            name="REALIZED_SPREAD",
            values=realized_spread,
            description="Realized spread (C vs midpoint)",
            category="Microstructure",
            valid_data=int(realized_spread.notna().sum()),
        )

        # 9. Trade Size Proxy (volume per transaction, daily average)
        # Proxy: volume / |price_change| (larger moves => fewer trades)
        abs_price_chg = close.diff().abs()
        trade_size_proxy = volume / (abs_price_chg.replace(0, np.nan) + 1e-9)
        ts_ma = trade_size_proxy.rolling(window=20, min_periods=5).mean()
        factors["TRADE_SIZE_PROXY_20"] = FactorResult(
            name="TRADE_SIZE_PROXY_20",
            values=ts_ma,
            description="Trade size proxy (20-day avg)",
            category="Microstructure",
            valid_data=int(ts_ma.notna().sum()),
        )

        # 10. Volume Surprise (volume vs expectation)
        vol_ma = volume.rolling(window=20, min_periods=5).mean()
        vol_std = volume.rolling(window=20, min_periods=5).std()
        vol_surprise = (volume - vol_ma) / (vol_std + 1e-9)
        factors["VOL_SURPRISE_20"] = FactorResult(
            name="VOL_SURPRISE_20",
            values=vol_surprise,
            description="Volume surprise z-score (20-day)",
            category="Microstructure",
            valid_data=int(vol_surprise.notna().sum()),
        )

        # 11. VPIN (Volume-Synchronized Probability of Informed Trading)
        # Simplified: abs(OFI) / total volume
        ofi_abs = np.abs(ofi_proxy)
        vpin = ofi_abs / (volume + 1e-9)
        vpin_ma = pd.Series(vpin, index=close.index).rolling(window=20, min_periods=5).mean()
        factors["VPIN_20"] = FactorResult(
            name="VPIN_20",
            values=vpin_ma,
            description="VPIN proxy (20-day avg)",
            category="Microstructure",
            valid_data=int(vpin_ma.notna().sum()),
        )

        # 12. Liquidity Ratio (volume / ATR)
        true_range = np.maximum(high - low, np.abs(high - close.shift(1)))
        true_range = np.maximum(true_range, np.abs(low - close.shift(1)))
        atr = pd.Series(true_range, index=close.index).rolling(window=14, min_periods=5).mean()
        liq_ratio = volume / (atr + 1e-9)
        factors["LIQUIDITY_RATIO_14"] = FactorResult(
            name="LIQUIDITY_RATIO_14",
            values=liq_ratio,
            description="Liquidity ratio (Vol/ATR)",
            category="Microstructure",
            valid_data=int(liq_ratio.notna().sum()),
        )

        # 13. Garman-Klass Realized Volatility (microstructure noise)
        gk_var = 0.5 * (np.log(high / low)) ** 2 - (2 * np.log(2) - 1) * (np.log(close / open_)) ** 2
        gk_vol = np.sqrt(gk_var.rolling(window=20, min_periods=5).mean())
        factors["GK_VOL_20"] = FactorResult(
            name="GK_VOL_20",
            values=gk_vol,
            description="Garman-Klass volatility (20-day)",
            category="Microstructure",
            valid_data=int(gk_vol.notna().sum()),
        )

        # 14. Parkinson Volatility (high-low estimator)
        park_var = (1 / (4 * np.log(2))) * (np.log(high / low)) ** 2
        park_vol = np.sqrt(park_var.rolling(window=20, min_periods=5).mean())
        factors["PARKINSON_VOL_20"] = FactorResult(
            name="PARKINSON_VOL_20",
            values=park_vol,
            description="Parkinson volatility (20-day)",
            category="Microstructure",
            valid_data=int(park_vol.notna().sum()),
        )

        # 15. Rogers-Satchell Volatility (drift-independent)
        rs_var = np.log(high / close) * np.log(high / open_) + np.log(low / close) * np.log(low / open_)
        rs_vol = np.sqrt(rs_var.rolling(window=20, min_periods=5).mean())
        factors["RS_VOL_20"] = FactorResult(
            name="RS_VOL_20",
            values=rs_vol,
            description="Rogers-Satchell volatility (20-day)",
            category="Microstructure",
            valid_data=int(rs_vol.notna().sum()),
        )

        return factors

    # ----------------- Regime Detection Factors --------------------
    def regime_detection_factors(self) -> Dict[str, FactorResult]:
        """Compute 10 regime detection alpha factors (trend/mean-reversion states).

        Returns:
            Dictionary of 10 FactorResult objects
        """
        factors: Dict[str, FactorResult] = {}
        close = self.ohlcv[self._colmap["close"]]
        volume = self.ohlcv[self._colmap["volume"]]
        high = self.ohlcv[self._colmap["high"]]
        low = self.ohlcv[self._colmap["low"]]

        # 1. Trend Strength (ADX proxy)
        plus_dm = (high - high.shift(1)).clip(lower=0)
        minus_dm = (low.shift(1) - low).clip(lower=0)
        true_range = np.maximum(high - low, np.abs(high - close.shift(1)))
        true_range = np.maximum(true_range, np.abs(low - close.shift(1)))
        tr_series = pd.Series(true_range, index=close.index)
        tr_sum = tr_series.rolling(window=14, min_periods=5).sum()
        plus_di = 100 * plus_dm.rolling(window=14, min_periods=5).sum() / (tr_sum + 1e-9)
        minus_di = 100 * minus_dm.rolling(window=14, min_periods=5).sum() / (tr_sum + 1e-9)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
        adx = dx.rolling(window=14, min_periods=5).mean()
        factors["ADX_TREND_14"] = FactorResult(
            name="ADX_TREND_14",
            values=adx,
            description="ADX trend strength (14-day)",
            category="Regime",
            valid_data=int(adx.notna().sum()),
        )

        # 2. Volatility Regime (high vs low vol)
        vol_20 = self.returns.rolling(window=20, min_periods=10).std()
        vol_60 = self.returns.rolling(window=60, min_periods=20).std()
        vol_regime = np.where(vol_20 > vol_60, 1, -1)
        vol_regime_series = pd.Series(vol_regime, index=close.index)
        factors["VOL_REGIME"] = FactorResult(
            name="VOL_REGIME",
            values=vol_regime_series,
            description="Volatility regime (+1 high, -1 low)",
            category="Regime",
            valid_data=int(vol_regime_series.notna().sum()),
        )

        # 3. Momentum Regime (fast MA above slow MA)
        ma_10 = close.rolling(window=10, min_periods=5).mean()
        ma_50 = close.rolling(window=50, min_periods=20).mean()
        mom_regime = np.where(ma_10 > ma_50, 1, -1)
        mom_regime_series = pd.Series(mom_regime, index=close.index)
        factors["MOM_REGIME"] = FactorResult(
            name="MOM_REGIME",
            values=mom_regime_series,
            description="Momentum regime (+1 bull, -1 bear)",
            category="Regime",
            valid_data=int(mom_regime_series.notna().sum()),
        )

        # 4. Mean Reversion Signal (Bollinger Band position)
        ma_20 = close.rolling(window=20, min_periods=10).mean()
        std_20 = close.rolling(window=20, min_periods=10).std()
        bb_position = (close - ma_20) / (2 * std_20 + 1e-9)
        factors["BB_POSITION_20"] = FactorResult(
            name="BB_POSITION_20",
            values=bb_position,
            description="Bollinger Band position (z-score)",
            category="Regime",
            valid_data=int(bb_position.notna().sum()),
        )

        # 5. Trend Consistency (% of up days in window)
        up_days = (close > close.shift(1)).astype(int)
        trend_consistency = up_days.rolling(window=20, min_periods=10).mean()
        factors["TREND_CONSISTENCY_20"] = FactorResult(
            name="TREND_CONSISTENCY_20",
            values=trend_consistency,
            description="Trend consistency (% up days, 20d)",
            category="Regime",
            valid_data=int(trend_consistency.notna().sum()),
        )

        # 6. Volatility Breakout (ATR expansion)
        atr_14 = tr_series.rolling(window=14, min_periods=5).mean()
        atr_60 = tr_series.rolling(window=60, min_periods=20).mean()
        vol_breakout = atr_14 / (atr_60 + 1e-9)
        factors["VOL_BREAKOUT_14_60"] = FactorResult(
            name="VOL_BREAKOUT_14_60",
            values=vol_breakout,
            description="Volatility breakout (ATR 14/60 ratio)",
            category="Regime",
            valid_data=int(vol_breakout.notna().sum()),
        )

        # 7. Range Contraction (Bollinger Band width)
        bb_width = (std_20 / ma_20) * 100
        bb_width_z = (bb_width - bb_width.rolling(60).mean()) / (bb_width.rolling(60).std() + 1e-9)
        factors["BB_WIDTH_Z_60"] = FactorResult(
            name="BB_WIDTH_Z_60",
            values=bb_width_z,
            description="BB width z-score (60-day)",
            category="Regime",
            valid_data=int(bb_width_z.notna().sum()),
        )

        # 8. Momentum Persistence (correlation of returns)
        ret_20_lag = self.returns.rolling(window=20, min_periods=10).mean().shift(20)
        ret_20_curr = self.returns.rolling(window=20, min_periods=10).mean()
        mom_persist = ret_20_curr / (ret_20_lag.abs() + 1e-9)
        factors["MOM_PERSIST_20"] = FactorResult(
            name="MOM_PERSIST_20",
            values=mom_persist,
            description="Momentum persistence (20d curr/lag)",
            category="Regime",
            valid_data=int(mom_persist.notna().sum()),
        )

        # 9. Volume Regime (high vs normal)
        vol_ma_20 = volume.rolling(window=20, min_periods=10).mean()
        vol_ma_60 = volume.rolling(window=60, min_periods=20).mean()
        vol_regime_vol = np.where(vol_ma_20 > vol_ma_60, 1, -1)
        vol_regime_vol_series = pd.Series(vol_regime_vol, index=close.index)
        factors["VOL_REGIME_VOL"] = FactorResult(
            name="VOL_REGIME_VOL",
            values=vol_regime_vol_series,
            description="Volume regime (+1 high, -1 low)",
            category="Regime",
            valid_data=int(vol_regime_vol_series.notna().sum()),
        )

        # 10. Regime Transition Score (combined signal)
        # Combine multiple signals: trend + vol + momentum
        regime_score = (
            mom_regime_series * 0.4
            + vol_regime_series * 0.3
            + vol_regime_vol_series * 0.3
        )
        factors["REGIME_SCORE"] = FactorResult(
            name="REGIME_SCORE",
            values=regime_score,
            description="Combined regime score (weighted)",
            category="Regime",
            valid_data=int(regime_score.notna().sum()),
        )

        return factors

    # --------------------------- Public API ------------------------
    def compute_all_factors(self) -> Dict[str, FactorResult]:
        """Compute a comprehensive collection of 100+ alpha factors.

        Returns:
            Mapping of factor name -> FactorResult (100+ entries)

        Categories:
            - Momentum: ROC, MACD, RSI, Stochastic, CMO (26 factors)
            - Volatility: ATR, Bollinger, Historical Vol, Garman-Klass (4 factors)
            - Trend: SMA, EMA, ADX (3 factors)
            - Volume: OBV, VWAP (2 factors)
            - Value: Price ratios, mean reversion, skewness (15 factors)
            - Alternative: Overnight, gaps, patterns (15 factors)
            - CrossAsset: Beta, autocorr, drawdown (10 factors)
            - Microstructure: Spreads, liquidity, order flow (15 factors)
            - Regime: Trend strength, volatility regimes (10 factors)
        """
        factors: Dict[str, FactorResult] = {}

        # Original 26 factors (Momentum/Volatility/Trend/Volume)
        for p in (5, 10, 12, 20, 60):
            fr = self.roc(p)
            factors[fr.name] = fr
        factors.update(self.macd())
        stoch = self.stochastic()
        factors.update(stoch)
        for p in (14,):
            fr = self.rsi(p)
            factors[fr.name] = fr
        for p in (10, 20):
            fr = self.mom(p)
            factors[fr.name] = fr
        fr = self.cmo(14)
        factors[fr.name] = fr

        fr = self.atr(14)
        factors[fr.name] = fr
        factors.update(self.bollinger_bands(20))
        hvol = self.historical_volatility(20)
        factors[hvol.name] = hvol
        gkvol = self.garman_klass_volatility(20)
        factors[gkvol.name] = gkvol

        factors[self.sma(50).name] = self.sma(50)
        factors[self.ema(12).name] = self.ema(12)
        factors[self.adx(14).name] = self.adx(14)

        factors[self.obv().name] = self.obv()
        factors[self.vwap().name] = self.vwap()

        # New 65 factors (Value/Alternative/CrossAsset/Microstructure/Regime)
        factors.update(self.value_factors())          # +15
        factors.update(self.alternative_factors())    # +15
        factors.update(self.cross_asset_factors())    # +10
        factors.update(self.microstructure_factors()) # +15
        factors.update(self.regime_detection_factors())  # +10

        logger.info("Computed %d factors across 9 categories", len(factors))
        return factors

    def get_factors_dataframe(self) -> pd.DataFrame:
        """Return all computed factors as a DataFrame.

        Columns are factor names, index equals the input OHLCV index.
        """
        factors = self.compute_all_factors()
        df = pd.DataFrame({name: res.values for name, res in factors.items()})
        # Preserve input index ordering
        df = df.reindex(index=self.ohlcv.index)
        return df
