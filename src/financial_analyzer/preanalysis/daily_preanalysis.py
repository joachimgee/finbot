"""Daily preanalysis orchestration.

Combines PIT data loading, reward registry warm-up, model drift detection,
and options market analysis prior to RL pipeline run. Triggers retrain if
performance degradation detected.
"""
from __future__ import annotations
from typing import List, Dict, Optional
from pathlib import Path
import numpy as np
import pandas as pd

from financial_analyzer.data.pit_loader import PITDataLoader
from financial_analyzer.rl.rewards.registry import list_rewards
from financial_analyzer.backtest.adaptive_walk_forward import (
    AdaptiveWalkForward,
    DriftDetector,
)
from financial_analyzer.derivatives.options import (
    BlackScholesModel,
    GreeksCalculator,
)
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def check_model_drift(
    model_path: str,
    recent_returns: np.ndarray,
    baseline_sharpe: float = 1.5,
    threshold: float = 0.5,
) -> Dict[str, object]:
    """
    Check if deployed model has performance drift.
    
    Args:
        model_path: Path to deployed model
        recent_returns: Recent returns (last N days)
        baseline_sharpe: Expected Sharpe from training
        threshold: Drift threshold (0.5 = 50% drop triggers retrain)
    
    Returns:
        Dict with drift status and metrics
    """
    if len(recent_returns) < 30:
        logger.warning("Insufficient data for drift detection (need 30+ days)")
        return {"drift_detected": False, "reason": "insufficient_data"}
    
    # Create drift detector
    detector = DriftDetector(
        baseline_sharpe=baseline_sharpe,
        threshold_pct=threshold,
        detection_method="combined",
    )
    
    # Compute current metrics
    from financial_analyzer.backtest.adaptive_walk_forward import PerformanceMetrics
    from datetime import datetime
    
    mean_ret = np.mean(recent_returns)
    std_ret = np.std(recent_returns)
    sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0
    
    current_metrics = PerformanceMetrics(
        sharpe_ratio=sharpe,
        sortino_ratio=0.0,  # Not critical for drift detection
        max_drawdown=0.0,
        win_rate=0.0,
        mean_return=mean_ret,
        std_return=std_ret,
        timestamp=datetime.now(),
    )
    
    # Detect drift
    drift_result = detector.detect_drift(recent_returns, current_metrics)
    
    if drift_result["is_drift"]:
        logger.warning(
            f"Model drift detected for {model_path}: {drift_result['reason']} "
            f"(confidence={drift_result['confidence']:.1%})"
        )
    else:
        logger.info(f"No drift detected for {model_path} (Sharpe={sharpe:.2f})")
    
    return {
        "drift_detected": drift_result["is_drift"],
        "reason": drift_result["reason"],
        "confidence": drift_result["confidence"],
        "current_sharpe": sharpe,
        "baseline_sharpe": baseline_sharpe,
        "model_path": model_path,
    }


def analyze_options_market(
    symbols: List[str],
    prices: pd.DataFrame,
    risk_free_rate: float = 0.05,
    volatility_window: int = 30,
) -> Dict[str, object]:
    """
    Analyze options market for given symbols.
    
    Computes ATM option prices and Greeks for risk assessment.
    
    Args:
        symbols: List of symbols to analyze
        prices: Price data (DataFrame with dates as index, symbols as columns)
        risk_free_rate: Risk-free rate (default: 5%)
        volatility_window: Days for volatility calculation (default: 30)
    
    Returns:
        Dict with options analysis for each symbol
    """
    options_analysis = {}
    
    for symbol in symbols:
        try:
            if symbol not in prices.columns:
                logger.warning(f"Symbol {symbol} not in price data, skipping options analysis")
                continue
            
            # Get recent prices
            symbol_prices = prices[symbol].dropna()
            if len(symbol_prices) < volatility_window:
                logger.warning(f"Insufficient data for {symbol} options analysis")
                continue
            
            # Current spot price
            S = float(symbol_prices.iloc[-1])
            
            # ATM strike (round to nearest $5)
            K = round(S / 5) * 5
            
            # Time to expiration (assume 3 months)
            T = 0.25
            
            # Historical volatility (annualized)
            returns = symbol_prices.pct_change().dropna()
            sigma = float(returns.tail(volatility_window).std() * np.sqrt(252))
            
            # Price options
            bs = BlackScholesModel(S=S, K=K, T=T, r=risk_free_rate, sigma=sigma)
            call_price = bs.call_price()
            put_price = bs.put_price()
            
            # Compute Greeks
            greeks_calc = GreeksCalculator(S=S, K=K, T=T, r=risk_free_rate, sigma=sigma)
            greeks = greeks_calc.compute_all()
            
            # Store results
            options_analysis[symbol] = {
                "spot": S,
                "strike": K,
                "volatility": sigma,
                "call_price": call_price,
                "put_price": put_price,
                "delta_call": greeks.delta_call,
                "delta_put": greeks.delta_put,
                "gamma": greeks.gamma,
                "vega": greeks.vega,
                "theta_call": greeks.theta_call,
                "implied_hedge_ratio": abs(greeks.delta_call),  # For portfolio hedging
            }
            
            logger.debug(
                f"{symbol}: S=${S:.2f}, Call=${call_price:.2f}, Put=${put_price:.2f}, "
                f"Delta={greeks.delta_call:.4f}, Vol={sigma:.2%}"
            )
            
        except Exception as e:
            logger.error(f"Options analysis failed for {symbol}: {e}")
            options_analysis[symbol] = None
    
    valid_count = sum(1 for v in options_analysis.values() if v is not None)
    logger.info(f"Options analysis complete: {valid_count}/{len(symbols)} symbols")
    
    return options_analysis


