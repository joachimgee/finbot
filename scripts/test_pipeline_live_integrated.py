#!/usr/bin/env python3
"""
Test complet pipeline live avec PyPortfolioOpt/Riskfolio intégrés.

Usage:
    export APCA_API_KEY_ID=...; export APCA_API_SECRET_KEY=...
    python scripts/test_pipeline_live_integrated.py
"""

import os
import sys

if not os.environ.get('APCA_API_KEY_ID') or not os.environ.get('APCA_API_SECRET_KEY'):
    print("ERREUR: Clés Alpaca manquantes.")
    sys.exit(1)

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline

print("\n" + "="*80)
print("TEST PIPELINE LIVE COMPLÈTE (PyPortfolioOpt + Riskfolio intégrés)")
print("="*80 + "\n")

adapter = AlpacaAdapter.from_env(mode='paper')
adapter.connect()

try:
    print("[1/3] Création pipeline (5 tickers)...")
    pipeline = LiveTradingPipeline(
        broker_adapter=adapter,
        tickers=['AAPL','MSFT','NVDA','GOOGL','AMZN'],
        initial_capital=100000.0,
        strategy='integrated_pfo_riskfolio'
    )
    print("✓ Pipeline créée\n")

    print("[2/3] Exécution forcée (fetch data + optimize + orders)...")
    result = pipeline.run(force=True)
    print("✓ Exécution terminée\n")

    print("[3/3] Résultats:")
    print(f"  Status: {result['status']}")
    print(f"  Portfolio value: ${result['portfolio_value']:,.2f}")
    print(f"  Daily P&L: ${result['daily_pnl']:+,.2f}")
    print(f"  Positions: {result['num_positions']}")
    print(f"  Orders generated: {result.get('orders_generated', 0)}")
    print(f"  Orders executed: {result.get('orders_executed', 0)}")
    print(f"  Orders rejected: {result.get('orders_rejected', 0)}")
    print(f"  Circuit breaker: {result.get('circuit_breaker_active', False)}")

    if 'reason' in result and result['reason']:
        print(f"  Reason: {result['reason']}")

    print("\n" + "="*80)
    if result['status'] == 'success':
        print("✓ TEST RÉUSSI: Pipeline live fonctionne avec optimisation intégrée")
    else:
        print(f"⚠ STATUT: {result['status']}")
    print("="*80 + "\n")

finally:
    adapter.disconnect()
