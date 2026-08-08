"""Tests du manifeste de run pour la reproductibilité (P5)."""
from __future__ import annotations

import platform
from unittest.mock import patch

from financial_analyzer.trading.journal import TradingJournal
from financial_analyzer.trading.run_manifest import (
    build_run_manifest,
    git_commit_sha,
    package_versions,
)


def test_manifest_has_core_fields():
    m = build_run_manifest(mode="paper", universe_size=1364)
    assert m["kind"] == "manifest"
    assert "ts" in m
    assert m["python_version"] == platform.python_version()
    assert "packages" in m and "numpy" in m["packages"]
    # extra fields passed through
    assert m["mode"] == "paper"
    assert m["universe_size"] == 1364


def test_git_sha_is_str_or_none():
    sha = git_commit_sha()
    assert sha is None or (isinstance(sha, str) and len(sha) >= 7)


def test_package_versions_absent_package_is_none():
    versions = package_versions(("numpy", "definitely-not-a-real-package-xyz"))
    assert versions["numpy"] is not None
    assert versions["definitely-not-a-real-package-xyz"] is None


def test_git_sha_none_on_failure():
    with patch(
        "financial_analyzer.trading.run_manifest.subprocess.run",
        side_effect=OSError("no git"),
    ):
        assert git_commit_sha() is None


def test_manifest_round_trips_through_journal(tmp_path):
    j = TradingJournal(tmp_path / "j.jsonl")
    j.record_manifest(build_run_manifest(mode="paper"))
    manifests = [e for e in j.read() if e.get("kind") == "manifest"]
    assert len(manifests) == 1
    assert manifests[0]["mode"] == "paper"
    assert "git_sha" in manifests[0]
