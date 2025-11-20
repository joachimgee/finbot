import types
import pandas as pd
import numpy as np
import datetime as dt

import importlib


def make_dummy_bars(n=30):
    dates = pd.date_range(end=dt.datetime.now(), periods=n, freq="B")
    base = 100 + np.cumsum(np.random.randn(len(dates)))
    close = pd.Series(base).clip(lower=1)
    open_ = close * (1 + np.random.randn(len(dates)) * 0.002)
    high = np.maximum(open_, close) * (1 + np.abs(np.random.randn(len(dates)) * 0.003))
    low = np.minimum(open_, close) * (1 - np.abs(np.random.randn(len(dates)) * 0.003))
    volume = (1e6 + np.random.randn(len(dates)) * 1e5).clip(min=1e3).astype(int)
    return pd.DataFrame({
        'open': open_.values,
        'high': high.values,
        'low': low.values,
        'close': close.values,
        'volume': volume
    }, index=dates)


def test_phase1_fallback_universe(monkeypatch):
    e2e = importlib.import_module('scripts.comprehensive_e2e_backtest')

    class DummyMarketSelector:
        def get_universe(self, **kwargs):
            return []

    class DummyAlpaca:
        def __init__(self, *args, **kwargs):
            pass
        def connect(self):
            return True
        def get_bars(self, symbol, start, end, timeframe='1D'):
            return pd.DataFrame()  # force synthetic path

    monkeypatch.setattr(e2e, 'MarketSelector', DummyMarketSelector)
    monkeypatch.setattr(e2e, 'AlpacaAdapter', DummyAlpaca)

    runner = e2e.ComprehensiveE2EBacktester()
    data = runner.test_phase1_universe()
    assert isinstance(data, dict)
    assert len(data) >= 1
    # Fallback tickers should be present
    fallback = {'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'}
    assert len(fallback.intersection(set(data.keys()))) >= 1


def test_phase2_uses_phase1_tickers(monkeypatch):
    e2e = importlib.import_module('scripts.comprehensive_e2e_backtest')

    # Build phase1 data explicitly
    data = {
        'FAKE1': make_dummy_bars(40),
        'FAKE2': make_dummy_bars(40),
    }

    # Mock sentiment analyzer to avoid external dependencies and ensure deterministic output
    class DummyAnalyzer:
        def analyze_single(self, text):
            return {'score': 0.1, 'label': 'positive', 'confidence': 0.9}

    monkeypatch.setattr(e2e, 'FinancialSentimentAnalyzer', lambda: DummyAnalyzer())

    runner = e2e.ComprehensiveE2EBacktester()
    res = runner.test_phase2_sentiment(list(data.keys()))
    assert set(res.keys()) == set(data.keys())


def test_phase3_technical_with_synthetic_data():
    e2e = importlib.import_module('scripts.comprehensive_e2e_backtest')
    runner = e2e.ComprehensiveE2EBacktester()
    data = {
        'FAKE1': make_dummy_bars(60),
        'FAKE2': make_dummy_bars(60),
    }
    tech = runner.test_phase3_technical(data)
    assert isinstance(tech, dict)
    assert len(tech) == 2


def test_phase4_portfolio_metrics():
    e2e = importlib.import_module('scripts.comprehensive_e2e_backtest')
    runner = e2e.ComprehensiveE2EBacktester()
    out = runner.test_phase4_portfolio()
    assert 'sharpe' in out and 'std' in out
    assert isinstance(out['sharpe'], float)
    assert isinstance(out['std'], float)


def test_phase5_ml_uses_tickers():
    e2e = importlib.import_module('scripts.comprehensive_e2e_backtest')
    runner = e2e.ComprehensiveE2EBacktester()
    tickers = ['FAKE1', 'FAKE2', 'FAKE3']
    preds = runner.test_phase5_ml(tickers)
    assert set(preds.keys()) == set(tickers)


def test_run_end_to_end_with_mocks(monkeypatch):
    e2e = importlib.import_module('scripts.comprehensive_e2e_backtest')

    class DummyMarketSelector:
        def get_universe(self, **kwargs):
            return ['FAKE1', 'FAKE2']

    class DummyAlpaca:
        def __init__(self, *args, **kwargs):
            pass
        def connect(self):
            return True
        def get_account(self):
            return {'portfolio_value': '100000', 'buying_power': '100000'}
        def get_positions(self):
            return []
        def get_bars(self, symbol, start, end, timeframe='1D'):
            return make_dummy_bars(50)

    monkeypatch.setattr(e2e, 'MarketSelector', DummyMarketSelector)
    monkeypatch.setattr(e2e, 'AlpacaAdapter', DummyAlpaca)

    runner = e2e.ComprehensiveE2EBacktester()
    # Should not raise
    runner.run_comprehensive_backtest()
