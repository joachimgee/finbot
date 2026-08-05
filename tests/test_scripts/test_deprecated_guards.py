"""P4: the redundant order-submitting scripts refuse to run (they bypass the
OrderGateway chokepoint). The canonical path is professional_analysis_daemon.py."""
import pytest


@pytest.fixture(autouse=True)
def _clear_override(monkeypatch):
    monkeypatch.delenv("FINBOT_ALLOW_DEPRECATED_SCRIPTS", raising=False)


def test_professional_analysis_refuses(capsys):
    from scripts.professional_analysis import main
    assert main() == 1
    assert "DEPRECATED" in capsys.readouterr().err


def test_run_daily_manager_refuses(capsys):
    from scripts.run_daily_professional_manager import main
    assert main() == 1
    assert "DEPRECATED" in capsys.readouterr().err


def test_override_bypasses_guard(monkeypatch):
    # With the override set, the guard no longer short-circuits — the script then
    # proceeds into argparse. We only assert the guard itself is passed (i.e. the
    # early return 1 does not fire), by checking it raises SystemExit from argparse
    # rather than returning 1.
    monkeypatch.setenv("FINBOT_ALLOW_DEPRECATED_SCRIPTS", "1")
    monkeypatch.setattr("sys.argv", ["run_daily_professional_manager.py", "--bad-unknown-flag"])
    from scripts.run_daily_professional_manager import main
    with pytest.raises(SystemExit):
        main()
