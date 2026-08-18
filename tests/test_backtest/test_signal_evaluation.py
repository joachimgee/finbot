"""Tests du harness d'évaluation de signal (coûts + IC + walk-forward)."""
import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    cross_sectional_weights,
    evaluate_signal,
    walk_forward_evaluate,
)


def _make_panel(n_dates=300, n_assets=20, beta=0.03, noise=0.02, seed=0):
    """Panel où scores[t] prédit le rendement t->t+1 (beta>0 = vrai edge)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    cols = [f"A{i}" for i in range(n_assets)]
    scores = pd.DataFrame(rng.standard_normal((n_dates, n_assets)), index=dates, columns=cols)
    # returns[t] = beta * scores[t-1] + bruit  =>  scores[t] prédit returns[t+1]
    shifted = scores.shift(1).fillna(0.0)
    rets = beta * shifted + rng.standard_normal((n_dates, n_assets)) * noise
    return scores, rets


# ----------------------------- cross_sectional_weights -----------------------------

def test_weights_dollar_neutral_and_normalized():
    row = pd.Series({f"A{i}": float(i) for i in range(20)})
    w = cross_sectional_weights(row, quantile=0.2, long_short=True)
    assert abs(w.sum()) < 1e-9              # dollar-neutre
    assert abs(w.abs().sum() - 1.0) < 1e-9  # normalisé
    assert w["A19"] > 0 and w["A0"] < 0     # top long, bottom short


def test_weights_long_only():
    row = pd.Series({f"A{i}": float(i) for i in range(20)})
    w = cross_sectional_weights(row, quantile=0.25, long_short=False)
    assert (w >= 0).all()
    assert abs(w.abs().sum() - 1.0) < 1e-9


def test_weights_too_few_assets_returns_zero():
    row = pd.Series({"A": 1.0, "B": 2.0})
    w = cross_sectional_weights(row, quantile=0.2)
    assert (w == 0).all()


# ----------------------------- evaluate_signal -----------------------------

def test_predictive_signal_has_positive_ic_and_edge():
    scores, rets = _make_panel(beta=0.04, seed=1)
    res = evaluate_signal(scores, rets, CostModel(commission_bps=5, slippage_bps=2))
    assert res.ic_mean > 0.05          # tri informatif
    assert res.ic_t_stat > 3           # statistiquement net
    assert res.gross_sharpe > 1.0      # edge brut réel
    assert res.net_sharpe > 0          # survit à des coûts modérés


def test_random_signal_has_no_edge():
    rng = np.random.default_rng(2)
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    cols = [f"A{i}" for i in range(20)]
    scores = pd.DataFrame(rng.standard_normal((300, 20)), index=dates, columns=cols)
    rets = pd.DataFrame(rng.standard_normal((300, 20)) * 0.02, index=dates, columns=cols)
    res = evaluate_signal(scores, rets)
    assert abs(res.ic_mean) < 0.03     # IC ≈ 0
    assert abs(res.ic_t_stat) < 2.5    # non significatif


def test_costs_reduce_net_return():
    scores, rets = _make_panel(beta=0.04, seed=3)
    cheap = evaluate_signal(scores, rets, CostModel(commission_bps=1, slippage_bps=0))
    dear = evaluate_signal(scores, rets, CostModel(commission_bps=50, slippage_bps=30))
    assert dear.net_ann_return < cheap.net_ann_return
    assert cheap.gross_ann_return == pytest.approx(dear.gross_ann_return, rel=1e-9)  # brut inchangé


def test_cost_model_rate():
    assert CostModel(commission_bps=20, slippage_bps=5).cost_rate == pytest.approx(0.0025)


# ----------------------------- walk_forward_evaluate -----------------------------

def test_walk_forward_out_of_sample_edge():
    scores, rets = _make_panel(n_dates=600, beta=0.04, seed=4)
    out = walk_forward_evaluate(scores, rets, n_splits=5,
                                cost_model=CostModel(commission_bps=5, slippage_bps=2))
    assert out["n_splits"] >= 4
    assert out["oos"] is not None
    assert out["oos"].ic_mean > 0.03        # edge persiste hors échantillon
    assert out["oos"].n_periods > 0


def test_walk_forward_rejects_short_history():
    scores, rets = _make_panel(n_dates=20, seed=5)
    with pytest.raises(ValueError):
        walk_forward_evaluate(scores, rets, n_splits=5)


def test_walk_forward_custom_fit_predict_is_out_of_sample():
    """Un fit_predict qui trahirait le futur échouerait ; ici on vérifie juste
    que le combinateur reçoit bien des fenêtres train/test disjointes."""
    scores, rets = _make_panel(n_dates=400, seed=6)
    seen = {}

    def fit_predict(s_train, r_train, s_test):
        # les indices train et test ne doivent jamais se chevaucher
        seen["overlap"] = set(s_train.index) & set(s_test.index)
        return s_test

    walk_forward_evaluate(scores, rets, fit_predict=fit_predict, n_splits=4)
    assert seen["overlap"] == set()


class TestRebalancePeriod:
    """Portail: a longer rebalancing period holds weights and cuts turnover/cost
    without dropping periods (addresses momentum over-trading in daily)."""

    @staticmethod
    def _data():
        import numpy as np
        import pandas as pd
        rng = np.random.default_rng(0)
        dates = pd.date_range("2021-01-01", periods=120, freq="B")
        cols = [f"A{i}" for i in range(8)]
        # Scores that change every day -> daily rebalancing churns a lot.
        scores = pd.DataFrame(rng.normal(size=(len(dates), len(cols))), index=dates, columns=cols)
        returns = pd.DataFrame(rng.normal(0, 0.02, size=(len(dates), len(cols))), index=dates, columns=cols)
        return scores, returns

    def test_longer_period_reduces_turnover(self):
        from financial_analyzer.backtest.signal_evaluation import evaluate_signal
        scores, returns = self._data()
        daily = evaluate_signal(scores, returns, rebalance_every=1)
        held = evaluate_signal(scores, returns, rebalance_every=10)
        assert held.avg_turnover < daily.avg_turnover
        # Holding must not drop evaluation periods.
        assert held.n_periods == daily.n_periods

    def test_period_one_matches_default(self):
        from financial_analyzer.backtest.signal_evaluation import evaluate_signal
        scores, returns = self._data()
        a = evaluate_signal(scores, returns)
        b = evaluate_signal(scores, returns, rebalance_every=1)
        assert a.avg_turnover == b.avg_turnover
        assert a.net_ann_return == b.net_ann_return


class TestICHorizon:
    """L'IC doit être mesuré sur l'horizon de DÉTENTION, pas sur une période.

    Régression du diagnostic Amihud : avec ``rebalance_every=21``, le book décide du
    rendement à 21 jours ; mesurer l'IC contre le rendement à 1 jour évaluait une
    décision que la stratégie ne prend pas, et rejetait le signal au portail pour une
    raison purement instrumentale.
    """

    @staticmethod
    def _slow_signal(n_dates=420, n_assets=25, seed=3):
        """Signal LENT : prédit le cumul à 20 jours, pas le rendement du lendemain.

        Chaque rendement quotidien est majoritairement du bruit ; la dérive
        proportionnelle au score ne devient visible qu'en s'accumulant.
        """
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
        cols = [f"A{i}" for i in range(n_assets)]
        base = pd.DataFrame(rng.standard_normal((n_dates // 20 + 1, n_assets)),
                            columns=cols)
        scores = base.reindex(base.index.repeat(20)).iloc[:n_dates]
        scores.index = dates
        drift = scores.to_numpy() * 0.0004          # dérive quotidienne minuscule
        noise = rng.standard_normal((n_dates, n_assets)) * 0.02  # bruit dominant
        returns = pd.DataFrame(drift, index=dates, columns=cols).shift(1).fillna(0.0)
        returns = returns + pd.DataFrame(noise, index=dates, columns=cols)
        return scores, returns

    def test_holding_horizon_ic_beats_one_period_ic_on_slow_signal(self):
        scores, returns = self._slow_signal()
        one = evaluate_signal(scores, returns, rebalance_every=20, ic_horizon=1)
        held = evaluate_signal(scores, returns, rebalance_every=20)
        assert held.ic_horizon == 20 and one.ic_horizon == 1
        # Le signal est lent : son IC n'est lisible qu'à l'horizon de détention.
        assert held.ic_t_stat > one.ic_t_stat

    def test_default_horizon_follows_rebalance_every(self):
        scores, returns = _make_panel(n_dates=200)
        assert evaluate_signal(scores, returns, rebalance_every=7).ic_horizon == 7
        assert evaluate_signal(scores, returns).ic_horizon == 1

    def test_daily_rebalance_ic_is_unchanged(self):
        """``rebalance_every=1`` -> horizon 1 : comportement historique préservé."""
        scores, returns = _make_panel(n_dates=200)
        a = evaluate_signal(scores, returns, rebalance_every=1)
        b = evaluate_signal(scores, returns, rebalance_every=1, ic_horizon=1)
        assert a.ic_t_stat == pytest.approx(b.ic_t_stat, nan_ok=True)

    def test_horizon_ic_is_sampled_without_overlap(self):
        """Observations non chevauchantes : ~n/h points, pas n (t-stat non gonflé)."""
        from financial_analyzer.backtest.ic_reporting import compute_cross_sectional_ic

        scores, returns = _make_panel(n_dates=200)
        cum = (1.0 + returns).cumprod()
        fwd_h = cum.shift(-10) / cum - 1.0
        ic = compute_cross_sectional_ic(scores.iloc[::10], fwd_h.iloc[::10]).dropna()
        assert len(ic) <= len(scores) // 10 + 1

    def test_walk_forward_propagates_holding_horizon(self):
        scores, returns = _make_panel(n_dates=400)
        out = walk_forward_evaluate(scores, returns, n_splits=3, rebalance_every=5)
        assert out["oos"].ic_horizon == 5
