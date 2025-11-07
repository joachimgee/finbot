"""Comprehensive catalog of 100+ alpha factors with metadata.

Provides structured metadata for all implemented alpha factors, including formulas,
descriptions, data requirements, expected IC ranges, and academic references.

Example:
    >>> from financial_analyzer.ml.factor_catalog import FACTOR_CATALOG, get_factor_info
    >>> info = get_factor_info('ROC_10')
    >>> print(f"{info['formula']} - Expected IC: {info['expected_ic']}")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# FACTOR_CATALOG: Comprehensive metadata for 100+ alpha factors
#
# NOTE: The catalog contains 100 entries (including period variants like ROC_5,
# ROC_10, etc.), but AlphaFactorEngine.compute_all_factors() generates 91
# unique factors. The catalog is exhaustive for documentation purposes and
# includes all commonly used parameter variations.
# ============================================================================

FACTOR_CATALOG: Dict[str, Dict[str, Any]] = {
    # ======================== MOMENTUM (26 factors) ========================
    "ROC_5": {
        "formula": "close.pct_change(5)",
        "description": "5-day rate of change (short-term momentum)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Jegadeesh & Titman (1993) - Returns to Buying Winners",
    },
    "ROC_10": {
        "formula": "close.pct_change(10)",
        "description": "10-day rate of change (medium-term momentum)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.04,
        "reference": "Jegadeesh & Titman (1993)",
    },
    "ROC_12": {
        "formula": "close.pct_change(12)",
        "description": "12-day rate of change (monthly momentum)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.05,
        "reference": "Jegadeesh & Titman (1993)",
    },
    "ROC_20": {
        "formula": "close.pct_change(20)",
        "description": "20-day rate of change (momentum)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.06,
        "reference": "Jegadeesh & Titman (1993)",
    },
    "ROC_60": {
        "formula": "close.pct_change(60)",
        "description": "60-day rate of change (long-term momentum)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.08,
        "reference": "Jegadeesh & Titman (1993)",
    },
    "MACD": {
        "formula": "EMA(12) - EMA(26)",
        "description": "MACD line (trend-following momentum)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.03,
        "reference": "Appel (1979) - Technical Analysis",
    },
    "MACD_SIGNAL": {
        "formula": "EMA(MACD, 9)",
        "description": "MACD signal line (smoothed MACD)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Appel (1979)",
    },
    "MACD_HIST": {
        "formula": "MACD - MACD_SIGNAL",
        "description": "MACD histogram (convergence/divergence)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.04,
        "reference": "Appel (1979)",
    },
    "STOCH_K": {
        "formula": "(close - low_14) / (high_14 - low_14)",
        "description": "Stochastic %K (overbought/oversold)",
        "category": "Momentum",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.02,
        "reference": "Lane (1950s) - Stochastic Oscillator",
    },
    "STOCH_D": {
        "formula": "SMA(STOCH_K, 3)",
        "description": "Stochastic %D (smoothed %K)",
        "category": "Momentum",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.02,
        "reference": "Lane (1950s)",
    },
    "RSI_14": {
        "formula": "100 - 100 / (1 + RS_14)",
        "description": "14-day Relative Strength Index (mean reversion)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.03,
        "reference": "Wilder (1978) - New Concepts in Technical Trading",
    },
    "MOM_10": {
        "formula": "close - close.shift(10)",
        "description": "10-day momentum (absolute price change)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.03,
        "reference": "Classic momentum indicator",
    },
    "MOM_20": {
        "formula": "close - close.shift(20)",
        "description": "20-day momentum (absolute price change)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.04,
        "reference": "Classic momentum indicator",
    },
    "CMO_14": {
        "formula": "100 * (up_sum - down_sum) / (up_sum + down_sum)",
        "description": "14-day Chande Momentum Oscillator",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.03,
        "reference": "Chande (1992) - Technical Analysis",
    },
    # ===================== VOLATILITY (4 factors) =======================
    "ATR_14": {
        "formula": "EMA(TrueRange, 14)",
        "description": "14-day Average True Range (volatility)",
        "category": "Volatility",
        "data_required": ["high", "low", "close"],
        "expected_ic": -0.02,
        "reference": "Wilder (1978)",
    },
    "BB_UPPER": {
        "formula": "SMA(20) + 2 * STD(20)",
        "description": "Bollinger Band upper (overbought)",
        "category": "Volatility",
        "data_required": ["close"],
        "expected_ic": 0.01,
        "reference": "Bollinger (1992) - Bollinger on Bollinger Bands",
    },
    "BB_LOWER": {
        "formula": "SMA(20) - 2 * STD(20)",
        "description": "Bollinger Band lower (oversold)",
        "category": "Volatility",
        "data_required": ["close"],
        "expected_ic": 0.01,
        "reference": "Bollinger (1992)",
    },
    "HVOL_20": {
        "formula": "STD(returns, 20) * sqrt(252)",
        "description": "20-day historical volatility (annualized)",
        "category": "Volatility",
        "data_required": ["close"],
        "expected_ic": -0.03,
        "reference": "Classic volatility measure",
    },
    "GKVOL_20": {
        "formula": "sqrt(0.5 * log(H/L)^2 - (2ln2-1) * log(C/O)^2)",
        "description": "Garman-Klass volatility estimator (20-day)",
        "category": "Volatility",
        "data_required": ["open", "high", "low", "close"],
        "expected_ic": -0.04,
        "reference": "Garman & Klass (1980) - Estimation of Volatility",
    },
    # ======================= TREND (3 factors) ==========================
    "SMA_50": {
        "formula": "close.rolling(50).mean()",
        "description": "50-day simple moving average",
        "category": "Trend",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Classic trend indicator",
    },
    "EMA_12": {
        "formula": "EMA(close, 12)",
        "description": "12-day exponential moving average",
        "category": "Trend",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Classic trend indicator",
    },
    "ADX_14": {
        "formula": "100 * EMA(|+DI - -DI| / (+DI + -DI), 14)",
        "description": "14-day Average Directional Index (trend strength)",
        "category": "Trend",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.03,
        "reference": "Wilder (1978)",
    },
    # ======================= VOLUME (2 factors) ==========================
    "OBV": {
        "formula": "cumsum(sign(close.diff()) * volume)",
        "description": "On-Balance Volume (momentum via volume)",
        "category": "Volume",
        "data_required": ["close", "volume"],
        "expected_ic": 0.03,
        "reference": "Granville (1963) - Granville's New Key to Stock Market Profits",
    },
    "VWAP": {
        "formula": "sum(typical_price * volume) / sum(volume)",
        "description": "Volume-Weighted Average Price ratio",
        "category": "Volume",
        "data_required": ["high", "low", "close", "volume"],
        "expected_ic": 0.02,
        "reference": "Classic institutional trading benchmark",
    },
    # ======================== VALUE (15 factors) =========================
    "PR_52W_HIGH": {
        "formula": "close / close.rolling(252).max()",
        "description": "Price to 52-week high ratio",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "George & Hwang (2004) - 52-Week High Effect",
    },
    "PR_52W_LOW": {
        "formula": "close / close.rolling(252).min() - 1",
        "description": "Price to 52-week low ratio minus 1",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Contrarian value signal",
    },
    "PR_MA200": {
        "formula": "close / close.rolling(200).mean() - 1",
        "description": "Price to 200-day MA ratio",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": 0.01,
        "reference": "Classic trend/value indicator",
    },
    "RS_60": {
        "formula": "close.pct_change(60)",
        "description": "60-day relative strength (momentum)",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": 0.05,
        "reference": "Jegadeesh & Titman (1993)",
    },
    "REVERSAL_5": {
        "formula": "-close.pct_change(5)",
        "description": "5-day price reversal signal",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Lehmann (1990) - Short-Term Reversals",
    },
    "EARN_YIELD_PROXY": {
        "formula": "1 / (1 + ret_252)",
        "description": "Earnings yield proxy (inverse momentum)",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": -0.03,
        "reference": "Value proxy from price momentum",
    },
    "PR_VOL_RATIO": {
        "formula": "(price/volume - mean) / std",
        "description": "Price-to-volume z-score (60-day)",
        "category": "Value",
        "data_required": ["close", "volume"],
        "expected_ic": 0.02,
        "reference": "Liquidity-adjusted value",
    },
    "DOWNSIDE_DEV_60": {
        "formula": "-std(returns[returns<0], 60)",
        "description": "Negative downside deviation (60-day)",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": 0.03,
        "reference": "Sortino & Van Der Meer (1991) - Downside Risk",
    },
    "HL_RANGE_Z": {
        "formula": "((H-L)/C - mean) / std",
        "description": "High-Low range z-score (60-day)",
        "category": "Value",
        "data_required": ["high", "low", "close"],
        "expected_ic": -0.02,
        "reference": "Volatility proxy",
    },
    "PRICE_ACCEL": {
        "formula": "ret_10.diff()",
        "description": "Price acceleration (momentum change)",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": 0.01,
        "reference": "Second derivative momentum",
    },
    "CLOSE_ZSCORE_60": {
        "formula": "(close - mean) / std",
        "description": "Z-score of close price (60-day)",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Mean reversion signal",
    },
    "RET_SKEW_60": {
        "formula": "returns.rolling(60).skew()",
        "description": "60-day return skewness",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": -0.01,
        "reference": "Harvey & Siddique (2000) - Conditional Skewness",
    },
    "RET_KURT_60": {
        "formula": "returns.rolling(60).kurt()",
        "description": "60-day return kurtosis (tail risk)",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Tail risk measure",
    },
    "PRICE_CV_60": {
        "formula": "close.rolling(60).std() / mean",
        "description": "Coefficient of variation (60-day)",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": -0.01,
        "reference": "Relative volatility measure",
    },
    "CUM_RETURN": {
        "formula": "(1 + returns).cumprod() - 1",
        "description": "Cumulative return since start",
        "category": "Value",
        "data_required": ["close"],
        "expected_ic": 0.05,
        "reference": "Buy-and-hold performance",
    },
    # =================== ALTERNATIVE (15 factors) =======================
    "OVERNIGHT_RET": {
        "formula": "(open - close.shift(1)) / close.shift(1)",
        "description": "Overnight return (gap risk)",
        "category": "Alternative",
        "data_required": ["open", "close"],
        "expected_ic": 0.01,
        "reference": "Berkman et al. (2012) - Overnight vs Intraday Returns",
    },
    "INTRADAY_RET": {
        "formula": "(close - open) / open",
        "description": "Intraday return",
        "category": "Alternative",
        "data_required": ["open", "close"],
        "expected_ic": 0.02,
        "reference": "Gao et al. (2018) - Intraday Momentum",
    },
    "HIGH_CLOSE_SPREAD": {
        "formula": "(high - close) / close",
        "description": "High-Close spread ratio",
        "category": "Alternative",
        "data_required": ["high", "close"],
        "expected_ic": -0.01,
        "reference": "Upper tail indicator",
    },
    "CLOSE_LOW_SPREAD": {
        "formula": "(close - low) / close",
        "description": "Close-Low spread ratio",
        "category": "Alternative",
        "data_required": ["low", "close"],
        "expected_ic": 0.01,
        "reference": "Lower tail indicator",
    },
    "VOL_MOM_10": {
        "formula": "volume.pct_change(10)",
        "description": "10-day volume momentum",
        "category": "Alternative",
        "data_required": ["volume"],
        "expected_ic": 0.02,
        "reference": "Lee & Swaminathan (2000) - Price Momentum & Volume",
    },
    "VOL_ZSCORE_60": {
        "formula": "(volume - mean) / std",
        "description": "Volume z-score (60-day)",
        "category": "Alternative",
        "data_required": ["volume"],
        "expected_ic": 0.02,
        "reference": "Abnormal volume indicator",
    },
    "TR_EXPANSION": {
        "formula": "TrueRange / TrueRange.rolling(14).mean() - 1",
        "description": "True Range expansion ratio",
        "category": "Alternative",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.01,
        "reference": "Volatility breakout signal",
    },
    "CONSEC_UP_10": {
        "formula": "(close > close.shift(1)).rolling(10).sum()",
        "description": "Count of up days in last 10",
        "category": "Alternative",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Winning streak indicator",
    },
    "CONSEC_DOWN_10": {
        "formula": "(close < close.shift(1)).rolling(10).sum()",
        "description": "Count of down days in last 10",
        "category": "Alternative",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Losing streak indicator",
    },
    "TURNOVER_Z_60": {
        "formula": "(volume/close - mean) / std",
        "description": "Turnover z-score (60-day)",
        "category": "Alternative",
        "data_required": ["volume", "close"],
        "expected_ic": 0.01,
        "reference": "Liquidity measure",
    },
    "GAP_MA_20": {
        "formula": "(open - close.shift(1)) / close.shift(1)).rolling(20).mean()",
        "description": "20-day average price gap",
        "category": "Alternative",
        "data_required": ["open", "close"],
        "expected_ic": 0.01,
        "reference": "Gap persistence indicator",
    },
    "HL_VOL_20": {
        "formula": "((high - low) / close).rolling(20).std()",
        "description": "High-Low volatility (20-day)",
        "category": "Alternative",
        "data_required": ["high", "low", "close"],
        "expected_ic": -0.02,
        "reference": "Range-based volatility",
    },
    "VWAP_DRIFT": {
        "formula": "(close - typical) / typical",
        "description": "Close vs typical price drift",
        "category": "Alternative",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.01,
        "reference": "Intraday drift indicator",
    },
    "VOL_PRICE_CORR_20": {
        "formula": "returns.rolling(20).corr(volume.pct_change())",
        "description": "20-day volume-price correlation",
        "category": "Alternative",
        "data_required": ["close", "volume"],
        "expected_ic": 0.02,
        "reference": "Volume confirmation signal",
    },
    "AMIHUD_ILLIQ_20": {
        "formula": "|returns| / volume",
        "description": "Amihud illiquidity (20-day avg)",
        "category": "Alternative",
        "data_required": ["close", "volume"],
        "expected_ic": -0.03,
        "reference": "Amihud (2002) - Illiquidity & Stock Returns",
    },
    # =================== CROSS-ASSET (10 factors) =======================
    "BETA_PROXY_60_252": {
        "formula": "vol_60 / vol_252",
        "description": "Beta proxy (60d/252d vol ratio)",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Volatility regime indicator",
    },
    "AUTOCORR_1_60": {
        "formula": "returns.rolling(60).apply(lambda x: x.autocorr(1))",
        "description": "Lag-1 autocorrelation (60-day)",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": -0.03,
        "reference": "Mean reversion indicator",
    },
    "AUTOCORR_5_60": {
        "formula": "returns.rolling(60).apply(lambda x: x.autocorr(5))",
        "description": "Lag-5 autocorrelation (60-day)",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Mean reversion indicator",
    },
    "MA_CROSS_20_50": {
        "formula": "(MA_20 - MA_50) / MA_50",
        "description": "MA crossover signal (20d vs 50d)",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Golden/Death cross",
    },
    "VOL_MOM_DIVERG_20": {
        "formula": "ret_20 - vol_20.pct_change()",
        "description": "Volume-momentum divergence (20d)",
        "category": "CrossAsset",
        "data_required": ["close", "volume"],
        "expected_ic": 0.01,
        "reference": "Divergence signal",
    },
    "VOL_RATIO_10_60": {
        "formula": "vol_10 / vol_60",
        "description": "Volatility regime ratio (10d/60d)",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": -0.01,
        "reference": "Volatility regime shift",
    },
    "PRICE_LAG5_CORR_60": {
        "formula": "close.rolling(60).corr(close.shift(5))",
        "description": "Price correlation with 5-day lag (60d)",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Momentum persistence",
    },
    "DRAWDOWN": {
        "formula": "(close - close.cummax()) / close.cummax()",
        "description": "Current drawdown from peak",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": -0.03,
        "reference": "Calmar (1991) - Drawdown measure",
    },
    "RECOVERY_60": {
        "formula": "(close - close.rolling(60).min()) / close.rolling(60).min()",
        "description": "Recovery from 60-day low",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Recovery momentum",
    },
    "HURST_PROXY_60": {
        "formula": "returns.rolling(60).sum().rolling(20).std() / vol_60",
        "description": "Hurst exponent proxy (trend persistence)",
        "category": "CrossAsset",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Hurst (1951) - Trend persistence",
    },
    # ================= MICROSTRUCTURE (15 factors) ======================
    "BA_SPREAD_PROXY": {
        "formula": "(high - low) / close",
        "description": "Bid-ask spread proxy (HL/Close)",
        "category": "Microstructure",
        "data_required": ["high", "low", "close"],
        "expected_ic": -0.02,
        "reference": "Roll (1984) - Spread estimator",
    },
    "ROLL_SPREAD_20": {
        "formula": "2 * sqrt(abs(-cov(price_diff, price_diff.shift(1))))",
        "description": "Roll spread estimator (20-day)",
        "category": "Microstructure",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Roll (1984)",
    },
    "EFF_SPREAD": {
        "formula": "2 * |close - (high+low)/2| / close",
        "description": "Effective spread",
        "category": "Microstructure",
        "data_required": ["high", "low", "close"],
        "expected_ic": -0.01,
        "reference": "Effective transaction cost",
    },
    "PRICE_IMPACT_20": {
        "formula": "|returns| / (volume * close)",
        "description": "Price impact (Kyle's lambda, 20-day)",
        "category": "Microstructure",
        "data_required": ["close", "volume"],
        "expected_ic": -0.03,
        "reference": "Kyle (1985) - Price impact",
    },
    "OFI_20": {
        "formula": "sign(close.diff()) * volume).rolling(20).sum()",
        "description": "Order flow imbalance proxy (20-day)",
        "category": "Microstructure",
        "data_required": ["close", "volume"],
        "expected_ic": 0.02,
        "reference": "Cont et al. (2014) - Order flow",
    },
    "VOL_CONC_HHI_20": {
        "formula": "sum(volume^2) / sum(volume)^2",
        "description": "Volume concentration HHI (20-day)",
        "category": "Microstructure",
        "data_required": ["volume"],
        "expected_ic": -0.01,
        "reference": "Herfindahl index",
    },
    "QUOTED_SPREAD": {
        "formula": "(high - low) / ((high+low)/2)",
        "description": "Quoted spread (HL / midpoint)",
        "category": "Microstructure",
        "data_required": ["high", "low"],
        "expected_ic": -0.02,
        "reference": "Quoted spread estimator",
    },
    "REALIZED_SPREAD": {
        "formula": "(close - (high+low)/2) / ((high+low)/2)",
        "description": "Realized spread (C vs midpoint)",
        "category": "Microstructure",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.01,
        "reference": "Realized transaction cost",
    },
    "TRADE_SIZE_PROXY_20": {
        "formula": "volume / |close.diff()|",
        "description": "Trade size proxy (20-day avg)",
        "category": "Microstructure",
        "data_required": ["close", "volume"],
        "expected_ic": 0.01,
        "reference": "Trade size estimator",
    },
    "VOL_SURPRISE_20": {
        "formula": "(volume - volume.rolling(20).mean()) / volume.rolling(20).std()",
        "description": "Volume surprise z-score (20-day)",
        "category": "Microstructure",
        "data_required": ["volume"],
        "expected_ic": 0.02,
        "reference": "Abnormal volume",
    },
    "VPIN_20": {
        "formula": "|OFI| / volume",
        "description": "VPIN proxy (20-day avg)",
        "category": "Microstructure",
        "data_required": ["close", "volume"],
        "expected_ic": -0.02,
        "reference": "Easley et al. (2012) - VPIN",
    },
    "LIQUIDITY_RATIO_14": {
        "formula": "volume / ATR_14",
        "description": "Liquidity ratio (Vol/ATR)",
        "category": "Microstructure",
        "data_required": ["high", "low", "close", "volume"],
        "expected_ic": 0.02,
        "reference": "Liquidity measure",
    },
    "GK_VOL_20": {
        "formula": "sqrt(0.5*log(H/L)^2 - (2ln2-1)*log(C/O)^2)",
        "description": "Garman-Klass volatility (20-day)",
        "category": "Microstructure",
        "data_required": ["open", "high", "low", "close"],
        "expected_ic": -0.03,
        "reference": "Garman & Klass (1980)",
    },
    "PARKINSON_VOL_20": {
        "formula": "sqrt((1/(4*ln2)) * log(H/L)^2)",
        "description": "Parkinson volatility (20-day)",
        "category": "Microstructure",
        "data_required": ["high", "low"],
        "expected_ic": -0.03,
        "reference": "Parkinson (1980) - Extreme value estimator",
    },
    "RS_VOL_20": {
        "formula": "sqrt(log(H/C)*log(H/O) + log(L/C)*log(L/O))",
        "description": "Rogers-Satchell volatility (20-day)",
        "category": "Microstructure",
        "data_required": ["open", "high", "low", "close"],
        "expected_ic": -0.03,
        "reference": "Rogers & Satchell (1991) - Drift-independent vol",
    },
    # ==================== REGIME (10 factors) ===========================
    "ADX_TREND_14": {
        "formula": "100 * EMA(|+DI - -DI| / (+DI + -DI), 14)",
        "description": "ADX trend strength (14-day)",
        "category": "Regime",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.03,
        "reference": "Wilder (1978)",
    },
    "VOL_REGIME": {
        "formula": "sign(vol_20 - vol_60)",
        "description": "Volatility regime (+1 high, -1 low)",
        "category": "Regime",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Volatility regime detection",
    },
    "MOM_REGIME": {
        "formula": "sign(MA_10 - MA_50)",
        "description": "Momentum regime (+1 bull, -1 bear)",
        "category": "Regime",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Trend regime detection",
    },
    "BB_POSITION_20": {
        "formula": "(close - MA_20) / (2 * STD_20)",
        "description": "Bollinger Band position (z-score)",
        "category": "Regime",
        "data_required": ["close"],
        "expected_ic": -0.02,
        "reference": "Mean reversion signal",
    },
    "TREND_CONSISTENCY_20": {
        "formula": "(close > close.shift(1)).rolling(20).mean()",
        "description": "Trend consistency (% up days, 20d)",
        "category": "Regime",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Trend strength measure",
    },
    "VOL_BREAKOUT_14_60": {
        "formula": "ATR_14 / ATR_60",
        "description": "Volatility breakout (ATR 14/60 ratio)",
        "category": "Regime",
        "data_required": ["high", "low", "close"],
        "expected_ic": 0.01,
        "reference": "Volatility expansion signal",
    },
    "BB_WIDTH_Z_60": {
        "formula": "(BB_width - BB_width.rolling(60).mean()) / BB_width.rolling(60).std()",
        "description": "BB width z-score (60-day)",
        "category": "Regime",
        "data_required": ["close"],
        "expected_ic": -0.01,
        "reference": "Bollinger squeeze",
    },
    "MOM_PERSIST_20": {
        "formula": "ret_20_curr / |ret_20_lag|",
        "description": "Momentum persistence (20d curr/lag)",
        "category": "Regime",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Momentum stability",
    },
    "VOL_REGIME_VOL": {
        "formula": "sign(vol_MA_20 - vol_MA_60)",
        "description": "Volume regime (+1 high, -1 low)",
        "category": "Regime",
        "data_required": ["volume"],
        "expected_ic": 0.01,
        "reference": "Volume regime detection",
    },
    "REGIME_SCORE": {
        "formula": "0.4*MOM_REGIME + 0.3*VOL_REGIME + 0.3*VOL_REGIME_VOL",
        "description": "Combined regime score (weighted)",
        "category": "Regime",
        "data_required": ["close", "volume"],
        "expected_ic": 0.03,
        "reference": "Multi-dimensional regime signal",
    },
    # =============== ADDITIONAL VARIATIONS (9+) =====================
    "ROC_30": {
        "formula": "close.pct_change(30)",
        "description": "30-day rate of change (momentum)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.07,
        "reference": "Jegadeesh & Titman (1993)",
    },
    "RSI_7": {
        "formula": "100 - 100 / (1 + RS_7)",
        "description": "7-day Relative Strength Index (short-term)",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Wilder (1978)",
    },
    "RSI_21": {
        "formula": "100 - 100 / (1 + RS_21)",
        "description": "21-day Relative Strength Index",
        "category": "Momentum",
        "data_required": ["close"],
        "expected_ic": 0.03,
        "reference": "Wilder (1978)",
    },
    "SMA_20": {
        "formula": "close.rolling(20).mean()",
        "description": "20-day simple moving average",
        "category": "Trend",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "Classic trend indicator",
    },
    "SMA_100": {
        "formula": "close.rolling(100).mean()",
        "description": "100-day simple moving average",
        "category": "Trend",
        "data_required": ["close"],
        "expected_ic": 0.03,
        "reference": "Classic long-term trend",
    },
    "SMA_200": {
        "formula": "close.rolling(200).mean()",
        "description": "200-day simple moving average",
        "category": "Trend",
        "data_required": ["close"],
        "expected_ic": 0.04,
        "reference": "Classic long-term trend",
    },
    "EMA_26": {
        "formula": "EMA(close, 26)",
        "description": "26-day exponential moving average",
        "category": "Trend",
        "data_required": ["close"],
        "expected_ic": 0.02,
        "reference": "MACD component",
    },
    "ATR_7": {
        "formula": "EMA(TrueRange, 7)",
        "description": "7-day Average True Range (short-term volatility)",
        "category": "Volatility",
        "data_required": ["high", "low", "close"],
        "expected_ic": -0.02,
        "reference": "Wilder (1978)",
    },
    "HVOL_60": {
        "formula": "STD(returns, 60) * sqrt(252)",
        "description": "60-day historical volatility (annualized)",
        "category": "Volatility",
        "data_required": ["close"],
        "expected_ic": -0.03,
        "reference": "Long-term volatility measure",
    },
    "VWAP_10": {
        "formula": "sum(typical_price * volume) / sum(volume) (10-day)",
        "description": "10-day Volume-Weighted Average Price ratio",
        "category": "Volume",
        "data_required": ["high", "low", "close", "volume"],
        "expected_ic": 0.02,
        "reference": "Short-term institutional benchmark",
    },
    "TURNOVER_20": {
        "formula": "volume / close (20-day avg)",
        "description": "20-day average turnover",
        "category": "Volume",
        "data_required": ["volume", "close"],
        "expected_ic": 0.02,
        "reference": "Liquidity measure",
    },
}


# ============================================================================
# Utility Functions
# ============================================================================


def get_factor_info(factor_name: str) -> Dict[str, Any]:
    """Retrieve metadata for a specific factor.

    Args:
        factor_name: Name of the factor (e.g., 'ROC_10')

    Returns:
        Dictionary with formula, description, category, etc.

    Raises:
        KeyError: If factor_name not found

    Example:
        >>> info = get_factor_info('MACD')
        >>> print(f"Formula: {info['formula']}")
        >>> print(f"Expected IC: {info['expected_ic']}")
    """
    if factor_name not in FACTOR_CATALOG:
        logger.error("Unknown factor: %s", factor_name)
        raise KeyError(f"Factor not found: {factor_name}")

    return FACTOR_CATALOG[factor_name]


def list_factors_by_category(category: str) -> List[str]:
    """List all factors in a specific category.

    Args:
        category: Category name (Momentum/Volatility/Trend/Volume/Value/Alternative/CrossAsset/Microstructure/Regime)

    Returns:
        List of factor names in the category

    Example:
        >>> momentum_factors = list_factors_by_category('Momentum')
        >>> print(f"Found {len(momentum_factors)} momentum factors")
    """
    factors = [name for name, meta in FACTOR_CATALOG.items() if meta["category"] == category]
    logger.info("Found %d factors in category '%s'", len(factors), category)
    return factors


def get_all_categories() -> List[str]:
    """Get list of all factor categories.

    Returns:
        Sorted list of unique categories

    Example:
        >>> categories = get_all_categories()
        >>> print(categories)
        ['Alternative', 'CrossAsset', 'Microstructure', 'Momentum', 'Regime', 'Trend', 'Value', 'Volume', 'Volatility']
    """
    categories = sorted(set(meta["category"] for meta in FACTOR_CATALOG.values()))
    return categories


def search_factors(
    keyword: str,
    search_fields: Optional[List[str]] = None,
) -> List[str]:
    """Search factors by keyword in specified fields.

    Args:
        keyword: Search term (case-insensitive)
        search_fields: Fields to search (default: ['description', 'formula'])

    Returns:
        List of matching factor names

    Example:
        >>> vol_factors = search_factors('volatility')
        >>> spread_factors = search_factors('spread', search_fields=['formula', 'description'])
    """
    if search_fields is None:
        search_fields = ["description", "formula"]

    keyword_lower = keyword.lower()
    matches = []

    for name, meta in FACTOR_CATALOG.items():
        for field in search_fields:
            if field in meta and keyword_lower in str(meta[field]).lower():
                matches.append(name)
                break

    logger.info("Found %d factors matching '%s'", len(matches), keyword)
    return matches


def get_catalog_summary() -> Dict[str, int]:
    """Get summary statistics of the factor catalog.

    Returns:
        Dictionary with total_factors, factors_per_category

    Example:
        >>> summary = get_catalog_summary()
        >>> print(f"Total factors: {summary['total_factors']}")
        >>> print(f"Categories: {summary['n_categories']}")
    """
    category_counts = {}
    for meta in FACTOR_CATALOG.values():
        cat = meta["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    summary = {
        "total_factors": len(FACTOR_CATALOG),
        "n_categories": len(category_counts),
        "factors_per_category": category_counts,
    }

    return summary
