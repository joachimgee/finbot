"""Tests du meta-labeling (filtre/sizing des paris du primaire, sans look-ahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from financial_analyzer.backtest.meta_labeling import (
    META_FEATURES,
    build_meta_samples,
    meta_filter_today,
    walk_forward_meta,
)


def _synth(n=400, k=12, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    cols = [f"S{i}" for i in range(k)]
    scores = pd.DataFrame(rng.normal(size=(n, k)), index=idx, columns=cols)
    returns = pd.DataFrame(rng.normal(scale=0.01, size=(n, k)), index=idx, columns=cols)
    features = {fn: pd.DataFrame(rng.normal(size=(n, k)), index=idx, columns=cols)
                for fn in META_FEATURES}
    return scores, returns, features


def test_samples_have_labels_and_features_no_lookahead() -> None:
    scores, returns, features = _synth()
    s = build_meta_samples(scores, returns, features, quantile=0.25, horizon=10)
    assert not s.empty
    assert set(["date", "symbol", "side", "y", "label_end_i"]).issubset(s.columns)
    assert set(s["y"].unique()).issubset({0, 1})
    assert set(s["side"].unique()).issubset({-1, 1})
    # Aucun échantillon ne doit avoir un horizon dépassant le panel.
    assert (s["label_end_i"] < len(scores.index)).all()


def test_win_label_respects_side() -> None:
    # Un short (side=-1) sur un rendement forward négatif doit gagner (y=1).
    idx = pd.date_range("2023-01-01", periods=30, freq="B")
    cols = ["A", "B", "C", "D", "E", "F"]
    scores = pd.DataFrame(0.0, index=idx, columns=cols)
    scores.iloc[0] = [5.0, 4.0, 0.0, 0.0, -4.0, -5.0]  # E,F shorts ; A,B longs
    returns = pd.DataFrame(0.0, index=idx, columns=cols)
    returns.iloc[1:11, cols.index("F")] = -0.01  # F chute -> short gagne
    returns.iloc[1:11, cols.index("A")] = +0.01  # A monte -> long gagne
    feats = {fn: pd.DataFrame(1.0, index=idx, columns=cols) for fn in META_FEATURES}
    s = build_meta_samples(scores, returns, feats, quantile=0.34, horizon=10)
    first = s[s["date_i"] == 0].set_index("symbol")
    assert first.loc["F", "y"] == 1 and first.loc["F", "side"] == -1
    assert first.loc["A", "y"] == 1 and first.loc["A", "side"] == 1


def test_walk_forward_runs_and_meta_defaults_to_raw_before_training() -> None:
    scores, returns, features = _synth(seed=3)
    res = walk_forward_meta(scores, returns, features, rebalance_every=10, horizon=10,
                            min_train=100000)  # jamais assez pour entraîner -> méta == raw
    assert res.n_samples > 0
    # Sans entraînement possible, filtre/sizing retombent sur raw (Sharpe identique).
    assert res.meta_filter_net_sharpe == res.raw_net_sharpe


def test_meta_filter_today_returns_long_short_book() -> None:
    scores, returns, features = _synth(seed=7, n=500)
    book = meta_filter_today(scores, returns, features, quantile=0.2, horizon=10, min_train=200)
    assert isinstance(book, dict)
    # Book long/short : au moins un poids, brut ~1 (ou vide si tout filtré).
    if book:
        assert abs(sum(abs(w) for w in book.values()) - 1.0) < 1e-6
        assert any(w > 0 for w in book.values()) or any(w < 0 for w in book.values())


def test_meta_filter_today_falls_back_to_raw_before_training() -> None:
    scores, returns, features = _synth(seed=8, n=300)
    # min_train énorme -> pas de méta -> renvoie les paris bruts du primaire (non filtrés).
    book = meta_filter_today(scores, returns, features, quantile=0.2, horizon=10,
                             min_train=10**9)
    raw_k = 2 * max(1, int(round(scores.shape[1] * 0.2)))  # longs + shorts
    assert len(book) == raw_k
    assert abs(sum(abs(w) for w in book.values()) - 1.0) < 1e-6


def test_meta_filter_today_empty_scores_is_empty() -> None:
    import pandas as pd
    assert meta_filter_today(pd.DataFrame(), pd.DataFrame(), {}) == {}


def test_triple_barrier_label_first_touch() -> None:
    import numpy as np

    from financial_analyzer.backtest.meta_labeling import _triple_barrier_label

    sigma = 0.01
    up_path = np.array([0.02, 0.0, -0.05])   # touche le profit-take (long) en premier
    dn_path = np.array([-0.05, 0.0, 0.02])   # touche le stop-loss en premier
    assert _triple_barrier_label(up_path, side=1, sigma=sigma, pt_mult=1.0, sl_mult=1.0) == 1
    assert _triple_barrier_label(dn_path, side=1, sigma=sigma, pt_mult=1.0, sl_mult=1.0) == 0
    # Short : un chemin qui BAISSE gagne (side=-1).
    assert _triple_barrier_label(dn_path, side=-1, sigma=sigma, pt_mult=1.0, sl_mult=1.0) == 1
    # sigma non exploitable → repli sur le signe du rendement final.
    flat = np.array([0.001, 0.001, 0.001])
    assert _triple_barrier_label(flat, side=1, sigma=float("nan"), pt_mult=1.0, sl_mult=1.0) == 1


def test_build_meta_samples_triple_barrier_runs() -> None:
    scores, returns, features = _synth(seed=21, n=400)
    s = build_meta_samples(scores, returns, features, quantile=0.25, horizon=10,
                           label_method="triple_barrier", pt_mult=1.0, sl_mult=1.0)
    assert not s.empty
    assert set(s["y"].unique()).issubset({0, 1})


def test_compare_meta_sizing_returns_three_schemes() -> None:
    from financial_analyzer.backtest.meta_labeling import compare_meta_sizing

    scores, returns, features = _synth(seed=13, n=500)
    r = compare_meta_sizing(scores, returns, features, rebalance_every=10, horizon=10,
                            min_train=200, feature_names=META_FEATURES)
    assert {"equal", "confidence", "kelly"}.issubset(r)
    for name in ("equal", "confidence", "kelly"):
        assert set(r[name]) == {"net_sharpe", "turnover", "maxdd", "avg_gross"}
    # equal est équipondéré → brut ≈ 1 ; kelly cape le brut ≤ 1.
    assert abs(r["equal"]["avg_gross"] - 1.0) < 0.2
    assert r["kelly"]["avg_gross"] <= 1.0 + 1e-9
    assert "win_loss_ratio" in r["_kelly_b"]


def test_regime_features_are_broadcast_and_rich_set_runs() -> None:
    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.meta_labeling import (
        META_FEATURES_RICH,
        confirm_meta_labeling,
        regime_features,
    )
    scores, returns, features = _synth(seed=11, n=500)
    close = (1.0 + returns).cumprod() * 100.0
    rf = regime_features(close, scores)
    assert set(rf) == {"mkt_ret_126", "mkt_vol_21", "xs_disp"}
    # Diffusé : mêmes valeurs sur toutes les colonnes une date donnée.
    assert bool((rf["mkt_vol_21"].nunique(axis=1) <= 1).all())
    rich = {**features, **rf}
    c = confirm_meta_labeling(scores, returns, rich, feature_names=META_FEATURES_RICH,
                              rebalance_every=10, horizon=10, min_train=200,
                              n_random=10, n_perm=50)
    assert 0.0 <= c.auc <= 1.0
    assert isinstance(c.meta_returns, pd.Series)  # série exposée pour le DSR


def test_walk_forward_trains_and_reports_auc() -> None:
    scores, returns, features = _synth(seed=5, n=500)
    res = walk_forward_meta(scores, returns, features, rebalance_every=10, horizon=10,
                            min_train=200)
    assert 0.0 <= res.oos_auc <= 1.0
    assert 0.0 <= res.base_win_rate <= 1.0
    # Le méta-filtre ne garde jamais plus de noms que le raw.
    assert res.meta_filter_avg_names <= res.raw_avg_names + 1e-9
