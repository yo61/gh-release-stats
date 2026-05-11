"""gh-release-stats: GitHub release-asset download stats."""

from __future__ import annotations

import re
from dataclasses import dataclass
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
