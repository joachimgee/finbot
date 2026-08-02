#!/usr/bin/env python3
"""Debug Live Trading Pipeline.

Outil interactif pour diagnostiquer:
- Chargement configuration
- Connexion broker
- Statut compte & positions
- Exécution pipeline (dry-run & forced)
- Inspection détails internes

Usage:
    python scripts/debug_pipeline.py --config config/live_trading.yaml
    python scripts/debug_pipeline.py --config config/live_trading.yaml --force
    python scripts/debug_pipeline.py --config config/live_trading.yaml --dry-run

Notes:
    Charge automatiquement .env (python-dotenv).
    Affiche logs en DEBUG pour visibilité complète.
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Load .env
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from financial_analyzer.trading import (
    AlpacaAdapter,
    LiveTradingPipeline,
    TradingSchedule
)

SEPARATOR = "=" * 80


def setup_logging(verbose: bool = True) -> logging.Logger:
    logger = logging.getLogger()
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    fmt = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s | %(message)s', '%H:%M:%S')
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    ch.setLevel(level)
    if not logger.handlers:
        logger.addHandler(ch)
    return logging.getLogger(__name__)


def load_config(path: str) -> Dict[str, Any]:
    import yaml
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config introuvable: {path}")
    with open(p, 'r') as fh:
        return yaml.safe_load(fh)


def print_header(title: str) -> None:
    print(f"\n{SEPARATOR}\n{title}\n{SEPARATOR}")


def init_broker(config: Dict[str, Any]) -> AlpacaAdapter:
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    if not api_key or not secret_key:
        raise ValueError("Clés Alpaca manquantes dans .env (ALPACA_API_KEY / ALPACA_SECRET_KEY)")
    broker_cfg = config['broker']
    mode = 'paper' if broker_cfg.get('paper', True) else 'live'
    adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key, mode=mode)
    print(f"Adapter initialisé: mode={mode}")
    return adapter


def init_pipeline(broker: AlpacaAdapter, config: Dict[str, Any]) -> LiveTradingPipeline:
    account = broker.get_account()
    schedule_cfg = config['schedule']
    schedule = TradingSchedule(
        execution_time=schedule_cfg.get('execution_time', '09:35'),
        frequency=schedule_cfg.get('frequency', 'daily'),
        day_of_week=schedule_cfg.get('day_of_week'),
        day_of_month=schedule_cfg.get('day_of_month'),
        enabled=schedule_cfg.get('enabled', True)
    )
    pipeline = LiveTradingPipeline(
        broker_adapter=broker,
        tickers=config['tickers'],
        initial_capital=float(account['portfolio_value']),
        strategy=config.get('strategy', 'factor_ensemble'),
        risk_config=config['risk'],
        schedule_config=schedule,
        enable_logging=True
    )
    return pipeline


def inspect_state(pipeline: LiveTradingPipeline) -> None:
    state = pipeline.get_status()
    print_header("PIPELINE STATE")
    print(f"Portfolio Value: ${state['portfolio']['portfolio_value']:.2f}")
    print(f"Positions: {state['portfolio']['num_positions']}")
    print(f"Circuit Breaker Active: {state['circuit_breaker_active']}")
    print(f"Risk Metrics: {state['risk_metrics']}")


def run_debug(pipeline: LiveTradingPipeline, force: bool, dry_run: bool) -> None:
    print_header("PIPELINE EXECUTION")
    if dry_run:
        print("Mode DRY-RUN: génération statuts sans exécution réelle.")
        inspect_state(pipeline)
        return
    result = pipeline.run(force=force)
    print(f"Status: {result['status']}")
    if result['status'] != 'failed':
        print(f"Orders Generated: {result.get('orders_generated', 0)}")
        print(f"Orders Executed: {result.get('orders_executed', 0)}")
        print(f"Orders Rejected: {result.get('orders_rejected', 0)}")
    else:
        print(f"Reason: {result['reason']}")
    print("Portfolio Value:", f"${result['portfolio_value']:.2f}")
    print("Daily PnL:", f"${result['daily_pnl']:+.2f}")

    if result.get('execution_results'):
        print_header("ORDER DETAILS")
        for i, exec_result in enumerate(result['execution_results'], 1):
            order = exec_result['order']
            st = exec_result['status']
            reason = exec_result.get('reason')
            line = f"[{i}] {order['symbol']} {order['side']} {order['qty']} @ {order['price']:.2f} => {st}"
            if reason:
                line += f" ({reason})"
            print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug pipeline de trading live")
    parser.add_argument('--config', required=True, help='Chemin fichier de config YAML')
    parser.add_argument('--force', action='store_true', help='Ignorer schedule et heures de marché')
    parser.add_argument('--dry-run', action='store_true', help='Sans exécution, affichage état uniquement')
    parser.add_argument('--no-verbose', action='store_true', help='Réduire logs (INFO au lieu de DEBUG)')
    args = parser.parse_args()

    setup_logging(verbose=not args.no_verbose)

    print_header("DEBUG PIPELINE")
    print(f"Config: {args.config}")
    print(f"Force: {args.force}")
    print(f"Dry-run: {args.dry_run}")
    print(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}")

    try:
        config = load_config(args.config)
        print("✓ Configuration chargée")
    except Exception as e:
        print(f"❌ Erreur chargement config: {e}")
        return 1

    try:
        broker = init_broker(config)
        print("✓ Broker initialisé")
    except Exception as e:
        print(f"❌ Erreur initialisation broker: {e}")
        return 2

    try:
        pipeline = init_pipeline(broker, config)
        print("✓ Pipeline initialisé")
    except Exception as e:
        print(f"❌ Erreur initialisation pipeline: {e}")
        return 3

    try:
        inspect_state(pipeline)
        run_debug(pipeline, force=args.force, dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Erreur exécution pipeline: {e}")
        return 4

    print_header("DEBUG COMPLETE")
    print("Utilisez scripts/verify_alpaca_orders.py pour vérifier ordres.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
