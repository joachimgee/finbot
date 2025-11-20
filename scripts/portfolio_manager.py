#!/usr/bin/env python3
"""
Portfolio Manager - Gestion intelligente du portefeuille Alpaca
Analyse les positions actuelles vs nouvelles opportunités
Décide: HOLD / SELL / BUY
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PortfolioManager:
    """Gestionnaire de portefeuille intelligent."""
    
    def __init__(self, mode: str = 'paper', max_positions: int = 200, 
                 rebalance_threshold: float = 0.15, hold_threshold_score: float = 0.0):
        """
        Initialize portfolio manager.
        
        Args:
            mode: 'paper' ou 'live'
            max_positions: Nombre max de positions
            rebalance_threshold: Seuil de rebalancement (15% par défaut)
            hold_threshold_score: Score minimum pour HOLD (0.0 = neutre)
        """
        self.adapter = AlpacaAdapter.from_env(mode=mode)
        self.adapter.connect()
        self.max_positions = max_positions
        self.rebalance_threshold = rebalance_threshold
        self.hold_threshold_score = hold_threshold_score
        
    def get_current_portfolio(self) -> Dict:
        """Récupère l'état actuel du portefeuille."""
        account = self.adapter.get_account()
        positions = self.adapter.get_positions()
        orders = self.adapter.get_orders(status='open')
        
        portfolio = {
            'account': {
                'cash': float(account.get('cash', 0)),
                'equity': float(account.get('equity', 0)),
                'buying_power': float(account.get('buying_power', 0))
            },
            'positions': {},
            'pending_orders': {}
        }
        
        # Positions actuelles
        for pos in positions:
            symbol = pos.get('symbol', pos.get('asset_id'))
            portfolio['positions'][symbol] = {
                'qty': float(pos.get('qty', 0)),
                'current_price': float(pos.get('current_price', 0)),
                'market_value': float(pos.get('market_value', 0)),
                'cost_basis': float(pos.get('cost_basis', 0)),
                'unrealized_pl': float(pos.get('unrealized_pl', 0)),
                'unrealized_plpc': float(pos.get('unrealized_plpc', 0))
            }
        
        # Ordres en attente
        for order in orders:
            symbol = order.get('symbol')
            portfolio['pending_orders'][symbol] = {
                'side': order.get('side'),
                'qty': float(order.get('qty', 0)),
                'type': order.get('type'),
                'order_id': order.get('id')
            }
        
        return portfolio
    
    def load_analysis_results(self, csv_path: str) -> pd.DataFrame:
        """Charge les résultats de l'analyse professionnelle."""
        df = pd.read_csv(csv_path)
        
        # Vérifier colonnes requises
        required = ['symbol', 'composite_score', 'confidence']
        if not all(col in df.columns for col in required):
            raise ValueError(f"CSV doit contenir: {required}")
        
        return df
    
    def make_decisions(self, portfolio: Dict, analysis_df: pd.DataFrame) -> Dict[str, List]:
        """
        Décide des actions à prendre: HOLD / SELL / BUY
        
        Returns:
            Dict avec 'hold', 'sell', 'buy' contenant les décisions
        """
        decisions = {
            'hold': [],
            'sell': [],
            'buy': [],
            'cancel': []
        }
        
        # Créer un dict des nouvelles opportunités
        top_opportunities = analysis_df.nlargest(self.max_positions, 'composite_score')
        opportunity_dict = top_opportunities.set_index('symbol').to_dict('index')
        
        print(f"\n📊 ANALYSE PORTEFEUILLE")
        print(f"{'='*80}")
        
        # 1. ANNULER les ordres en attente qui ne sont plus dans le top
        print(f"\n🚫 ANNULATION D'ORDRES:")
        for symbol, order_info in portfolio['pending_orders'].items():
            if symbol not in opportunity_dict:
                decisions['cancel'].append({
                    'symbol': symbol,
                    'order_id': order_info['order_id'],
                    'reason': 'Plus dans top opportunités'
                })
                print(f"  ❌ CANCEL {symbol}: Plus dans le top {self.max_positions}")
            else:
                print(f"  ✅ KEEP order {symbol}: Toujours dans le top")
        
        # 2. ANALYSER positions actuelles
        print(f"\n📈 ANALYSE POSITIONS ACTUELLES:")
        for symbol, pos_info in portfolio['positions'].items():
            if symbol in opportunity_dict:
                # Position existe dans les nouvelles opportunités
                new_score = opportunity_dict[symbol]['composite_score']
                pl_pct = pos_info['unrealized_plpc'] * 100
                
                # Décision HOLD si score >= seuil
                if new_score >= self.hold_threshold_score:
                    decisions['hold'].append({
                        'symbol': symbol,
                        'qty': pos_info['qty'],
                        'market_value': pos_info['market_value'],
                        'pl_pct': pl_pct,
                        'new_score': new_score,
                        'reason': f'Score {new_score:.3f} >= seuil {self.hold_threshold_score}'
                    })
                    print(f"  ✅ HOLD {symbol}: Score={new_score:.3f}, P/L={pl_pct:+.2f}%")
                else:
                    # Score trop faible -> SELL
                    decisions['sell'].append({
                        'symbol': symbol,
                        'qty': pos_info['qty'],
                        'market_value': pos_info['market_value'],
                        'pl_pct': pl_pct,
                        'new_score': new_score,
                        'reason': f'Score {new_score:.3f} < seuil {self.hold_threshold_score}'
                    })
                    print(f"  🔴 SELL {symbol}: Score trop faible ({new_score:.3f})")
            else:
                # Position n'est plus dans les opportunités -> SELL
                pl_pct = pos_info['unrealized_plpc'] * 100
                decisions['sell'].append({
                    'symbol': symbol,
                    'qty': pos_info['qty'],
                    'market_value': pos_info['market_value'],
                    'pl_pct': pl_pct,
                    'new_score': None,
                    'reason': 'Plus dans top opportunités'
                })
                print(f"  🔴 SELL {symbol}: Plus dans le top (P/L={pl_pct:+.2f}%)")
        
        # 3. IDENTIFIER nouvelles opportunités (BUY)
        print(f"\n🟢 NOUVELLES OPPORTUNITÉS:")
        current_symbols = set(portfolio['positions'].keys())
        pending_symbols = set(portfolio['pending_orders'].keys())
        
        for symbol in opportunity_dict:
            if symbol not in current_symbols and symbol not in pending_symbols:
                opp = opportunity_dict[symbol]
                decisions['buy'].append({
                    'symbol': symbol,
                    'score': opp['composite_score'],
                    'confidence': opp.get('confidence', 0),
                    'reason': f"Nouvelle opportunité (score={opp['composite_score']:.3f})"
                })
                print(f"  🟢 BUY {symbol}: Score={opp['composite_score']:.3f}")
        
        return decisions
    
    def execute_decisions(self, decisions: Dict[str, List], max_investment: float = 1000.0):
        """
        Exécute les décisions de trading.
        
        Args:
            decisions: Dict avec hold/sell/buy/cancel
            max_investment: Investissement max par position
        """
        print(f"\n⚡ EXÉCUTION DES ORDRES")
        print(f"{'='*80}")
        
        executed = {
            'cancelled': 0,
            'sold': 0,
            'bought': 0,
            'held': 0,
            'errors': []
        }
        
        # 1. ANNULER ordres obsolètes
        print(f"\n🚫 Annulation de {len(decisions['cancel'])} ordres:")
        for cancel in decisions['cancel']:
            try:
                self.adapter.cancel_order(cancel['order_id'])
                print(f"  ✅ Cancelled {cancel['symbol']}: {cancel['reason']}")
                executed['cancelled'] += 1
            except Exception as e:
                error_msg = f"Failed to cancel {cancel['symbol']}: {e}"
                print(f"  ❌ {error_msg}")
                executed['errors'].append(error_msg)
        
        # 2. VENDRE positions à liquider
        print(f"\n🔴 Vente de {len(decisions['sell'])} positions:")
        for sell in decisions['sell']:
            try:
                order = self.adapter.place_order(
                    symbol=sell['symbol'],
                    qty=sell['qty'],
                    side='sell',
                    order_type='market'
                )
                print(f"  ✅ SELL {sell['symbol']}: {sell['qty']} shares (raison: {sell['reason']})")
                executed['sold'] += 1
            except Exception as e:
                error_msg = f"Failed to sell {sell['symbol']}: {e}"
                print(f"  ❌ {error_msg}")
                executed['errors'].append(error_msg)
        
        # 3. CONSERVER positions (rien à faire)
        print(f"\n✅ Conservation de {len(decisions['hold'])} positions:")
        for hold in decisions['hold']:
            print(f"  ✅ HOLD {hold['symbol']}: Score={hold['new_score']:.3f}, P/L={hold['pl_pct']:+.2f}%")
            executed['held'] += 1
        
        # 4. ACHETER nouvelles positions
        print(f"\n🟢 Achat de {len(decisions['buy'])} nouvelles positions:")
        
        # Récupérer cash disponible
        account = self.adapter.get_account()
        available_cash = float(account.get('cash', 0))
        
        if len(decisions['buy']) > 0:
            cash_per_position = min(max_investment, available_cash / len(decisions['buy']))
            print(f"  💰 Cash disponible: ${available_cash:.2f}")
            print(f"  💰 Par position: ${cash_per_position:.2f}")
            
            for buy in decisions['buy']:
                try:
                    # Calculer quantité basée sur cash_per_position
                    # Note: On utilise notional pour investir un montant fixe
                    order = self.adapter.place_order(
                        symbol=buy['symbol'],
                        notional=cash_per_position,
                        side='buy',
                        order_type='market'
                    )
                    print(f"  ✅ BUY {buy['symbol']}: ${cash_per_position:.2f} (score={buy['score']:.3f})")
                    executed['bought'] += 1
                except Exception as e:
                    error_msg = f"Failed to buy {buy['symbol']}: {e}"
                    print(f"  ❌ {error_msg}")
                    executed['errors'].append(error_msg)
        
        # Résumé
        print(f"\n📊 RÉSUMÉ EXÉCUTION:")
        print(f"  • Ordres annulés: {executed['cancelled']}")
        print(f"  • Positions vendues: {executed['sold']}")
        print(f"  • Positions conservées: {executed['held']}")
        print(f"  • Nouvelles positions: {executed['bought']}")
        print(f"  • Erreurs: {len(executed['errors'])}")
        
        if executed['errors']:
            print(f"\n⚠️  ERREURS:")
            for error in executed['errors']:
                print(f"  • {error}")
        
        return executed
    
    def run_full_cycle(self, analysis_csv: str, execute: bool = False, 
                       max_investment: float = 1000.0):
        """
        Cycle complet: analyse → décisions → exécution.
        
        Args:
            analysis_csv: Path vers CSV d'analyse
            execute: Si True, exécute les ordres, sinon dry-run
            max_investment: Investissement max par position
        """
        print(f"\n{'='*80}")
        print(f"🤖 PORTFOLIO MANAGER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        # 1. État actuel
        portfolio = self.get_current_portfolio()
        print(f"\n💼 ÉTAT ACTUEL:")
        print(f"  • Cash: ${portfolio['account']['cash']:,.2f}")
        print(f"  • Equity: ${portfolio['account']['equity']:,.2f}")
        print(f"  • Positions: {len(portfolio['positions'])}")
        print(f"  • Ordres en attente: {len(portfolio['pending_orders'])}")
        
        # 2. Charger analyse
        print(f"\n📂 Chargement analyse: {analysis_csv}")
        analysis_df = self.load_analysis_results(analysis_csv)
        print(f"  • Symboles analysés: {len(analysis_df)}")
        print(f"  • Top score: {analysis_df['composite_score'].max():.3f}")
        print(f"  • Score moyen: {analysis_df['composite_score'].mean():.3f}")
        
        # 3. Décisions
        decisions = self.make_decisions(portfolio, analysis_df)
        
        # 4. Exécution ou dry-run
        if execute:
            print(f"\n⚠️  MODE EXÉCUTION RÉEL")
            executed = self.execute_decisions(decisions, max_investment)
        else:
            print(f"\n🔍 MODE DRY-RUN (pas d'exécution réelle)")
            print(f"\n📋 RÉSUMÉ DES DÉCISIONS:")
            print(f"  • À annuler: {len(decisions['cancel'])}")
            print(f"  • À vendre: {len(decisions['sell'])}")
            print(f"  • À conserver: {len(decisions['hold'])}")
            print(f"  • À acheter: {len(decisions['buy'])}")
            
            if decisions['buy']:
                print(f"\n🟢 TOP 10 NOUVELLES OPPORTUNITÉS:")
                top_buys = sorted(decisions['buy'], key=lambda x: x['score'], reverse=True)[:10]
                for i, buy in enumerate(top_buys, 1):
                    print(f"  {i}. {buy['symbol']}: score={buy['score']:.3f}")
        
        print(f"\n{'='*80}")
        print(f"✅ CYCLE TERMINÉ")
        print(f"{'='*80}\n")


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Manager - Gestion intelligente du portefeuille')
    parser.add_argument('--analysis', type=str, required=True,
                       help='Path vers le CSV d\'analyse professionnelle')
    parser.add_argument('--execute', action='store_true',
                       help='Exécuter les ordres réellement (sinon dry-run)')
    parser.add_argument('--max-positions', type=int, default=200,
                       help='Nombre max de positions (défaut: 200)')
    parser.add_argument('--max-investment', type=float, default=1000.0,
                       help='Investissement max par position en $ (défaut: 1000)')
    parser.add_argument('--hold-threshold', type=float, default=0.0,
                       help='Score minimum pour HOLD (défaut: 0.0)')
    parser.add_argument('--mode', type=str, default='paper', choices=['paper', 'live'],
                       help='Mode Alpaca (défaut: paper)')
    
    args = parser.parse_args()
    
    # Créer manager
    manager = PortfolioManager(
        mode=args.mode,
        max_positions=args.max_positions,
        hold_threshold_score=args.hold_threshold
    )
    
    # Exécuter cycle
    manager.run_full_cycle(
        analysis_csv=args.analysis,
        execute=args.execute,
        max_investment=args.max_investment
    )


if __name__ == '__main__':
    main()
