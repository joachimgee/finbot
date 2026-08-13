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

from financial_analyzer.trading.framework import (
    AlphaModel,
    ExecutionModel,
    PipelineAlpha,
    PipelineConstruction,
    PipelineExecution,
    PipelineRisk,
    PortfolioConstructionModel,
    RiskModel,
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
