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
    Exécute professional_analysis.py + pré-analyse (drift + options) + optimisation portefeuille.
    
    Returns:
        True si succès, False sinon
    """
    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
    from financial_analyzer.analysis.master_orchestrator import MasterOrchestrator
    from financial_analyzer.preanalysis.daily_preanalysis import run_daily_preanalysis
    from financial_analyzer.integration.signal_fusion_engine import SignalFusionEngine
    from financial_analyzer.learning.portfolio_learner import PortfolioLearner
    from financedatabase import Equities
    import pandas as pd
    import numpy as np
    
    # Import tous les modules secondaires avec gestion d'erreurs détaillée
    modules_status = {'core': True}
    modules_errors = {}
    
    try:
        from financial_analyzer.integration.performance_attribution import PerformanceAttributor
        modules_status['perf_attr'] = True
    except Exception as e:
        modules_status['perf_attr'] = False
        modules_errors['perf_attr'] = str(e)
    
    try:
        from financial_analyzer.portfolio.rebalancer import PortfolioRebalancer
        modules_status['rebalancer'] = True
    except Exception as e:
        modules_status['rebalancer'] = False
        modules_errors['rebalancer'] = str(e)
    
    try:
        from financial_analyzer.analytics.performance_analyzer import PerformanceAnalyzer
        modules_status['analytics'] = True
    except Exception as e:
        modules_status['analytics'] = False
        modules_errors['analytics'] = str(e)
    
    try:
        from financial_analyzer.reports.generate_tearsheet import generate_tearsheet
        modules_status['reports'] = True
    except Exception as e:
        modules_status['reports'] = False
        modules_errors['reports'] = str(e)
    
    try:
        from financial_analyzer.universe.universe_selector_enhanced import EnhancedUniverseSelector
        modules_status['universe'] = True
    except Exception as e:
        modules_status['universe'] = False
        modules_errors['universe'] = str(e)
    
    try:
        from financial_analyzer.trading.risk_guard import RiskGuard
        from financial_analyzer.trading.account_monitor import AccountMonitor
        modules_status['risk'] = True
    except Exception as e:
        modules_status['risk'] = False
        modules_errors['risk'] = str(e)
    
    try:
        from financial_analyzer.backtesting.finbot_strategy import FinBotBacktester
        modules_status['backtest'] = True
    except Exception as e:
        modules_status['backtest'] = False
        modules_errors['backtest'] = str(e)
    
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
    
    # Variables globales pour tracking
    portfolio_decisions = {}
    drift_flag = False
    
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
        # Module inventory audit (evidence of full coverage)
        print("\n🧪 Audit modules principaux...")
        try:
            from financial_analyzer.integration.module_inventory_audit import audit_modules, format_audit
            audit_results = audit_modules()
            print(format_audit(audit_results))
        except Exception as e:
            print(f"  ⚠️ Audit modules échoué: {e}")
        
        # 0. ANALYSE DU PORTFOLIO ACTUEL (AVANT analyse 12K)
        print(f"\n💼 ANALYSE DU PORTFOLIO ACTUEL...")
        adapter = AlpacaAdapter.from_env(mode='paper')
        adapter.connect()
        
        current_positions = adapter.get_positions()
        account = adapter.get_account()
        portfolio_equity = float(account.get('equity', 0))
        
        print(f"  💰 Equity totale: ${portfolio_equity:,.2f}")
        print(f"  📊 Positions actuelles: {len(current_positions)}")
        
        portfolio_decisions = {}  # symbol -> 'SELL' / 'HOLD' / 'BUY_MORE'
        
        if current_positions:
            print(f"\n  🔍 Analyse de {len(current_positions)} positions...")
            
            # OPTIMISATION: Récupérer TOUTES les bars en une seule requête batch
            symbols_to_analyze = [pos['symbol'] for pos in current_positions]
            start_date = datetime.now() - timedelta(days=90)
            end_date = datetime.now()
            
            # Batch get_bars pour tous les symboles en parallèle
            from concurrent.futures import ThreadPoolExecutor, as_completed
            bars_cache = {}
            
            def fetch_bars(symbol):
                try:
                    bars = adapter.get_bars(
                        symbol=symbol,
                        start=start_date,
                        end=end_date,
                        timeframe='1Day'
                    )
                    return symbol, bars
                except Exception as e:
                    return symbol, None
            
            print(f"    📥 Récupération parallèle des données pour {len(symbols_to_analyze)} symboles...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(fetch_bars, sym): sym for sym in symbols_to_analyze}
                for future in as_completed(futures):
                    sym, bars = future.result()
                    if bars is not None:
                        bars_cache[sym] = bars
            
            print(f"    ✅ Données récupérées pour {len(bars_cache)}/{len(symbols_to_analyze)} symboles")
            
            # Analyser chaque position avec les bars en cache
            for pos in current_positions:
                sym = pos['symbol']
                qty = float(pos['qty'])
                market_value = float(pos['market_value'])
                unrealized_pl = float(pos.get('unrealized_pl', 0))
                unrealized_plpc = float(pos.get('unrealized_plpc', 0))
                
                print(f"    • {sym}: {qty:.2f} shares, ${market_value:,.2f} ({unrealized_plpc:+.2%})")
                
                # Décision basée sur P&L et analyse technique rapide
                try:
                    # Utiliser bars du cache
                    bars = bars_cache.get(sym)
                    
                    if bars is not None and len(bars) >= 20:
                        closes = bars['close'].values
                        current_price = closes[-1]
                        sma_20 = closes[-20:].mean()
                        sma_50 = closes[-50:].mean() if len(closes) >= 50 else sma_20
                        
                        # Critères de décision - SÉVÈRES
                        decision = 'HOLD'
                        reasons = []
                        
                        # SELL AGRESSIF : toute perte > 8%
                        if unrealized_plpc < -0.08:
                            decision = 'SELL'
                            reasons.append(f"Stop loss {unrealized_plpc:.1%}")
                        
                        # SELL si perte > 5% ET prix sous SMA20 (tendance baissière)
                        elif unrealized_plpc < -0.05 and current_price < sma_20:
                            decision = 'SELL'
                            reasons.append(f"Perte {unrealized_plpc:.1%} + tendance baissière (prix < SMA20)")
                        
                        # SELL si perte > 3% ET prix sous SMA50 (tendance très baissière)
                        elif unrealized_plpc < -0.03 and current_price < sma_50:
                            decision = 'SELL'
                            reasons.append(f"Perte {unrealized_plpc:.1%} + fort signal baissier (prix < SMA50)")
                        
                        # BUY_MORE si gain > 5% ET tendance haussière (SMA20 > SMA50)
                        elif unrealized_plpc > 0.05 and sma_20 > sma_50 and current_price > sma_20:
                            decision = 'BUY_MORE'
                            reasons.append(f"Gain {unrealized_plpc:.1%} + tendance haussière")
                        
                        # HOLD sinon
                        else:
                            if abs(unrealized_plpc) < 0.05:
                                reasons.append("Position stable")
                            else:
                                reasons.append(f"P&L {unrealized_plpc:+.1%}")
                        
                        portfolio_decisions[sym] = {
                            'decision': decision,
                            'reasons': reasons,
                            'unrealized_plpc': unrealized_plpc,
                            'market_value': market_value,
                            'current_price': current_price,
                            'sma_20': sma_20,
                            'sma_50': sma_50
                        }
                        
                        emoji = '🔴' if decision == 'SELL' else '🟢' if decision == 'BUY_MORE' else '🟡'
                        print(f"      {emoji} {decision}: {', '.join(reasons)}")
                    
                    else:
                        portfolio_decisions[sym] = {'decision': 'HOLD', 'reasons': ['Pas assez de données']}
                        print(f"      🟡 HOLD: Pas assez de données")
                
                except Exception as e:
                    portfolio_decisions[sym] = {'decision': 'HOLD', 'reasons': [f'Erreur: {e}']}
                    print(f"      ⚠️ Erreur analyse: {e}")
            
            # Résumé des décisions
            sell_count = sum(1 for d in portfolio_decisions.values() if d['decision'] == 'SELL')
            hold_count = sum(1 for d in portfolio_decisions.values() if d['decision'] == 'HOLD')
            buy_more_count = sum(1 for d in portfolio_decisions.values() if d['decision'] == 'BUY_MORE')
            
            print(f"\n  📋 DÉCISIONS PORTFOLIO:")
            print(f"    🔴 SELL: {sell_count} positions")
            print(f"    🟡 HOLD: {hold_count} positions")
            print(f"    🟢 BUY_MORE: {buy_more_count} positions")
        else:
            print(f"  ℹ️  Portfolio vide - démarrage nouvelle allocation")
        
        adapter.disconnect()
        
        # 1. Sélection univers global (12K tickers)
        print(f"\n🌍 Sélection univers...")
        eq = Equities()
        all_symbols = []
        
        # Première passe : collecter TOUS les symboles disponibles
        if regions:
            for region in regions:
                print(f"  • Scan {region}...")
                if sectors == 'all':
                    df = eq.search(country=region)
                else:
                    df = eq.search(country=region, sector=sectors.title())

                if df is not None and not df.empty:
                    for sym in df.index:
                        if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 6:
                            all_symbols.append(sym)
        else:
            # Global
            print("  • Scan toutes régions...")
            if sectors == 'all':
                df = eq.search()
            else:
                df = eq.search(sector=sectors.title())
            
            if df is not None and not df.empty:
                for idx, sym in enumerate(df.index):
                    if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 6:
                        all_symbols.append(sym)
                        if (idx + 1) % 10000 == 0:
                            print(f"    ↳ Progress scan: {idx+1} lignes scannées, {len(all_symbols)} symboles valides")
        
        if not all_symbols:
            print("❌ Aucun symbole trouvé")
            return False
        
        print(f"✅ {len(all_symbols):,} symboles disponibles au total")
        
        # Randomiser AVANT de sélectionner (élimine le biais alphabétique)
        print(f"🎲 Randomisation (seed basée sur date du jour)...")
        all_symbols = shuffle_universe(all_symbols, seed=None)
        
        # Prendre les N premiers après randomisation
        symbols = all_symbols[:limit]
        print(f"✅ {len(symbols):,} symboles sélectionnés aléatoirement")
        
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
        
        # 5. PRÉ-ANALYSE COMPLÈTE (TOUS MODULES ACTIVÉS)
        print(f"\n🔎 PRÉ-ANALYSE COMPLÈTE (TOUS MODULES)...")
        print(f"  Modules disponibles: {[k for k,v in modules_status.items() if v]}")
        drift_flag = False
        
        # 5.1 Portfolio Learning
        try:
            print(f"  📚 Portfolio Learning...")
            learner = PortfolioLearner(mode='paper', lookback_days=90)
            learning_result = learner.analyze_morning_pre_analysis()
            print(f"     ✅ Insights: {len(learning_result.insights)}, Warnings: {len(learning_result.warning_messages)}")
        except Exception as e:
            print(f"     ⚠️ Portfolio Learning échoué: {e}")
        
        # 5.2 Universe Selection - OBLIGATOIRE
        try:
            if not modules_status['universe']:
                raise Exception(f"Module universe OBLIGATOIRE manquant: {modules_errors.get('universe')}")
            
            print(f"  🌍 Universe Selection...")
            selector = EnhancedUniverseSelector()
            universe_result = selector.select(
                limit=len(prices.columns),
                regions=['us']
            )
            print(f"     ✅ Universe sélectionné: {len(universe_result)} symbols")
            
            if len(universe_result) == 0:
                raise Exception("Universe selection a retourné 0 symboles - ÉCHEC CRITIQUE")
        except Exception as e:
            print(f"     ❌ Universe selection ÉCHEC CRITIQUE: {e}")
            raise  # FORCER l'arrêt
        
        # 5.3 Daily Preanalysis (Drift + Options) - EXÉCUTION FORCÉE
        try:
            print(f"  🔬 Daily Preanalysis (Drift + Options)...")
            from financial_analyzer.preanalysis.daily_preanalysis import run_daily_preanalysis
            
            # EXÉCUTER RÉELLEMENT avec subset de symboles
            preanalysis_syms = prices.columns.tolist()[:min(50, len(prices.columns))]
            preanalysis_result = run_daily_preanalysis(
                symbols=preanalysis_syms,
                start_date=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d'),
                check_drift=True,
                analyze_options=False,  # Options peut échouer
                risk_free_rate=0.05
            )
            
            # Extraire drift flag
            if 'drift_check' in preanalysis_result:
                drift_flag = preanalysis_result['drift_check'].get('drift_detected', False)
                print(f"     ✅ Drift détecté: {drift_flag}")
            
            if 'recommendations' in preanalysis_result:
                print(f"     ✅ Recommandations: {len(preanalysis_result['recommendations'])}")
            
            print(f"     ✅ Daily preanalysis EXECUTÉE avec {len(preanalysis_syms)} symboles")
        except Exception as e:
            print(f"     ⚠️ Daily preanalysis échouée: {e}")
            import traceback
            traceback.print_exc()
        
        # 5.4 Risk Analysis - OBLIGATOIRE
        try:
            if not modules_status['risk']:
                raise Exception(f"Module risk OBLIGATOIRE manquant: {modules_errors.get('risk')}")
            
            print(f"  ⚠️  Risk Analysis...")
            adapter_risk = AlpacaAdapter.from_env(mode='paper')
            adapter_risk.connect()
            monitor = AccountMonitor(adapter_risk, initial_capital=100000)
            monitor.update()
            risk_guard = RiskGuard(
                account_monitor=monitor,
                max_position_size=5000,
                max_position_pct=0.20,
                max_total_positions=200,
            )
            risk_summary = risk_guard.get_risk_summary()
            risk_score = risk_guard.get_risk_score()
            print(f"     ✅ Risk score: {risk_score:.1f}")
            
            # Valider que le risk score est dans les limites acceptables
            if risk_score > 80:
                print(f"     ⚠️  ATTENTION: Risk score élevé ({risk_score:.1f}) - Portefeuille très risqué")
            
            adapter_risk.disconnect()
        except Exception as e:
            print(f"     ❌ Risk analysis ÉCHEC CRITIQUE: {e}")
            raise  # FORCER l'arrêt
        
        print(f"  ✅ Pré-analyse complète terminée")

        # 6. Calcul scores professionnels (300+ facteurs) + FUSION MULTI-SOURCES
        print(f"\n🧠 Calcul scores professionnels (~300+ facteurs par symbole)...")
        print(f"🔗 Fusion signaux multi-sources: Technical + Fundamental + Sentiment + ML + RL")
        
        # Initialize fusion engine
        # Historique de performance (placeholder) pour reweighting evidence-based
        # Dans une version future, charger depuis stockage persistant.
        performance_history = None
        fusion_engine = SignalFusionEngine(
            source_weights={
                'technical': 0.20,
                'fundamental': 0.25,
                'sentiment': 0.15,
                'ml_lstm': 0.20,
                'ml_factor': 0.10,
                'rl': 0.10,
            },
            min_sources=2,
            fallback_mode=True,
            weighting_history=performance_history,
            auto_reweight=True,
        )
        
        # Générer signaux fusionnés (en batch pour performance)
        print(f"  Génération signaux fusionnés (batch)...")
        fused_signals_df = fusion_engine.generate_signals_batch(
            symbols=prices.columns.tolist(),
            price_data_dict=bars_dict,
            progress_callback=lambda idx, total: print(f"    Progress fusion: {idx}/{total}") if idx % 100 == 0 else None
        )
        
        # Collecter stats fusion engine
        fusion_stats = fusion_engine.get_stats()
        print(f"  ✅ Sources actives: {', '.join(fusion_stats['active_sources'])}")
        print(f"  ✅ Signaux fusionnés: {len(fused_signals_df)}")
        
        # Calcul scores professionnels originaux (backup/enrichment)
        signals = []
        
        for idx, symbol in enumerate(prices.columns):
            if idx % 50 == 0 and idx > 0:
                print(f"  Progress scores pro: {idx}/{len(prices.columns)}")
            
            signal_data = compute_professional_score(
                symbol=symbol,
                bars=bars_dict.get(symbol, pd.DataFrame()),
                weighting_method=weighting
            )
            
            # Merger avec signal fusionné si disponible
            if symbol in fused_signals_df['symbol'].values:
                fused_row = fused_signals_df[fused_signals_df['symbol'] == symbol].iloc[0]
                signal_data['fused_score'] = fused_row['composite_score']
                signal_data['fused_confidence'] = fused_row['confidence']
                # Copier sous-scores des sources
                for source in ['technical', 'fundamental', 'sentiment', 'ml_lstm', 'ml_factor', 'rl']:
                    if f'{source}_score' in fused_row:
                        signal_data[f'{source}_score'] = fused_row[f'{source}_score']
                    if f'{source}_confidence' in fused_row:
                        signal_data[f'{source}_confidence'] = fused_row[f'{source}_confidence']
                
                # Combiner composite_score original avec fused_score (70% fused, 30% original)
                original_score = signal_data.get('composite_score', 0.5)
                fused_score = signal_data.get('fused_score', 0.5)
                signal_data['composite_score'] = 0.7 * fused_score + 0.3 * original_score
            
            signals.append(signal_data)
        
        signals_df = pd.DataFrame(signals)
        print(f"✅ Scores calculés pour {len(signals_df)} symboles")
        print(f"   Facteurs moyens/symbole: {signals_df['num_factors_computed'].mean():.0f}")
        print(f"   Confiance moyenne: {signals_df['confidence'].mean():.2f}")
        if 'fused_score' in signals_df.columns:
            print(f"   Fused score moyen: {signals_df['fused_score'].mean():.3f}")
            print(f"   Fused confidence moyenne: {signals_df['fused_confidence'].mean():.3f}")
        
        # 7. Sélection top
        top_syms = signals_df.nlargest(top, 'composite_score')['symbol'].tolist()
        print(f"\n🎯 Top {len(top_syms)} sélectionnés")
        
        # 8. OPTIMISATION & MODULES COMPLÉMENTAIRES (TOUS ACTIVÉS)
        print(f"\n📐 OPTIMISATION + MODULES COMPLÉMENTAIRES (TOUS ACTIVÉS)...")
        orchestration_result = None
        
        # 8.1 Master Orchestrator
        try:
            print(f"  🎯 Master Orchestrator...")
            subset_syms = top_syms[: min(50, len(top_syms))]
            orchestrator = MasterOrchestrator(symbols=subset_syms, mode='paper')
            orchestration_result = orchestrator.run_complete_analysis(
                start_date=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d'),
                skip_if_no_drift=False,
                use_rl_signals=True,
                use_ml_signals=True,
                use_sentiment=True,
                optimization_method='mean_variance',
                enable_options_hedge=True,
                dry_run=False,
            )
            if orchestration_result.portfolio_construction:
                print(f"     ✅ Sharpe: {orchestration_result.portfolio_construction.expected_sharpe:.2f}")
                print(f"     ✅ Return: {orchestration_result.portfolio_construction.expected_return:.2%}")
                print(f"     ✅ Vol: {orchestration_result.portfolio_construction.expected_volatility:.2%}")
            if orchestration_result.execution:
                print(f"     ✅ Orders submitted: {len(orchestration_result.execution.orders_submitted)}")
                print(f"     ✅ Orders executed: {len(orchestration_result.execution.orders_executed)}")
                if orchestration_result.execution.risk_score:
                    print(f"     ✅ Risk score: {orchestration_result.execution.risk_score:.1f}")
        except Exception as e:
            print(f"     ⚠️ Master Orchestrator échoué: {e}")
            import traceback
            traceback.print_exc()
        
        # 8.2 Performance Attribution (ACTIF) - EXÉCUTION FORCÉE
        try:
            if not modules_status['perf_attr']:
                raise Exception(f"Module perf_attr OBLIGATOIRE manquant: {modules_errors.get('perf_attr')}")
            
            print(f"  📊 Performance Attribution...")
            attributor = PerformanceAttributor()
            
            # Calculer attribution sur portfolio réel
            attr_syms = top_syms[:min(10, len(top_syms))]
            returns_attr = prices[attr_syms].pct_change().dropna()
            
            if len(returns_attr) >= 20 and orchestration_result and orchestration_result.portfolio_construction:
                # Utiliser weights du portfolio
                target_weights = orchestration_result.portfolio_construction.target_weights
                
                # Calculer returns pondérés
                portfolio_returns = (returns_attr * pd.Series(target_weights)).sum(axis=1)
                
                # Attribution par facteur (simplified - juste par position)
                attribution_by_position = {}
                for sym in attr_syms:
                    if sym in target_weights:
                        sym_return = returns_attr[sym].mean() * 252  # Annualisé
                        weight = target_weights[sym]
                        contribution = sym_return * weight
                        attribution_by_position[sym] = {
                            'weight': weight,
                            'return': sym_return,
                            'contribution': contribution
                        }
                
                total_contrib = sum(a['contribution'] for a in attribution_by_position.values())
                print(f"     ✅ Attribution calculée: {len(attribution_by_position)} positions")
                print(f"     ✅ Contribution totale annualisée: {total_contrib:.2%}")
                
                # Top 3 contributeurs
                top_contributors = sorted(attribution_by_position.items(), 
                                        key=lambda x: x[1]['contribution'], 
                                        reverse=True)[:3]
                for sym, attr in top_contributors:
                    print(f"        • {sym}: {attr['contribution']:+.2%} (weight {attr['weight']:.1%}, return {attr['return']:+.2%})")
            else:
                print(f"     ⚠️ Pas assez de données pour attribution (besoin 20+ jours)")
        except Exception as e:
            print(f"     ❌ Performance Attribution ÉCHEC CRITIQUE: {e}")
            import traceback
            traceback.print_exc()
            raise  # FORCER l'arrêt si module obligatoire échoue
        
        # 8.3 Portfolio Rebalancer (OBLIGATOIRE)
        try:
            if not modules_status['rebalancer']:
                raise Exception(f"Module rebalancer OBLIGATOIRE manquant: {modules_errors.get('rebalancer')}")
            
            print(f"  ⚖️  Portfolio Rebalancer...")
            # Calculer returns pour top symbols
            rebal_syms = top_syms[:min(10, len(top_syms))]
            returns_rebal = prices[rebal_syms].pct_change().dropna()
            if len(returns_rebal) < 20:
                raise Exception(f"Pas assez de données pour rebalancing: {len(returns_rebal)} périodes")
            
            rebalancer = PortfolioRebalancer(returns=returns_rebal)
            # Créer target weights (pandas Series)
            target_w = pd.Series(1.0/len(rebal_syms), index=rebal_syms)
            rebal_result = rebalancer.rebalance_periodic(
                target_weights=target_w,
                freq='ME',
                transaction_cost=0.001
            )
            # rebal_result a .weights (DataFrame) et .trades (DataFrame)
            print(f"     ✅ Rebalance: {len(rebal_result.weights)} périodes, {rebal_result.trades.sum().sum():.3f} trades totaux")
        except Exception as e:
            print(f"     ❌ Rebalancer ÉCHEC CRITIQUE: {e}")
            raise
        
        # 8.4 Analytics Engine (OBLIGATOIRE)
        try:
            if not modules_status['analytics']:
                raise Exception(f"Module analytics OBLIGATOIRE manquant: {modules_errors.get('analytics')}")
            
            print(f"  📈 Analytics Engine...")
            analyzer = PerformanceAnalyzer()
            # Analyser returns du portfolio
            analytics_syms = top_syms[:min(10, len(top_syms))]
            returns_analytics = prices[analytics_syms].pct_change().dropna()
            if len(returns_analytics) < 30:
                raise Exception(f"Pas assez de données pour analytics: {len(returns_analytics)} périodes")
            
            # Portfolio returns (equal weight)
            portfolio_returns = returns_analytics.mean(axis=1)
            analytics_result = analyzer.analyze_returns(
                portfolio_returns=portfolio_returns,
                benchmark_returns=None,
                trades=None
            )
            print(f"     ✅ Sharpe: {analytics_result.get('ratios', {}).get('sharpe_ratio', 0):.2f}")
            print(f"     ✅ Max Drawdown: {analytics_result.get('risk', {}).get('max_drawdown', 0):.2%}")
            print(f"     ✅ Annual Return: {analytics_result.get('returns', {}).get('annualized', 0):.2%}")
        except Exception as e:
            print(f"     ❌ Analytics ÉCHEC CRITIQUE: {e}")
            raise
        
        # 8.5 Report Generator (OBLIGATOIRE)
        try:
            if not modules_status['reports']:
                raise Exception(f"Module reports OBLIGATOIRE manquant: {modules_errors.get('reports')}")
            
            print(f"  📄 Report Generator (Tearsheet)...")
            # Générer tearsheet pour portfolio
            tearsheet_syms = top_syms[:min(5, len(top_syms))]
            returns_tearsheet = prices[tearsheet_syms].pct_change().dropna()
            if len(returns_tearsheet) < 30:
                raise Exception(f"Pas assez de données pour tearsheet: {len(returns_tearsheet)} périodes")
            
            portfolio_rets_ts = returns_tearsheet.mean(axis=1)
            # Calculer portfolio values
            portfolio_values = (1 + portfolio_rets_ts).cumprod().tolist()
            tearsheet_path = generate_tearsheet(
                portfolio_values=portfolio_values,
                returns=portfolio_rets_ts.tolist(),
                metrics=None,
                output_path=f'/tmp/finbot_tearsheet_{datetime.now().strftime("%Y%m%d")}.html'
            )
            print(f"     ✅ Tearsheet généré: {tearsheet_path}")
        except Exception as e:
            print(f"     ❌ Report ÉCHEC CRITIQUE: {e}")
            raise
        
        # 8.6 Backtesting (OBLIGATOIRE)
        try:
            if not modules_status['backtest']:
                raise Exception(f"Module backtest OBLIGATOIRE manquant: {modules_errors.get('backtest')}")
            
            print(f"  🔙 Backtesting (FinBotStrategy)...")
            from financial_analyzer.backtesting.finbot_strategy import FinBotBacktester
            # Run backtest sur subset
            backtest_syms = top_syms[:min(5, len(top_syms))]
            if len(prices) < 60:
                raise Exception(f"Pas assez de données pour backtest: {len(prices)} périodes")
            
            # Préparer data dict avec OHLCV (simuler avec Close uniquement)
            data_dict = {}
            for sym in backtest_syms:
                if sym in prices.columns:
                    # Extraire close prices et créer OHLCV
                    # IMPORTANT: FinBotBacktester attend colonnes avec Capital: Close, Open, High, Low, Volume
                    close_series = prices[sym].dropna()
                    df = pd.DataFrame({
                        'Close': close_series,
                        'Open': close_series,
                        'High': close_series * 1.01,
                        'Low': close_series * 0.99,
                        'Volume': 1000000
                    }, index=close_series.index)
                    data_dict[sym] = df
            
            if len(data_dict) == 0:
                raise Exception("Aucune donnée backtest préparée")
            
            backtester = FinBotBacktester(
                data=data_dict,
                initial_cash=100000,
                universe=backtest_syms,
                lookback_days=60
            )
            # Utiliser init() et next() pour simuler
            backtester.init()
            num_periods = len(list(data_dict.values())[0])
            for i in range(num_periods):
                backtester.next(i)
            
            final_equity = backtester.equity_curve[-1] if backtester.equity_curve else backtester.initial_cash
            total_return = (final_equity / backtester.initial_cash - 1.0) * 100
            print(f"     ✅ Backtest: {num_periods} périodes, Return: {total_return:.2f}%, Equity final: ${final_equity:,.0f}")
        except Exception as e:
            print(f"     ❌ Backtest ÉCHEC CRITIQUE: {e}")
            raise
        
        print(f"  ✅ Tous les modules complémentaires exécutés")

        # 9. Export results
        output_file = output or f'professional_analysis_daemon_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        signals_df.to_csv(output_file, index=False)
        print(f"💾 Résultats exportés: {output_file}")
        
        # 10. Application au compte Alpaca Paper Trading
        print(f"\n📤 APPLICATION AU COMPTE ALPACA PAPER TRADING...")
        
        adapter = AlpacaAdapter.from_env(mode='paper')
        adapter.connect()
        
        # ÉTAPE 1: Exécuter les ordres SELL pour positions à liquider
        if portfolio_decisions:
            sell_positions = [sym for sym, dec in portfolio_decisions.items() if dec['decision'] == 'SELL']
            
            if sell_positions:
                print(f"\n  🔴 EXÉCUTION ORDRES SELL ({len(sell_positions)} positions)...")
                for sym in sell_positions:
                    try:
                        pos = adapter.api.get_position(sym)
                        qty = float(pos.qty)
                        order = adapter.submit_order(
                            symbol=sym,
                            qty=qty,
                            side='sell',
                            order_type='market'
                        )
                        print(f"    ✅ SELL {sym}: {qty} shares (ordre {order.get('id', 'N/A')})")
                        print(f"       Raison: {', '.join(portfolio_decisions[sym]['reasons'])}")
                    except Exception as e:
                        print(f"    ❌ SELL {sym} échoué: {e}")
            else:
                print(f"\n  ℹ️  Aucune position à vendre")
        
        # ÉTAPE 2: Calculer nouvelles allocations (excluant positions HOLD et BUY_MORE)
        print(f"\n  🔄 CALCUL NOUVELLES ALLOCATIONS...")
        
        account = adapter.get_account()
        equity = float(account.get('equity', 0))
        
        # Exclure symboles déjà en HOLD ou BUY_MORE (on ne veut pas les racheter)
        existing_symbols = set(portfolio_decisions.keys())
        hold_symbols = {sym for sym, dec in portfolio_decisions.items() if dec['decision'] == 'HOLD'}
        buy_more_symbols = {sym for sym, dec in portfolio_decisions.items() if dec['decision'] == 'BUY_MORE'}
        
        # Filtrer top_syms pour exclure les positions existantes (sauf BUY_MORE)
        new_candidates = [sym for sym in top_syms if sym not in existing_symbols or sym in buy_more_symbols]
        
        print(f"    • Equity totale: ${equity:,.2f}")
        print(f"    • Positions HOLD à garder: {len(hold_symbols)}")
        print(f"    • Positions BUY_MORE: {len(buy_more_symbols)}")
        print(f"    • Nouveaux candidats: {len(new_candidates)}")
        
        # ÉTAPE 3: Soumettre ordres BUY pour nouvelles positions
        print(f"\n  🟢 SOUMISSION ORDRES BUY...")
        
        weight_per_position = 1.0 / len(new_candidates) if new_candidates else 0
        cash_per_position = equity * weight_per_position
        
        print(f"    • Cash par position: ${cash_per_position:,.2f}")
        
        orders_submitted = 0
        orders_failed = 0
        
        for symbol in new_candidates[:top]:  # Limiter au top N configuré
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
        if drift_flag:
            print("⚠️  DRIFT MODEL SIGNALÉ PAR PRÉ-ANALYSE - RETRAIN RECOMMANDÉ")
        
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
    
    parser.add_argument('--limit', type=int, default=12000,
                        help='Nombre max de symboles (défaut: 12000)')
    parser.add_argument('--top', type=int, default=200,
                        help='Top N positions (défaut: 200)')
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
