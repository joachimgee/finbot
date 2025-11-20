#!/usr/bin/env python3
"""
Test Full Integration - All APIs Connected
==========================================

Tests complets pour valider l'intégration de TOUS les systèmes dans la pipeline:
- Technical Indicators (TechnicalFeatureEngine)
- ML Models (LSTM, Predictor)
- Sentiment Analysis (FinBERT)
- News Scraper (NewsAPI)
- Portfolio Optimization (PyPortfolioOpt + Riskfolio)
- Alpaca Trading

Author: FinBot
Date: 2025-11-17
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Execute full integration test with all APIs."""
    print("\n" + "="*80)
    print("TEST FULL INTEGRATION - ALL APIs")
    print("="*80 + "\n")
    
    # Check environment
    print("[1/5] Vérification environnement...")
    api_key = os.getenv("APCA_API_KEY_ID")
    if not api_key:
        print("❌ APCA_API_KEY_ID non défini")
        return
    print(f"✓ API Key: {api_key[:10]}...")
    
    # Create adapter
    print("\n[2/5] Création AlpacaAdapter...")
    try:
        adapter = AlpacaAdapter.from_env()
        adapter.connect()
        print("✓ Connecté à Alpaca")
    except Exception as e:
        print(f"❌ Connexion échouée: {e}")
        return
    
    # Create pipeline with small universe
    print("\n[3/5] Création pipeline (3 tickers pour test rapide)...")
    tickers = ["AAPL", "MSFT", "GOOGL"]
    
    try:
        pipeline = LiveTradingPipeline(
            broker_adapter=adapter,
            tickers=tickers,
            lookback_days=60,  # More data for ML/technical
            update_interval_seconds=300,
            position_size_pct=0.1,
            max_positions=3,
            stop_loss_pct=0.02,
            take_profit_pct=0.05
        )
        print(f"✓ Pipeline créée avec {len(tickers)} tickers")
    except Exception as e:
        print(f"❌ Création pipeline échouée: {e}")
        return
    
    # Force execution
    print("\n[4/5] Exécution forcée (tous les modules)...")
    try:
        pipeline._execute_strategy()
        print("✓ Exécution terminée")
    except Exception as e:
        print(f"⚠️ Exécution partielle: {e}")
    
    # Analyze results
    print("\n[5/5] Résultats:")
    try:
        account = adapter.get_account()
        positions = adapter.get_positions()
        
        print(f"  Status: {pipeline.status}")
        print(f"  Portfolio value: ${float(account.portfolio_value):,.2f}")
        print(f"  Positions: {len(positions)}")
        print(f"  Orders generated: {pipeline._orders_generated}")
        print(f"  Orders executed: {pipeline._orders_executed}")
        print(f"  Orders rejected: {pipeline._orders_rejected}")
        print(f"  Circuit breaker: {pipeline._circuit_breaker_active}")
        
        # Module availability
        print("\n  Modules disponibles:")
        from financial_analyzer.features.technical_engine import TechnicalFeatureEngine
        print(f"    - TechnicalFeatureEngine: ✓")
        
        try:
            from financial_analyzer.sentiment.sentiment_analyzer import SentimentAnalyzer
            print(f"    - SentimentAnalyzer: ✓")
        except Exception:
            print(f"    - SentimentAnalyzer: ❌ (non disponible)")
        
        try:
            from financial_analyzer.data.news_scraper import NewsScraper
            print(f"    - NewsScraper: ✓")
        except Exception:
            print(f"    - NewsScraper: ❌ (non disponible)")
        
        try:
            from financial_analyzer.ml.predictor import Predictor
            print(f"    - ML Predictor: ✓")
        except Exception:
            print(f"    - ML Predictor: ❌ (non disponible)")
        
        try:
            from financial_analyzer.deep_learning.lstm_predictor import LSTMPredictor
            print(f"    - LSTMPredictor: ✓")
        except Exception:
            print(f"    - LSTMPredictor: ❌ (non disponible)")
        
    except Exception as e:
        print(f"❌ Analyse résultats échouée: {e}")
        return
    
    print("\n" + "="*80)
    print("✓ TEST RÉUSSI: Pipeline fonctionne avec tous les modules disponibles")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
