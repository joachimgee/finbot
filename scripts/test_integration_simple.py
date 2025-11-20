#!/usr/bin/env python3
"""
Test Simple Integration - Modules Disponibles
==============================================

Teste uniquement les modules disponibles avec les bonnes APIs.

Author: FinBot
Date: 2025-11-17
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def test_technical_features():
    """Test TechnicalFeatureEngine."""
    print("\n[1/5] Test TechnicalFeatureEngine...")
    try:
        from financial_analyzer.features.technical import TechnicalFeatureEngine
        
        # Create sample OHLCV data (use uppercase column names)
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        ohlcv = pd.DataFrame({
            'Open': np.random.randn(100).cumsum() + 100,
            'High': np.random.randn(100).cumsum() + 102,
            'Low': np.random.randn(100).cumsum() + 98,
            'Close': np.random.randn(100).cumsum() + 100,
            'Volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        engine = TechnicalFeatureEngine(ohlcv)
        features = engine.compute_all_features()
        
        print(f"  ✓ {len(features.columns)} features computed")
        print(f"    Sample: {list(features.columns)[:5]}")
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
        
        # Try get_all_news (without max_results, use default limit)
        news_df = scraper.get_all_news("AAPL")
        
        print(f"  ✓ {len(news_df)} articles récupérés")
        if not news_df.empty:
            print(f"    Exemple: {news_df.iloc[0]['title'][:60]}...")
        return True
    except Exception as e:
        print(f"  ⚠️  Erreur: {e}")
        print(f"    (Nécessite NEWS_API_KEY ou connexion internet)")
        return False


def test_finbert():
    """Test FinBERTEngine."""
    print("\n[3/5] Test FinBERTEngine...")
    try:
        from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
        
        engine = FinBERTEngine()
        
        texts = [
            "Apple reported strong quarterly earnings beating expectations",
            "Stock market crashes amid recession fears",
        ]
        
        # Use get_sentiment (not analyze_text)
        results = [engine.get_sentiment(t) for t in texts]
        
        print(f"  ✓ {len(results)} textes analysés:")
        for i, (text, result) in enumerate(zip(texts, results)):
            label = result['label']
            score = result['score']
            print(f"    [{label:8s}] {score:+.2f}: {text[:50]}...")
        return True
    except Exception as e:
        print(f"  ⚠️  Non disponible: {e}")
        print(f"    (Nécessite transformers + model download ~400MB)")
        return False


def test_ml_predictor():
    """Test MLPredictor."""
    print("\n[4/5] Test MLPredictor...")
    try:
        from financial_analyzer.analysis.ml_predictor import MLPredictor
        
        # Create sample price data (use uppercase column names)
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        df_prices = pd.DataFrame({
            'Open': np.random.randn(100).cumsum() + 100,
            'High': np.random.randn(100).cumsum() + 102,
            'Low': np.random.randn(100).cumsum() + 98,
            'Close': np.random.randn(100).cumsum() + 100,
            'Volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        predictor = MLPredictor(target_horizon=5)
        
        # Use prepare_features (no sentiment argument)
        X, y = predictor.prepare_features(df_prices)
        
        if len(X) > 10:
            # Train
            predictor.train(X, y, model_type='random_forest')
            
            # Predict
            predictions = predictor.predict(X.tail(5))
            
            print(f"  ✓ Model trained: {X.shape[1]} features, {len(X)} samples")
            print(f"    Predictions: {predictions[:3]}")
            return True
        else:
            print(f"  ⚠️  Insufficient data")
            return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_portfolio_optimizers():
    """Test PyPortfolioOpt + Riskfolio."""
    print("\n[5/5] Test Portfolio Optimization...")
    try:
        from financial_analyzer.portfolio_optimization.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
        from financial_analyzer.portfolio_optimization.riskfolio_optimizer import RiskfolioOptimizer
        
        # Create sample price data
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
        prices = pd.DataFrame(
            np.random.randn(100, 5).cumsum(axis=0) + 100,
            index=dates,
            columns=tickers
        )
        
        # Test PyPortfolioOpt
        opt1 = PyPortfolioOptOptimizer(prices)
        weights1 = opt1.optimize_max_sharpe()
        print(f"  ✓ PyPortfolioOpt: {len(weights1)} weights")
        print(f"    {dict(list(weights1.items())[:3])}")
        
        # Test Riskfolio (uses optimize_mean_cvar method)
        opt2 = RiskfolioOptimizer(prices)
        weights2 = opt2.optimize_mean_cvar()
        print(f"  ✓ Riskfolio: {len(weights2)} weights")
        print(f"    {dict(list(weights2.items())[:3])}")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run simple integration tests."""
    print("\n" + "="*80)
    print("TEST SIMPLE INTEGRATION - MODULES DISPONIBLES")
    print("="*80)
    
    results = {
        'Technical Features': test_technical_features(),
        'News Scraper': test_news_scraper(),
        'FinBERT': test_finbert(),
        'ML Predictor': test_ml_predictor(),
        'Portfolio Optimization': test_portfolio_optimizers()
    }
    
    print("\n" + "="*80)
    print("RÉSUMÉ:")
    print("="*80)
    
    for name, result in results.items():
        status = "✓" if result else "❌"
        print(f"  {status} {name}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\nTotal: {passed}/{total} modules fonctionnels ({passed*100//total}%)")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
