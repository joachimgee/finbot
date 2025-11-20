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
    
    # Normalize columns to lowercase
    data.columns = data.columns.str.lower()
    
    # Compute microstructure
    micro = MicrostructureFeatures()
    
    # VWAP
    vwap = micro.compute_vwap(data)
    
    # Order flow (requires buy/sell, use proxy)
    data['buy_volume'] = data['volume'] * (data['close'] > data['open']).astype(float)
    data['sell_volume'] = data['volume'] - data['buy_volume']
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
    
    # Phase F arguments
    parser.add_argument('--hurst', action='store_true', help='Compute Hurst exponent (regime detection)')
    parser.add_argument('--microstructure', action='store_true', help='Compute microstructure features (VWAP, spreads, liquidity)')
    parser.add_argument('--pipeline', action='store_true', help='Run full Phase F pipeline adapter')
    
    # Common arguments
    parser.add_argument('--ticker', type=str, default='AAPL', help='Ticker symbol')
    parser.add_argument('--start', type=str, default='2020-01-01', help='Start date')
    parser.add_argument('--end', type=str, default='2023-12-31', help='End date')
    parser.add_argument('--universe', type=str, nargs='*', help='Universe tickers for pipeline (override single ticker)')
    
    args = parser.parse_args()
    
    if not any([args.hurst, args.microstructure, args.pipeline]):
        parser.print_help()
        sys.exit(1)
    
    try:
        # Phase F commands
        if args.hurst:
            results = run_hurst(args.ticker, args.start, args.end)
            print("\n=== Hurst Exponent Results ===")
            print(f"Hurst Exponent: {results['hurst_exponent']:.3f}")
            print(f"Regime: {results['regime']}")
            print(f"Trending: {results['is_trending']}, Mean-Reverting: {results['is_mean_reverting']}")
        
        if args.microstructure:
            results = run_microstructure(args.ticker, args.start, args.end)
            print("\n=== Microstructure Features Results ===")
            print(f"VWAP mean: {results['vwap_mean']:.2f}")
            print(f"Order Flow mean: {results['order_flow_mean']:.3f}")
            print(f"Spread mean: {results['spread_mean']:.5f}")
            print(f"Illiquidity mean: {results['illiquidity_mean']:.6f}")
            print(f"Kyle's Lambda: {results['kyles_lambda']:.6f}")
        
        if args.pipeline:
            from financial_analyzer.pipeline.pipeline_phase_f_adapter import PhaseFPipeline
            universe = args.universe if args.universe else [args.ticker]
            pipe = PhaseFPipeline()
            presult = pipe.run(args.end, universe, start_date=args.start)
            
            # Phase F Advanced Features
            adv = presult['steps'].get('advanced_features_detail', {})
            print("\n=== Phase F Pipeline (Advanced Features) ===")
            print(f"Universe size: {len(universe)}")
            for t, metrics in adv.items():
                print(f"\nTicker: {t}")
                for k, v in metrics.items():
                    print(f"  {k}: {v:.6f}")
            
            # Phase E Metrics
            wf = presult['steps'].get('walk_forward', {})
            if wf:
                print("\n=== Phase E: Walk-Forward Analysis ===")
                print(f"Ticker: {wf.get('ticker', 'N/A')}")
                print(f"Overfitting Ratio: {wf.get('overfitting_ratio', 0.0):.3f}")
                print(f"In-sample Sharpe: {wf.get('in_sample_sharpe', 0.0):.3f}")
                print(f"Out-of-sample Sharpe: {wf.get('out_sample_sharpe', 0.0):.3f}")
                print(f"Num Windows: {wf.get('num_windows', 0)}")
            
            pcv = presult['steps'].get('purged_cv', {})
            if pcv:
                print("\n=== Phase E: Purged K-Fold CV ===")
                print(f"Ticker: {pcv.get('ticker', 'N/A')}")
                print(f"N Splits: {pcv.get('n_splits', 0)}")
                print(f"Embargo: {pcv.get('pct_embargo', 0.0)*100:.1f}%")
                print(f"Avg Train Size: {pcv.get('avg_train_size', 0.0):.0f}")
                print(f"Avg Test Size: {pcv.get('avg_test_size', 0.0):.0f}")
            
            ml = presult['steps'].get('meta_labeling', {})
            if ml:
                print("\n=== Phase E: Meta-Labeling ===")
                print(f"Ticker: {ml.get('ticker', 'N/A')}")
                print(f"Accuracy: {ml.get('accuracy', 0.0):.3f}")
                print(f"Precision: {ml.get('precision', 0.0):.3f}")
                print(f"Recall: {ml.get('recall', 0.0):.3f}")
                print(f"F1: {ml.get('f1', 0.0):.3f}")
        
        logger.info("CLI execution completed successfully")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"CLI execution failed: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
