#!/usr/bin/env python3
"""
Test réel Alpaca paper avec 1 ordre minimal.

Usage:
    export APCA_API_KEY_ID=...; export APCA_API_SECRET_KEY=...
    python scripts/test_real_alpaca_order.py
"""

import os
import sys
from datetime import datetime, timedelta

# Vérifier clés
if not os.environ.get('APCA_API_KEY_ID') or not os.environ.get('APCA_API_SECRET_KEY'):
    print("ERREUR: Clés Alpaca non présentes. Définir APCA_API_KEY_ID et APCA_API_SECRET_KEY.")
    sys.exit(1)

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

print("\n" + "="*80)
print("TEST RÉEL ALPACA PAPER - 1 ORDRE MINIMAL")
print("="*80 + "\n")

# 1. Connexion
print("[1/5] Connexion à Alpaca (paper)...")
adapter = AlpacaAdapter.from_env(mode='paper')
try:
    adapter.connect()
    print("✓ Connecté avec succès\n")
except Exception as e:
    print(f"✗ Échec connexion: {e}")
    sys.exit(1)

try:
    # 2. Vérifier compte
    print("[2/5] Vérification du compte...")
    account = adapter.get_account()
    print(f"  Cash: ${account['cash']:,.2f}")
    print(f"  Equity: ${account['equity']:,.2f}")
    print(f"  Buying Power: ${account['buying_power']:,.2f}\n")

    # 3. Vérifier market status
    print("[3/5] Vérification marché...")
    is_open = adapter.is_market_open()
    print(f"  Marché ouvert: {'OUI' if is_open else 'NON (extended/fermé)'}\n")

    # 4. Récupérer prix récent AAPL
    print("[4/5] Récupération prix AAPL...")
    end = datetime.now()
    start = end - timedelta(days=5)
    bars = adapter.get_bars('AAPL', start, end, timeframe='1D')
    if bars.empty:
        print("✗ Pas de données prix")
        sys.exit(1)
    latest_price = float(bars['close'].iloc[-1])
    print(f"  Prix AAPL (dernier close): ${latest_price:.2f}\n")

    # 5. Soumettre 1 ordre market BUY 1 action AAPL
    print("[5/5] Soumission ordre: BUY 1 AAPL market...")
    order = adapter.submit_order(
        symbol='AAPL',
        qty=1,
        side='buy',
        order_type='market',
        time_in_force='day'
    )
    print(f"✓ Ordre soumis avec succès!")
    print(f"  Order ID: {order['order_id']}")
    print(f"  Symbol: {order['symbol']}")
    print(f"  Qty: {order['qty']}")
    print(f"  Side: {order['side']}")
    print(f"  Type: {order['order_type']}")
    print(f"  Status: {order['status']}")
    print(f"  Submitted at: {order['submitted_at']}\n")

    # Optionnel: lister ordres récents
    print("Ordres récents (5 derniers):")
    recent = adapter.get_orders(status='all', limit=5)
    for o in recent[:5]:
        print(f"  - {o['order_id'][:8]}... {o['side']} {o['qty']} {o['symbol']} ({o['status']})")

    print("\n" + "="*80)
    print("TEST RÉUSSI: Ordre paper soumis et accepté par Alpaca")
    print("="*80 + "\n")

finally:
    adapter.disconnect()
    print("Déconnecté.\n")