def run_daily_preanalysis(
    symbols: List[str],
    start_date: str,
    end_date: str,
    check_drift: bool = True,
    analyze_options: bool = True,
    model_path: Optional[str] = None,
    risk_free_rate: float = 0.05,
) -> Dict[str, object]:
    """
    Run daily preanalysis with optional drift detection and options analysis.
    
    Args:
        symbols: List of symbols to analyze
        start_date: Start date for data loading
        end_date: End date for data loading
        check_drift: Whether to check model drift (default: True)
        analyze_options: Whether to analyze options market (default: True)
        model_path: Path to model for drift check (default: latest trained model)
        risk_free_rate: Risk-free rate for options pricing (default: 5%)
    
    Returns:
        Dict with preanalysis results including drift status and options analysis
    """
    # Real adjusted prices when Alpaca credentials are present; degrades to
    # synthetic (loudly) otherwise so offline/CI pre-analysis still runs.
    loader = PITDataLoader(source="alpaca")
    prices_dict = loader.load_prices(symbols, start_date, end_date)
    metadata = loader.load_metadata(symbols)
    rewards = list(list_rewards().keys())
    
    # Convert dict of DataFrames to single DataFrame with symbols as columns
    if isinstance(prices_dict, dict):
        prices = pd.DataFrame({sym: df['close'] for sym, df in prices_dict.items()})
    else:
        prices = prices_dict
    
    result = {
        "prices": prices,
        "metadata": metadata,
        "available_rewards": rewards,
        "drift_check": None,
        "options_analysis": None,
    }
    
    # Check model drift if enabled
    if check_drift:
        if model_path is None:
            # Default to long-trained model
            model_path = "models/rl_long/best/ppo/best_model.zip"
        
        if Path(model_path).exists():
            # Compute recent returns from prices (last 60 days)
            recent_prices = prices.iloc[-60:] if len(prices) >= 60 else prices
            recent_returns = recent_prices.pct_change().mean(axis=1).dropna().values
            
            drift_result = check_model_drift(
                model_path=model_path,
                recent_returns=recent_returns,
                baseline_sharpe=1.5,  # From rl_long training
                threshold=0.5,
            )
            result["drift_check"] = drift_result
            
            if drift_result["drift_detected"]:
                logger.warning(
                    "⚠️  MODEL RETRAIN RECOMMENDED: "
                    f"{drift_result['reason']} (confidence={drift_result['confidence']:.1%})"
                )
        else:
            logger.warning(f"Model not found at {model_path}, skipping drift check")
    
    # Analyze options market if enabled
    if analyze_options:
        options_analysis = analyze_options_market(
            symbols=symbols,
            prices=prices,
            risk_free_rate=risk_free_rate,
        )
        result["options_analysis"] = options_analysis
        
        # Log portfolio hedging suggestion
        if options_analysis:
            avg_delta = np.mean([
                v["implied_hedge_ratio"] 
                for v in options_analysis.values() 
                if v is not None
            ])
            logger.info(f"💡 Average hedge ratio: {avg_delta:.2%} (use put options to hedge)")
    
    logger.info(
        f"✅ Preanalysis complete: {len(symbols)} symbols, "
        f"rewards={len(rewards)}, "
        f"drift_detected={result['drift_check']['drift_detected'] if result['drift_check'] else 'N/A'}, "
        f"options_analyzed={sum(1 for v in (result['options_analysis'] or {}).values() if v)}"
    )
    return result


__all__ = ["run_daily_preanalysis", "check_model_drift", "analyze_options_market"]
