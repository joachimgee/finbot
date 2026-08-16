"""Tests des configs de risque committées (source unique de vérité)."""
from __future__ import annotations

from financial_analyzer.trading.risk_config import (
    REQUIRED_LIMIT_KEYS,
    daemon_paper_risk_config,
    live_risk_config,
    risk_config_for,
)


def test_live_config_populates_all_required_limits() -> None:
    cfg = live_risk_config(100_000.0)
    assert all(cfg.get(k) is not None for k in REQUIRED_LIMIT_KEYS)
    assert cfg["enable_circuit_breaker"] is True


def test_live_config_is_conservative() -> None:
    cfg = live_risk_config(100_000.0)
    assert cfg["max_leverage"] == 1.0            # aucun levier au démarrage live
    assert cfg["max_position_pct"] <= 0.10       # concentration serrée
    assert cfg["max_drawdown"] >= -0.10          # halte à -10 % (aligné runbook #2)
    # Garde-fous portefeuille actifs (pas None).
    assert cfg["max_portfolio_vol"] and cfg["max_var_95"] and cfg["min_effective_bets"]


def test_dollar_limits_scale_with_capital() -> None:
    small = live_risk_config(10_000.0)
    big = live_risk_config(1_000_000.0)
    assert big["max_position_size"] == 100 * small["max_position_size"]
    assert big["max_daily_loss"] == 100 * small["max_daily_loss"]


def test_paper_config_reproduces_historical_daemon_values() -> None:
    # Comportement paper strictement inchangé : mêmes valeurs que l'inline historique.
    cfg = daemon_paper_risk_config(200_000.0)
    assert cfg["max_position_size"] == max(200_000.0, 50_000.0)
    assert cfg["max_position_pct"] == 0.35
    assert cfg["max_total_positions"] == 100
    assert cfg["max_drawdown"] == -0.25
    assert cfg["max_daily_loss"] == max(200_000.0 * 0.10, 1000.0)
    assert cfg["max_leverage"] == 1.5


def test_paper_config_low_equity_floor() -> None:
    cfg = daemon_paper_risk_config(0.0)
    assert cfg["max_position_size"] == 50_000.0   # plancher
    assert cfg["max_daily_loss"] == 1000.0        # plancher


def test_risk_config_for_selects_by_mode() -> None:
    assert risk_config_for("live", 100_000.0)["max_leverage"] == 1.0
    assert risk_config_for("paper", 100_000.0)["max_leverage"] == 1.5
