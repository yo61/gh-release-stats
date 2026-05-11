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


def test_main_text_happy_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = (FIXTURES / "single_release.json").read_text()
    monkeypatch.setattr(rs, "run_gh", lambda args: payload)
    exit_code = rs.main(["yo61/x"])
    out = capsys.readouterr()
    assert exit_code == 0
    assert "v1.0.0" in out.out
    assert "Total" in out.out
    assert out.err == ""


def test_main_json_happy_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = (FIXTURES / "single_release.json").read_text()
    monkeypatch.setattr(rs, "run_gh", lambda args: payload)
    exit_code = rs.main(["yo61/x", "--json"])
    out = capsys.readouterr()
    assert exit_code == 0
    doc = json.loads(out.out)
    assert doc["repo"] == "yo61/x"
    assert doc["releases"][0]["tag"] == "v1.0.0"


def test_main_no_releases_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(rs, "run_gh", lambda args: "[]")
    assert rs.main(["yo61/x"]) == 2
    assert "no releases" in capsys.readouterr().err


def test_main_gh_missing_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(_args: list[str]) -> str:
        raise FileNotFoundError("gh")

    monkeypatch.setattr(rs, "run_gh", boom)
    assert rs.main(["yo61/x"]) == 2
    assert "gh CLI not found" in capsys.readouterr().err


def test_main_gh_error_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(_args: list[str]) -> str:
        raise rs.GhError("auth required")

    monkeypatch.setattr(rs, "run_gh", boom)
    assert rs.main(["yo61/x"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "auth required" in err


def test_main_no_arg_no_repo_context_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """When run without REPO and gh repo view fails."""

    def fail_repo_view(args: list[str]) -> str:
        raise rs.GhError("not a git repository")

    monkeypatch.setattr(rs, "run_gh", fail_repo_view)
    assert rs.main([]) == 2
    assert "not a git repository" in capsys.readouterr().err


def test_main_malformed_json_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(rs, "run_gh", lambda args: "not json")
    assert rs.main(["yo61/x"]) == 2
    assert "failed to parse" in capsys.readouterr().err


def test_main_keyboard_interrupt_exits_130(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_args: list[str]) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(rs, "run_gh", boom)
    assert rs.main(["yo61/x"]) == 130


def test_main_broken_pipe_exits_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = (FIXTURES / "single_release.json").read_text()
    monkeypatch.setattr(rs, "run_gh", lambda args: payload)
    monkeypatch.setattr(
        "sys.stdout.write",
        lambda *a, **kw: (_ for _ in ()).throw(BrokenPipeError),
    )
    assert rs.main(["yo61/x"]) == 0
