"""
Track REAL performance metrics with REALISTIC expectations.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv('.env.production')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.portfolio.metrics import (
    calculate_portfolio_return,
    calculate_portfolio_volatility,
    calculate_portfolio_sharpe
)
import pandas as pd
import numpy as np


def calculate_max_drawdown(cumulative_returns):
    """Calculate maximum drawdown from cumulative returns."""
    running_max = cumulative_returns.expanding().max()
    drawdown = (cumulative_returns - running_max) / running_max
    return drawdown.min()


def calculate_sortino_ratio(weights, returns_df, risk_free_rate=0.02):
    """Calculate Sortino ratio (return over downside deviation)."""
    portfolio_returns = (returns_df @ weights).fillna(0)
    excess_returns = portfolio_returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0:
        return np.nan
    
    downside_std = downside_returns.std() * np.sqrt(252)
    
    if downside_std == 0:
        return np.nan
    
    return (portfolio_returns.mean() * 252 - risk_free_rate) / downside_std


def generate_performance_report():
    """Generate performance report with REALISTIC expectations."""
    print("\n" + "="*80)
    print("FINBOT DAILY PERFORMANCE REPORT")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    try:
        # Fetch recent performance data
        fetcher = MarketDataFetcher()
        
        # Get 3 months of data (realistic backtesting period)
        end = datetime.now()
        start = end - timedelta(days=90)
        
        # Use 10 tickers for realistic diversification
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 
                   'META', 'TSLA', 'NFLX', 'AMD', 'INTC']
        
        print("📊 Fetching performance data (90 days)...")
        df = fetcher.get_historical_data(
            tickers=tickers,
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d')
        )
        
        # MarketDataFetcher returns dict of DataFrames
        if not isinstance(df, dict):
            print("❌ Unexpected data format")
            return
        
        if not df or len(df) == 0:
            print("❌ No data available")
            return
        
        print(f"   ✅ Data points: {sum(len(v) for v in df.values())}")
        
        # Calculate returns
        print("\n💹 Calculating returns...")
        returns_dict = {}
        for ticker in tickers:
            if ticker in df and not df[ticker].empty and 'Close' in df[ticker].columns:
                returns_dict[ticker] = df[ticker]['Close'].pct_change().dropna()
        
        if not returns_dict:
            print("❌ No returns calculated")
            return
        
        returns_df = pd.DataFrame(returns_dict).dropna()
        
        # Equal weight portfolio
        weights = pd.Series(1.0 / len(tickers), index=tickers)
        
        # Calculate REALISTIC metrics
        print("\n📈 REALISTIC PERFORMANCE METRICS:\n")
        
        # Portfolio return (annualized from 90 days)
        portfolio_return = calculate_portfolio_return(weights, returns_df.mean() * 252)
        print(f"   Annual Return (est.): {portfolio_return:.2%}")
        print(f"   📌 Realistic range: 8-15% for diversified portfolio")
        
        # Portfolio volatility
        cov_matrix = returns_df.cov() * 252
        portfolio_vol = calculate_portfolio_volatility(weights, cov_matrix)
        print(f"\n   Annual Volatility: {portfolio_vol:.2%}")
        print(f"   📌 Realistic range: 15-25% for equity portfolio")
        
        # Sharpe ratio
        sharpe = calculate_portfolio_sharpe(weights, returns_df.mean() * 252, cov_matrix, risk_free_rate=0.04)
        print(f"\n   Sharpe Ratio: {sharpe:.2f}")
        print(f"   📌 Realistic range: 0.5-1.5 (good), 1.5-2.0 (excellent)")
        
        # Sortino ratio
        sortino = calculate_sortino_ratio(weights, returns_df)
        print(f"\n   Sortino Ratio: {sortino:.2f}")
        print(f"   📌 Better than Sharpe for downside risk")
        
        # Max drawdown
        portfolio_returns = (returns_df @ weights).fillna(0)
        cumulative = (1 + portfolio_returns).cumprod()
        max_dd = calculate_max_drawdown(cumulative)
        print(f"\n   Max Drawdown: {max_dd:.2%}")
        print(f"   📌 Realistic range: -10% to -20% (3 months)")
        
        # Recent performance (REALISTIC timeframes)
        print(f"\n📊 RECENT PERFORMANCE (90 days):\n")
        
        daily_return = portfolio_returns.iloc[-1] if not portfolio_returns.empty else 0
        print(f"   Last Day Return: {daily_return:.2%}")
        
        week_return = portfolio_returns.tail(5).sum() if len(portfolio_returns) >= 5 else 0
        print(f"   Last Week Return: {week_return:.2%}")
        
        month_return = portfolio_returns.tail(21).sum() if len(portfolio_returns) >= 21 else 0
        print(f"   Last Month Return: {month_return:.2%}")
        
        period_return = portfolio_returns.sum()
        print(f"   90-Day Return: {period_return:.2%}")
        
        # Win rate
        winning_days = (portfolio_returns > 0).sum()
        total_days = len(portfolio_returns)
        win_rate = winning_days / total_days if total_days > 0 else 0
        print(f"\n   Win Rate: {win_rate:.1%}")
        print(f"   📌 Realistic range: 50-55% for good strategy")
        
        # Asset allocation
        print(f"\n🎯 CURRENT ALLOCATION (Equal Weight):\n")
        for ticker, weight in weights.items():
            print(f"   {ticker:6s}: {weight:5.1%}")
        
        # Reality check
        print("\n" + "="*80)
        print("⚠️  REALITY CHECK:")
        print("="*80)
        print("• Sharpe > 2.0 is VERY RARE (be suspicious)")
        print("• Returns > 20% annually are EXCEPTIONAL (not sustainable)")
        print("• Drawdowns < -5% over 3 months are UNREALISTIC (too smooth)")
        print("• Win rate > 60% is VERY DIFFICULT to achieve consistently")
        print("="*80)
        
        print("\n" + "="*80)
        print("✅ REPORT COMPLETE (Realistic Expectations)")
        print("="*80 + "\n")
    
    except Exception as e:
        print(f"\n❌ ERROR generating report: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Generate and display performance report."""
    generate_performance_report()


if __name__ == '__main__':
    main()
