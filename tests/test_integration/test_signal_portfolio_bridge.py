import pytest
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

from financial_analyzer.integration.signal_portfolio_bridge import SignalPortfolioBridge


def _make_prices(days: int = 60) -> pd.DataFrame:
    idx = pd.date_range('2024-01-01', periods=days, tz='UTC')
    # Simple random walk for a single generic asset's Close; OHLC are derived
    close = 100 + np.cumsum(np.random.randn(days)) * 0.5
    df = pd.DataFrame({
        'Open': close * (1 - 0.002),
        'High': close * (1 + 0.003),
        'Low': close * (1 - 0.003),
        'Close': close,
        'Volume': np.random.randint(900_000, 1_200_000, size=days)
    }, index=idx)
    return df


@pytest.fixture
def bridge_default():
    # Use relaxed max_weight so normalization to sum=1 is feasible for tests
    return SignalPortfolioBridge(
        portfolio_optimizer=None,
        sentiment_engine=None,
        feature_selector=None,
        max_weight=1.0,
        min_weight=0.01
    )


@pytest.fixture
def prices_df():
    return _make_prices(120)


# ---------------- Valid signals tests -----------------

def test_convert_valid_signals_long_only(bridge_default, prices_df):
    signals = {'AAPL': 1.5, 'MSFT': 0.8, 'GOOGL': 0.2}
    w = bridge_default.convert_signals_to_weights(signals, prices_df)
    assert isinstance(w, dict)
    assert 0.99 < sum(w.values()) <= 1.01
    assert all(v >= 0 for v in w.values())


def test_convert_mixed_signals_long_short_longonly_behavior(bridge_default, prices_df):
    signals = {'AAPL': 1.0, 'MSFT': -1.0, 'GOOGL': 0.0}
    w = bridge_default.convert_signals_to_weights(signals, prices_df)
    # Long-only: negatives should not produce negative weights
    assert all(v >= 0 for v in w.values())
    assert 0.99 < sum(w.values()) <= 1.01


def test_convert_signals_normalization_sums_to_one(bridge_default, prices_df):
    signals = {'AAPL': 0.5, 'MSFT': 0.5, 'GOOGL': 0.5}
    w = bridge_default.convert_signals_to_weights(signals, prices_df)
    assert abs(sum(w.values()) - 1.0) < 1e-8


def test_convert_signals_respects_max_weight_constraint(prices_df):
    bridge = SignalPortfolioBridge(None, None, None, max_weight=0.10, min_weight=0.01)
    signals = {'AAPL': 2.0, 'MSFT': 2.0, 'GOOGL': 2.0, 'AMZN': 2.0}
    # Infeasible: 4 * 0.10 < 1.0 → should raise
    with pytest.raises(ValueError):
        bridge.convert_signals_to_weights(signals, prices_df)


def test_convert_signals_respects_min_weight_constraint(prices_df):
    bridge = SignalPortfolioBridge(None, None, None, max_weight=0.50, min_weight=0.05)
    signals = {'AAPL': 2.0, 'MSFT': 0.1, 'GOOGL': 0.1}
    w = bridge.convert_signals_to_weights(signals, prices_df)
    # All non-zero positions must be at least min_weight after constraint step
    assert all((v == 0.0) or (v >= 0.05 - 1e-9) for v in w.values())


# ---------------- Invalid signals tests -----------------

def test_convert_invalid_signal_values_not_in_range(bridge_default, prices_df):
    signals = {'AAPL': 3.0}
    with pytest.raises(ValueError):
        bridge_default.convert_signals_to_weights(signals, prices_df)


def test_convert_signals_all_zeros(bridge_default, prices_df):
    signals = {'AAPL': 0.0, 'MSFT': 0.0}
    w = bridge_default.convert_signals_to_weights(signals, prices_df)
    assert 0.99 < sum(w.values()) <= 1.01


def test_convert_signals_with_nan(bridge_default, prices_df):
    signals = {'AAPL': np.nan, 'MSFT': 0.5}
    with pytest.raises(ValueError):
        bridge_default.convert_signals_to_weights(signals, prices_df)


def test_convert_signals_empty_dict(bridge_default, prices_df):
    with pytest.raises(ValueError):
        bridge_default.convert_signals_to_weights({}, prices_df)


def test_prices_invalid_type(bridge_default):
    with pytest.raises(TypeError):
        bridge_default.convert_signals_to_weights({'AAPL': 1.0}, None)  # type: ignore[arg-type]


