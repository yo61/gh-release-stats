"""gh-release-stats: GitHub release-asset download stats."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

# Asset filename → column key. Order matters: arm64 patterns must be
# checked before amd64/x86_64 patterns to avoid false positives.
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
