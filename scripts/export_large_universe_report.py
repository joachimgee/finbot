#!/usr/bin/env python3
"""
Export Large Universe Report
===========================

Génère un rapport CSV détaillé pour chaque ticker analysé lors du run massif :
- Signal momentum
- Poids optimal (PyPortfolioOpt)
- Quantité cible
- Quantité actuelle
- Delta
- Statut d'ordre
- Order ID

Usage :
    python scripts/export_large_universe_report.py --limit 3000 --top 50 --days 180 --chunk 50 --mode paper --timeframe 1d --output report_large_universe.csv

Author: FinBot
Date: 2025-11-17
"""

import os
from pathlib import Path

# Charger .env AVANT tous les imports
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

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.portfolio_optimization.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
from financial_analyzer.trading.account_monitor import AccountMonitor
from financial_analyzer.trading.risk_guard import RiskGuard, RiskLimitExceeded, CircuitBreakerTriggered

# Import Equities correctement
try:
    from financedatabase import Equities
except Exception:
    Equities = None

# Sélection d'univers

def select_universe(limit: int) -> list:
    if Equities is None:
        return ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AVGO","CRM","AMD","ADBE"][:limit]
    try:
        eq = Equities()
        df = eq.search(country="United States", sector="Technology")
        if df is None or df.empty:
            return ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AVGO","CRM","AMD","ADBE"][:limit]
        # Filtrer uniquement symboles US (pas de points, pas de tirets multiples)
        symbols = []
        for sym in df.index:
            if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 5:
                symbols.append(sym)
            if len(symbols) >= limit:
                break
        return symbols if symbols else ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AVGO","CRM","AMD","ADBE"][:limit]
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

def build_prices_frame(bars_dict):
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
    p.add_argument("--output", type=str, default="report_large_universe.csv")
    args = p.parse_args()

    adapter = AlpacaAdapter.from_env(mode=args.mode)
    adapter.connect()

    try:
        tickers = select_universe(args.limit)
        print(f"Selected {len(tickers)} tickers from universe")
        end = datetime.now()
        start = end - timedelta(days=args.days)
        
        # Fetch bars with error handling per symbol
        print(f"Fetching bars from {start.date()} to {end.date()} (timeframe={args.timeframe})...")
        bars = {}
        failed = []
        for i in range(0, len(tickers), args.chunk):
            batch = tickers[i:i + args.chunk]
            try:
                batch_bars = adapter.get_bars_multi(batch, start, end, timeframe=args.timeframe, chunk_size=len(batch))
                bars.update(batch_bars)
                print(f"Progress: {len(bars)}/{len(tickers)} symbols fetched ({len(failed)} failed)")
            except Exception as e:
                # If batch fails, try symbols individually
                print(f"Batch {i}-{i+len(batch)} failed: {e}, trying individually...")
                for sym in batch:
                    try:
                        sym_bars = adapter.get_bars(sym, start, end, timeframe=args.timeframe)
                        if not sym_bars.empty:
                            bars[sym] = sym_bars
                    except Exception as e2:
                        failed.append(sym)
                        continue
        
        print(f"Successfully fetched {len(bars)} symbols, {len(failed)} failed")
        prices = build_prices_frame(bars)
        if prices.empty:
            raise RuntimeError("No prices retrieved for any symbol.")

        # Compute signals
        signals = {sym: momentum_signal(prices[sym].dropna()) for sym in prices.columns}
        top_syms = [s for s, sc in sorted(signals.items(), key=lambda x: x[1], reverse=True) if sc > 0][:args.top]
        sel_prices = prices[top_syms]

        # Optimize weights
        optimizer = PyPortfolioOptOptimizer(sel_prices)
        weights = optimizer.optimize_max_sharpe().clip(lower=0)
        weights = weights / weights.sum()

        monitor = AccountMonitor(adapter, initial_capital=100000)
        monitor.update()
        guard = RiskGuard(account_monitor=monitor)
        pv = monitor.portfolio_value
        latest_close = sel_prices.iloc[-1]
        curr = {pos['symbol']: pos for pos in monitor.positions}

        # Prepare report rows
        rows = []
        for sym in top_syms:
            w = float(weights.get(sym, 0))
            signal = float(signals.get(sym, 0))
            price = float(latest_close[sym])
            tgt_qty = int(max(0, np.floor(pv * w / max(price, 1e-6))))
            cur_qty = int(curr.get(sym, {}).get('qty', 0))
            delta = tgt_qty - cur_qty
            side = 'buy' if delta > 0 else ('sell' if delta < 0 else 'hold')
            status = 'not_submitted'
            order_id = ''
            reason = ''
            if delta != 0:
                try:
                    guard.validate_order(sym, abs(delta), side, price=price)
                    res = adapter.submit_order(sym, qty=abs(delta), side=side, order_type='market', time_in_force='day')
                    status = res.get('status', 'unknown')
                    order_id = res.get('order_id', '')
                    reason = f"Momentum={signal:.3f}, Weight={w:.3f}, Price={price:.2f}, Qty={tgt_qty}, Delta={delta}"
                except (RiskLimitExceeded, CircuitBreakerTriggered) as e:
                    status = 'risk_rejected'
                    reason = str(e)
            else:
                status = 'hold'
                reason = f"No delta (current={cur_qty}, target={tgt_qty})"
            rows.append({
                'symbol': sym,
                'momentum_signal': signal,
                'weight': w,
                'last_price': price,
                'target_qty': tgt_qty,
                'current_qty': cur_qty,
                'delta': delta,
                'side': side,
                'order_status': status,
                'order_id': order_id,
                'reason': reason
            })

        # Export CSV
        df_report = pd.DataFrame(rows)
        df_report.to_csv(args.output, index=False)
        print(f"Rapport exporté: {args.output} ({len(rows)} tickers)")

    finally:
        adapter.disconnect()

if __name__ == "__main__":
    main()
