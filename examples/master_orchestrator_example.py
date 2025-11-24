#!/usr/bin/env python3
"""
Master Orchestrator - Exemple d'utilisation complète.

Démontre le workflow complet:
1. Portfolio Pre-Analysis (morning routine)
2. Signal Generation (RL + ML + Sentiment)
3. Portfolio Optimization
4. Risk Validation & Execution

Sans doublons - Réutilise tous les modules existants.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.financial_analyzer.analysis.master_orchestrator import MasterOrchestrator


def main():
    """Run complete analysis workflow."""
    
    print("=" * 80)
    print("MASTER ORCHESTRATOR - COMPLETE WORKFLOW EXAMPLE")
    print("=" * 80)
    
    # Configuration
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # 1 year
    
    # Initialize orchestrator
    orchestrator = MasterOrchestrator(
        symbols=symbols,
        mode='paper',  # Use paper trading
        initial_capital=100_000.0,
        max_positions=200,
        risk_free_rate=0.05,
        lookback_days=60,
    )
    
    print(f"\n📊 Configuration:")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Period: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
    print(f"  Mode: paper")
    print(f"  Capital: $100,000")
    
    # Run complete analysis
    print(f"\n🚀 Running complete analysis...")
    
    result = orchestrator.run_complete_analysis(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        skip_if_no_drift=False,  # Always run for demo
        use_rl_signals=True,
        use_ml_signals=True,
        use_sentiment=True,
        optimization_method='mean_variance',
        enable_options_hedge=True,
        dry_run=True,  # Don't execute actual orders
    )
    
    # Display results
    print(f"\n" + "=" * 80)
    print(f"RESULTS")
    print(f"=" * 80)
    
    print(f"\nStatus: {result.status}")
    print(f"Elapsed time: {result.elapsed_time_seconds:.1f}s")
    
    # Phase 1: Pre-Analysis
    if result.pre_analysis:
        print(f"\n📋 PHASE 1: PRE-ANALYSIS")
        print(f"  Drift detected: {result.pre_analysis.drift_detected}")
        if result.pre_analysis.drift_detected:
            print(f"  Drift reason: {result.pre_analysis.drift_reason}")
        print(f"  Should retrain: {result.pre_analysis.should_retrain}")
        print(f"  Options analyzed: {len(result.pre_analysis.options_analysis)}")
        print(f"  Learning insights: {len(result.pre_analysis.learning_insights)}")
        print(f"  Warnings: {len(result.pre_analysis.warnings)}")
        
        # Portfolio decisions
        decisions = result.pre_analysis.portfolio_decisions
        print(f"\n  Portfolio Decisions:")
        print(f"    HOLD: {len(decisions.get('hold', []))} positions")
        print(f"    SELL: {len(decisions.get('sell', []))} positions")
        print(f"    BUY: {len(decisions.get('buy', []))} opportunities")
        print(f"    CANCEL: {len(decisions.get('cancel', []))} orders")
        
        # Options analysis sample
        if result.pre_analysis.options_analysis:
            print(f"\n  Options Analysis (sample):")
            for i, (symbol, opt) in enumerate(list(result.pre_analysis.options_analysis.items())[:3]):
                if opt:
                    print(f"    {symbol}:")
                    print(f"      Spot: ${opt['spot']:.2f}")
                    print(f"      Strike: ${opt['strike']:.2f}")
                    print(f"      Vol: {opt['volatility']:.2%}")
                    print(f"      Call: ${opt['call_price']:.2f}")
                    print(f"      Put: ${opt['put_price']:.2f}")
                    print(f"      Delta: {opt['delta_call']:.4f}")
                    print(f"      Hedge ratio: {opt['implied_hedge_ratio']:.2%}")
    
    # Phase 2: Signal Generation
    if result.signal_generation:
        print(f"\n📊 PHASE 2: SIGNAL GENERATION")
        print(f"  RL signals: {len(result.signal_generation.rl_signals or {})}")
        print(f"  ML predictions: {len(result.signal_generation.ml_predictions or {})}")
        print(f"  Sentiment scores: {len(result.signal_generation.sentiment_scores or {})}")
        print(f"  Combined signals: {len(result.signal_generation.combined_signals)}")
        
        # Top signals
        print(f"\n  Top Signals:")
        sorted_signals = sorted(
            result.signal_generation.combined_signals.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]
        for symbol, signal in sorted_signals:
            confidence = result.signal_generation.confidence_scores.get(symbol, 0)
            direction = "BUY" if signal > 0 else "SELL" if signal < 0 else "NEUTRAL"
            print(f"    {symbol}: {direction} (signal={signal:+.4f}, confidence={confidence:.2%})")
    
    # Phase 3: Portfolio Construction
    if result.portfolio_construction:
        print(f"\n💼 PHASE 3: PORTFOLIO CONSTRUCTION")
        print(f"  Optimization method: {result.portfolio_construction.optimization_method}")
        print(f"  Rebalance needed: {result.portfolio_construction.rebalance_needed}")
        print(f"  Expected return: {result.portfolio_construction.expected_return:.2%}")
        print(f"  Expected volatility: {result.portfolio_construction.expected_volatility:.2%}")
        print(f"  Expected Sharpe: {result.portfolio_construction.expected_sharpe:.2f}")
        
        # Target weights
        print(f"\n  Target Weights (Top 5):")
        top_weights = result.portfolio_construction.target_weights.nlargest(5)
        for symbol, weight in top_weights.items():
            current = result.portfolio_construction.current_weights.get(symbol, 0)
            trade = result.portfolio_construction.trades_required.get(symbol, 0)
            print(f"    {symbol}: {weight:.2%} (current={current:.2%}, trade={trade:+.2%})")
        
        # Options hedge
        if result.portfolio_construction.options_hedge_overlay:
            print(f"\n  Options Hedge Overlay:")
            hedge = result.portfolio_construction.options_hedge_overlay
            print(f"    Portfolio delta: {hedge['portfolio_delta']:.4f}")
            print(f"    Hedge ratio: {hedge['hedge_ratio']:.2%}")
            print(f"    Hedge type: {hedge['hedge_type']}")
            print(f"    Hedge allocation: {hedge['hedge_allocation']:.2%}")
    
    # Phase 4: Execution
    if result.execution:
        print(f"\n⚡ PHASE 4: EXECUTION")
        print(f"  Orders submitted: {len(result.execution.orders_submitted)}")
        print(f"  Orders executed: {len(result.execution.orders_executed)}")
        print(f"  Orders rejected: {len(result.execution.orders_rejected)}")
        print(f"  Circuit breakers: {len(result.execution.circuit_breakers_triggered)}")
        print(f"  Portfolio value before: ${result.execution.portfolio_value_before:,.2f}")
        print(f"  Portfolio value after: ${result.execution.portfolio_value_after:,.2f}")
        print(f"  Execution cost: ${result.execution.execution_cost:,.2f}")
    
    print(f"\n" + "=" * 80)
    print(f"✅ COMPLETE WORKFLOW FINISHED")
    print(f"=" * 80)
    
    # Architecture recap
    print(f"\n📚 ARCHITECTURE MODULES USED (NO DUPLICATES):")
    print(f"  ✅ preanalysis/daily_preanalysis.py : drift detection, options analysis")
    print(f"  ✅ learning/portfolio_learner.py : morning learning routine")
    print(f"  ✅ scripts/portfolio_manager.py : HOLD/SELL/BUY decisions")
    print(f"  ✅ portfolio/optimizer.py : Mean-Variance optimization")
    print(f"  ✅ portfolio/rebalancer.py : Rebalancing logic")
    print(f"  ✅ derivatives/options : Black-Scholes, Greeks, Strategies")
    print(f"  ✅ pipeline/rl_trading_pipeline.py : RL signals")
    print(f"  ✅ pipeline/ml_trading_pipeline.py : ML predictions")
    print(f"  ✅ sentiment/realtime_pipeline.py : Sentiment analysis")
    print(f"  ✅ trading/broker_adapter.py : Alpaca integration")
    print(f"  ✅ trading/risk_guard.py : Risk validation")
    
    print(f"\n🎯 WORKFLOW:")
    print(f"  1. Portfolio Pre-Analysis → Morning learning + drift check + options")
    print(f"  2. Signal Generation → RL + ML + Sentiment")
    print(f"  3. Portfolio Construction → Optimization + hedging")
    print(f"  4. Risk Validation & Execution → Circuit breakers + orders")


if __name__ == '__main__':
    main()
