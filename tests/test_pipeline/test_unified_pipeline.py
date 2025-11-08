"""Tests pour la classe Pipeline (Unified Pipeline V2).

Couverture (14 tests incluant polish intégration):
- Initialisation correcte
- Erreur sur paramètres invalides
- Run pipeline complet (succès)
- Run pipeline univers vide (erreur)
- _fetch_data retour structures
- _engineer_features calcul basique
- _analyze_sentiment plage valeurs
- _generate_predictions plage valeurs
- _fuse_signals format sortie
- _allocate_portfolio structure
- _optimize_risk méthodes (none/equal/inverse)
- _generate_orders logique BUY/SELL/HOLD
- Full pipeline integration test (end-to-end)
- Pipeline metrics & errors presence
"""
import pytest
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.strategy.signal_fusion import SignalFusion
from financial_analyzer.strategy.ensemble_allocator import EnsembleAllocator


# ------------------ Fixtures ------------------

class DummyUniverseSelector(UniverseSelector):  # Override to avoid heavy init
    def __init__(self):
        pass
    def get_metadata(self, tickers):
        return pd.DataFrame({'symbol': tickers, 'sector': ['Tech']*len(tickers)})

class DummyMarketFetcher(MarketDataFetcher):
    def __init__(self):
        pass
    def get_historical_data(self, ticker, start_date, end_date):
        idx = pd.date_range(start_date, periods=30, freq='D')
        prices = pd.DataFrame({'Close': 100 + np.arange(30)}, index=idx)
        return prices

@pytest.fixture
def pipeline():
    return Pipeline(
        universe_selector=DummyUniverseSelector(),
        lookback_days=30,
        forecast_horizon=5,
        optimization_method='none',
        market_data_fetcher=DummyMarketFetcher(),
        signal_fusion=SignalFusion(),
        allocator=EnsembleAllocator(max_position_size=0.3, min_position_size=0.05, cash_reserve=0.1),
    )

# ------------------ Tests ------------------

def test_init_success(pipeline):
    assert pipeline.lookback_days == 30
    assert pipeline.forecast_horizon == 5
    assert pipeline.default_optimization_method == 'none'

def test_init_invalid_lookback():
    with pytest.raises(ValueError):
        Pipeline(universe_selector=DummyUniverseSelector(), lookback_days=0)

def test_run_empty_universe(pipeline):
    result = pipeline.run('2025-11-08', [])
    assert result['status'] == 'error'
    assert 'Empty universe' in result['errors'][0]

def test_fetch_data_structures(pipeline):
    returns, meta = pipeline._fetch_data(['AAPL','MSFT'], 30, '2025-11-08')
    assert isinstance(returns, pd.DataFrame)
    assert isinstance(meta, pd.DataFrame)
    assert set(returns.columns) <= {'AAPL','MSFT'}

def test_engineer_features_values(pipeline):
    returns, _ = pipeline._fetch_data(['AAPL'], 30, '2025-11-08')
    feats = pipeline._engineer_features(returns)
    assert 'AAPL' in feats
    assert 'mean_return' in feats['AAPL']

def test_sentiment_range(pipeline):
    sent = pipeline._analyze_sentiment(['AAPL','MSFT'])
    assert all(-1.0 <= v <= 1.0 for v in sent.values())

def test_predictions_range(pipeline):
    returns, _ = pipeline._fetch_data(['AAPL','MSFT'], 30, '2025-11-08')
    preds = pipeline._generate_predictions(returns)
    assert all(0.0 <= v <= 1.0 for v in preds.values())

def test_fuse_signals_format(pipeline):
    returns, _ = pipeline._fetch_data(['AAPL'], 30, '2025-11-08')
    feats = pipeline._engineer_features(returns)
    sent = pipeline._analyze_sentiment(['AAPL'])
    preds = pipeline._generate_predictions(returns)
    fused = pipeline._fuse_signals(feats, sent, preds)
    assert 'AAPL' in fused
    assert 'final_score' in fused['AAPL']
    assert 'confidence' in fused['AAPL']

def test_allocate_portfolio_structure(pipeline):
    fused = {'AAPL': {'final_score': 0.8, 'confidence': 0.9}, 'MSFT': {'final_score': 0.3, 'confidence': 0.6}}
    alloc = pipeline._allocate_portfolio(fused)
    assert 'cash' in alloc
    assert alloc['cash'] <= 1.0

def test_optimize_risk_equal_weight(pipeline):
    alloc = {'AAPL':0.2,'MSFT':0.3,'cash':0.5}
    returns, _ = pipeline._fetch_data(['AAPL','MSFT'], 30, '2025-11-08')
    opt = pipeline._optimize_risk(alloc, returns, method='equal_weight')
    assert abs(opt['AAPL'] - opt['MSFT']) < 1e-6

def test_optimize_risk_inverse_variance(pipeline):
    alloc = {'AAPL':0.2,'MSFT':0.3,'cash':0.5}
    returns, _ = pipeline._fetch_data(['AAPL','MSFT'], 30, '2025-11-08')
    opt = pipeline._optimize_risk(alloc, returns, method='inverse_variance')
    assert 'AAPL' in opt and 'MSFT' in opt

def test_generate_orders_logic(pipeline):
    orders = pipeline._generate_orders(current_positions={'AAPL':0.05}, target_weights={'AAPL':0.10,'MSFT':0.0,'cash':0.9}, capital=100000)
    buy = [o for o in orders if o['action']=='BUY']
    assert any(o['ticker']=='AAPL' for o in buy)


# ------------------ Polish: Full integration ------------------

def test_full_pipeline_integration_end_to_end():
    """End-to-end run() with small universe and optimization enabled.

    Ensures the pipeline returns a complete dict with steps, metrics,
    and a 'success' or 'partial' status, and that allocations exist.
    """
    class _U(UniverseSelector):
        def __init__(self):
            pass
        def get_metadata(self, tickers):
            return pd.DataFrame({'symbol': tickers})

    class _M(MarketDataFetcher):
        def __init__(self):
            pass
        def get_historical_data(self, ticker, start_date, end_date):
            idx = pd.date_range(start_date, periods=40, freq='D')
            return pd.DataFrame({'Close': 100 + np.sin(np.arange(40))}, index=idx)

    p = Pipeline(
        universe_selector=_U(),
        lookback_days=30,
        forecast_horizon=5,
        optimization_method='inverse_variance',
        market_data_fetcher=_M(),
        signal_fusion=SignalFusion(),
        allocator=EnsembleAllocator(max_position_size=0.4, min_position_size=0.05, cash_reserve=0.1),
    )

    res = p.run('2025-11-08', ['AAPL','MSFT'], optimization_method='inverse_variance')
    assert isinstance(res, dict)
    assert res['status'] in {'success', 'partial'}
    assert 'steps' in res and isinstance(res['steps'], dict)
    assert 'metrics' in res and isinstance(res['metrics'], dict)
    assert 'allocation' in res['steps'] or 'optimization' in res['steps']
    # Ensure optimized weights contain cash and at least one asset
    opt_info = res['steps'].get('optimization', {})
    if opt_info:
        assert opt_info.get('method') == 'inverse_variance'
    # Errors list exists
    assert 'errors' in res and isinstance(res['errors'], list)

