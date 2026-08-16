"""Tests du rapport de préparation au live (go/no-go depuis les artefacts)."""
from __future__ import annotations

import json
from pathlib import Path

from financial_analyzer.trading.readiness import (
    CLEAN_RUN_TARGET,
    evaluate_readiness,
    load_runs,
)


def _write_journal(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _run(tmp: Path, name: str, *, recon_ok: bool | None, equity: float | None = None) -> Path:
    recs: list[dict] = [{"ts": name, "kind": "order", "symbol": "AAPL"}]
    if equity is not None:
        recs.append({"ts": name, "kind": "snapshot", "equity": equity, "event": "run_end"})
    if recon_ok is not None:  # None = dry-run (pas de réconciliation)
        recs.append({"ts": name, "kind": "reconciliation", "ok": recon_ok, "n_matched": 3})
    p = tmp / f"{name}.jsonl"
    _write_journal(p, recs)
    return p


def test_load_runs_flags_reconciliation(tmp_path: Path) -> None:
    paths = [
        _run(tmp_path, "2026-01-01", recon_ok=True),
        _run(tmp_path, "2026-01-02", recon_ok=None),   # dry-run
        _run(tmp_path, "2026-01-03", recon_ok=False),
    ]
    runs = load_runs(paths)
    assert [r["has_recon"] for r in runs] == [True, False, True]
    assert [r["recon_ok"] for r in runs] == [True, False, False]


def test_streak_counts_only_trailing_clean_runs(tmp_path: Path) -> None:
    # Un écart ancien puis 3 runs propres -> streak = 3 (dry-runs ignorés).
    paths = [
        _run(tmp_path, "2026-01-01", recon_ok=False),
        _run(tmp_path, "2026-01-02", recon_ok=True),
        _run(tmp_path, "2026-01-03", recon_ok=None),   # dry-run, ignoré
        _run(tmp_path, "2026-01-04", recon_ok=True),
        _run(tmp_path, "2026-01-05", recon_ok=True),
    ]
    rep = evaluate_readiness(paths)
    crit1 = next(c for c in rep.criteria if c.id == 1)
    assert "streak=3" in crit1.measured
    assert crit1.status == "fail"  # 3 < 20


def test_ready_when_all_auto_pass(tmp_path: Path, monkeypatch) -> None:
    # 20 runs propres consécutifs avec equity stable (drawdown 0) + env/état requis.
    paths = [_run(tmp_path, f"2026-02-{i:02d}", recon_ok=True, equity=100000.0)
             for i in range(1, CLEAN_RUN_TARGET + 1)]
    (tmp_path / "rebalance_state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("FINBOT_ALERT_WEBHOOK", "https://hook.example")
    rep = evaluate_readiness(paths, rebalance_state=tmp_path / "rebalance_state.json")
    crit1 = next(c for c in rep.criteria if c.id == 1)
    assert crit1.status == "pass"
    # Tous les critères auto doivent passer -> prêt côté auto.
    assert rep.ready, [f"#{c.id}:{c.status}:{c.measured}" for c in rep.auto if c.status != "pass"]


def test_missing_snapshots_fail_drawdown_criterion(tmp_path: Path) -> None:
    paths = [_run(tmp_path, "2026-03-01", recon_ok=True)]  # pas d'equity
    rep = evaluate_readiness(paths)
    crit2 = next(c for c in rep.criteria if c.id == 2)
    assert crit2.status == "fail"
    assert "snapshot" in crit2.measured


def test_large_drawdown_fails(tmp_path: Path) -> None:
    paths = [
        _run(tmp_path, "2026-04-01", recon_ok=True, equity=100000.0),
        _run(tmp_path, "2026-04-02", recon_ok=True, equity=85000.0),  # −15 %
    ]
    rep = evaluate_readiness(paths)
    crit2 = next(c for c in rep.criteria if c.id == 2)
    assert crit2.status == "fail"


def test_operator_criteria_are_manual(tmp_path: Path) -> None:
    rep = evaluate_readiness([_run(tmp_path, "2026-05-01", recon_ok=True)])
    manual_ids = {c.id for c in rep.operator}
    # #5 (config de risque live) est désormais auto-vérifiable → reste 4/8/10.
    assert manual_ids == {4, 8, 10}  # chokepoint, kill-switch, capital


def test_live_risk_config_criterion_passes(tmp_path: Path) -> None:
    rep = evaluate_readiness([_run(tmp_path, "2026-06-01", recon_ok=True)])
    crit5 = next(c for c in rep.criteria if c.id == 5)
    assert crit5.kind == "auto" and crit5.status == "pass"
