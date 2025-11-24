"""
Example: Daily Preanalysis with Options Market Analysis

Demonstrates the integrated daily preanalysis workflow:
1. Load historical data
2. Check model drift
3. Analyze options market
4. Generate portfolio hedging suggestions
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from financial_analyzer.preanalysis.daily_preanalysis import run_daily_preanalysis

# Configuration
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

# Run comprehensive daily preanalysis
print("🚀 Running daily preanalysis...")
print(f"Symbols: {SYMBOLS}")
print(f"Date range: {START_DATE} to {END_DATE}")
print("-" * 60)

result = run_daily_preanalysis(
    symbols=SYMBOLS,
    start_date=START_DATE,
    end_date=END_DATE,
    check_drift=True,  # Check RL model performance drift
    analyze_options=True,  # Analyze options market
    risk_free_rate=0.05,  # 5% risk-free rate
)

# 1. Display drift check results
print("\n📊 MODEL DRIFT CHECK")
print("-" * 60)
if result["drift_check"]:
    drift = result["drift_check"]
    print(f"Drift detected: {drift['drift_detected']}")
    print(f"Reason: {drift['reason']}")
    print(f"Confidence: {drift['confidence']:.1%}")
    print(f"Current Sharpe: {drift['current_sharpe']:.2f}")
    print(f"Baseline Sharpe: {drift['baseline_sharpe']:.2f}")
    
    if drift["drift_detected"]:
        print("\n⚠️  RECOMMENDATION: Retrain model with recent data")
else:
    print("Drift check disabled")

# 2. Display options analysis
print("\n💰 OPTIONS MARKET ANALYSIS")
print("-" * 60)
if result["options_analysis"]:
    options = result["options_analysis"]
    
    # Summary table
    print(f"{'Symbol':<8} {'Spot':<10} {'Strike':<10} {'Vol':<8} {'Call':<10} {'Put':<10} {'Delta':<8}")
    print("-" * 60)
    
    for symbol, data in options.items():
        if data:
            print(
                f"{symbol:<8} "
                f"${data['spot']:<9.2f} "
                f"${data['strike']:<9.2f} "
                f"{data['volatility']:<7.2%} "
                f"${data['call_price']:<9.2f} "
                f"${data['put_price']:<9.2f} "
                f"{data['delta_call']:<7.4f}"
            )
    
    # Portfolio hedging suggestion
    print("\n📈 PORTFOLIO HEDGING SUGGESTIONS")
    print("-" * 60)
    
    valid_data = [v for v in options.values() if v is not None]
    if valid_data:
        avg_delta = np.mean([v["implied_hedge_ratio"] for v in valid_data])
        avg_vol = np.mean([v["volatility"] for v in valid_data])
        
        print(f"Average hedge ratio: {avg_delta:.2%}")
        print(f"Average volatility: {avg_vol:.2%}")
        print()
        print("💡 Hedging Strategy:")
        print(f"  - For $100K long portfolio: buy {avg_delta*100:.1f}K in put options")
        print(f"  - Recommended strike: ATM (current spot)")
        print(f"  - Recommended expiration: 3 months")
        
        if avg_vol > 0.30:
            print("\n⚠️  High volatility detected - consider protective puts")
        elif avg_vol < 0.15:
            print("\n✅ Low volatility - covered calls may be profitable")

else:
    print("Options analysis disabled")

# 3. Display available rewards
print("\n🎁 AVAILABLE REWARDS")
print("-" * 60)
rewards = result.get("available_rewards", [])
print(f"Total: {len(rewards)} reward functions")
print(f"Examples: {', '.join(rewards[:5])}")

# 4. Summary
print("\n✅ PREANALYSIS SUMMARY")
print("-" * 60)
print(f"Symbols loaded: {len(SYMBOLS)}")
print(f"Price data: {len(result['prices'])} days")
print(f"Drift check: {'PASS' if not result.get('drift_check', {}).get('drift_detected') else 'FAIL'}")
print(f"Options analyzed: {sum(1 for v in (result.get('options_analysis') or {}).values() if v)}/{len(SYMBOLS)}")

print("\n🚀 Ready for RL pipeline execution!")
