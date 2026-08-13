"""Cadre en couches enfichables (audit #5) — contrats + injection.

Vérifie (1) que les adaptateurs par défaut satisfont les Protocols, (2) que le
pipeline câble bien les quatre étages par défaut, (3) qu'injecter un modèle custom
remplace *ce seul* étage (pluggabilité), (4) que le comportement par défaut est
inchangé (les défauts délèguent à la logique existante).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.trading.framework import (
    AlphaModel,
    ExecutionModel,
    HRPConstruction,
    PipelineAlpha,
    PipelineConstruction,
    PipelineExecution,
    PipelineRisk,
    PortfolioConstructionModel,
    RiskModel,
    ScheduledExecution,
)
from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline


def _price_df(drift: float, n: int = 260, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": 1e6}, index=idx)


def _make_pipeline(**kw):
    broker = MagicMock()
    broker.connected = True
    broker.mode = "paper"
    return LiveTradingPipeline(
        broker_adapter=broker, tickers=["UP", "DOWN"], account_monitor=MagicMock(),
        risk_guard=MagicMock(), **kw)


def test_default_layers_are_wired_and_conform_to_protocols() -> None:
    pipe = _make_pipeline()
    assert isinstance(pipe.alpha, (PipelineAlpha, AlphaModel))
    assert isinstance(pipe.construction, (PipelineConstruction, PortfolioConstructionModel))
    assert isinstance(pipe.risk_model, (PipelineRisk, RiskModel))
    assert isinstance(pipe.execution, (PipelineExecution, ExecutionModel))
    # Conformité structurelle (Protocol runtime_checkable).
    assert isinstance(pipe.alpha, AlphaModel)
    assert isinstance(pipe.execution, ExecutionModel)


def test_injected_alpha_replaces_only_that_stage() -> None:
    """Un alpha custom pilote les signaux ; la construction par défaut suit."""
    class ConstantAlpha:
        def generate(self, data):
            return {"UP": 1.0}  # conviction longue sur UP uniquement

    pipe = _make_pipeline(alpha=ConstantAlpha())
    data = {"prices": {"UP": _price_df(0.0, seed=1), "DOWN": _price_df(0.0, seed=2)},
            "fundamentals": {}, "news": {}, "sentiment": {}}
    weights, _ = pipe.compute_target_weights(data=data)
    assert set(weights).issubset({"UP"})  # l'alpha injecté décide de l'univers retenu
    assert weights.get("UP", 0) > 0


def test_injected_construction_replaces_only_that_stage() -> None:
    """Une construction custom impose les poids, quels que soient les signaux."""
    class FixedConstruction:
        def construct(self, signals, data):
            return {"UP": 0.7, "DOWN": 0.3}

    pipe = _make_pipeline(construction=FixedConstruction())
    data = {"prices": {"UP": _price_df(0.004, seed=1)}, "fundamentals": {},
            "news": {}, "sentiment": {}}
    weights, _ = pipe.compute_target_weights(data=data)
    assert weights == {"UP": 0.7, "DOWN": 0.3}


def test_hrp_construction_sizes_selected_names() -> None:
    """HRP conforme au Protocol, dimensionne les noms sélectionnés (signal>0),
    poids ≥ 0 sommant ≈ 1 sur ces noms."""
    pipe = _make_pipeline()
    pipe.tickers = ["A", "B", "C", "D"]
    hrp = HRPConstruction(pipe, lookback=200, min_names=3)
    assert isinstance(hrp, PortfolioConstructionModel)
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=260, freq="D")

    def _px(vol):
        return pd.DataFrame({"close": 100 * np.exp(np.cumsum(rng.normal(0, vol, 260)))}, index=idx)

    data = {"prices": {"A": _px(0.01), "B": _px(0.02), "C": _px(0.015), "D": _px(0.008)}}
    signals = {"A": 0.8, "B": 0.5, "C": 0.3, "D": 0.6}  # tous longs
    weights = hrp.construct(signals, data)
    assert set(weights).issubset({"A", "B", "C", "D"})
    assert all(w >= 0 for w in weights.values())
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_hrp_construction_falls_back_when_too_few_names() -> None:
    """Trop peu de noms exploitables -> repli sur la construction BL par défaut."""
    pipe = _make_pipeline()
    called = {}

    def _bl(signals, data):
        called["bl"] = True
        return {"X": 1.0}

    pipe._construct_weights = _bl
    hrp = HRPConstruction(pipe, min_names=3)
    out = hrp.construct({"A": 0.5}, {"prices": {}})  # aucune donnée -> repli
    assert called.get("bl") is True
    assert out == {"X": 1.0}


def test_scheduled_execution_slices_parent_into_children() -> None:
    """ScheduledExecution découpe un ordre parent en tranches à clés idempotentes
    uniques, toutes soumises via le gateway, quantité totale préservée."""
    pipe = _make_pipeline()
    pipe._generate_orders = lambda tw, data: [
        {"symbol": "UP", "qty": 100, "side": "buy", "price": 10.0, "order_type": "market"}]
    submitted = []

    def _exec(orders, dry_run=False):
        submitted.extend(orders)
        return [{"status": "executed"} for _ in orders]

    pipe._execute_orders_with_risk_checks = _exec
    ex = ScheduledExecution(pipe, n_slices=4, kappa=0.0)  # TWAP
    results = ex.execute({"UP": 1.0}, {"prices": {}}, dry_run=False)
    assert len(submitted) == 4  # 4 tranches
    assert sum(o["qty"] for o in submitted) == 100  # total préservé
    keys = [o["idempotency_key"] for o in submitted]
    assert len(set(keys)) == 4  # clés uniques -> pas de dédup
    assert len(results) == 4


def test_scheduled_execution_conforms_to_protocol() -> None:
    assert isinstance(ScheduledExecution(_make_pipeline()), ExecutionModel)


def test_injected_risk_model_can_veto() -> None:
    """Un risk model qui refuse tout fait sauter le rééquilibrage (status skipped)."""
    class VetoRisk:
        def evaluate(self, weights, data):
            return False, weights

    pipe = _make_pipeline(risk_model=VetoRisk())
    pipe.monitor.portfolio_value = 100000.0
    pipe.monitor.daily_pnl = 0.0
    pipe.monitor.positions = []
    pipe.risk_guard.circuit_breaker_active = False
    pipe.compute_target_weights = lambda data=None: ({"UP": 1.0}, {"prices": {}})
    pipe.broker.is_market_open = lambda: True
    result = pipe.run(force=True)
    assert result["status"] == "skipped"
    assert result["reason"] == "portfolio_risk_limit"


def test_injected_execution_receives_target_weights() -> None:
    """Un exécuteur custom reçoit les poids cibles et son retour pilote le résultat."""
    seen = {}

    class SpyExecution:
        def execute(self, target_weights, data, *, dry_run):
            seen["weights"] = target_weights
            seen["dry_run"] = dry_run
            return [{"status": "executed"}, {"status": "executed"}]

    pipe = _make_pipeline(execution=SpyExecution())
    pipe.monitor.portfolio_value = 100000.0
    pipe.monitor.daily_pnl = 0.0
    pipe.monitor.positions = []
    pipe.risk_guard.circuit_breaker_active = False
    pipe.compute_target_weights = lambda data=None: ({"UP": 1.0}, {"prices": {}})
    pipe.broker.is_market_open = lambda: True

    result = pipe.run(force=True, dry_run=True)
    assert seen["weights"] == {"UP": 1.0}
    assert seen["dry_run"] is True
    assert result["orders_executed"] == 2
