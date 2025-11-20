from __future__ import annotations
from datetime import datetime

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline


def main():
    adapter = AlpacaAdapter.from_env(mode='paper')
    adapter.connect()
    try:
        pipeline = LiveTradingPipeline(
            broker_adapter=adapter,
            tickers=['AAPL','MSFT','NVDA','GOOGL','AMZN'],
            initial_capital=100000.0,
            strategy='factor_ensemble'
        )
        result = pipeline.run(force=True)
        print(result)
    finally:
        adapter.disconnect()


if __name__ == "__main__":
    main()
