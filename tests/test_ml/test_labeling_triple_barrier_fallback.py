import numpy as np
import pandas as pd
from financial_analyzer.ml.labeling import triple_barrier_labels


def test_triple_barrier_labels_fallback_runs():
    idx = pd.date_range("2024-01-01", periods=50, freq="D")
    # Synthetic price path with mild trend
    prices = pd.Series(100.0 + np.cumsum(np.random.default_rng(0).normal(0, 0.5, size=len(idx))), index=idx)
    labels = triple_barrier_labels(prices, pt_sl=(1.0, 1.0), min_hold=2, max_hold=5)
    assert isinstance(labels, pd.Series)
    assert labels.index.equals(prices.index)
    assert set(labels.unique()).issubset({-1, 0, 1})
