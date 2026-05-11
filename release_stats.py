"""gh-release-stats: GitHub release-asset download stats."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

# Asset filename → column key. Listed in display order (arm64 before
# x86_64 within each OS group is convention only — the patterns are
# unambiguous, so order doesn't affect correctness).
_CLASSIFIERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"linux[_-]arm64"), "larm"),
    (re.compile(r"linux[_-](?:amd64|x86_64)"), "lx86"),
    (re.compile(r"(?:macos|darwin)[_-]arm64"), "marm"),
    (re.compile(r"(?:macos|darwin)[_-](?:amd64|x86_64)"), "mx86"),
    (re.compile(r"windows"), "win"),
    (re.compile(r"^SHA256SUMS$"), "sha"),
)


def classify_asset(name: str) -> str:
    """Map a release-asset filename to its column key.

    Args:
        name: The asset's filename as returned by the GitHub API.

    Returns:
        One of: ``lx86``, ``larm``, ``mx86``, ``marm``, ``win``,
        ``sha``, ``other``.
    """
    for pattern, key in _CLASSIFIERS:
        if pattern.search(name):
            return key
    return "other"


@dataclass(frozen=True, slots=True)
class Row:
    """Per-release download counts. One per tag."""

    tag: str
    linux_x86_64: int
    linux_arm64: int
    macos_x86_64: int
    macos_arm64: int
    windows: int
    sha256sums: int
    total: int


@dataclass(frozen=True, slots=True)
class Totals:
    """Cross-release totals. One per invocation."""

    linux_x86_64: int
    linux_arm64: int
    macos_x86_64: int
    macos_arm64: int
    windows: int
    sha256sums: int
    grand_total: int


# column key (from classify_asset) → Row attribute
_KEY_TO_ATTR: dict[str, str] = {
    "lx86": "linux_x86_64",
    "larm": "linux_arm64",
    "mx86": "macos_x86_64",
    "marm": "macos_arm64",
    "win": "windows",
    "sha": "sha256sums",
}


def aggregate(releases: list[dict[str, Any]]) -> tuple[list[Row], Totals]:
    """Group asset downloads by release and column.

    Args:
        releases: The raw list returned by ``gh api repos/X/Y/releases``.

    Returns:
        A tuple ``(rows, totals)`` where ``rows`` is one ``Row`` per
        release in input order, and ``totals`` is the cross-release
        ``Totals`` object.
    """
    cols = list(_KEY_TO_ATTR.values())
    rows: list[Row] = []
    grand: dict[str, int] = dict.fromkeys(cols, 0)

    for release in releases:
        per_row: dict[str, int] = dict.fromkeys(cols, 0)
        for asset in release.get("assets", []):
            key = classify_asset(asset["name"])
            attr = _KEY_TO_ATTR.get(key)
            if attr is None:  # 'other' — drop silently
                continue
            per_row[attr] += asset["download_count"]
            grand[attr] += asset["download_count"]
        row_total = sum(per_row.values())
        rows.append(Row(tag=release["tag_name"], **per_row, total=row_total))

    totals = Totals(**grand, grand_total=sum(grand.values()))
    return rows, totals


# (display_label, Row attribute name, Totals attribute name)
# Order is the rendering order, left to right.
_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("Tag", "tag", ""),  # special: not numeric, no Totals attr
    ("linux x86_64", "linux_x86_64", "linux_x86_64"),
    ("linux arm64", "linux_arm64", "linux_arm64"),
    ("macos x86_64", "macos_x86_64", "macos_x86_64"),
    ("macos arm64", "macos_arm64", "macos_arm64"),
    ("windows", "windows", "windows"),
    ("SHA256SUMS", "sha256sums", "sha256sums"),
    ("Total", "total", "grand_total"),
)

_COL_GAP = "   "


def render_text(rows: list[Row], totals: Totals) -> str:
    """Render rows + totals as an aligned plain-text table.

    Args:
        rows: Per-release rows (in display order).
        totals: Cross-release totals (rendered as the bottom row).

    Returns:
        The full table as a single UTF-8 string ending with a newline.
    """
    # Build raw cell values for each column (header + data + total).
    cells: list[list[str]] = []
    for label, row_attr, tot_attr in _COLUMNS:
        col = [label]
        for r in rows:
            col.append(str(getattr(r, row_attr)))
        if tot_attr:
            col.append(str(getattr(totals, tot_attr)))
        else:
            col.append("Total")
        cells.append(col)

    widths = [max(len(c) for c in col) for col in cells]

    def fmt(values: list[str]) -> str:
        parts: list[str] = []
        for i, (v, w) in enumerate(zip(values, widths, strict=True)):
            parts.append(v.ljust(w) if i == 0 else v.rjust(w))
        return _COL_GAP.join(parts)

    header = fmt([col[0] for col in cells])
    sep = _COL_GAP.join("-" * w for w in widths)
    data_lines = [fmt([col[i] for col in cells]) for i in range(1, len(cells[0]) - 1)]
    total_line = fmt([col[-1] for col in cells])

    lines = [header, sep, *data_lines, sep, total_line]
    return "\n".join(lines) + "\n"


def render_json(repo: str, rows: list[Row], totals: Totals, *, fetched_at: str) -> str:
    """Render rows + totals as a pretty-printed JSON document.

    Args:
        repo: ``owner/name`` of the repository (for traceability).
        rows: Per-release rows (in display order).
        totals: Cross-release totals.
        fetched_at: ISO-8601 UTC timestamp of when ``gh api`` was called.

    Returns:
        UTF-8 JSON, indent=2, with a trailing newline.
    """
    doc = {
        "repo": repo,
        "fetched_at": fetched_at,
        "releases": [asdict(r) for r in rows],
        "totals": asdict(totals),
    }
    return json.dumps(doc, indent=2) + "\n"


class GhError(RuntimeError):
    """Raised when `gh` exits non-zero. Carries gh's stderr verbatim."""


