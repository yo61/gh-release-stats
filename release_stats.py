"""gh-release-stats: GitHub release-asset download stats."""

from __future__ import annotations

import re

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
