"""Tests for the gh-subprocess seam, repo resolution, fetching, and main()."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

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


def test_resolve_repo_returns_arg_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[list[str]] = []

    def fake_run_gh(args: list[str]) -> str:
        called.append(args)
        return ""

    monkeypatch.setattr(rs, "run_gh", fake_run_gh)
    assert rs.resolve_repo("yo61/go-udap") == "yo61/go-udap"
    assert called == []  # gh was not invoked


def test_resolve_repo_calls_gh_when_arg_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_gh(args: list[str]) -> str:
        assert args == ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
        return "yo61/go-udap\n"

    monkeypatch.setattr(rs, "run_gh", fake_run_gh)
    assert rs.resolve_repo(None) == "yo61/go-udap"


FIXTURES = Path(__file__).parent / "fixtures"


def test_fetch_releases_parses_real_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (FIXTURES / "yo61_go-udap_releases.json").read_text()

    def fake_run_gh(args: list[str]) -> str:
        assert args == ["api", "repos/yo61/go-udap/releases", "--paginate"]
        return payload

    monkeypatch.setattr(rs, "run_gh", fake_run_gh)
    releases = rs.fetch_releases("yo61/go-udap")
    assert isinstance(releases, list)
    assert len(releases) > 0
    assert "tag_name" in releases[0]
    assert "assets" in releases[0]


def test_fetch_releases_raises_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rs, "run_gh", lambda _args: "not json")
    with pytest.raises(json.JSONDecodeError):
        rs.fetch_releases("yo61/go-udap")
