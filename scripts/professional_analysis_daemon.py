#!/usr/bin/env python3
"""
PROFESSIONAL ANALYSIS - DAEMON MODE
====================================

Lance professional_analysis.py en mode daemon avec planification quotidienne.
Support multi-régions global.

Usage:
    # Lancement mode daemon (quotidien à 09:35)
    python scripts/professional_analysis_daemon.py \\
        --limit 10000 \\
        --regions "United States,United Kingdom,Germany,Japan,Canada" \\
        --schedule-time "09:35"
    
    # Exécution unique
    python scripts/professional_analysis_daemon.py --once --limit 5000

Author: FinBot Professional Edition
Date: 2025-01-20
"""

import os
import sys
import argparse
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Charger .env
env_file = Path('/workspaces/finbot/.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.split('#')[0].strip()
                if key and value:
                    os.environ[key] = value

# Signal handler
should_stop = False
def signal_handler(sig, frame):
    global should_stop
    print("\n⚠️  Signal reçu, arrêt en cours...")
    should_stop = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def parse_regions(regions_arg: str) -> List[str] | None:
    """Parse l'argument --regions."""
    if regions_arg == 'global':
        return None  # Toutes régions
    elif regions_arg == 'us':
        return ['United States']
    elif regions_arg == 'eu':
        return ['United Kingdom', 'Germany', 'France', 'Switzerland', 'Netherlands', 'Sweden', 'Spain', 'Italy']
    elif regions_arg == 'asia':
        return ['Japan', 'China', 'South Korea', 'Singapore', 'Hong Kong', 'India']
    elif regions_arg == 'americas':
        return ['United States', 'Canada', 'Brazil', 'Mexico']
    else:
        # CSV custom
        return [r.strip() for r in regions_arg.split(',')]


def run_professional_analysis(
    limit: int,
    regions: List[str] | None,
    top: int = 100,
    days: int = 365,
    risk_level: str = 'medium-high',
    sectors: str = 'all',
    weighting: str = 'ic-weighted',
    output: str = None
) -> bool:
    """
    Exécute professional_analysis.py.
    
    Returns:
        True si succès, False sinon
    """
    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
    from financedatabase import Equities
    import pandas as pd
    import numpy as np
    
    # Import compute_professional_score from professional_analysis
    sys.path.insert(0, str(Path(__file__).parent))
    from professional_analysis import (
        compute_professional_score,
        build_prices_frame,
        shuffle_universe,
        RISK_PROFILES
    )
    
    # Sanitize env vars
    for key in ('APCA_API_BASE_URL', 'APCA_API_KEY_ID', 'APCA_API_SECRET_KEY'):
        if os.getenv(key):
            os.environ[key] = os.getenv(key).strip().strip('"').strip("'")
    
    risk_profile = RISK_PROFILES[risk_level]
    
    # Banner
    region_txt = ', '.join(regions) if regions else 'GLOBAL (toutes régions)'
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           PROFESSIONAL ANALYSIS - EXÉCUTION DAEMON {datetime.now().strftime('%Y-%m-%d %H:%M')}      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Configuration :
  🌍 Régions      : {region_txt}
  📊 Limite       : {limit:,} symboles
  🎯 Top positions: {top}
  📅 Période      : {days} jours
  ⚖️  Risque       : {risk_level}
  🏭 Secteurs     : {sectors}
  📐 Pondération  : {weighting}
  💾 Output       : {output or 'professional_analysis_daemon.csv'}
    """)
    
    try:
        # 1. Sélection univers global
        print(f"\n🌍 Sélection univers...")
        eq = Equities()
        symbols = []
        
        fetched_count = 0
        if regions:
            for region in regions:
                print(f"  • {region}...")
                if sectors == 'all':
                    df = eq.search(country=region)
                else:
                    df = eq.search(country=region, sector=sectors.title())

                if df is not None and not df.empty:
                    for sym in df.index:
                        if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 6:
                            symbols.append(sym)
                            fetched_count += 1
                            if fetched_count % 1000 == 0:
                                print(f"    ↳ Progress sélection: {fetched_count} symboles (limite {limit})")
                        if len(symbols) >= limit:
                            break
                if len(symbols) >= limit:
                    break
        else:
            # Global
            print("  • Toutes régions...")
            if sectors == 'all':
                df = eq.search()
            else:
                df = eq.search(sector=sectors.title())
            
            if df is not None and not df.empty:
                for idx, sym in enumerate(df.index):
                    if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 6:
                        symbols.append(sym)
                        if (idx + 1) % 2000 == 0:
                            print(f"    ↳ Progress global: {idx+1} lignes scannées, {len(symbols)} retenus")
                    if len(symbols) >= limit:
                        break
        
        if not symbols:
            print("❌ Aucun symbole trouvé")
            return False
        
        # Shuffle pour supprimer biais alphabétique (seed basée sur la date du jour)
        symbols = shuffle_universe(symbols, seed=None)
        print(f"✅ {len(symbols)} symboles sélectionnés (ordre randomisé quotidiennement)")
        
        # 2. Filtre Alpaca tradable
        print(f"\n🔍 Filtrage symboles tradables sur Alpaca...")
        adapter = AlpacaAdapter.from_env(mode='paper')
        adapter.connect()
        
        tradable = []
        for idx, sym in enumerate(symbols[:min(len(symbols), limit)]):
            try:
                asset = adapter.api.get_asset(sym)
                if asset.tradable and asset.status == 'active':
                    tradable.append(sym)
            except Exception:
                pass
            if (idx + 1) % 1000 == 0:
                print(f"  ↳ Filtrage Alpaca: {idx+1} examinés, {len(tradable)} tradables")
        
        print(f"✅ {len(tradable)} symboles tradables")
        tickers = tradable[:limit]
        
        # 3. Récupération prix
        print(f"\n📥 Récupération historique {days} jours...")
        end = datetime.now()
        start = end - timedelta(days=days)
        
        bars_dict = {}
        failed = []
        chunk_size = 50
        
        for i in range(0, len(tickers), chunk_size):
            batch = tickers[i:i + chunk_size]
            try:
                batch_bars = adapter.get_bars_multi(batch, start, end, timeframe='1Day', chunk_size=len(batch))
                bars_dict.update(batch_bars)
                print(f"  Progress: {len(bars_dict)}/{len(tickers)} ({len(failed)} failed)")
            except Exception as e:
                print(f"  Batch {i}-{i+len(batch)} failed: {e}")
                for sym in batch:
                    try:
                        sym_bars = adapter.get_bars(sym, start, end, timeframe='1Day')
                        if not sym_bars.empty:
                            bars_dict[sym] = sym_bars
                    except:
                        failed.append(sym)
        
        print(f"✅ {len(bars_dict)} symboles avec données prix")
        
        # 4. Build prices DataFrame
        prices = build_prices_frame(bars_dict)
        if prices.empty:
            print("❌ Aucun prix récupéré")
            adapter.disconnect()
            return False
        
        print(f"✅ DataFrame prix: {prices.shape[0]} jours × {prices.shape[1]} symboles")
        
        # 5. Calcul scores professionnels (300+ facteurs)
        print(f"\n🧠 Calcul scores professionnels (~300+ facteurs par symbole)...")
        signals = []
        
        for idx, symbol in enumerate(prices.columns):
            if idx % 50 == 0 and idx > 0:
                print(f"  Progress: {idx}/{len(prices.columns)}")
            
            signal_data = compute_professional_score(
                symbol=symbol,
                bars=bars_dict.get(symbol, pd.DataFrame()),
                weighting_method=weighting
            )
            signals.append(signal_data)
        
        signals_df = pd.DataFrame(signals)
        print(f"✅ Scores calculés pour {len(signals_df)} symboles")
        print(f"   Facteurs moyens/symbole: {signals_df['num_factors_computed'].mean():.0f}")
        print(f"   Confiance moyenne: {signals_df['confidence'].mean():.2f}")
        
        # 6. Sélection top
        top_syms = signals_df.nlargest(top, 'composite_score')['symbol'].tolist()
        print(f"\n🎯 Top {len(top_syms)} sélectionnés")
        
        # 7. Export results
        output_file = output or f'professional_analysis_daemon_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        signals_df.to_csv(output_file, index=False)
        print(f"💾 Résultats exportés: {output_file}")
        
        # 8. Apply to Alpaca Paper Trading (simplified for daemon)
        print(f"\n📤 Application au compte Alpaca Paper Trading...")
        
        # Simple equal weight portfolio for daemon mode
        # (can be enhanced with optimization later)
        weight_per_position = 1.0 / len(top_syms)
        
        account = adapter.get_account()
        equity = account['equity']
        cash_per_position = equity * weight_per_position
        
        print(f"  Portfolio equity: ${equity:,.2f}")
        print(f"  Cash per position: ${cash_per_position:,.2f}")
        
        orders_submitted = 0
        orders_failed = 0
        
        for symbol in top_syms:
            try:
                # Get current price
                last_bars = adapter.get_bars(symbol, datetime.now() - timedelta(days=5), datetime.now(), timeframe='1Day')
                if last_bars.empty:
                    continue
                
                price = last_bars['close'].iloc[-1]
                qty = int(cash_per_position / price)
                
                if qty > 0:
                    # Check position exists
                    try:
                        pos = adapter.api.get_position(symbol)
                        current_qty = int(pos.qty)
                    except:
                        current_qty = 0
                    
                    delta = qty - current_qty
                    
                    if abs(delta) > 0:
                        if delta > 0:
                            # Buy
                            order = adapter.submit_order(symbol, abs(delta), 'buy', order_type='market')
                            if order:
                                orders_submitted += 1
                                print(f"  ✅ BUY {symbol}: {abs(delta)} shares @ ${price:.2f}")
                        else:
                            # Sell
                            order = adapter.submit_order(symbol, abs(delta), 'sell', order_type='market')
                            if order:
                                orders_submitted += 1
                                print(f"  ✅ SELL {symbol}: {abs(delta)} shares @ ${price:.2f}")
            except Exception as e:
                orders_failed += 1
                print(f"  ❌ {symbol}: {e}")
        
        print(f"\n✅ Ordres soumis: {orders_submitted}, Échecs: {orders_failed}")
        
        adapter.disconnect()
        return True
    
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Professional Analysis - Daemon Mode (Multi-Regions)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--limit', type=int, default=5000,
                        help='Nombre max de symboles (défaut: 5000)')
    parser.add_argument('--top', type=int, default=100,
                        help='Top N positions (défaut: 100)')
    parser.add_argument('--days', type=int, default=365,
                        help='Historique en jours (défaut: 365)')
    parser.add_argument('--risk-level', type=str, default='medium-high',
                        choices=['low', 'medium', 'medium-high', 'high'],
                        help='Niveau de risque')
    parser.add_argument('--sectors', type=str, default='all',
                        help='Secteurs (all, Technology, etc.)')
    parser.add_argument('--weighting', type=str, default='ic-weighted',
                        choices=['equal', 'ic-weighted', 'bayesian'],
                        help='Méthode de pondération')
    parser.add_argument('--output', type=str, default=None,
                        help='Fichier de sortie CSV')
    parser.add_argument('--regions', type=str, default='global',
                        help='Régions: "global", "us", "eu", "asia", "americas", ou CSV')
    parser.add_argument('--schedule-time', type=str, default='09:35',
                        help='Heure exécution quotidienne (HH:MM)')
    parser.add_argument('--once', action='store_true',
                        help='Exécution unique (pas de daemon)')
    
    args = parser.parse_args()
    
    # Parse regions
    regions = parse_regions(args.regions)
    
    if args.once:
        # Single run
        print("🚀 MODE EXÉCUTION UNIQUE")
        success = run_professional_analysis(
            limit=args.limit,
            regions=regions,
            top=args.top,
            days=args.days,
            risk_level=args.risk_level,
            sectors=args.sectors,
            weighting=args.weighting,
            output=args.output
        )
        sys.exit(0 if success else 1)
    else:
        # Daemon mode
        region_txt = args.regions
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              🤖 MODE DAEMON - Analyse Professionnelle Quotidienne           ║
╚══════════════════════════════════════════════════════════════════════════════╝

⏰ Planification : Tous les jours à {args.schedule_time}
🌍 Régions      : {region_txt}
📊 Limite       : {args.limit:,} symboles
🎯 Top positions: {args.top}
⚖️  Risque       : {args.risk_level}
💾 Output       : {args.output or 'auto-generated'}

Appuyez Ctrl+C pour arrêter proprement.
        """)
        
        while not should_stop:
            now = datetime.now()
            target_hour, target_min = map(int, args.schedule_time.split(':'))
            
            # Calculer prochaine exécution
            next_run = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now).total_seconds()
            print(f"\n⏳ Prochaine exécution: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (dans {wait_seconds/3600:.1f}h)")
            
            # Sleep avec checks périodiques
            slept = 0
            while slept < wait_seconds and not should_stop:
                time.sleep(min(60, wait_seconds - slept))
                slept += 60
            
            if should_stop:
                break
            
            # Exécution
            print(f"\n" + "="*80)
            print(f"🚀 EXÉCUTION PLANIFIÉE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
            
            try:
                run_professional_analysis(
                    limit=args.limit,
                    regions=regions,
                    top=args.top,
                    days=args.days,
                    risk_level=args.risk_level,
                    sectors=args.sectors,
                    weighting=args.weighting,
                    output=args.output
                )
            except Exception as e:
                print(f"\n❌ ERREUR durant exécution: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n✅ Daemon arrêté proprement.")


if __name__ == '__main__':
    main()
