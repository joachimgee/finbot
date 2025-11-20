#!/usr/bin/env python3
"""
Test Integration Offline - All Modules
=======================================

Tests l'intégration de tous les modules SANS connexion broker:
- Technical Indicators
- News Scraper
- Sentiment Analysis
- ML Models
- Portfolio Optimization

Author: FinBot
Date: 2025-11-17
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from financial_analyzer.utils.logger import get_logger

logger = get_logger(__name__)


def test_technical_indicators():
    """Test TechnicalFeatureEngine."""
    print("\n[1/5] Test TechnicalFeatureEngine...")
    try:
        from financial_analyzer.features.technical import TechnicalFeatureEngine
        
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 102,
            'low': np.random.randn(100).cumsum() + 98,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        engine = TechnicalFeatureEngine()
        features = engine.generate_features(df)
        
        indicators = [col for col in features.columns if not col.startswith('Unnamed')]
        print(f"  ✓ {len(indicators)} indicators générés:")
        print(f"    {', '.join(indicators[:10])}...")
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False


def test_news_scraper():
    """Test FinancialNewsScraper."""
    print("\n[2/5] Test FinancialNewsScraper...")
    try:
        from financial_analyzer.data.news_scraper import FinancialNewsScraper
        
        scraper = FinancialNewsScraper()
        news = scraper.get_news("AAPL", limit=3)
        
        print(f"  ✓ {len(news)} articles récupérés pour AAPL")
        if news:
            print(f"    Exemple: {news[0].get('title', 'N/A')[:60]}...")
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False


def test_sentiment_analyzer():
    """Test FinBERTEngine."""
    print("\n[3/5] Test FinBERTEngine...")
    try:
        from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
        
        analyzer = FinBERTEngine()
        
        texts = [
            "Apple reported strong quarterly earnings beating expectations",
            "Stock market crashes amid recession fears",
            "Company announces new product line"
        ]
        
        scores = [analyzer.analyze_text(t) for t in texts]
        
        print(f"  ✓ {len(scores)} textes analysés:")
        for i, (text, score) in enumerate(zip(texts, scores)):
            sentiment = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
            print(f"    [{sentiment:8s}] {score:+.2f}: {text[:50]}...")
        return True
    except Exception as e:
        print(f"  ⚠️  Non disponible: {e}")
        print(f"    (FinBERT nécessite transformers + model download)")
        return False


def test_ml_models():
    """Test MLPredictor."""
    print("\n[4/5] Test MLPredictor...")
    try:
        from financial_analyzer.analysis.ml_predictor import MLPredictor, MLPredictorConfig
        
        # Create sample price data
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        df_prices = pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 102,
            'low': np.random.randn(100).cumsum() + 98,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        predictor = MLPredictor(target_horizon=5)
        
        # Prepare features (no sentiment for simplicity)
        X, y = predictor.prepare_features(df_prices, daily_sentiment=None)
        
        if len(X) > 10:
            # Train
            predictor.train(X, y, model_type='random_forest')
            
            # Predict
            predictions = predictor.predict(X.tail(5))
            
            print(f"  ✓ Model trained and predictions generated")
            print(f"    Features: {X.shape[1]}, Samples: {len(X)}")
            print(f"    Sample predictions: {predictions[:3]}")
            return True
        else:
            print(f"  ⚠️  Insufficient data for training")
            return False
    except Exception as e:
        print(f"  ⚠️  Erreur: {e}")
        return False


def test_portfolio_optimization():
    """Test PyPortfolioOpt + Riskfolio."""
    print("\n[5/5] Test Portfolio Optimization...")
    try:
        from financial_analyzer.portfolio_optimization.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
        from financial_analyzer.portfolio_optimization.riskfolio_optimizer import RiskfolioOptimizer
        
        # Create sample price data (not returns!)
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
        prices = pd.DataFrame(
            np.random.randn(100, 5).cumsum(axis=0) + 100,
            index=dates,
            columns=tickers
        )
        
        # Test PyPortfolioOpt
        optimizer1 = PyPortfolioOptOptimizer(prices)
        weights1 = optimizer1.optimize_max_sharpe()
        print(f"  ✓ PyPortfolioOpt: {len(weights1)} weights")
        print(f"    {dict(list(weights1.items())[:3])}")
        
        # Test Riskfolio
        optimizer2 = RiskfolioOptimizer(prices)
        weights2 = optimizer2.optimize(method='mean_cvar')
        print(f"  ✓ Riskfolio: {len(weights2)} weights")
        print(f"    {dict(list(weights2.items())[:3])}")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all offline integration tests."""
    print("\n" + "="*80)
    print("TEST INTEGRATION OFFLINE - ALL MODULES")
    print("="*80)
    
    results = {
        'Technical Indicators': test_technical_indicators(),
        'News Scraper': test_news_scraper(),
        'Sentiment Analyzer': test_sentiment_analyzer(),
        'ML Predictor': test_ml_models(),
        'Portfolio Optimization': test_portfolio_optimization()
    }
    
    print("\n" + "="*80)
    print("RÉSUMÉ:")
    print("="*80)
    total = len(results)
    passed = sum(results.values())
    
    for name, result in results.items():
        status = "✓" if result else "❌"
        print(f"  {status} {name}")
    
    print(f"\nTotal: {passed}/{total} modules fonctionnels")
    
    if passed == total:
        print("\n✓ TOUS LES MODULES SONT INTÉGRÉS ET FONCTIONNELS")
    else:
        print(f"\n⚠️  {total - passed} module(s) nécessitent configuration additionnelle")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
