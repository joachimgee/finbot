#!/usr/bin/env python3
"""Verify Alpaca orders and positions.

Adapté du guide `GUIDE_VERIFY_ORDERS_API_KEYS.md`.
Gère:
- Connexion (paper ou live selon ALPACA_BASE_URL)
- Récupération compte, positions, ordres récents (24h)
- Affichage tabulaire (tabulate)
- Messages d'erreur clairs

Usage:
    python scripts/verify_alpaca_orders.py

Pré-requis:
    pip install tabulate python-dotenv

Variables requises (.env):
    ALPACA_API_KEY, ALPACA_SECRET_KEY (obligatoire)
    ALPACA_BASE_URL (optionnel, défaut paper)
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta
from typing import List

try:
    from tabulate import tabulate
except ImportError:
    print("❌ 'tabulate' non installé. Exécutez: pip install tabulate")
    sys.exit(1)

# Chargement .env automatique si python-dotenv présent
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Ajouter src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter  # type: ignore

SEPARATOR = "=" * 80


def _print_section(title: str) -> None:
    print(f"\n{SEPARATOR}\n  {title}\n{SEPARATOR}\n")


def _safe_fmt_money(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "N/A"


def main() -> None:
    _print_section("ALPACA ORDERS & POSITIONS VERIFICATION")

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not secret_key:
        print("❌ ERROR: ALPACA_API_KEY ou ALPACA_SECRET_KEY non définies !")
        print("   Ajoutez-les dans votre fichier .env puis relancez.")
        sys.exit(1)

    # Initialisation adapter
    try:
        adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key, mode='paper' if 'paper' in base_url else 'live')
        print("✅ Adapter créé")
    except Exception as e:
        print(f"❌ Impossible de créer l'adapter: {e}")
        sys.exit(1)

    # Connexion (si non auto)
    try:
        if not getattr(adapter, 'connected', False):
            adapter.connect()  # type: ignore[attr-defined]
        print("✅ Connecté à Alpaca (Paper Trading)" if 'paper' in base_url else "✅ Connecté à Alpaca (Live Trading)")
    except Exception as e:
        print(f"❌ Échec connexion: {e}")
        sys.exit(1)

    # Compte
    try:
        account = adapter.get_account()
        _print_section("📊 ACCOUNT SUMMARY")
        rows = [
            ["Portfolio Value", _safe_fmt_money(account.get('portfolio_value'))],
            ["Cash", _safe_fmt_money(account.get('cash'))],
            ["Equity", _safe_fmt_money(account.get('equity'))],
            ["Buying Power", _safe_fmt_money(account.get('buying_power'))],
            ["Day Trade Count", str(account.get('daytrade_count', 0))],
        ]
        print(tabulate(rows, tablefmt="grid"))
    except Exception as e:
        print(f"❌ Impossible de récupérer le compte: {e}")

    # Positions
    try:
        positions = adapter.get_positions()
        _print_section("📈 CURRENT POSITIONS")
        if positions:
            pos_rows: List[List[str]] = []
            for pos in positions:
                pos_rows.append([
                    pos.get('symbol', 'N/A'),
                    str(pos.get('qty', '0')),
                    _safe_fmt_money(pos.get('current_price')),
                    _safe_fmt_money(pos.get('market_value')),
                    _safe_fmt_money(pos.get('unrealized_pl')),
                    f"{float(pos.get('unrealized_plpc', 0))*100:.2f}%"
                ])
            print(tabulate(pos_rows, headers=["Symbol", "Qty", "Price", "Market Val", "P&L", "P&L %"], tablefmt="grid"))
        else:
            print("⚠️  Aucune position ouverte")
    except Exception as e:
        print(f"❌ Impossible de récupérer les positions: {e}")

    # Ordres récents
    _print_section("📋 RECENT ORDERS (last 24h)")
    try:
        since = (datetime.utcnow() - timedelta(days=1)).isoformat()
        orders = []
        rest_client = getattr(adapter, 'rest_client', None)
        if rest_client:
            try:
                orders = rest_client.list_orders(status='all', limit=20, after=since)
            except Exception as e:
                print(f"⚠️  Impossible de récupérer les ordres via REST: {e}")
        else:
            print("⚠️  REST client non disponible, utilisez le dashboard Alpaca.")

        if orders:
            ord_rows = []
            for o in orders:
                try:
                    ord_rows.append([
                        getattr(o, 'symbol', 'N/A'),
                        getattr(o, 'qty', 'N/A'),
                        getattr(o, 'side', 'N/A').upper(),
                        getattr(o, 'status', 'N/A').upper(),
                        getattr(o, 'filled_qty', 0),
                        _safe_fmt_money(getattr(o, 'filled_avg_price', None)),
                        getattr(o, 'created_at', datetime.utcnow()).strftime('%H:%M:%S'),
                    ])
                except Exception:
                    continue
            print(tabulate(ord_rows, headers=["Symbol", "Qty", "Side", "Status", "Filled", "Fill Price", "Time"], tablefmt="grid"))
            total = len(orders)
            filled = sum(1 for x in orders if getattr(x, 'status', '') == 'filled')
            pending = sum(1 for x in orders if getattr(x, 'status', '') == 'pending')
            cancelled = sum(1 for x in orders if getattr(x, 'status', '') == 'cancelled')
            print(f"\n  Total: {total} | Filled: {filled} | Pending: {pending} | Cancelled: {cancelled}\n")
        else:
            print("Aucun ordre dans les dernières 24h")
    except Exception as e:
        print(f"❌ Erreur récupération ordres: {e}")

    # Résumé
    print(SEPARATOR)
    print("✅ VERIFICATION COMPLETE")
    print(SEPARATOR)
    print("\n💡 TIPS:")
    print("  • Dashboard: https://app.alpaca.markets/paper/dashboard")
    print("  • Vérifier contenu .env")
    print("  • Logs: tail -f logs/live_trading_$(date +%Y%m%d).log")
    print("  • Script debug: python scripts/debug_pipeline.py")


if __name__ == '__main__':
    main()
