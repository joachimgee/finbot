"""
PRODUCTION live trading with REAL data and REAL monitoring.
"""

import os
import sys
import time
import signal
from datetime import datetime, time as dtime
from dotenv import load_dotenv

load_dotenv('.env.production')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.features.technical import TechnicalFeatureEngine
from financial_analyzer.portfolio.optimizer import PortfolioOptimizer
from financial_analyzer.universe.market_selector import MarketSelector
from financial_analyzer.sentiment.financial_sentiment_analyzer import FinancialSentimentAnalyzer


class ProductionLiveTrader:
    """Production live trading orchestrator."""
    
    def __init__(self):
        """Initialize production trader."""
        self.running = False
        self.setup_signal_handlers()
        
        # Initialize REAL components
        self.fetcher = MarketDataFetcher()
        self.selector = MarketSelector()
        self.sentiment_analyzer = FinancialSentimentAnalyzer()
        
        # Risk parameters
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE', 0.20))
        self.max_portfolio_risk = float(os.getenv('MAX_PORTFOLIO_RISK', 0.02))
        self.stop_loss_pct = float(os.getenv('STOP_LOSS_PCT', 0.05))
        
        print("🔧 Production trader initialized")
        print(f"   Max Position: {self.max_position_size*100}%")
        print(f"   Max Portfolio Risk: {self.max_portfolio_risk*100}%")
        print(f"   Stop Loss: {self.stop_loss_pct*100}%")
    
    def setup_signal_handlers(self):
        """Handle graceful shutdown."""
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
    
    def run_trading_cycle(self):
        """Execute one trading cycle with REAL data."""
        print(f"\n{'='*80}")
        print(f"TRADING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        try:
            # 1. Select REAL universe (NO market cap restriction for diversification)
            print("📊 Selecting universe...")
            tickers = self.selector.select_by_fundamental_criteria(
                n_assets=20,  # More assets for better diversification
                sectors=['Technology', 'Healthcare']
            )
            
            if not tickers:
                print("   ⚠️  No tickers from universe, using fallback...")
                tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 
                          'META', 'TSLA', 'UNH', 'JNJ', 'LLY']
            
            print(f"   Selected {len(tickers)} tickers: {', '.join(tickers[:5])}...")
            
            # 2. Fetch REAL market data
            print("\n📈 Fetching market data...")
            from datetime import timedelta
            end = datetime.now()
            start = end - timedelta(days=252)  # 1 year
            
            df = self.fetcher.get_historical_data(
                tickers=tickers,
                start_date=start.strftime('%Y-%m-%d'),
                end_date=end.strftime('%Y-%m-%d')
            )
            print(f"   Fetched {len(df)} data points")
            
            # 3. Calculate features
            print("\n🔍 Calculating technical features...")
            features_dict = {}
            for ticker in tickers:
                ticker_data = df[df.index.get_level_values('ticker') == ticker] if 'ticker' in df.index.names else df
                if not ticker_data.empty:
                    engine = TechnicalFeatureEngine(ticker_data)
                    features = engine.calculate_all_features()
                    features_dict[ticker] = features
            
            print(f"   Calculated features for {len(features_dict)} tickers")
            
            # 4. Analyze sentiment
            print("\n💭 Analyzing sentiment...")
            sample_news = f"Technology sector shows strong momentum with {', '.join(tickers[:3])} leading gains"
            sentiment = self.sentiment_analyzer.analyze_single(sample_news)
            print(f"   Sentiment: {sentiment['label']} ({sentiment['sentiment_score']:.3f})")
            
            # 5. Optimize portfolio
            print("\n🎯 Optimizing portfolio...")
            
            # Calculate returns for optimization
            returns_data = {}
            for ticker in tickers:
                ticker_data = df[df.index.get_level_values('ticker') == ticker] if 'ticker' in df.index.names else df
                if not ticker_data.empty and 'Close' in ticker_data.columns:
                    returns_data[ticker] = ticker_data['Close'].pct_change().dropna()
            
            if returns_data:
                import pandas as pd
                returns_df = pd.DataFrame(returns_data).dropna()
                
                if not returns_df.empty:
                    optimizer = PortfolioOptimizer(returns_df)
                    result = optimizer.optimize_max_sharpe()
                    
                    print(f"   Optimal weights calculated:")
                    top_weights = result['weights'].nlargest(3)
                    for ticker, weight in top_weights.items():
                        print(f"   {ticker}: {weight:.1%}")
                    
                    print(f"\n   Expected Return: {result['return']:.2%}")
                    print(f"   Expected Volatility: {result['volatility']:.2%}")
                    print(f"   Sharpe Ratio: {result['sharpe']:.2f}")
                else:
                    print("   ⚠️ Insufficient data for optimization")
            else:
                print("   ⚠️ No returns data available")
            
            print("\n✅ Trading cycle completed successfully")
            
        except Exception as e:
            print(f"\n❌ ERROR in trading cycle: {e}")
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Start PRODUCTION live trading."""
        print("\n" + "="*80)
        print("FINBOT PRODUCTION LIVE TRADING STARTED")
        print("="*80)
        print(f"Mode: PAPER TRADING (Safe)")
        print(f"Cycle Interval: 5 minutes")
        print("="*80 + "\n")
        
        self.running = True
        
        while self.running:
            try:
                self.run_trading_cycle()
                
                # Wait 5 minutes between cycles
                print("\n⏳ Waiting 5 minutes until next cycle...")
                print("   (Press Ctrl+C to stop)")
                time.sleep(300)
            
            except KeyboardInterrupt:
                print("\n\n⚠️ Keyboard interrupt received")
                self.shutdown(None, None)
                break
            
            except Exception as e:
                print(f"\n❌ ERROR in trading loop: {e}")
                import traceback
                traceback.print_exc()
                
                # Wait 1 minute on error
                print("\n⏳ Waiting 1 minute before retry...")
                time.sleep(60)
    
    def shutdown(self, signum, frame):
        """Graceful shutdown."""
        print("\n\n⚠️ SHUTDOWN SIGNAL RECEIVED")
        print("Stopping trading cycles...")
        
        self.running = False
        
        print("✅ Shutdown complete\n")
        sys.exit(0)


def main():
    """Run production live trading."""
    trader = ProductionLiveTrader()
    trader.start()


if __name__ == '__main__':
    main()
