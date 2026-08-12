"""Suivi P&L (P4) — dérivation depuis les snapshots du journal."""
from __future__ import annotations

import pytest

from financial_analyzer.trading.journal import TradingJournal
from financial_analyzer.trading.pnl import compute_pnl, load_snapshots


def _snap(ts, equity, event=None):
    d = {"kind": "snapshot", "ts": ts, "equity": equity}
    if event:
        d["event"] = event
    return d


def test_empty_report() -> None:
    r = compute_pnl([])
    assert r.n_snapshots == 0 and r.total_pnl == 0.0
    assert "aucun snapshot" in r.summary()


def test_pnl_and_return() -> None:
    snaps = [_snap("2026-01-01T00:00:00Z", 100_000, "run_start"),
             _snap("2026-01-02T00:00:00Z", 110_000, "run_end")]
    r = compute_pnl(snaps)
    assert r.start_equity == 100_000 and r.end_equity == 110_000
    assert r.total_pnl == pytest.approx(10_000)
    assert r.total_return_pct == pytest.approx(10.0)
    assert r.n_runs == 1  # un seul run_end


def test_max_drawdown_peak_to_trough() -> None:
    snaps = [_snap("2026-01-01T00:00:00Z", 100.0),
             _snap("2026-01-02T00:00:00Z", 120.0),   # pic
             _snap("2026-01-03T00:00:00Z", 90.0),    # creux -> dd = (90-120)/120
             _snap("2026-01-04T00:00:00Z", 110.0)]
    r = compute_pnl(snaps)
    assert r.peak_equity == pytest.approx(120.0)
    assert r.max_drawdown_pct == pytest.approx(-25.0, abs=1e-9)


def test_sorts_by_ts_and_ignores_non_numeric() -> None:
    snaps = [_snap("2026-01-03T00:00:00Z", 130.0),
             _snap("2026-01-01T00:00:00Z", 100.0),
             {"kind": "snapshot", "ts": "2026-01-02T00:00:00Z", "equity": None}]  # ignoré
    r = compute_pnl(snaps)
    assert r.n_snapshots == 2  # le None est écarté
    assert r.start_equity == 100.0 and r.end_equity == 130.0


def test_load_snapshots_merges_journals(tmp_path) -> None:
    j1 = TradingJournal(tmp_path / "a.jsonl")
    j1.record_snapshot(equity=100.0, event="run_start")
    j1.record_order(symbol="AAPL", side="buy", qty=1, order_type="market",
                    mode="paper", status="filled")  # pas un snapshot
    j2 = TradingJournal(tmp_path / "b.jsonl")
    j2.record_snapshot(equity=105.0, event="run_end")

    snaps = load_snapshots([tmp_path / "a.jsonl", tmp_path / "b.jsonl", tmp_path / "missing.jsonl"])
    assert len(snaps) == 2  # ordres et fichier absent ignorés
    r = compute_pnl(snaps)
    assert r.total_pnl == pytest.approx(5.0)
