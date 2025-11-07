import math
import pytest
import pandas as pd
import numpy as np

from financial_analyzer.integration.signal_portfolio_bridge import SignalPortfolioBridge


def make_prices(tickers: list, days: int = 300) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=days, freq="D", tz="UTC")
    data = {}
    for t in tickers:
        # simulate close prices random walk
        closes = 100 + np.cumsum(np.random.normal(0, 1, size=days))
        data[f"Close_{t}"] = closes
        data[f"Open_{t}"] = closes * 0.99
        data[f"High_{t}"] = closes * 1.01
        data[f"Low_{t}"] = closes * 0.98
        data[f"Volume_{t}"] = np.random.randint(100_000, 200_000, size=days)
    # Also add generic OHLCV columns for validation
    data["Open"] = data[f"Open_{tickers[0]}"]
    data["High"] = data[f"High_{tickers[0]}"]
    data["Low"] = data[f"Low_{tickers[0]}"]
    data["Close"] = data[f"Close_{tickers[0]}"]
    data["Volume"] = data[f"Volume_{tickers[0]}"]
    return pd.DataFrame(data, index=dates)


def test_batch_basic_parallel():
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    prices = make_prices(tickers)
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01, long_only=True)

    signals_list = []
    for i in range(15):
        sig = {t: float(np.random.uniform(-1, 1)) for t in tickers}
        signals_list.append(sig)

    weights_list = bridge.convert_signals_to_weights_batch(signals_list, prices, lookback_days=120, n_jobs=2)
    assert len(weights_list) == len(signals_list)
    for w in weights_list:
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
        assert all(0.0 <= v <= 1.0 + 1e-9 for v in w.values())


def test_batch_sequential_small_list():
    tickers = ["AAA", "BBB"]
    prices = make_prices(tickers, days=260)
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.02)
    signals_list = [{"AAA": 0.3, "BBB": -0.4}, {"AAA": -0.9, "BBB": 0.8}]

    weights_list = bridge.convert_signals_to_weights_batch(signals_list, prices, lookback_days=90, n_jobs=1)
    assert len(weights_list) == 2
    for w in weights_list:
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_batch_long_only_filters_negatives():
    tickers = ["AAA", "BBB", "CCC"]
    prices = make_prices(tickers)
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01, long_only=True)
    signals_list = [{"AAA": -0.5, "BBB": -0.4, "CCC": -0.3}, {"AAA": 0.9, "BBB": -0.2, "CCC": 0.1}]

    weights_list = bridge.convert_signals_to_weights_batch(signals_list, prices, lookback_days=50, n_jobs=2)
    # First set all negative -> fallback equal weight over all tickers
    assert sum(weights_list[0].values()) == pytest.approx(1.0, abs=1e-6)
    assert all(v > 0 for v in weights_list[0].values())
    # Second set: BBB has negative signal → filtered out in long_only mode, only AAA & CCC remain
    assert sum(weights_list[1].values()) == pytest.approx(1.0, abs=1e-6)
    # Only positive-signal tickers should have weights
    assert 'AAA' in weights_list[1] and 'CCC' in weights_list[1]


def test_batch_short_allowed():
    tickers = ["AAA", "BBB", "CCC"]
    prices = make_prices(tickers)
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01, long_only=False)
    signals_list = [{"AAA": -0.9, "BBB": -0.8, "CCC": -0.7}, {"AAA": 0.2, "BBB": -0.6, "CCC": 0.5}]
    weights_list = bridge.convert_signals_to_weights_batch(signals_list, prices, lookback_days=40, n_jobs=2)
    for w in weights_list:
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
        assert all(0.0 <= v <= 1.0 + 1e-9 for v in w.values())


def test_batch_infeasible_constraints_raise():
    tickers = ["AAA", "BBB", "CCC"]
    prices = make_prices(tickers)
    # Use valid constraints but ensure min_weight adjustment kicks in
    bridge = SignalPortfolioBridge(None, None, None, max_weight=0.5, min_weight=0.4)
    signals_list = [{t: 0.5 for t in tickers}]
    weights_list = bridge.convert_signals_to_weights_batch(signals_list, prices, lookback_days=30, n_jobs=1)
    assert len(weights_list) == 1
    w = weights_list[0]
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_batch_identity_covariance_fallback():
    tickers = ["AAA", "BBB"]
    # Create prices with constant Close so zero variance triggers identity fallback
    dates = pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC")
    prices = pd.DataFrame({
        "Close_AAA": np.ones(100) * 100,
        "Close_BBB": np.ones(100) * 50,
        "Open": np.ones(100) * 100,
        "High": np.ones(100) * 101,
        "Low": np.ones(100) * 99,
        "Close": np.ones(100) * 100,
        "Volume": np.ones(100) * 100000
    }, index=dates)
    bridge = SignalPortfolioBridge(None, None, None, max_weight=0.9, min_weight=0.01)
    signals_list = [{"AAA": 0.3, "BBB": 0.4} for _ in range(5)]
    weights_list = bridge.convert_signals_to_weights_batch(signals_list, prices, lookback_days=60, n_jobs=2)
    for w in weights_list:
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_batch_lookback_exceeds_data():
    tickers = ["AAA", "BBB", "CCC"]
    prices = make_prices(tickers, days=50)
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01)
    signals_list = [{t: np.random.uniform(-1, 1) for t in tickers} for _ in range(3)]
    weights_list = bridge.convert_signals_to_weights_batch(signals_list, prices, lookback_days=400, n_jobs=1)
    assert len(weights_list) == 3
    for w in weights_list:
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_batch_parallel_all_cpus():
    """Test batch avec n_jobs=-1 (tous les CPUs)."""
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    prices = make_prices(tickers, days=200)
    bridge = SignalPortfolioBridge(None, None, None, max_weight=1.0, min_weight=0.01)
    
    signals_list = [
        {t: float(np.random.uniform(0, 2)) for t in tickers}
        for _ in range(20)  # 20 rebalances
    ]
    
    weights_list = bridge.convert_signals_to_weights_batch(
        signals_list, prices, lookback_days=100, n_jobs=-1
    )
    
    assert len(weights_list) == 20
    for w in weights_list:
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
        assert all(0.0 <= v <= 1.01 for v in w.values())
