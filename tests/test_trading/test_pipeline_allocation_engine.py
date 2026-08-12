"""Tests de la fusion : LiveTradingPipeline comme moteur signal→allocation du daemon.

Le daemon délègue désormais sa décision de *taille* de position au
``LiveTradingPipeline`` (au lieu d'un poids égal 1/N) : signaux validés
(momentum 12-1 + abstention des sources stub) inclinés par Black-Litterman.
Ces tests verrouillent :

1. l'injection de dépendance (moniteur / RiskGuard / journal partagés), qui
   garantit un seul chokepoint audité entre le daemon et le pipeline ;
2. l'API publique ``compute_target_weights`` : poids pilotés par le signal,
   long-only, somme≈1, abstention (dict vide) quand aucun signal positif.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.trading.live_trading_pipeline import (
    LiveTradingPipeline,
    _cap_and_renormalize,
)


def _price_df(daily_drift: float, n: int = 260, seed: int = 0) -> pd.DataFrame:
    """OHLCV synthétique avec une dérive quotidienne contrôlée (momentum net)."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(daily_drift, 0.01, n)
    close = 100 * np.exp(np.cumsum(steps))
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99,
         "close": close, "volume": 1e6},
        index=idx,
    )


def _make_pipeline(tickers, journal=None):
    """Pipeline avec broker/moniteur/risk mockés (aucun appel réseau)."""
    broker = MagicMock()
    broker.connected = True
    broker.mode = "paper"
    monitor = MagicMock()
    risk = MagicMock()
    pipe = LiveTradingPipeline(
        broker_adapter=broker,
        tickers=list(tickers),
        account_monitor=monitor,
        risk_guard=risk,
        journal=journal,
    )
    return pipe, monitor, risk


# --- Injection de dépendance (chokepoint unique partagé) ---------------------

def test_dependency_injection_shares_instances() -> None:
    """Moniteur, RiskGuard et journal fournis sont réutilisés tels quels."""
    journal = object()
    pipe, monitor, risk = _make_pipeline(["AAPL", "MSFT"], journal=journal)
    assert pipe.monitor is monitor
    assert pipe.risk_guard is risk
    # Le journal partagé est bien branché sur l'unique gateway audité.
    assert pipe.order_gateway.journal is journal
    assert pipe.order_gateway.risk_guard is risk


def test_requires_connected_broker() -> None:
    """Contrat inchangé : un broker non connecté est refusé."""
    broker = MagicMock()
    broker.connected = False
    with pytest.raises(ValueError):
        LiveTradingPipeline(broker_adapter=broker, tickers=["AAPL"])


# --- compute_target_weights : allocation pilotée par le signal ---------------

def test_weights_are_signal_tilted_long_only() -> None:
    """Un titre en tendance haussière est retenu ; un baissier est exclu."""
    pipe, _, _ = _make_pipeline(["UP", "DOWN"])
    data = {
        "prices": {"UP": _price_df(0.004, seed=1), "DOWN": _price_df(-0.004, seed=2)},
        "fundamentals": {}, "news": {}, "sentiment": {},
    }
    weights, _ = pipe.compute_target_weights(data=data)

    assert weights, "un signal haussier doit produire au moins une position"
    assert set(weights).issubset({"UP", "DOWN"})
    assert "DOWN" not in weights  # momentum négatif -> signal <=0 -> exclu (long-only)
    assert all(w >= 0 for w in weights.values())
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_abstention_yields_no_positions() -> None:
    """Sans aucun signal positif (tout baissier), le moteur s'abstient (dict vide)."""
    pipe, _, _ = _make_pipeline(["D1", "D2"])
    data = {
        "prices": {"D1": _price_df(-0.005, seed=3), "D2": _price_df(-0.004, seed=4)},
        "fundamentals": {}, "news": {}, "sentiment": {},
    }
    weights, _ = pipe.compute_target_weights(data=data)
    assert weights == {}


def test_missing_price_data_symbol_is_dropped() -> None:
    """Un symbole sans données ne reçoit pas de poids (pas de 0.0 fabriqué)."""
    pipe, _, _ = _make_pipeline(["UP", "NODATA"])
    data = {
        "prices": {"UP": _price_df(0.004, seed=5)},  # NODATA absent
        "fundamentals": {}, "news": {}, "sentiment": {},
    }
    weights, _ = pipe.compute_target_weights(data=data)
    assert "NODATA" not in weights
    assert set(weights).issubset({"UP"})


def test_run_reuses_compute_target_weights(monkeypatch) -> None:
    """``run()`` et la délégation partagent le même cœur de décision."""
    pipe, monitor, risk = _make_pipeline(["UP"])
    monitor.portfolio_value = 100000.0
    monitor.daily_pnl = 0.0
    monitor.positions = []
    risk.circuit_breaker_active = False
    called = {}

    real = pipe.compute_target_weights

    def _spy(data=None):
        called["hit"] = True
        return real(data={
            "prices": {"UP": _price_df(0.004, seed=6)},
            "fundamentals": {}, "news": {}, "sentiment": {},
        })

    monkeypatch.setattr(pipe, "compute_target_weights", _spy)
    monkeypatch.setattr(pipe.broker, "is_market_open", lambda: True, raising=False)
    pipe.order_gateway.submit = MagicMock(return_value={"status": "filled", "order_id": "x"})

    result = pipe.run(force=True)
    assert called.get("hit") is True
    assert result["status"] in {"success", "failed"}  # exécution mockée, cœur appelé


