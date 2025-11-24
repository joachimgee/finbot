#!/usr/bin/env python3
"""
Daily Portfolio Management - Workflow complet automatisé
1. Exécute l'analyse professionnelle quotidienne (12K symboles)
2. Gère le portefeuille avec PortfolioManager
3. Applique le rebalancement intelligent
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
import argparse
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.portfolio_manager import PortfolioManager
from src.financial_analyzer.portfolio.rebalancer import PortfolioRebalancer
from src.financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from src.financial_analyzer.learning.portfolio_learner import PortfolioLearner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DailyPortfolioWorkflow:
    """Workflow complet de gestion de portefeuille quotidienne."""
    
    def __init__(self, mode: str = 'paper', max_positions: int = 200,
                 max_investment_per_position: float = 1000.0,
                 hold_threshold_score: float = 0.0):
        """
        Initialize workflow.
        
        Args:
            mode: 'paper' ou 'live'
            max_positions: Nombre max de positions
            max_investment_per_position: Investissement max par position ($)
            hold_threshold_score: Score minimum pour conserver une position
        """
        self.mode = mode
        self.max_positions = max_positions
        self.max_investment_per_position = max_investment_per_position
        self.hold_threshold_score = hold_threshold_score
        
        # Output paths
        self.analysis_csv = Path('professional_daily_global.csv')
        self.log_dir = Path('logs')
        self.log_dir.mkdir(exist_ok=True)
        
        # Learning component
        self.learner = PortfolioLearner(
            mode=mode,
            lookback_days=30,
            learning_rate=0.1
        )
        
    def step0_morning_learning(self) -> tuple:
        """
        Étape 0: Apprentissage matinal (AVANT analyse).
        
        Analyse :
        - Portfolio actuel vs hier
        - Performance attribution
        - Détection erreurs systématiques
        - Ajustement paramètres
        
        Returns:
            (should_proceed, learning_result)
        """
        print(f"\n{'='*80}")
        print(f"🧠 ÉTAPE 0: APPRENTISSAGE MATINAL (PRÉ-ANALYSE)")
        print(f"{'='*80}\n")
        
        try:
            result = self.learner.analyze_morning_pre_analysis()
            
            # Afficher snapshot
            print(f"📊 PORTFOLIO ACTUEL:")
            print(f"  • Equity: ${result.portfolio_snapshot.equity:,.2f}")
            print(f"  • Cash: ${result.portfolio_snapshot.cash:,.2f}")
            print(f"  • Positions: {result.portfolio_snapshot.positions_count}")
            print(f"  • P&L jour: ${result.portfolio_snapshot.day_pnl:+,.2f}")
            print(f"  • P&L total: ${result.portfolio_snapshot.total_pnl:+,.2f}")
            
            # Afficher métriques professionnelles
            if result.performance_metrics:
                print(f"\n📈 MÉTRIQUES PROFESSIONNELLES:")
                metrics = result.performance_metrics
                
                if 'sharpe_ratio' in metrics:
                    print(f"  • Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
                if 'sortino_ratio' in metrics:
                    print(f"  • Sortino Ratio: {metrics['sortino_ratio']:.3f}")
                if 'calmar_ratio' in metrics:
                    print(f"  • Calmar Ratio: {metrics['calmar_ratio']:.3f}")
                if 'max_drawdown_pct' in metrics:
                    print(f"  • Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
                if 'annualized_return_pct' in metrics:
                    print(f"  • Rendement annualisé: {metrics['annualized_return_pct']:+.2f}%")
            
            # Afficher insights
            if result.insights:
                print(f"\n💡 INSIGHTS ({len(result.insights)}):")
                
                # Grouper par priorité
                high_priority = [i for i in result.insights if i.priority == 'high']
                medium_priority = [i for i in result.insights if i.priority == 'medium']
                low_priority = [i for i in result.insights if i.priority == 'low']
                
                if high_priority:
                    print(f"\n  🔴 HIGH PRIORITY ({len(high_priority)}):")
                    for insight in high_priority[:3]:  # Top 3
                        print(f"    • {insight.description}")
                        print(f"      → Action: {insight.action_recommended[:80]}...")
                
                if medium_priority:
                    print(f"\n  🟡 MEDIUM PRIORITY ({len(medium_priority)}):")
                    for insight in medium_priority[:2]:  # Top 2
                        print(f"    • {insight.description}")
                
                if low_priority:
                    print(f"\n  🟢 SUCCESS ({len(low_priority)}):")
                    for insight in low_priority[:1]:  # Top 1
                        print(f"    • {insight.description}")
            
            # Afficher ajustements recommandés
            if result.parameter_adjustments:
                print(f"\n⚙️  AJUSTEMENTS RECOMMANDÉS:")
                for param, value in result.parameter_adjustments.items():
                    print(f"  • {param}: {value:.2f}")
                    
                # Appliquer les ajustements
                if 'max_positions' in result.parameter_adjustments:
                    new_val = int(result.parameter_adjustments['max_positions'])
                    print(f"    → Appliqué: max_positions = {new_val}")
                    self.max_positions = new_val
                
                if 'hold_threshold' in result.parameter_adjustments:
                    new_val = result.parameter_adjustments['hold_threshold']
                    print(f"    → Appliqué: hold_threshold = {new_val:.2f}")
                    self.hold_threshold_score = new_val
                
                if 'max_investment' in result.parameter_adjustments:
                    new_val = result.parameter_adjustments['max_investment']
                    print(f"    → Appliqué: max_investment = ${new_val:.2f}")
                    self.max_investment_per_position = new_val
            
            # Warnings
            if result.warning_messages:
                print(f"\n⚠️  WARNINGS:")
                for warning in result.warning_messages:
                    print(f"  • {warning}")
            
            # Décision
            if result.should_proceed:
                print(f"\n✅ Apprentissage terminé, procéder avec analyse")
            else:
                print(f"\n🛑 STOP: Conditions critiques détectées")
            
            return result.should_proceed, result
            
        except Exception as e:
            logger.error(f"Learning error: {e}", exc_info=True)
            print(f"⚠️  Apprentissage échoué, procéder quand même: {e}")
            return True, None  # Safe default: toujours procéder si erreur
        
    def step1_run_analysis(self, limit: int = 12000, regions: str = "global",
                          days: int = 365, skip_if_exists: bool = False) -> bool:
        """
        Étape 1: Exécuter l'analyse professionnelle.
        
        Args:
            limit: Nombre de symboles à analyser
            regions: Régions à analyser
            days: Période historique
            skip_if_exists: Si True, skip si CSV existe déjà
            
        Returns:
            True si succès
        """
        print(f"\n{'='*80}")
        print(f"📊 ÉTAPE 1: ANALYSE PROFESSIONNELLE")
        print(f"{'='*80}\n")
        
        # Check if already exists
        if skip_if_exists and self.analysis_csv.exists():
            age_hours = (datetime.now().timestamp() - self.analysis_csv.stat().st_mtime) / 3600
            if age_hours < 24:
                print(f"✅ Analyse récente trouvée ({age_hours:.1f}h), skip")
                return True
        
        # Run analysis
        cmd = [
            'python', '-u', 'scripts/professional_analysis_daemon.py',
            '--once',
            '--limit', str(limit),
            '--top', str(self.max_positions),
            '--regions', regions,
            '--days', str(days),
            '--risk-level', 'medium-high',
            '--weighting', 'ic-weighted',
            '--output', str(self.analysis_csv)
        ]
        
        log_file = self.log_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
        
        print(f"🚀 Lancement analyse: {limit:,} symboles ({regions})")
        print(f"📝 Logs: {log_file}")
        
        try:
            with open(log_file, 'w') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=14400  # 4 heures max
                )
            
            if result.returncode == 0 and self.analysis_csv.exists():
                print(f"✅ Analyse terminée avec succès")
                print(f"📄 Résultats: {self.analysis_csv}")
                return True
            else:
                print(f"❌ Analyse échouée (code: {result.returncode})")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"❌ Analyse timeout (>4h)")
            return False
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False
    
    def step2_manage_portfolio(self, execute: bool = False) -> bool:
        """
        Étape 2: Gérer le portefeuille avec PortfolioManager.
        
        Args:
            execute: Si True, exécute les ordres réellement
            
        Returns:
            True si succès
        """
        print(f"\n{'='*80}")
        print(f"💼 ÉTAPE 2: GESTION PORTEFEUILLE")
        print(f"{'='*80}\n")
        
        if not self.analysis_csv.exists():
            print(f"❌ Fichier analyse introuvable: {self.analysis_csv}")
            return False
        
        try:
            # Create portfolio manager
            manager = PortfolioManager(
                mode=self.mode,
                max_positions=self.max_positions,
                hold_threshold_score=self.hold_threshold_score
            )
            
            # Run full cycle
            result = manager.run_full_cycle(
                analysis_csv=str(self.analysis_csv),
                execute=execute,
                max_investment=self.max_investment_per_position
            )
            # Si exécution réelle, result contient risk metrics
            if isinstance(result, dict) and 'risk_score_after' in result:
                print("\n🛡️  RISK SUMMARY (PortfolioManager):")
                print(f"  • Risk score avant: {result.get('risk_score_before')}")
                print(f"  • Risk score après: {result.get('risk_score_after')}")
                if result.get('circuit_breakers'):
                    print(f"  • Circuit breakers: {result['circuit_breakers']}")
            
            print(f"✅ Gestion portefeuille terminée")
            return True
            
        except Exception as e:
            print(f"❌ Erreur gestion portefeuille: {e}")
            logger.exception("Portfolio management error")
            return False
    
    def step3_check_status(self) -> dict:
        """
        Étape 3: Vérifier l'état final du portefeuille.
        
        Returns:
            Dict avec stats du portefeuille
        """
        print(f"\n{'='*80}")
        print(f"📈 ÉTAPE 3: ÉTAT FINAL PORTEFEUILLE")
        print(f"{'='*80}\n")
        
        try:
            adapter = AlpacaAdapter.from_env(mode=self.mode)
            adapter.connect()
            
            account = adapter.get_account()
            positions = adapter.get_positions()
            orders = adapter.get_orders(status='open')
            
            stats = {
                'equity': float(account.get('equity', 0)),
                'cash': float(account.get('cash', 0)),
                'buying_power': float(account.get('buying_power', 0)),
                'num_positions': len(positions),
                'num_pending_orders': len(orders),
                'positions_value': sum(float(p.get('market_value', 0)) for p in positions)
            }
            
            print(f"💰 COMPTE:")
            print(f"  • Equity totale: ${stats['equity']:,.2f}")
            print(f"  • Cash disponible: ${stats['cash']:,.2f}")
            print(f"  • Buying power: ${stats['buying_power']:,.2f}")
            
            print(f"\n📊 POSITIONS:")
            print(f"  • Nombre de positions: {stats['num_positions']}")
            print(f"  • Valeur totale: ${stats['positions_value']:,.2f}")
            print(f"  • Ordres en attente: {stats['num_pending_orders']}")
            
            if positions:
                print(f"\n📋 TOP 10 POSITIONS PAR VALEUR:")
                sorted_positions = sorted(
                    positions,
                    key=lambda p: float(p.get('market_value', 0)),
                    reverse=True
                )[:10]
                
                for i, pos in enumerate(sorted_positions, 1):
                    symbol = pos.get('symbol')
                    qty = float(pos.get('qty', 0))
                    value = float(pos.get('market_value', 0))
                    pl_pct = float(pos.get('unrealized_plpc', 0)) * 100
                    print(f"  {i:2d}. {symbol:6s}: {qty:6.0f} shares, ${value:8,.2f} ({pl_pct:+6.2f}%)")
            
            return stats
            
        except Exception as e:
            print(f"❌ Erreur récupération stats: {e}")
            logger.exception("Status check error")
            return {}
    
    def run_full_workflow(self, execute: bool = False, skip_analysis: bool = False) -> bool:
        """
        Exécute le workflow complet.
        
        Args:
            execute: Si True, exécute les ordres réellement
            skip_analysis: Si True, skip l'analyse si CSV récent existe
            
        Returns:
            True si succès complet
        """
        start_time = datetime.now()
        
        print(f"\n{'#'*80}")
        print(f"# DAILY PORTFOLIO MANAGEMENT - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"# Mode: {self.mode.upper()}")
        print(f"# Execute: {'YES (REAL ORDERS)' if execute else 'NO (DRY-RUN)'}")
        print(f"{'#'*80}\n")
        
        success = True
        
        # Étape 0: Apprentissage matinal
        should_proceed, learning_result = self.step0_morning_learning()
        
        if not should_proceed:
            print(f"\n🛑 Workflow arrêté: Conditions critiques détectées par learner")
            return False
        
        # Étape 1: Analyse
        if not self.step1_run_analysis(skip_if_exists=skip_analysis):
            print(f"\n❌ Workflow arrêté: Analyse échouée")
            return False
        
        # Étape 2: Gestion portefeuille
        if not self.step2_manage_portfolio(execute=execute):
            print(f"\n❌ Workflow arrêté: Gestion portefeuille échouée")
            success = False
        else:
            print("\n✅ Gestion portefeuille + validation risque terminées")
        
        # Étape 3: Status final
        self.step3_check_status()
        
        # Résumé
        duration = datetime.now() - start_time
        print(f"\n{'#'*80}")
        print(f"# WORKFLOW TERMINÉ")
        print(f"# Durée: {duration}")
        print(f"# Statut: {'✅ SUCCÈS' if success else '❌ ÉCHEC'}")
        print(f"{'#'*80}\n")
        
        return success


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description='Daily Portfolio Management - Workflow complet automatisé'
    )
    
    # Analysis params
    parser.add_argument('--limit', type=int, default=12000,
                       help='Nombre de symboles à analyser (défaut: 12000)')
    parser.add_argument('--regions', type=str, default='global',
                       help='Régions à analyser (défaut: global)')
    parser.add_argument('--skip-analysis', action='store_true',
                       help='Skip analyse si CSV récent existe (<24h)')
    
    # Portfolio params
    parser.add_argument('--max-positions', type=int, default=200,
                       help='Nombre max de positions (défaut: 200)')
    parser.add_argument('--max-investment', type=float, default=1000.0,
                       help='Investissement max par position en $ (défaut: 1000)')
    parser.add_argument('--hold-threshold', type=float, default=0.0,
                       help='Score minimum pour HOLD (défaut: 0.0)')
    
    # Execution params
    parser.add_argument('--execute', action='store_true',
                       help='Exécuter les ordres réellement (sinon dry-run)')
    parser.add_argument('--mode', type=str, default='paper', choices=['paper', 'live'],
                       help='Mode Alpaca (défaut: paper)')
    
    args = parser.parse_args()
    
    # Créer workflow
    workflow = DailyPortfolioWorkflow(
        mode=args.mode,
        max_positions=args.max_positions,
        max_investment_per_position=args.max_investment,
        hold_threshold_score=args.hold_threshold
    )
    
    # Exécuter
    success = workflow.run_full_workflow(
        execute=args.execute,
        skip_analysis=args.skip_analysis
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
