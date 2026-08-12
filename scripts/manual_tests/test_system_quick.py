#!/usr/bin/env python3
"""
Quick test du système pour vérifier toutes les connexions sans exécuter de trades.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

sys.path.insert(0, '/workspaces/finbot/src')
sys.path.insert(0, '/workspaces/finbot')

print("=" * 70)
print("FINBOT MODULES & API KEYS TEST")
print("=" * 70)
print()

# Test 1: API Keys
print("📋 CHECKING API KEYS...")
print("-" * 70)

api_keys = {
    'Alpaca Trading': ['APCA_API_KEY_ID', 'APCA_API_SECRET_KEY'],
    'Financial Modeling Prep': ['FINANCIAL_MODELING_PREP_API_KEY'],
    'Alpha Vantage': ['ALPHA_VANTAGE_API_KEY'],
    'News API': ['NEWS_API_KEY'],
    'Interactive Brokers': ['IB_ACCOUNT'],
    'Twitter': ['TWITTER_API_KEY'],
    'Reddit': ['REDDIT_CLIENT_ID'],
}

for service, keys in api_keys.items():
    all_present = all(os.getenv(key) for key in keys)
    status = "✅" if all_present else "❌"
    print(f"{status} {service:30s} - {keys[0]}")

print()

# Test 2: Module Imports
print("📦 CHECKING MODULE IMPORTS...")
print("-" * 70)

modules_to_test = [
    ('AlpacaAdapter', 'from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter'),
    ('MarketDataFetcher', 'from financial_analyzer.data.market_data import MarketDataFetcher'),
    ('TechnicalFeatureEngine', 'from financial_analyzer.features.technical import TechnicalFeatureEngine'),
    ('PyPortfolioOptOptimizer', 'from financial_analyzer.portfolio.pyportfolioopt_optimizer import PyPortfolioOptOptimizer'),
    ('RiskfolioOptimizer', 'from financial_analyzer.portfolio.riskfolio_optimizer import RiskfolioOptimizer'),
    ('StressTester', 'from financial_analyzer.risk.stress_test import StressTester'),
    ('VaR Backtest', 'from financial_analyzer.risk.var_backtest import backtest_multi_methods'),
    ('SentimentAnalyzer', 'from financial_analyzer.ml.sentiment_pipeline import SentimentAnalyzer'),
    ('FinBERTEngine', 'from financial_analyzer.sentiment.finbert_engine import FinBERTEngine'),
    ('AccountMonitor', 'from financial_analyzer.trading.account_monitor import AccountMonitor'),
    ('RiskGuard', 'from financial_analyzer.trading.risk_guard import RiskGuard'),
    ('LiveTradingPipeline', 'from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline'),
]

import_results = {}
for name, import_statement in modules_to_test:
    try:
        exec(import_statement)
        print(f"✅ {name:30s} - Available")
        import_results[name] = True
    except Exception as e:
        print(f"❌ {name:30s} - {str(e)[:40]}")
        import_results[name] = False

print()

# Test 3: Alpaca Connection (si disponible)
print("🔌 TESTING ALPACA CONNECTION...")
print("-" * 70)

if import_results.get('AlpacaAdapter'):
    try:
        from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
        
        api_key = os.getenv('APCA_API_KEY_ID')
        api_secret = os.getenv('APCA_API_SECRET_KEY')
        
        if api_key and api_secret:
            alpaca = AlpacaAdapter.from_env(mode='paper')
            alpaca.connect()
            account = alpaca.get_account()
            
            print(f"✅ Connection successful!")
            print(f"   Account ID: {account.get('account_id', 'N/A')}")
            print(f"   Cash: ${float(account.get('cash', 0)):,.2f}")
            print(f"   Portfolio Value: ${float(account.get('portfolio_value', 0)):,.2f}")
            print(f"   Status: {account.get('status', 'unknown')}")
            
            alpaca.disconnect()
        else:
            print("❌ Alpaca keys not found")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
else:
    print("❌ AlpacaAdapter not available")

print()

# Test 4: Data Fetch Test (petit échantillon)
print("📊 TESTING DATA FETCH...")
print("-" * 70)

if import_results.get('MarketDataFetcher'):
    try:
        from financial_analyzer.data.market_data import MarketDataFetcher
        from datetime import datetime, timedelta
        
        fetcher = MarketDataFetcher()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Test avec un ticker simple
        df = fetcher.get_historical_data(
            'AAPL',
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        print(f"✅ Data fetch successful!")
        print(f"   Ticker: AAPL")
        print(f"   Days fetched: {len(df)}")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
else:
    print("❌ MarketDataFetcher not available")

print()

# Summary
print("=" * 70)
print("SUMMARY")
print("=" * 70)

total_modules = len(modules_to_test)
working_modules = sum(import_results.values())
percentage = (working_modules / total_modules) * 100

print(f"Modules Working: {working_modules}/{total_modules} ({percentage:.0f}%)")

alpaca_key_present = bool(os.getenv('APCA_API_KEY_ID') and os.getenv('APCA_API_SECRET_KEY'))
fmp_key_present = bool(os.getenv('FINANCIAL_MODELING_PREP_API_KEY'))
av_key_present = bool(os.getenv('ALPHA_VANTAGE_API_KEY'))
news_key_present = bool(os.getenv('NEWS_API_KEY'))

api_key_count = sum([alpaca_key_present, fmp_key_present, av_key_present, news_key_present])
print(f"API Keys Present: {api_key_count}/4 essential")

print()

if alpaca_key_present and import_results.get('AlpacaAdapter'):
    print("✅ SYSTEM READY - Continuous trading can be started")
    print("   Run: python run_continuous_alpaca_trading.py")
else:
    print("❌ SYSTEM NOT READY - Fix issues above")

print("=" * 70)
