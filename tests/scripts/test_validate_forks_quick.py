import os
import sys
import subprocess
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_forks_quick.py"


def run_script_offline_env():
    env = os.environ.copy()
    env["FINBOT_OFFLINE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=ROOT,
        text=True,
        timeout=60,
    )
    return proc


def test_quick_validation_offline_passes_exit_zero():
    proc = run_script_offline_env()
    assert proc.returncode == 0, f"Unexpected exit code. Output:\n{proc.stdout}"


def test_quick_validation_offline_outputs_skip_markers():
    proc = run_script_offline_env()
    out = proc.stdout
    assert "SKIP (OFFLINE): FinanceDatabase" in out
    assert "SKIP (OFFLINE): yfinance" in out


def test_quick_validation_offline_contains_cvar_optimization():
    proc = run_script_offline_env()
    out = proc.stdout
    assert "CVaR optimization:" in out
    assert "VALIDATION 3: PASS" in out


def test_quick_validation_flag_offline_passes_via_runpy(monkeypatch, capsys):
    # Run in-process to ensure flag parsing works
    argv_backup = sys.argv[:]
    try:
        sys.argv = [str(SCRIPT), "--offline"]
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as e:
            assert int(e.code) == 0
        out = capsys.readouterr().out
        assert "Mode OFFLINE" in out
        assert "SKIP (OFFLINE): FinanceDatabase" in out
        assert "SKIP (OFFLINE): yfinance" in out
    finally:
        sys.argv = argv_backup
