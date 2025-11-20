"""Tests PhaseFPipeline (intégration Phase F).

Utilise données synthétiques pour éviter appels réseau.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from financial_analyzer.pipeline.pipeline_phase_f_adapter import PhaseFPipeline


def _synthetic_ohlcv(n: int = 120) -> pd.DataFrame:
    idx = pd.date_range('2024-01-01', periods=n, freq='D')
    price = 100 + np.cumsum(np.random.normal(0, 1, size=n))
    high = price + np.random.uniform(0, 1, size=n)
    low = price - np.random.uniform(0, 1, size=n)
    vol = np.random.randint(1000, 5000, size=n)
    df = pd.DataFrame({'Open': price, 'High': high, 'Low': low, 'Close': price, 'Volume': vol}, index=idx)
    return df

class DummyFetcher:
    def get_historical_data(self, ticker: str, start_date: str, end_date: str):
        return _synthetic_ohlcv()

class DummyUniverseSelector:
    def get_metadata(self, universe):
        return pd.DataFrame({'symbol': universe})


def test_phase_f_pipeline_basic(monkeypatch):
    # Monkeypatch dependencies inside underlying Pipeline
    from financial_analyzer.pipeline import pipeline as core
    from financial_analyzer.pipeline import pipeline_phase_f_adapter as adapter_mod
    monkeypatch.setattr(core, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    monkeypatch.setattr(core, 'UniverseSelector', lambda *a, **k: DummyUniverseSelector())
    monkeypatch.setattr(adapter_mod, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    p = PhaseFPipeline(lookback_days=60)
    result = p.run('2024-06-30', ['AAA', 'BBB'])
    assert 'advanced_features' in result['steps']
    assert result['steps']['advanced_features']['count'] == 2
    detail = result['steps']['advanced_features_detail']
    assert set(detail.keys()) == {'AAA', 'BBB'}
    for metrics in detail.values():
        # Check keys existence
        for k in ['fractional_diff_var_reduction', 'hurst_exponent', 'micro_liquidity_spread', 'micro_order_flow_mean', 'mdi_top_feature_importance']:
            assert k in metrics


def test_phase_f_pipeline_hurst_range(monkeypatch):
    from financial_analyzer.pipeline import pipeline as core
    from financial_analyzer.pipeline import pipeline_phase_f_adapter as adapter_mod
    monkeypatch.setattr(core, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    monkeypatch.setattr(core, 'UniverseSelector', lambda *a, **k: DummyUniverseSelector())
    monkeypatch.setattr(adapter_mod, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    p = PhaseFPipeline()
    result = p.run('2024-06-30', ['AAA'])
    hurst = result['steps']['advanced_features_detail']['AAA']['hurst_exponent']
    assert 0.0 <= hurst <= 1.5  # loose bounds


def test_phase_f_pipeline_fractional_diff(monkeypatch):
    from financial_analyzer.pipeline import pipeline as core
    from financial_analyzer.pipeline import pipeline_phase_f_adapter as adapter_mod
    monkeypatch.setattr(core, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    monkeypatch.setattr(core, 'UniverseSelector', lambda *a, **k: DummyUniverseSelector())
    monkeypatch.setattr(adapter_mod, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    p = PhaseFPipeline()
    result = p.run('2024-06-30', ['AAA'])
    var_red = result['steps']['advanced_features_detail']['AAA']['fractional_diff_var_reduction']
    assert -1.0 <= var_red <= 1.0  # sanity range


def test_phase_f_pipeline_feature_importance(monkeypatch):
    from financial_analyzer.pipeline import pipeline as core
    from financial_analyzer.pipeline import pipeline_phase_f_adapter as adapter_mod
    monkeypatch.setattr(core, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    monkeypatch.setattr(core, 'UniverseSelector', lambda *a, **k: DummyUniverseSelector())
    monkeypatch.setattr(adapter_mod, 'MarketDataFetcher', lambda *a, **k: DummyFetcher())
    p = PhaseFPipeline()
    result = p.run('2024-06-30', ['AAA'])
    mdi_top = result['steps']['advanced_features_detail']['AAA']['mdi_top_feature_importance']
    assert 0.0 <= mdi_top <= 1.0