def test_prices_missing_ohlcv_columns(bridge_default):
    idx = pd.date_range('2024-01-01', periods=10, tz='UTC')
    bad = pd.DataFrame({'Close': np.arange(10)}, index=idx)
    with pytest.raises(ValueError):
        bridge_default.convert_signals_to_weights({'AAPL': 1.0}, bad)


def test_prices_empty_df(bridge_default):
    empty = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
    empty.index = pd.DatetimeIndex([], tz='UTC')
    with pytest.raises(ValueError):
        bridge_default.convert_signals_to_weights({'AAPL': 1.0}, empty)


def test_prices_index_not_datetime(bridge_default):
    df = _make_prices(10)
    df.index = list(range(10))  # type: ignore[assignment]
    with pytest.raises(ValueError):
        bridge_default.convert_signals_to_weights({'AAPL': 1.0}, df)


# ---------------- Edge cases -----------------

def test_convert_signals_single_asset(bridge_default, prices_df):
    signals = {'AAPL': 1.0}
    w = bridge_default.convert_signals_to_weights(signals, prices_df)
    assert set(w.keys()) == {'AAPL'}
    assert abs(sum(w.values()) - 1.0) < 1e-8


def test_convert_signals_perfect_correlation(prices_df):
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01)
    # Build prices with identical Close for 2 tickers by using same series in covariance
    signals = {'AAPL': 1.0, 'MSFT': 1.0}
    w = bridge.convert_signals_to_weights(signals, prices_df)
    assert 0.99 < sum(w.values()) <= 1.01


def test_convert_signals_missing_prices(bridge_default, prices_df):
    bad = prices_df.copy()
    bad.loc[bad.index[5:8], 'Close'] = np.nan
    w = bridge_default.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 0.5}, bad)
    assert 0.99 < sum(w.values()) <= 1.01


def test_high_volatility_prices(bridge_default):
    df = _make_prices(300)
    df['Close'] = 100 + np.cumsum(np.random.randn(300)) * 5.0
    w = bridge_default.convert_signals_to_weights({'AAPL': 1.2, 'MSFT': 0.7, 'TSLA': 0.2}, df)
    assert 0.99 < sum(w.values()) <= 1.01


# ---------------- Integration (mocked optimizer) -----------------

def test_convert_with_mock_nco_optimizer(prices_df):
    mock_opt = MagicMock()
    mock_opt.optimize_nco.return_value = {'AAPL': 0.6, 'MSFT': 0.4}
    # Use relaxed constraints but valid (min>0) so weights should remain close after normalization
    bridge = SignalPortfolioBridge(mock_opt, None, None, max_weight=1.0, min_weight=0.001)
    signals = {'AAPL': 2.0, 'MSFT': 1.0}
    w = bridge.convert_signals_to_weights(signals, prices_df)
    assert w == {'AAPL': pytest.approx(0.6), 'MSFT': pytest.approx(0.4)}


def test_nco_fallback_to_mean_variance(prices_df):
    mock_opt = MagicMock()
    mock_opt.optimize_nco.side_effect = ValueError("nco fail")
    mock_opt.optimize_mean_variance.return_value = {'AAPL': 0.55, 'MSFT': 0.45}
    bridge = SignalPortfolioBridge(mock_opt, None, None, max_weight=1.0, min_weight=0.01)
    w = bridge.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 1.0}, prices_df)
    assert 0.99 < sum(w.values()) <= 1.01
    assert set(w.keys()) == {'AAPL', 'MSFT'}


def test_mv_fallback_to_equal_weight(prices_df):
    mock_opt = MagicMock()
    mock_opt.optimize_nco.side_effect = Exception("nco crash")
    mock_opt.optimize_mean_variance.side_effect = Exception("mv crash")
    bridge = SignalPortfolioBridge(mock_opt, None, None, max_weight=1.0, min_weight=0.01)
    w = bridge.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 0.5, 'GOOGL': 0.2}, prices_df)
    assert 0.99 < sum(w.values()) <= 1.01


def test_sentiment_ic_used_when_available(prices_df):
    # Sentiment engine returns per-ticker ICs boosting expected returns for AAPL
    class Sent:
        def get_ic(self, tickers):
            return {'AAPL': 0.10, 'MSFT': 0.02}
    bridge = SignalPortfolioBridge(None, Sent(), None, max_weight=1.0, min_weight=0.01)
    w = bridge.convert_signals_to_weights({'AAPL': 2.0, 'MSFT': 1.0}, prices_df)
    # AAPL weight should be >= MSFT weight due to higher IC and stronger signal
    assert w['AAPL'] >= w['MSFT']


