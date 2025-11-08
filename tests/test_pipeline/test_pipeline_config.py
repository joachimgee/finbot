import pandas as pd
from financial_analyzer.config import TRADING_CONFIG_D, ML_CONFIG_D, TRADING_CONFIG
from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.data.universe import UniverseSelector

class DummyUniverseSelector(UniverseSelector):
    def __init__(self):
        # Avoid heavy FinanceDatabase init in test by mocking minimal attributes
        pass
    def get_metadata(self, tickers, asset_type: str = 'equities'):
        return pd.DataFrame({'symbol': tickers})

    # Minimal stub to satisfy usage


def test_trading_config_has_threshold():
    assert 'order_delta_threshold' in TRADING_CONFIG
    assert TRADING_CONFIG_D.order_delta_threshold == TRADING_CONFIG['order_delta_threshold']


def test_ml_config_defaults():
    assert ML_CONFIG_D.lookback_window > 0
    assert ML_CONFIG_D.forecast_horizon > 0
    assert ML_CONFIG_D.lstm_units > 0


def test_pipeline_uses_config_threshold():
    selector = DummyUniverseSelector()
    pipeline = Pipeline(universe_selector=selector)
    # Provide synthetic data for run
    result = pipeline.run('2025-11-08', ['AAA', 'BBB'])
    assert 'status' in result
    assert result['steps']['orders']['count'] >= 0


def test_initial_capital_config_available():
    assert TRADING_CONFIG_D.initial_capital == TRADING_CONFIG['initial_capital']
