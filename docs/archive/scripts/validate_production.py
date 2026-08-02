"""
Validate PRODUCTION setup with REAL data (no mocks).
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load production env
load_dotenv('.env.production')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.universe.market_selector import MarketSelector
from financial_analyzer.sentiment.financial_sentiment_analyzer import FinancialSentimentAnalyzer


def validate_broker_connection():
    """Test REAL data connection."""
    print("\n🔍 Testing REAL market data connection...")
    
    try:
        fetcher = MarketDataFetcher()
        
        # Try to fetch real data
        end = datetime.now()
        start = end - timedelta(days=5)
        
        df = fetcher.get_historical_data(
            tickers=['AAPL'],
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d')
        )
        
        # MarketDataFetcher returns dict of DataFrames
        if isinstance(df, dict):
            df = df.get('AAPL') if 'AAPL' in df else None
        
        if df is not None and not df.empty:
            print("✅ Market data connection working (REAL)")
            print(f"   Fetched {len(df)} data points")
            print(f"   Latest close: ${df['Close'].iloc[-1]:.2f}" if 'Close' in df.columns else "")
            return True
        else:
            print("❌ No data returned")
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def validate_market_data():
    """Test REAL market data fetching."""
    print("\n🔍 Fetching REAL market data for multiple tickers...")
    
    try:
        fetcher = MarketDataFetcher()
        
        # Fetch REAL data for multiple tickers
        end = datetime.now()
        start = end - timedelta(days=30)
        
        tickers = ['AAPL', 'MSFT', 'GOOGL']
        df = fetcher.get_historical_data(
            tickers=tickers,
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d')
        )
        
        # MarketDataFetcher returns dict of DataFrames
        if not isinstance(df, dict):
            print("❌ Unexpected data format")
            return False
        
        if df and len(df) > 0:
            print(f"✅ Fetched REAL data for {len(df)} tickers")
            
            # Show sample data
            for ticker in tickers:
                if ticker in df and not df[ticker].empty and 'Close' in df[ticker].columns:
                    print(f"   {ticker}: ${df[ticker]['Close'].iloc[-1]:.2f} ({len(df[ticker])} points)")
            
            return True
        else:
            print("❌ Failed to fetch market data")
            return False
            
    except Exception as e:
        print(f"❌ Market data fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_universe_selection():
    """Validate universe selection with REALISTIC diversification."""
    print("\n3️⃣  VALIDATING UNIVERSE SELECTION...")
    
    try:
        from financial_analyzer.universe.market_selector import MarketSelector
        
        selector = MarketSelector()
        
        # Real production parameters (NO market cap restriction for diversification)
        tickers = selector.select_by_fundamental_criteria(
            n_assets=20,  # More tickers for better diversification
            sectors=['Technology', 'Healthcare']
        )
        
        print(f"   ✅ Retrieved {len(tickers)} tickers (target: 20)")
        print(f"   📌 NO market cap filter = includes mid/small caps")
        if tickers:
            print(f"   📊 Sample tickers: {', '.join(list(tickers)[:10])}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Universe validation error: {e}")
        return False


def validate_sentiment_analysis():
    """Test REAL sentiment analysis."""
    print("\n🔍 Analyzing REAL sentiment...")
    
    try:
        analyzer = FinancialSentimentAnalyzer()
        
        # Analyze REAL news headline
        text = "Apple reports record earnings, stock surges on strong iPhone sales"
        
        result = analyzer.analyze_single(text)
        
        print(f"✅ REAL sentiment analysis:")
        print(f"   Score: {result['sentiment_score']:.3f}")
        print(f"   Label: {result['label']}")
        print(f"   Positive: {result.get('positive', 'N/A'):.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Sentiment analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all production validations."""
    print("\n" + "="*80)
    print("FINBOT PRODUCTION VALIDATION - REAL DATA ONLY")
    print("="*80)
    
    results = {
        'data_connection': validate_broker_connection(),
        'market_data': validate_market_data(),
        'universe': validate_universe_selection(),
        'sentiment': validate_sentiment_analysis()
    }
    
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)
    
    all_pass = True
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check:20s}: {status}")
        if not passed:
            all_pass = False
    
    print("\n" + "="*80)
    
    if all_pass:
        print("✅ ALL CHECKS PASSED - READY FOR PRODUCTION")
    else:
        print("❌ SOME CHECKS FAILED - FIX BEFORE PRODUCTION")
    
    print("="*80 + "\n")
    
    return all_pass


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