def test_constraints_invalid_values():
    with pytest.raises(ValueError):
        SignalPortfolioBridge(None, None, None, max_weight=0.0, min_weight=0.01)


def test_empty_optimizer_result_then_equal_weight(prices_df):
    mock_opt = MagicMock()
    mock_opt.optimize_nco.return_value = {}
    mock_opt.optimize_mean_variance.return_value = {}
    bridge = SignalPortfolioBridge(mock_opt, None, None, max_weight=1.0, min_weight=0.01)
    w = bridge.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 1.0, 'TSLA': 1.0}, prices_df)
    assert 0.99 < sum(w.values()) <= 1.01


def test_optimizer_returns_nan_weights_fallback_equal(prices_df):
    mock_opt = MagicMock()
    mock_opt.optimize_nco.return_value = {'AAPL': float('nan'), 'MSFT': 0.2}
    bridge = SignalPortfolioBridge(mock_opt, None, None, max_weight=1.0, min_weight=0.01)
    w = bridge.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 1.0}, prices_df)
    assert 0.99 < sum(w.values()) <= 1.01
    assert all(0.0 <= v <= 1.0 for v in w.values())


def test_min_weight_enforced_after_optimization(prices_df):
    mock_opt = MagicMock()
    mock_opt.optimize_nco.return_value = {'AAPL': 0.9, 'MSFT': 0.1}
    bridge = SignalPortfolioBridge(mock_opt, None, None, max_weight=0.5, min_weight=0.2)
    w = bridge.convert_signals_to_weights({'AAPL': 2.0, 'MSFT': 0.1}, prices_df)
    # After enforcing min_weight and normalization, both non-zero should be >= 0.2
    assert all(v >= 0.2 - 1e-9 for v in w.values())


def test_handling_prices_without_timezone():
    df = _make_prices(50)
    df.index = pd.DatetimeIndex(df.index.tz_localize(None))
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01)
    w = bridge.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 1.0}, df)
    assert 0.99 < sum(w.values()) <= 1.01


def test_nan_in_prices_forward_filled():
    df = _make_prices(50)
    df.loc[df.index[10:12], 'Close'] = np.nan
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01)
    w = bridge.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 1.0}, df)
    assert 0.99 < sum(w.values()) <= 1.01


def test_lookback_exceeds_available_data(bridge_default):
    df = _make_prices(30)
    w = bridge_default.convert_signals_to_weights({'AAPL': 1.0, 'MSFT': 1.0}, df, lookback_days=365)
    assert 0.99 < sum(w.values()) <= 1.01


def test_all_negative_signals_long_only_false(prices_df):
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01, long_only=False)
    w = bridge.convert_signals_to_weights({'AAPL': -1.0, 'MSFT': -0.5, 'GOOGL': -0.2}, prices_df)
    assert 0.99 < sum(w.values()) <= 1.01
    assert all(v >= 0.0 for v in w.values())


def test_risk_measure_passed_to_optimizer(prices_df):
    """Vérifier que risk_measure est passé à l'optimizer."""
    mock_opt = MagicMock()
    mock_opt.optimize_nco.return_value = {'AAPL': 0.6, 'MSFT': 0.4}
    
    bridge = SignalPortfolioBridge(mock_opt, None, None, max_weight=1.0, min_weight=0.01)
    signals = {'AAPL': 1.5, 'MSFT': 1.0}
    
    # Test avec CVaR
    w = bridge.convert_signals_to_weights(signals, prices_df, risk_measure='CVaR')
    mock_opt.optimize_nco.assert_called_once()
    # Le 3e argument doit être risk_measure
    call_args = mock_opt.optimize_nco.call_args[0]
    assert len(call_args) == 3 and call_args[2] == 'CVaR'
    
    # Reset et test avec CDaR
    mock_opt.reset_mock()
    mock_opt.optimize_nco.return_value = {'AAPL': 0.5, 'MSFT': 0.5}
    w = bridge.convert_signals_to_weights(signals, prices_df, risk_measure='CDaR')
    call_args = mock_opt.optimize_nco.call_args[0]
    assert len(call_args) == 3 and call_args[2] == 'CDaR'
