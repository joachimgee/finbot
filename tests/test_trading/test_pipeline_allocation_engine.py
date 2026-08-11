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

from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline


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