def test_cap_and_renormalize_respects_cap_and_sums_to_one() -> None:
    """Un poids au-dessus du cap est plafonné et l'excédent redistribué (somme=1)."""
    capped = _cap_and_renormalize(
        {"JNJ": 0.32, "GOOGL": 0.14, "XOM": 0.13, "AAPL": 0.11, "NVDA": 0.10,
         "KO": 0.08, "CVX": 0.06, "JPM": 0.05, "AMZN": 0.01}, 0.25)
    assert max(capped.values()) <= 0.25 + 1e-9
    assert sum(capped.values()) == pytest.approx(1.0, abs=1e-9)
    assert capped["JNJ"] == pytest.approx(0.25, abs=1e-9)


def test_cap_leaves_cash_when_too_few_names() -> None:
    """Si cap*n < 1, tout est au cap et le reste demeure en cash (limite respectée)."""
    capped = _cap_and_renormalize({"A": 0.5, "B": 0.3, "C": 0.2}, 0.25)
    assert all(v <= 0.25 + 1e-9 for v in capped.values())
    assert sum(capped.values()) == pytest.approx(0.75, abs=1e-9)


def test_compute_target_weights_applies_concentration_cap() -> None:
    """compute_target_weights ne renvoie aucun poids au-dessus du cap du RiskGuard."""
    pipe, _, risk = _make_pipeline(["UP"])
    risk.max_position_pct = 0.25
    pipe._generate_signals = lambda data: {}  # type: ignore[assignment]
    pipe._optimize_portfolio = lambda signals, data: {"A": 0.6, "B": 0.25, "C": 0.15}  # type: ignore[assignment]
    weights, _ = pipe.compute_target_weights(data={"prices": {}})
    assert max(weights.values()) <= 0.25 + 1e-9


def test_vol_overlay_off_by_default_leaves_weights() -> None:
    """Sans target_vol, l'exposition reste pleine (somme des poids ≈ 1)."""
    pipe, _, _ = _make_pipeline(["UP", "DOWN"])
    assert pipe.target_vol is None
    data = {"prices": {"UP": _price_df(0.004, seed=1), "DOWN": _price_df(-0.004, seed=2)},
            "fundamentals": {}, "news": {}, "sentiment": {}}
    weights, _ = pipe.compute_target_weights(data=data)
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_vol_overlay_reduces_exposure_when_enabled() -> None:
    """Avec target_vol bas et des titres volatils, l'exposition est réduite (< 1)."""
    broker = MagicMock()
    broker.connected = True
    broker.mode = "paper"
    pipe = LiveTradingPipeline(
        broker_adapter=broker, tickers=["UP"], account_monitor=MagicMock(),
        risk_guard=MagicMock(), target_vol=0.05, max_exposure=1.0, risk_off_ma=50,
    )
    # Titre haussier (momentum 12-1 > 0, historique ≥252 j) mais très volatil ->
    # vol ex-ante >> 5% -> l'overlay réduit l'exposition.
    close = 100 * np.exp(np.cumsum(np.random.default_rng(9).normal(0.004, 0.05, 300)))
    idx = pd.date_range("2024-01-01", periods=300, freq="D")
    df = pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99,
         "close": close, "volume": 1e6}, index=idx)
    data = {"prices": {"UP": df}, "fundamentals": {}, "news": {}, "sentiment": {}}
    weights, _ = pipe.compute_target_weights(data=data)
    assert weights, "attendu au moins une position"
    assert sum(weights.values()) < 0.95  # exposition réduite par l'overlay


def test_dry_run_flows_through_to_gateway(monkeypatch) -> None:
    """run(dry_run=True) fait passer dry_run jusqu'au gateway (aucune soumission réelle)."""
    pipe, monitor, risk = _make_pipeline(["UP"])
    monitor.portfolio_value = 100000.0
    monitor.daily_pnl = 0.0
    monitor.positions = []
    risk.circuit_breaker_active = False

    monkeypatch.setattr(pipe, "compute_target_weights", lambda data=None: (
        {"UP": 1.0},
        {"prices": {"UP": _price_df(0.004, seed=7)}, "fundamentals": {}, "news": {}, "sentiment": {}},
    ))
    monkeypatch.setattr(pipe.broker, "is_market_open", lambda: True, raising=False)
    submit = MagicMock(return_value={"status": "dry_run"})
    pipe.order_gateway.submit = submit

    pipe.run(force=True, dry_run=True)
    assert submit.called, "un ordre aurait dû atteindre le gateway"
    assert all(call.kwargs.get("dry_run") is True for call in submit.call_args_list)
