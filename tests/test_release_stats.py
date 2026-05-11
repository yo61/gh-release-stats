"""Tests for the gh-subprocess seam, repo resolution, fetching, and main()."""

from __future__ import annotations

import subprocess

import pytest

import release_stats as rs


def test_run_gh_returns_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:
        assert cmd[0] == "gh"
        assert cmd[1:] == ["api", "/test"]
        return subprocess.CompletedProcess(cmd, 0, stdout="hello\n", stderr="")

    monkeypatch.setattr(rs.subprocess, "run", fake_run)
    assert rs.run_gh(["api", "/test"]) == "hello\n"


def test_run_gh_raises_on_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_kw: object) -> None:
        raise FileNotFoundError("gh")

    monkeypatch.setattr(rs.subprocess, "run", boom)
    with pytest.raises(FileNotFoundError):
        rs.run_gh(["--version"])


def test_run_gh_raises_with_stderr_on_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="auth required\n")

    monkeypatch.setattr(rs.subprocess, "run", fail)
    with pytest.raises(rs.GhError) as ei:
        rs.run_gh(["api", "/x"])
    assert "auth required" in str(ei.value)


def test_run_gh_raises_with_fallback_on_empty_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="")

    monkeypatch.setattr(rs.subprocess, "run", fail)
    with pytest.raises(rs.GhError, match="gh exited 2"):
        rs.run_gh(["api", "/x"])
