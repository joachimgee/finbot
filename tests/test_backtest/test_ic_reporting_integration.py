import pandas as pd
import numpy as np
from financial_analyzer.backtest.backtester import BacktestRunner, CustomStrategy


class DummyStrategy(CustomStrategy):
    def init(self):
        pass
    def next(self):
        pass


def test_generate_ic_report_integration(tmp_path):
    # Build minimal OHLCV to init runner (single asset)
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    ohlcv = pd.DataFrame({
        'Open': np.linspace(100, 101, len(dates)),
        'High': np.linspace(101, 102, len(dates)),
        'Low': np.linspace(99, 100, len(dates)),
        'Close': np.linspace(100, 101, len(dates)),
        'Volume': np.arange(len(dates)) + 1000,
    }, index=dates)

    runner = BacktestRunner(ohlcv, DummyStrategy)

    # Build cross-sectional matrices for IC
    assets = [f"S{i}" for i in range(10)]
    fac = pd.DataFrame(np.random.default_rng(0).normal(0,1,(len(dates), len(assets))), index=dates, columns=assets)
    fwd = fac.shift(-1).fillna(0) + np.random.default_rng(1).normal(0,0.3,(len(dates), len(assets)))

    out = runner.generate_ic_report(fac, fwd, max_horizon=3, out_html_path=str(tmp_path/"ic.html"))
    assert 'summary' in out and 'decay' in out and 'html' in out
    assert (tmp_path/"ic.html").exists()