def run_gh(args: list[str]) -> str:
    """Run ``gh <args...>`` and return stdout.

    Args:
        args: Arguments to pass to ``gh`` (the binary name itself is prepended).

    Returns:
        The captured stdout as a string.

    Raises:
        FileNotFoundError: If ``gh`` is not on PATH.
        GhError: If ``gh`` exits non-zero.
    """
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GhError(result.stderr.strip() or f"gh exited {result.returncode}")
    return result.stdout


def fetch_releases(repo: str) -> list[dict[str, Any]]:
    """Fetch all releases (paginated) for ``repo`` via ``gh api``.

    Args:
        repo: ``owner/name`` of the repository.

    Returns:
        The raw JSON list as returned by the GitHub API.

    Raises:
        GhError: From ``run_gh``.
        json.JSONDecodeError: If gh's stdout is not valid JSON.
    """
    stdout = run_gh(["api", f"repos/{repo}/releases", "--paginate"])
    return json.loads(stdout)


def resolve_repo(arg: str | None) -> str:
    """Return ``arg`` if given, else delegate to ``gh repo view``.

    Args:
        arg: Either ``owner/name`` or ``None``.

    Returns:
        ``owner/name`` of the target repository.

    Raises:
        GhError: Propagated from ``run_gh`` if the user is not in a repo.
    """
    if arg:
        return arg
    return run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()


def _die(msg: str) -> int:
    """Write ``error: <msg>`` to stderr and return exit code 2."""
    print(f"error: {msg}", file=sys.stderr)
    return 2


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse argv via argparse and return the resulting namespace."""
    parser = argparse.ArgumentParser(
        prog="gh release-stats",
        description="Print GitHub release-asset download stats.",
    )
    parser.add_argument(
        "repo",
        nargs="?",
        help="owner/name (default: current repo via 'gh repo view')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of a text table",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list (excluding the program name). ``None`` means
            read from ``sys.argv``.

    Returns:
        Process exit code (0 success, 2 expected failure, 130 Ctrl-C).
    """
    try:
        args = _parse_args(argv)
        repo = resolve_repo(args.repo)
        releases = fetch_releases(repo)
        if not releases:
            return _die(f"{repo} has no releases")
        rows, totals = aggregate(releases)
        if args.json:
            fetched_at = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            output = render_json(repo, rows, totals, fetched_at=fetched_at)
        else:
            output = render_text(rows, totals)
        try:
            sys.stdout.write(output)
        except BrokenPipeError:
            return 0
        return 0
    except FileNotFoundError:
        return _die("gh CLI not found on PATH; install from https://cli.github.com/")
    except GhError as exc:
        return _die(str(exc))
    except json.JSONDecodeError as exc:
        return _die(f"failed to parse gh output: {exc.msg}")
    except KeyboardInterrupt:
        return 130
