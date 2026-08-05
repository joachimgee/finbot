#!/usr/bin/env python3
"""
Daily Professional Manager

- Runs professional analysis across global Universe (FinanceDatabase) in batches
- Filters to Alpaca-tradable tickers
- Builds target portfolio (top N by score) and applies to Alpaca Paper Trading
- Runs once per day (loop) or single-run with --dry-run

Usage:
    python scripts/run_daily_professional_manager.py --dry-run --limit 50
    python scripts/run_daily_professional_manager.py --top 100 --batch-size 500

"""
from __future__ import annotations
import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict

# Ensure src is importable
sys.path.insert(0, '/workspaces/finbot')
sys.path.insert(0, '/workspaces/finbot/src')

from financedatabase import Equities
import pandas as pd
import numpy as np

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.portfolio_optimization.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
from financial_analyzer.risk.var_backtest import backtest_multi_methods

# Import scoring function from professional_analysis
from scripts.professional_analysis import compute_professional_score

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('daily_manager')


def get_global_universe(limit: int = 20000, regions: List[str] | None = None) -> List[str]:
    """Fetch global tickers from FinanceDatabase. Limit is number of tickers returned.
    If regions provided, fetch for each region (country codes or names).
    """
    eq = Equities()
    symbols: List[str] = []

    if regions is None:
        # Search all equities
        df = eq.search()
        if df is None or df.empty:
            return []
        for sym in df.index:
            if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 6:
                symbols.append(sym)
            if len(symbols) >= limit:
                break
        return symbols

    # If regions specified
    for r in regions:
        df = eq.search(country=r)
        if df is None or df.empty:
            continue
        for sym in df.index:
            if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 6:
                symbols.append(sym)
            if len(symbols) >= limit:
                break
        if len(symbols) >= limit:
            break
    return symbols


def is_tradable_on_alpaca(alpaca: AlpacaAdapter, symbol: str) -> bool:
    """Try to check if Alpaca accepts the symbol. Uses get_asset or get_latest_quote fallback."""
    try:
        # AlpacaAdapter may have get_asset or get_latest_quote
        if hasattr(alpaca, 'get_asset'):
            asset = alpaca.get_asset(symbol)
            return bool(asset)
        else:
            q = alpaca.get_latest_quote(symbol)
            return q is not None and 'price' in q and q['price'] is not None
    except Exception:
        return False


def batch(iterable, n=1000):
    l = len(iterable)
    for i in range(0, l, n):
        yield iterable[i:i+n]


def fetch_prices_for_batch(market_data: MarketDataFetcher, tickers: List[str], days: int = 180) -> pd.DataFrame:
    """Fetch close prices for tickers via MarketDataFetcher with fallback to yfinance/Alpaca.
    Returns DataFrame with columns=tickers and index dates.
    """
    end = datetime.utcnow()
    start = end - pd.Timedelta(days=days)

    all_series = {}
    for t in tickers:
        try:
            df = market_data.get_historical_data(t, start_date=start.strftime('%Y-%m-%d'), end_date=end.strftime('%Y-%m-%d'))
            if df is not None and 'Close' in df.columns:
                s = df['Close'].rename(t)
                all_series[t] = s
        except Exception:
            continue
    if not all_series:
        return pd.DataFrame()
    prices = pd.concat(all_series.values(), axis=1)
    return prices


def compute_scores_for_universe(market_data: MarketDataFetcher, universe: List[str], batch_size: int = 500) -> pd.DataFrame:
    """Compute professional scores for all tickers in universe in batches.
    Returns DataFrame with columns ['symbol','score'] sorted by score desc.
    """
    results = []
    logger.info(f"Computing scores for universe of size {len(universe)} in batches of {batch_size}...")
    for b in batch(universe, batch_size):
        prices = fetch_prices_for_batch(market_data, b, days=365)
        if prices.empty:
            logger.info(f"Batch returned no data (size={len(b)})")
            continue
        for sym in prices.columns:
            try:
                bars = pd.DataFrame({
                    'close': prices[sym].dropna(),
                    'open': prices[sym].dropna(),
                    'high': prices[sym].dropna() * 1.01,
                    'low': prices[sym].dropna() * 0.99,
                    'volume': 100000
                })
                score = compute_professional_score(sym, bars)
                # compute_professional_score returns dict in professional_analysis; support both
                if isinstance(score, dict):
                    s = score.get('composite_score') or score.get('composite') or 0.0
                else:
                    s = float(score)
                results.append((sym, s))
            except Exception:
                continue
    df = pd.DataFrame(results, columns=['symbol', 'score'])
    df = df.sort_values('score', ascending=False).reset_index(drop=True)
    return df


