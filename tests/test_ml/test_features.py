import pytest
import pandas as pd
import numpy as np

from financial_analyzer.ml import AlphaFactorEngine, FactorAnalyzer


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate sample OHLCV data for tests.

    Returns:
        DataFrame with columns open/high/low/close/volume and 252 business days.
    """
    rng = np.random.default_rng(123)
    dates = pd.date_range("2023-01-01", periods=252, freq="B")
    price = 100 + rng.normal(0, 1, size=252).cumsum()
    high = price + rng.uniform(0, 1, size=252)
    low = price - rng.uniform(0, 1, size=252)
    open_ = price + rng.normal(0, 0.5, size=252)
    close = price
    volume = rng.integers(1_000_000, 5_000_000, size=252)
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=dates)


def test_afe_initialization(sample_ohlcv: pd.DataFrame) -> None:
    """AlphaFactorEngine initializes properly."""
    afe = AlphaFactorEngine(sample_ohlcv)
    assert afe is not None
    assert hasattr(afe, "ohlcv")


def test_roc_factor(sample_ohlcv: pd.DataFrame) -> None:
    """ROC factor has correct length and naming."""
    afe = AlphaFactorEngine(sample_ohlcv)
    result = afe.roc(12)
    assert result.name == "ROC_12"
    assert len(result.values) == len(sample_ohlcv)
    assert result.category == "Momentum"


def test_macd_factor(sample_ohlcv: pd.DataFrame) -> None:
    """MACD returns dict with required keys."""
    afe = AlphaFactorEngine(sample_ohlcv)
    results = afe.macd()
    assert set(results.keys()) == {"MACD", "Signal", "Histogram"}
    for fr in results.values():
        assert fr.category == "Momentum"


def test_compute_all_factors(sample_ohlcv: pd.DataFrame) -> None:
    """compute_all_factors returns a sufficient number of factors."""
    afe = AlphaFactorEngine(sample_ohlcv)
    df = afe.get_factors_dataframe()
    assert df.shape[0] == len(sample_ohlcv)
    assert df.shape[1] >= 20  # At least 20 factors
    assert "ROC_12" in df.columns


def test_factor_analyzer(sample_ohlcv: pd.DataFrame) -> None:
    """FactorAnalyzer ranks factors with IC values."""
    afe = AlphaFactorEngine(sample_ohlcv)
    df = afe.get_factors_dataframe()
    returns = sample_ohlcv["close"].pct_change().shift(-1)  # forward returns
    fa = FactorAnalyzer(df, returns)
    ranked = fa.rank_factors(top_n=10)
    # Columns Factor, IC
    assert set(ranked.columns) == {"Factor", "IC"}
    assert len(ranked) <= 10


# ==================== PRIORITY 2: EDGE CASE TESTS ====================


def test_invalid_ohlcv_columns_raises() -> None:
    """AlphaFactorEngine raises ValueError if OHLCV columns missing."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2023-01-01", periods=100, freq="B")
    df_missing = pd.DataFrame({
        "open": rng.normal(100, 1, 100),
        "high": rng.normal(101, 1, 100),
        "close": rng.normal(100, 1, 100),
        # MISSING 'low' and 'volume'
    }, index=dates)
    with pytest.raises(ValueError, match="OHLCV must contain"):
        AlphaFactorEngine(df_missing)


def test_nan_handling_in_factors(sample_ohlcv: pd.DataFrame) -> None:
    """AlphaFactorEngine handles NaN gracefully without crashing."""
    # Inject NaNs in close prices (middle section)
    ohlcv_with_nan = sample_ohlcv.copy()
    ohlcv_with_nan.loc[ohlcv_with_nan.index[50:60], "close"] = np.nan
    afe = AlphaFactorEngine(ohlcv_with_nan)
    factors = afe.compute_all_factors()
    # Ensure factors are computed and valid_data reflects NaN presence
    assert len(factors) >= 20
    for name, fr in factors.items():
        assert fr.valid_data >= 0
        assert fr.valid_data <= len(ohlcv_with_nan)
    # Ensure get_factors_dataframe runs without error
    df = afe.get_factors_dataframe()
    assert df.shape[0] == len(ohlcv_with_nan)


def test_empty_factor_selection_scenario(sample_ohlcv: pd.DataFrame) -> None:
    """Factor computation with minimal periods and potential empty valid factors."""
    # Use minimal data (edge case: very short dataset)
    ohlcv_short = sample_ohlcv.head(15).copy()
    afe = AlphaFactorEngine(ohlcv_short)
    factors = afe.compute_all_factors()
    # All factors computed (might have many NaNs)
    assert len(factors) >= 20
    # Validate get_factors_dataframe doesn't crash
    df = afe.get_factors_dataframe()
    assert df.shape[0] == len(ohlcv_short)
    # Validate FactorAnalyzer can handle mostly-NaN factors
    returns = ohlcv_short["close"].pct_change().shift(-1)
    fa = FactorAnalyzer(df, returns)
    ranked = fa.rank_factors(top_n=5)
    # May have no valid factors -> check graceful handling
    # FactorAnalyzer should return what it can (even if empty or partial)
    assert isinstance(ranked, pd.DataFrame)
