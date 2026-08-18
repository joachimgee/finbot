"""Tests du moniteur de décroissance des signaux du registre."""
from __future__ import annotations

import numpy as np
import pandas as pd

from financial_analyzer.backtest.signal_monitor import evaluate_signal_health


def _panels(sign: float, n: int = 300, seed: int = 0):
    """Construit (scores, returns) où le rdt de t→t+1 corrèle à ``sign`` × score.

    sign > 0 : signal prédictif (edge sain) ; sign < 0 : edge inversé.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    cols = [f"S{i}" for i in range(12)]
    scores = pd.DataFrame(rng.normal(size=(n, len(cols))), index=idx, columns=cols)
    noise = rng.normal(scale=0.01, size=(n, len(cols)))
    # rdt[t] (de t-1→t) aligné pour que score[t-1] prédise rdt[t] : on décale.
    fwd = sign * 0.02 * scores.shift(1).fillna(0.0).to_numpy() + noise
    returns = pd.DataFrame(fwd, index=idx, columns=cols)
    return scores, returns


def test_healthy_signal_reports_healthy() -> None:
    scores, returns = _panels(sign=+1.0, seed=1)
    h = evaluate_signal_health("momentum_12_1", scores, returns, lookback=200)
    assert h.status == "healthy"
    assert h.net_sharpe >= 0.0 and h.ic_mean >= 0.0
    assert not any("perdu" in r or "inversé" in r for r in h.reasons)


def test_inverted_edge_flagged_dead() -> None:
    # Edge inversé (sign<0) : Sharpe net < 0 ET IC moyen < 0 -> dead.
    scores, returns = _panels(sign=-1.0, seed=2)
    h = evaluate_signal_health("momentum_12_1", scores, returns, lookback=200)
    assert h.status == "dead"
    assert h.level == "error"
    assert len(h.reasons) >= 2


def test_baseline_pulled_from_registry() -> None:
    scores, returns = _panels(sign=+1.0, seed=3)
    h = evaluate_signal_health("momentum_12_1", scores, returns, lookback=150)
    # La base vient du registre — y compris pour un signal DÉCLASSÉ : surveiller sa
    # dérive reste utile même s'il n'a plus le droit de trader.
    assert h.baseline_ic_t == 1.83
    assert h.baseline_net_sharpe == 0.76


def test_evaluation_failure_is_degraded_not_raised() -> None:
    # Panels vides -> l'éval échoue proprement -> statut dégradé, jamais d'exception.
    empty = pd.DataFrame()
    h = evaluate_signal_health("momentum_12_1", empty, empty, lookback=50)
    assert h.status in ("degraded", "dead")
    assert h.n_periods == 0
