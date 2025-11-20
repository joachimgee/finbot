"""
CLI pour FinBot - Advanced Backtesting (Phase E) + ML Features (Phase F).

Permet de lancer walk-forward analysis, purged CV, meta-labeling depuis CLI.
Ajoute fractional differentiation, Hurst exponent, feature importance, microstructure.

Usage:
    # Phase E
    python -m financial_analyzer.cli.analysis_cli --walk-forward --ticker AAPL
    python -m financial_analyzer.cli.analysis_cli --purged-cv --ticker MSFT
    python -m financial_analyzer.cli.analysis_cli --meta-label --ticker GOOGL
    
    # Phase F
    python -m financial_analyzer.cli.analysis_cli --frac-diff --ticker AAPL
    python -m financial_analyzer.cli.analysis_cli --hurst --ticker MSFT
    python -m financial_analyzer.cli.analysis_cli --feature-importance --ticker GOOGL
    python -m financial_analyzer.cli.analysis_cli --microstructure --ticker TSLA
"""

import argparse
import sys
from typing import Dict, Any
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.features.technical import TechnicalFeatureEngine
from financial_analyzer.backtest_advanced import (
    WalkForwardAnalyzer,
    PurgedKFold,
    MetaLabeler,
    walk_forward_optimize,
)
from financial_analyzer.ml_features_advanced import (
    FractionalDifferentiator,
    frac_diff,
    FeatureImportanceAnalyzer,
    get_feature_importance,
    AutocorrelationFeatures,
    compute_hurst,
    MicrostructureFeatures,
    compute_vwap,
)
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def run_walk_forward(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Exécute walk-forward analysis.
    
    Args:
    ticker: Symbole ticker
    start_date: Date début
    end_date: Date fin
    
    Returns:
    Résultats walk-forward
    """
    logger.info(f"Walk-Forward Analysis: {ticker} ({start_date} - {end_date})")
    
    # Fetch data
    fetcher = MarketDataFetcher()
    data = fetcher.get_historical_data(ticker, start_date=start_date, end_date=end_date)
    
    # Add features
    tech = TechnicalFeatureEngine()
    data = tech.add_sma(data, periods=[20, 50])
    data = tech.add_rsi(data)
    data['returns'] = data['Close'].pct_change()
    
    # Walk-forward analyzer
    wf = WalkForwardAnalyzer(
    data=data,
    window_type='rolling',
    train_size=100,
    test_size=20,
    step_size=20
    )
    
    # Dummy optimize/backtest functions
    def optimize_func(train_data):
    # Simple SMA crossover optimization
    return {'sma_fast': 20, 'sma_slow': 50}
    
    def backtest_func(test_data, params):
    # Simple backtest
    signals = (test_data['sma_20'] > test_data['sma_50']).astype(int)
    returns = test_data['returns'] * signals.shift(1)
    total_return = (1 + returns).prod() - 1
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    return {'total_return': total_return, 'sharpe': sharpe}
    
    # Run
    results = wf.run(optimize_func, backtest_func)
    
    logger.info(f"Walk-Forward Results: Overfitting Ratio={results['overfitting_ratio']:.2f}")
    logger.info(f"In-sample Sharpe: {results['in_sample']['sharpe']:.2f}")
    logger.info(f"Out-of-sample Sharpe: {results['out_of_sample']['sharpe']:.2f}")
    
    return results


def run_purged_cv(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Exécute purged K-Fold CV.
    
    Args:
    ticker: Symbole ticker
    start_date: Date début
    end_date: Date fin
    
    Returns:
    Résultats purged CV
    """
    logger.info(f"Purged K-Fold CV: {ticker} ({start_date} - {end_date})")
    
    # Fetch data
    fetcher = MarketDataFetcher()
    data = fetcher.get_historical_data(ticker, start_date=start_date, end_date=end_date)
    
    # Add features
    tech = TechnicalFeatureEngine()
    data = tech.add_sma(data, periods=[20, 50])
    data = tech.add_rsi(data)
    
    # Features matrix
    X = data[['sma_20', 'sma_50', 'rsi']].dropna()
    
    # Purged K-Fold
    cv = PurgedKFold(n_splits=5, pct_embargo=0.01)
    
    logger.info(f"Purged CV: {cv.get_n_splits()} splits avec embargo de {cv.pct_embargo*100}%")
    
    results = {
    'n_splits': cv.get_n_splits(),
    'pct_embargo': cv.pct_embargo,
    'data_size': len(X)
    }
    
    return results


def run_meta_labeling(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Exécute meta-labeling analysis.
    
    Args:
    ticker: Symbole ticker
    start_date: Date début
    end_date: Date fin
    
    Returns:
    Résultats meta-labeling
    """
    logger.info(f"Meta-Labeling: {ticker} ({start_date} - {end_date})")
    
    # Fetch data
    fetcher = MarketDataFetcher()
    data = fetcher.get_historical_data(ticker, start_date=start_date, end_date=end_date)
    
    # Add features + returns
    tech = TechnicalFeatureEngine()
    data = tech.add_sma(data, periods=[20, 50])
    data = tech.add_rsi(data)
    data['returns'] = data['Close'].pct_change()
    
    # Primary signals (SMA crossover)
    data['primary_signal'] = (data['sma_20'] > data['sma_50']).astype(int) * 2 - 1  # -1 or 1
    
    # Features + clean
    features = data[['sma_20', 'sma_50', 'rsi']].dropna()
    returns = data['returns'].loc[features.index]
    signals = data['primary_signal'].loc[features.index]
    
    # Split train/test
    split_idx = int(len(features) * 0.7)
    X_train = features.iloc[:split_idx]
    X_test = features.iloc[split_idx:]
    returns_train = returns.iloc[:split_idx]
    returns_test = returns.iloc[split_idx:]
    signals_train = signals.iloc[:split_idx]
    signals_test = signals.iloc[split_idx:]
    
    # Meta-labeler
    ml = MetaLabeler()
    ml.fit(X_train, returns_train, signals_train, horizon=5)
    
    # Evaluate
    metrics = ml.evaluate(X_test, returns_test, signals_test, horizon=5)
    
    logger.info(f"Meta-Labeling Results: Accuracy={metrics['accuracy']:.3f}, Precision={metrics['precision']:.3f}")
    
    return metrics


def run_frac_diff(ticker: str, start_date: str, end_date: str, d: float = 0.5) -> Dict[str, Any]:
    """
    Exécute fractional differentiation sur close prices.
    
    Args:
    ticker: Symbole ticker
    start_date: Date début
    end_date: Date fin
    d: Ordre de différentiation (0 < d < 1)
    
    Returns:
    Résultats fractional differentiation
    """
    logger.info(f"Fractional Differentiation: {ticker} (d={d})")
    
    # Fetch data
    fetcher = MarketDataFetcher()
    data = fetcher.get_historical_data(ticker, start_date=start_date, end_date=end_date)
    
    # Apply fractional diff
    prices = data['Close']
    fd = FractionalDifferentiator()
    frac_prices = fd.transform(prices, d=d)
    
    # Compare variance
    var_original = prices.var()
    var_frac = frac_prices.var()
    
    logger.info(f"Variance - Original: {var_original:.4f}, Frac: {var_frac:.4f}")
    
    results = {
    'd': d,
    'original_variance': float(var_original),
    'frac_variance': float(var_frac),
    'variance_reduction': float(1 - var_frac/var_original) if var_original > 0 else 0,
    'data_length': len(frac_prices.dropna())
    }
    
    return results


def run_hurst(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Calcule Hurst exponent (régime detection).
    
    Args:
    ticker: Symbole ticker
    start_date: Date début
    end_date: Date fin
    
    Returns:
    Hurst exponent et interprétation
    """
    logger.info(f"Hurst Exponent: {ticker}")
    
    # Fetch data
    fetcher = MarketDataFetcher()
    data = fetcher.get_historical_data(ticker, start_date=start_date, end_date=end_date)
    
    # Compute Hurst
    prices = data['Close']
    acf_features = AutocorrelationFeatures()
    hurst = acf_features.compute_hurst_exponent(prices)
    
    # Interpretation
    if hurst > 0.5:
    regime = "Trending (persistent)"
    elif hurst < 0.5:
    regime = "Mean-Reverting (anti-persistent)"
    else:
    regime = "Random Walk (Brownian)"
    
    logger.info(f"Hurst Exponent: {hurst:.3f} → {regime}")
    
    results = {
    'hurst_exponent': hurst,
    'regime': regime,
    'is_trending': hurst > 0.5,
    'is_mean_reverting': hurst < 0.5,
    'data_length': len(prices)
    }
    
    return results


def run_feature_importance(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Analyse feature importance (MDI + MDA).
    
    Args:
    ticker: Symbole ticker
    start_date: Date début
    end_date: Date fin
    
    Returns:
    Feature importance scores
    """
    logger.info(f"Feature Importance: {ticker}")
    
    # Fetch data + features
    fetcher = MarketDataFetcher()
    data = fetcher.get_historical_data(ticker, start_date=start_date, end_date=end_date)
    
    tech = TechnicalFeatureEngine()
    data = tech.add_sma(data, periods=[20, 50])
    data = tech.add_rsi(data)
    data = tech.add_macd(data)
    data['returns'] = data['Close'].pct_change()
    
    # Target: 1 if returns > 0, else 0
    data['target'] = (data['returns'] > 0).astype(int)
    
    # Features matrix
    X = data[['sma_20', 'sma_50', 'rsi', 'macd', 'macd_signal']].dropna()
    y = data['target'].loc[X.index]
    
    # Train/test split
    split_idx = int(len(X) * 0.7)
    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:split_idx]
    y_test = y.iloc[split_idx:]
    
    # Train model
    model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    model.fit(X_train, y_train)
    
    # Feature importance
    fi_analyzer = FeatureImportanceAnalyzer(model, X_train, y_train, X_test, y_test)
    mdi_scores = fi_analyzer.get_mdi_importance()
    mda_scores = fi_analyzer.get_mda_importance(n_repeats=10)
    
    logger.info("Feature Importance (MDI):")
    for feat, score in mdi_scores.items():
    logger.info(f"  {feat}: {score:.4f}")
    
    results = {
    'mdi_scores': mdi_scores.to_dict(),
    'mda_scores': mda_scores.to_dict(),
    'top_mdi_feature': mdi_scores.idxmax(),
    'top_mda_feature': mda_scores.idxmax(),
    'model_accuracy': model.score(X_test, y_test)
    }
    
    return results


def run_microstructure(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Calcule microstructure features (VWAP, spreads, liquidity).
    
    Args:
    ticker: Symbole ticker
    start_date: Date début
    end_date: Date fin
    
    Returns:
    Microstructure metrics
    """
    logger.info(f"Microstructure Features: {ticker}")
    
    # Fetch data
    fetcher = MarketDataFetcher()
    data = fetcher.get_historical_data(ticker, start_date=start_date, end_date=end_date)
    
    # Normalize columns to lowercase for microstructure module
    data.columns = data.columns.str.lower()
    
    # Compute microstructure
    micro = MicrostructureFeatures()
    
    # VWAP
    vwap = micro.compute_vwap(data)
    
    # Order flow (requires buy/sell, use proxy)
    data['buy_volume'] = data['Volume'] * (data['Close'] > data['Open']).astype(float)
    data['sell_volume'] = data['Volume'] - data['buy_volume']
    order_flow = micro.compute_order_flow_imbalance(data)
    
    # Spread (Roll estimator)
    spread = micro.compute_bid_ask_spread(data, method='roll')
    
    # Amihud illiquidity
    illiquidity = micro.compute_amihud_illiquidity(data)
    
    # Kyle's Lambda
    kyles_lambda = micro.compute_kyles_lambda(data)
    
    logger.info(f"VWAP mean: {vwap.mean():.2f}")
    logger.info(f"Order Flow mean: {order_flow.mean():.3f}")
    logger.info(f"Spread mean: {spread.mean():.5f}")
    logger.info(f"Illiquidity mean: {illiquidity.mean():.6f}")
    logger.info(f"Kyle's Lambda: {kyles_lambda:.6f}")
    
    results = {
    'vwap_mean': float(vwap.mean()),
    'order_flow_mean': float(order_flow.mean()),
    'spread_mean': float(spread.mean()),
    'illiquidity_mean': float(illiquidity.mean()),
    'kyles_lambda': float(kyles_lambda),
    'data_length': len(data)
    }
    
    return results


def main():
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description='FinBot Advanced Backtesting + ML Features CLI')
    
    # Phase E arguments
    parser.add_argument('--walk-forward', action='store_true', help='Run walk-forward analysis')
    parser.add_argument('--purged-cv', action='store_true', help='Run purged K-Fold CV')
    parser.add_argument('--meta-label', action='store_true', help='Run meta-labeling')
    
    # Phase F arguments
    parser.add_argument('--frac-diff', action='store_true', help='Run fractional differentiation')
    parser.add_argument('--hurst', action='store_true', help='Compute Hurst exponent (regime detection)')
    parser.add_argument('--feature-importance', action='store_true', help='Analyze feature importance (MDI/MDA)')
    parser.add_argument('--microstructure', action='store_true', help='Compute microstructure features (VWAP, spreads, liquidity)')
    
    # Common arguments
    parser.add_argument('--ticker', type=str, default='AAPL', help='Ticker symbol')
    parser.add_argument('--start', type=str, default='2020-01-01', help='Start date')
    parser.add_argument('--end', type=str, default='2023-12-31', help='End date')
    parser.add_argument('--d', type=float, default=0.5, help='Fractional differentiation order (for --frac-diff)')
    
    args = parser.parse_args()
    
    if not any([args.walk_forward, args.purged_cv, args.meta_label, 
                args.frac_diff, args.hurst, args.feature_importance, args.microstructure]):
    parser.print_help()
    sys.exit(1)
    
    try:
    # Phase E commands
    if args.walk_forward:
            results = run_walk_forward(args.ticker, args.start, args.end)
            print("\n=== Walk-Forward Results ===")
            print(f"Overfitting Ratio: {results['overfitting_ratio']:.2f}")
            print(f"In-sample Sharpe: {results['in_sample']['sharpe']:.2f}")
            print(f"Out-of-sample Sharpe: {results['out_of_sample']['sharpe']:.2f}")
    
    if args.purged_cv:
            results = run_purged_cv(args.ticker, args.start, args.end)
            print("\n=== Purged K-Fold CV Results ===")
            print(f"N splits: {results['n_splits']}")
            print(f"Embargo: {results['pct_embargo']*100}%")
            print(f"Data size: {results['data_size']}")
    
    if args.meta_label:
            results = run_meta_labeling(args.ticker, args.start, args.end)
            print("\n=== Meta-Labeling Results ===")
            print(f"Accuracy: {results['accuracy']:.3f}")
            print(f"Precision: {results['precision']:.3f}")
            print(f"Recall: {results['recall']:.3f}")
            print(f"F1: {results['f1']:.3f}")
    
    # Phase F commands
    if args.frac_diff:
            results = run_frac_diff(args.ticker, args.start, args.end, d=args.d)
            print("\n=== Fractional Differentiation Results ===")
            print(f"Order d: {results['d']}")
            print(f"Original Variance: {results['original_variance']:.4f}")
            print(f"Frac Diff Variance: {results['frac_variance']:.4f}")
            print(f"Variance Reduction: {results['variance_reduction']*100:.2f}%")
            print(f"Data length: {results['data_length']}")
    
    if args.hurst:
            results = run_hurst(args.ticker, args.start, args.end)
            print("\n=== Hurst Exponent Results ===")
            print(f"Hurst Exponent: {results['hurst_exponent']:.3f}")
            print(f"Regime: {results['regime']}")
            print(f"Trending: {results['is_trending']}, Mean-Reverting: {results['is_mean_reverting']}")
    
    if args.feature_importance:
            results = run_feature_importance(args.ticker, args.start, args.end)
            print("\n=== Feature Importance Results ===")
            print(f"Model Accuracy: {results['model_accuracy']:.3f}")
            print("\nMDI Scores:")
            for feat, score in results['mdi_scores'].items():
                print(f"  {feat}: {score:.4f}")
            print(f"\nTop MDI Feature: {results['top_mdi_feature']}")
            print(f"Top MDA Feature: {results['top_mda_feature']}")
    
    if args.microstructure:
            results = run_microstructure(args.ticker, args.start, args.end)
            print("\n=== Microstructure Features Results ===")
            print(f"VWAP mean: {results['vwap_mean']:.2f}")
            print(f"Order Flow mean: {results['order_flow_mean']:.3f}")
            print(f"Spread mean: {results['spread_mean']:.5f}")
            print(f"Illiquidity mean: {results['illiquidity_mean']:.6f}")
            print(f"Kyle's Lambda: {results['kyles_lambda']:.6f}")
    
    logger.info("CLI execution completed successfully")
    sys.exit(0)
    
    except Exception as e:
    logger.error(f"CLI execution failed: {e}")
    print(f"ERROR: {e}")
    sys.exit(1)


if __name__ == '__main__':
    main()
