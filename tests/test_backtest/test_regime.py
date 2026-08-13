"""Détection de régime HMM gaussien — recouvrement + causalité (no look-ahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.regime import (
    fit_gaussian_hmm,
    regime_risk_series,
)


def _two_regime_series(seed: int = 0) -> np.ndarray:
    """Calme (faible vol) → turbulent (forte vol) → calme."""
    rng = np.random.default_rng(seed)
    return np.concatenate([
        rng.normal(0.0005, 0.006, 300),
        rng.normal(-0.001, 0.030, 150),   # régime turbulent
        rng.normal(0.0005, 0.006, 300),
    ])


def test_hmm_recovers_two_vol_regimes() -> None:
    x = _two_regime_series(1)
    m = fit_gaussian_hmm(x, n_states=2)
    # Deux variances bien distinctes (un état calme, un état volatil).
    lo, hi = sorted(m.var)
    assert hi > 3 * lo
    assert m.high_vol_state in (0, 1)


def test_filtered_proba_flags_turbulent_middle() -> None:
    """La proba filtrée d'état turbulent est plus haute au milieu (krach) qu'au calme."""
    x = _two_regime_series(2)
    m = fit_gaussian_hmm(x, n_states=2)
    p_high = m.filtered_proba(x)[:, m.high_vol_state]
    assert p_high[300:450].mean() > p_high[:300].mean() + 0.3


def test_filtered_proba_is_causal_no_lookahead() -> None:
    """Modifier un rendement FUTUR ne change pas la proba filtrée au temps présent."""
    x = _two_regime_series(3)
    m = fit_gaussian_hmm(x, n_states=2)  # modèle gelé
    base = m.filtered_proba(x)
    x2 = x.copy()
    x2[500] = 0.5  # choc énorme à t=500
    after = m.filtered_proba(x2)
    # Les probas filtrées à t < 500 n'utilisent que le passé -> inchangées.
    np.testing.assert_allclose(base[:500], after[:500], atol=1e-9)


def test_fit_rejects_short_history() -> None:
    with pytest.raises(ValueError):
        fit_gaussian_hmm(np.zeros(10))


def _panel_from_market(mkt: np.ndarray, k: int = 8, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=len(mkt), freq="B")
    cols = {f"S{j}": 100 * np.exp(np.cumsum(mkt + rng.normal(0, 0.004, len(mkt))))
            for j in range(k)}
    return pd.DataFrame(cols, index=idx)


def test_regime_risk_series_reduces_exposure_in_turbulence() -> None:
    px = _panel_from_market(_two_regime_series(4))
    exp = regime_risk_series(px, warmup=252, refit_every=63, risk_off_factor=0.5)
    assert (exp <= 1.0 + 1e-9).all() and (exp >= 0.5 - 1e-9).all()
    assert exp.iloc[:252].eq(1.0).all()  # warm-up -> pleine exposition
    # Exposition moyenne plus basse pendant le régime turbulent (indices 300-450).
    assert exp.iloc[300:450].mean() < exp.iloc[600:].mean()


def test_regime_risk_series_empty_is_safe() -> None:
    assert regime_risk_series(pd.DataFrame()).empty
