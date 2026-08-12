#!/usr/bin/env python3
from __future__ import annotations
"""
Paper trading run on a large universe using Alpaca (paper mode).

- Universe: FinanceDatabase (US Technology) with limit N
- Data: Alpaca get_bars_multi in chunks
- Signal: 20D momentum
- Weights: PyPortfolioOpt Max Sharpe on selected top-N
- Orders: Market orders with RiskGuard validation

Usage:
    export APCA_API_KEY_ID=...; export APCA_API_SECRET_KEY=...
    python scripts/paper_large_universe_run.py --limit 1000 --top 50 --days 180 --chunk 50

Notes:
- Starts with a large candidate set, selects top by momentum, allocates via PFO.
- Always use paper mode unless you explicitly pass --live.
"""

import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import numpy as np
import pandas as pd

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.account_monitor import AccountMonitor
from financial_analyzer.trading.risk_guard import RiskGuard, RiskLimitExceeded, CircuitBreakerTriggered

try:
    from financedatabase import Equities
except Exception:
    Equities = None

from financial_analyzer.portfolio.pyportfolioopt_optimizer import PyPortfolioOptOptimizer


def select_universe(limit: int) -> List[str]:
    if Equities is None:
        # Fallback minimal
        return ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AVGO","CRM","AMD","ADBE"][:limit]
    try:
        eq = Equities()
        df = eq.search(country="United States", sector="Technology")
        if df is None or df.empty:
            return ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AVGO","CRM","AMD","ADBE"][:limit]
        return list(df.index)[:limit]
    except Exception:
        return ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AVGO","CRM","AMD","ADBE"][:limit]


def momentum_signal(close: pd.Series, window: int = 20) -> float:
    if len(close) < window + 1:
        return 0.0
    try:
        ret = float(close.iloc[-1] / close.iloc[-window] - 1.0)
        return float(np.tanh(ret * 10))
    except Exception:
        return 0.0


def build_prices_frame(bars_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for sym, df in bars_dict.items():
        if df is None or df.empty or 'close' not in df.columns:
            continue
        s = df['close'].rename(sym)
        frames.append(s)
    if not frames:
        return pd.DataFrame()
    dfp = pd.concat(frames, axis=1).sort_index()
    dfp = dfp.dropna(axis=1, how='any')
    return dfp


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--chunk", type=int, default=50)
    p.add_argument("--mode", type=str, default="paper", choices=["paper","live"])
    p.add_argument("--timeframe", type=str, default="1D")
    args = p.parse_args()

    adapter = AlpacaAdapter.from_env(mode=args.mode)
    adapter.connect()

    try:
        tickers = select_universe(args.limit)
        end = datetime.now()
        start = end - timedelta(days=args.days)

        # Fetch bars in batches
        bars = adapter.get_bars_multi(tickers, start, end, timeframe=args.timeframe, chunk_size=args.chunk)
        # Build prices DataFrame
        prices = build_prices_frame(bars)
        if prices.empty:
            raise RuntimeError("No prices retrieved for any symbol.")

        # Compute signals and select top
        scores = {sym: momentum_signal(prices[sym].dropna()) for sym in prices.columns}
        top_syms = [s for s, sc in sorted(scores.items(), key=lambda x: x[1], reverse=True) if sc > 0][:args.top]
        if not top_syms:
            print("No positive momentum; exiting without trades.")
            return

        sel_prices = prices[top_syms]
        # Optimize weights via PyPortfolioOpt
        optimizer = PyPortfolioOptOptimizer(sel_prices)
        weights = optimizer.optimize_max_sharpe()
        weights = weights.clip(lower=0)
        weights = weights / weights.sum()

        # Account monitor and risk guard
        monitor = AccountMonitor(adapter, initial_capital=100000)
        monitor.update()
        guard = RiskGuard(account_monitor=monitor)

        pv = monitor.portfolio_value
        latest_close = sel_prices.iloc[-1]

        # Compute target shares
        target_shares = {}
        for sym, w in weights.items():
            dollar = float(pv * float(w))
            price = float(latest_close[sym])
            qty = int(max(0, np.floor(dollar / max(price, 1e-6))))
            target_shares[sym] = qty

        # Current positions map
        curr = {pos['symbol']: pos for pos in monitor.positions}

        orders_submitted = []
        for sym, tgt_qty in target_shares.items():
            cur_qty = int(curr.get(sym, {}).get('qty', 0))
            delta = tgt_qty - cur_qty
            if delta == 0:
                continue
            side = 'buy' if delta > 0 else 'sell'
            qty = abs(delta)
            price = float(latest_close[sym])

            # Risk validation
            try:
                guard.validate_order(sym, qty, side, price=price)
            except (RiskLimitExceeded, CircuitBreakerTriggered) as e:
                print(f"Risk rejected {sym} {side} {qty}: {e}")
                continue

            # Submit order (market)
            res = adapter.submit_order(sym, qty=qty, side=side, order_type='market', time_in_force='day')
            orders_submitted.append(res)
            print(f"Submitted {side} {qty} {sym}: {res['status']} id={res['order_id']}")

        print(f"Total orders submitted: {len(orders_submitted)}")

    finally:
        adapter.disconnect()


if __name__ == "__main__":
    main()
