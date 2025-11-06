import pytest
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from financial_analyzer.ml import AlphaFactorEngine, FactorAnalyzer, FeatureImportance


def make_sample_ohlcv(n: int = 252, seed: int = 123) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    price = 100 + rng.normal(0, 1, size=n).cumsum()
    high = price + rng.uniform(0, 1, size=n)
    low = price - rng.uniform(0, 1, size=n)
    open_ = price + rng.normal(0, 0.5, size=n)
    close = price
    volume = rng.integers(1_000_000, 5_000_000, size=n)
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=dates)


def test_invalid_ohlcv_columns_raises() -> None:
    df = make_sample_ohlcv()
    # Drop a required column
    df_bad = df.drop(columns=["volume"])  # missing volume
    with pytest.raises(ValueError):
        _ = AlphaFactorEngine(df_bad)
    # Wrong casing should still work if present
    df_case = df.rename(columns={"Open": "OPEN", "High": "HIGH", "Low": "LOW", "Close": "CLOSE", "Volume": "VOLUME"})
    # Ensure case-insensitive mapping works
    afe = AlphaFactorEngine(df_case)
    assert hasattr(afe, "ohlcv")


def test_nan_handling_valid_data_counts() -> None:
    df = make_sample_ohlcv()
    # Inject NaNs
    df.loc[df.index[:5], "close"] = np.nan
    df.loc[df.index[10:13], "high"] = np.nan
    df.loc[df.index[20], "low"] = np.nan
    afe = AlphaFactorEngine(df)
    factors = afe.compute_all_factors()
    # Pick a known factor and verify valid_data matches non-NaN count
    fr = factors["ROC_12"]
    assert fr.valid_data == int(fr.values.notna().sum())


def test_rank_factors_empty_when_insufficient_valid_points() -> None:
    # Create a small factor set (<30 valid points)
    n = 20
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    factors_df = pd.DataFrame({
        "F1": np.linspace(0, 1, n),
        "F2": np.ones(n),
    }, index=dates)
    returns = pd.Series(np.linspace(0, 0.1, n), index=dates)
    fa = FactorAnalyzer(factors_df, returns)
    ranked = fa.rank_factors(top_n=5)
    assert isinstance(ranked, pd.DataFrame)
    assert ranked.shape[0] == 0
    assert list(ranked.columns) == ["Factor", "IC"]


def test_feature_importance_random_state_reproducible() -> None:
    # Simple regression dataset
    rng = np.random.default_rng(42)
    X = rng.normal(size=(200, 5))
    true_coef = np.array([1.0, 0.5, 0.0, -0.5, 0.2])
    y = X @ true_coef + rng.normal(scale=0.1, size=200)
    model = LinearRegression().fit(X, y)

    fi1 = FeatureImportance(model, X, y, random_state=123)
    fi2 = FeatureImportance(model, X, y, random_state=123)
    imp1 = fi1.permutation_importance(n_repeats=5)
    imp2 = fi2.permutation_importance(n_repeats=5)
    assert imp1 == imp2  # exact same due to same RNG sequence

    fi3 = FeatureImportance(model, X, y, random_state=456)
    imp3 = fi3.permutation_importance(n_repeats=5)
    # At least one feature importance should differ
    diffs = [imp1[k] != imp3[k] for k in imp1.keys()]
    assert any(diffs)
