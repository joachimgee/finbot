#!/usr/bin/env python3
"""
Live Trading Execution Script.

CLI tool for running FinBot live trading pipeline.
Supports:
- YAML configuration
- Scheduled execution (cron-compatible)
- Console and file logging
- Signal handling (graceful shutdown)
- Dry-run mode

Usage:
    # Run with config
    python scripts/run_live_trading.py --config config/live_trading.yaml
    
    # Dry run (test without execution)
    python scripts/run_live_trading.py --config config/live_trading.yaml --dry-run
    
    # Force execution (ignore schedule/market hours)
    python scripts/run_live_trading.py --config config/live_trading.yaml --force
    
    # Set up cron job (daily at 9:35 AM ET)
    35 9 * * 1-5 cd /path/to/finbot && python scripts/run_live_trading.py --config config/live_trading.yaml >> logs/cron.log 2>&1
"""

import argparse
import logging
import os
import signal
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from financial_analyzer.trading import (
    AlpacaAdapter,
    LiveTradingPipeline,
    TradingSchedule
)

# Auto-load .env for credentials (ALPACA_API_KEY, etc.)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
    logging.getLogger(__name__).debug(".env loaded successfully")
except Exception:
    # Silencieux si absence
    pass


# Global flag for graceful shutdown
SHUTDOWN_REQUESTED = False


def signal_handler(signum: int, frame: Any):
    """Handle SIGINT and SIGTERM for graceful shutdown."""
    global SHUTDOWN_REQUESTED
    signal_name = signal.Signals(signum).name
    logging.warning(f"Received {signal_name}, shutting down gracefully...")
    SHUTDOWN_REQUESTED = True