def build_and_apply_portfolio(alpaca: AlpacaAdapter, market_data: MarketDataFetcher, scores_df: pd.DataFrame, top_n: int = 100, dry_run: bool = True):
    """Select top_n tradable tickers and apply portfolio on Alpaca.
    Uses simple weight = score positive normalized. If PyPortfolioOpt present, optional optimization.
    """
    # Filter positive scores
    if scores_df.empty:
        logger.warning('Empty scores_df, nothing to do.')
        return

    # Keep only positive scores
    candidates = scores_df[scores_df['score'] > 0].copy()
    if candidates.empty:
        logger.warning('No positive scores to invest in.')
        return

    # Filter tradable on Alpaca
    tradable = []
    for sym in candidates['symbol'].tolist():
        if is_tradable_on_alpaca(alpaca, sym):
            tradable.append(sym)
        if len(tradable) >= top_n * 3:
            break
    logger.info(f"Found {len(tradable)} tradable candidates (will select top {top_n})")

    # Narrow to top_n by score
    tradable_df = candidates[candidates['symbol'].isin(tradable)].head(top_n)
    if tradable_df.empty:
        logger.warning('No tradable tickers after filtering')
        return

    # Simple weighting
    weights = tradable_df['score'].clip(lower=0)
    weights = weights / weights.sum()
    weights.index = tradable_df['symbol'].values

    # Get account value
    acct = alpaca.get_account()
    try:
        portfolio_value = float(acct.get('portfolio_value', acct.get('equity', 0)))
    except Exception:
        portfolio_value = 10000.0
    logger.info(f"Portfolio value: ${portfolio_value:,.2f}")

    # Build target dollar allocations
    target_values = weights * portfolio_value

    # Get current positions
    current_positions = {p['symbol']: float(p['market_value']) for p in alpaca.get_positions()}

    # Close positions not in target
    current_syms = set(current_positions.keys())
    target_syms = set(weights.index.tolist())

    to_close = current_syms - target_syms
    for s in to_close:
        try:
            if dry_run:
                logger.info(f"DRY RUN: Would close position {s}")
            else:
                alpaca.close_position(s)
                logger.info(f"Closed position {s}")
        except Exception as e:
            logger.warning(f"Failed to close {s}: {e}")

    # Place/update orders for target
    for sym, w in weights.items():
        tval = target_values.loc[sym]
        try:
            # get latest price
            q = alpaca.get_latest_quote(sym)
            price = float(q.get('price') or q.get('last') or 0)
            if price <= 0:
                logger.warning(f"Invalid price for {sym}, skipping")
                continue
            qty = int(np.floor(tval / price))
            if qty <= 0:
                logger.info(f"Target value for {sym} too small (${tval:.2f}), skipping")
                continue
            if dry_run:
                logger.info(f"DRY RUN: Would submit MARKET BUY {qty} {sym} (@ ${price:.2f}) => ${qty*price:.2f}")
            else:
                order = alpaca.submit_order(symbol=sym, qty=qty, side='buy', order_type='market', time_in_force='day')
                logger.info(f"Order submitted: {sym} qty={qty} order_id={order.get('order_id')}")
        except Exception as e:
            logger.warning(f"Failed to submit order for {sym}: {e}")

    logger.info('Portfolio apply completed')


def main():
    # DEPRECATED: this script submits orders directly, bypassing the OrderGateway
    # safety chokepoint. Use scripts/professional_analysis_daemon.py (routes every
    # order through OrderGateway). Refuse to run unless explicitly overridden.
    if os.environ.get("FINBOT_ALLOW_DEPRECATED_SCRIPTS") != "1":
        print(
            "DEPRECATED: run_daily_professional_manager.py bypasses the OrderGateway "
            "safety chokepoint. Use scripts/professional_analysis_daemon.py instead. "
            "Set FINBOT_ALLOW_DEPRECATED_SCRIPTS=1 to override (not recommended).",
            file=sys.stderr,
        )
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Do not submit orders to Alpaca')
    parser.add_argument('--limit', type=int, default=5000, help='Max tickers to analyze (global)')
    parser.add_argument('--batch-size', type=int, default=500, help='Batch size for analysis')
    parser.add_argument('--top', type=int, default=100, help='Top N to trade')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--sleep-hours', type=int, default=24, help='Hours between runs')
    args = parser.parse_args()

    # Sanitize potential quoted env vars (some .env entries include quotes)
    for key in ('APCA_API_BASE_URL', 'APCA_API_KEY_ID', 'APCA_API_SECRET_KEY'):
        if os.getenv(key):
            os.environ[key] = os.getenv(key).strip().strip('"').strip("'")

    # Alpaca connection
    alpaca = AlpacaAdapter.from_env(mode='paper')
    if not alpaca:
        logger.error('AlpacaAdapter.from_env() failed')
        return
    alpaca.connect()

    market_data = MarketDataFetcher()

    logger.info('Starting daily professional manager')

    while True:
        start_ts = datetime.utcnow()
        logger.info(f'Run started at {start_ts.isoformat()}')

        # Get universe
        universe = get_global_universe(limit=args.limit)
        logger.info(f'Universe loaded: {len(universe)} symbols')

        # Compute scores
        scores_df = compute_scores_for_universe(market_data, universe, batch_size=args.batch_size)
        logger.info(f'Scores computed for {len(scores_df)} symbols')

        # Apply to Alpaca (dry-run default)
        build_and_apply_portfolio(alpaca, market_data, scores_df, top_n=args.top, dry_run=args.dry_run)

        end_ts = datetime.utcnow()
        elapsed = (end_ts - start_ts).total_seconds()
        logger.info(f'Run completed in {elapsed/60:.2f} minutes')

        if args.once:
            break

        # Sleep until next run
        logger.info(f'Sleeping for {args.sleep_hours} hours...')
        time.sleep(args.sleep_hours * 3600)


if __name__ == '__main__':
    main()