def setup_logging(log_file: Optional[str] = None, verbose: bool = False) -> logging.Logger:
    """
    Configure logging with console and optional file output.
    
    Args:
        log_file: Path to log file (optional)
        verbose: Enable DEBUG level logging
    
    Returns:
        Configured logger
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        logging.info(f"Logging to file: {log_file}")
    
    return logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file.
    
    Args:
        config_path: Path to YAML config
    
    Returns:
        Configuration dictionary
    
    Raises:
        FileNotFoundError: If config file not found
        yaml.YAMLError: If config is invalid
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Validate required sections
    required = ['broker', 'tickers', 'risk', 'schedule']
    missing = [section for section in required if section not in config]
    
    if missing:
        raise ValueError(f"Missing required config sections: {missing}")
    
    return config


def validate_api_credentials() -> Tuple[str, str]:
    """
    Validate Alpaca API credentials from environment.
    
    Returns:
        Tuple of (api_key, api_secret)
    
    Raises:
        ValueError: If credentials not found
    """
    api_key = os.getenv('ALPACA_API_KEY')
    api_secret = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not api_secret:
        raise ValueError(
            "Alpaca API credentials not found. "
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables."
        )
    
    return api_key, api_secret


def initialize_broker(config: Dict[str, Any]) -> AlpacaAdapter:
    """
    Initialize broker adapter from config.
    
    Args:
        config: Broker configuration
    
    Returns:
        Initialized BrokerAdapter
    
    Raises:
        Exception: If connection fails
    """
    api_key, api_secret = validate_api_credentials()
    
    broker_config = config['broker']
    mode = 'paper' if broker_config.get('paper', True) else 'live'
    
    logging.info(f"Connecting to Alpaca ({mode.upper()} Trading)...")
    
    broker = AlpacaAdapter(
        api_key=api_key,
        secret_key=api_secret,
        mode=mode
    )
    
    if not broker.connected:
        raise Exception("Failed to connect to broker")
    
    logging.info(f"✓ Connected to Alpaca (Account: {broker.account_id})")
    
    # Log account info
    account = broker.get_account()
    logging.info(f"Portfolio Value: ${float(account['portfolio_value']):,.2f}")
    logging.info(f"Cash: ${float(account['cash']):,.2f}")
    logging.info(f"Buying Power: ${float(account['buying_power']):,.2f}")
    
    return broker


def initialize_pipeline(
    broker: AlpacaAdapter,
    config: Dict[str, Any]
) -> LiveTradingPipeline:
    """
    Initialize live trading pipeline from config.
    
    Args:
        broker: Connected broker adapter
        config: Full configuration dict
    
    Returns:
        Initialized LiveTradingPipeline
    """
    # Get account info for initial capital
    account = broker.get_account()
    initial_capital = float(account['portfolio_value'])
    
    # Extract config sections
    tickers = config['tickers']
    risk_config = config['risk']
    schedule_config = config['schedule']
    
    # Create schedule
    schedule = TradingSchedule(
        execution_time=schedule_config.get('execution_time', '09:35'),
        frequency=schedule_config.get('frequency', 'daily'),
        day_of_week=schedule_config.get('day_of_week'),
        day_of_month=schedule_config.get('day_of_month'),
        enabled=schedule_config.get('enabled', True)
    )
    
    logging.info(f"Schedule: {schedule.frequency} at {schedule.execution_time} ET")
    logging.info(f"Tickers: {', '.join(tickers)}")
    
    # Initialize pipeline
    pipeline = LiveTradingPipeline(
        broker_adapter=broker,
        tickers=tickers,
        initial_capital=initial_capital,
        strategy=config.get('strategy', 'factor_ensemble'),
        risk_config=risk_config,
        schedule_config=schedule,
        enable_logging=True
    )
    
    logging.info("✓ Pipeline initialized successfully")
    
    # Log risk config
    logging.info("Risk Configuration:")
    logging.info(f"  Max Position Size: ${risk_config.get('max_position_size', 0):,.0f}")
    logging.info(f"  Max Concentration: {risk_config.get('max_position_pct', 0):.0%}")
    logging.info(f"  Max Positions: {risk_config.get('max_total_positions', 0)}")
    logging.info(f"  Drawdown Limit: {risk_config.get('max_drawdown', 0):.0%}")
    logging.info(f"  Daily Loss Limit: ${risk_config.get('max_daily_loss', 0):,.0f}")
    
    return pipeline


def log_execution_result(result: Dict[str, Any]):
    """
    Log pipeline execution result.
    
    Args:
        result: Execution result dictionary
    """
    status = result['status']
    
    if status == 'success':
        logging.info("✓ Execution SUCCESSFUL")
        logging.info(f"Orders Generated: {result.get('orders_generated', 0)}")
        logging.info(f"Orders Executed: {result.get('orders_executed', 0)}")
        logging.info(f"Orders Rejected: {result.get('orders_rejected', 0)}")
        
        # Log order details
        if result.get('execution_results'):
            logging.info("\nOrder Details:")
            for i, exec_result in enumerate(result['execution_results'], 1):
                order = exec_result['order']
                status = exec_result['status']
                
                log_msg = (
                    f"  [{i}] {order['symbol']} {order['side'].upper()} "
                    f"{order['qty']} @ ${order['price']:.2f} - {status.upper()}"
                )
                
                if status == 'rejected':
                    log_msg += f" ({exec_result.get('reason', 'Unknown')})"
                
                logging.info(log_msg)
    
    elif status == 'skipped':
        logging.warning(f"⚠️  Execution SKIPPED: {result['reason']}")
    
    elif status == 'failed':
        logging.error(f"✗ Execution FAILED: {result['reason']}")
    
    # Log portfolio metrics
    logging.info(f"\nPortfolio Metrics:")
    logging.info(f"  Value: ${result['portfolio_value']:,.2f}")
    logging.info(f"  Daily P&L: ${result['daily_pnl']:+,.2f}")
    logging.info(f"  Positions: {result['num_positions']}")


def main():
    """Main execution function."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='FinBot Live Trading Execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to YAML configuration file'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        help='Path to log file (optional, default: logs/live_trading_YYYYMMDD.log)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force execution (ignore schedule and market hours)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (test without actual execution)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )
    
    args = parser.parse_args()
    
    # Setup default log file if not specified
    if not args.log_file:
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d')
        args.log_file = str(log_dir / f'live_trading_{timestamp}.log')
    
    # Setup logging
    logger = setup_logging(args.log_file, args.verbose)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 80)
    logger.info("FinBot Live Trading Pipeline - Starting")
    logger.info("=" * 80)
    logger.info(f"Config: {args.config}")
    logger.info(f"Force Execution: {args.force}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Timestamp: {datetime.now()}")
    
    try:
        # Load configuration
        logger.info("\n[1/4] Loading configuration...")
        config = load_config(args.config)
        logger.info(f"✓ Config loaded from {args.config}")
        
        # Check for shutdown signal
        if SHUTDOWN_REQUESTED:
            logger.warning("Shutdown requested, exiting")
            return 0
        
        # Initialize broker
        logger.info("\n[2/4] Connecting to broker...")
        broker = initialize_broker(config)
        
        # Check for shutdown signal
        if SHUTDOWN_REQUESTED:
            logger.warning("Shutdown requested, exiting")
            return 0
        
        # Initialize pipeline
        logger.info("\n[3/4] Initializing pipeline...")
        pipeline = initialize_pipeline(broker, config)
        
        # Dry run mode
        if args.dry_run:
            logger.info("\n[DRY RUN] Skipping execution")
            status = pipeline.get_status()
            
            logger.info("\nCurrent Status:")
            logger.info(f"  Portfolio Value: ${status['portfolio']['portfolio_value']:,.2f}")
            logger.info(f"  Positions: {status['portfolio']['num_positions']}")
            logger.info(f"  Circuit Breaker: {'ACTIVE' if status['circuit_breaker_active'] else 'OK'}")
            
            logger.info("\n✓ Dry run complete (no orders executed)")
            return 0
        
        # Check for shutdown signal
        if SHUTDOWN_REQUESTED:
            logger.warning("Shutdown requested, exiting")
            return 0
        
        # Execute pipeline
        logger.info("\n[4/4] Executing pipeline...")
        result = pipeline.run(force=args.force)
        
        # Log results
        logger.info("")
        log_execution_result(result)
        
        # Success
        logger.info("\n" + "=" * 80)
        logger.info("FinBot Live Trading Pipeline - Complete")
        logger.info("=" * 80)
        
        return 0 if result['status'] in ('success', 'skipped') else 1
    
    except KeyboardInterrupt:
        logger.warning("\nExecution interrupted by user")
        return 130  # Standard exit code for SIGINT
    
    except Exception as e:
        logger.error(f"\n✗ Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
