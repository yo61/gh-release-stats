"""Tests for aggregate(): raw releases → (rows, totals)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from release_stats import Row, Totals, aggregate


def test_aggregate_empty(load_fixture: Callable[[str], Any]) -> None:
    rows, totals = aggregate(load_fixture("empty_releases.json"))
    assert rows == []
    assert totals == Totals(
        linux_x86_64=0,
        linux_arm64=0,
        macos_x86_64=0,
        macos_arm64=0,
        windows=0,
        sha256sums=0,
        grand_total=0,
    )


def test_aggregate_single_release(load_fixture: Callable[[str], Any]) -> None:
    rows, totals = aggregate(load_fixture("single_release.json"))
    assert rows == [
        Row(
            tag="v1.0.0",
            linux_x86_64=7,
            linux_arm64=0,
            macos_x86_64=0,
            macos_arm64=3,
            windows=0,
            sha256sums=1,
            total=11,
        )
    ]
    assert totals == Totals(
        linux_x86_64=7,
        linux_arm64=0,
        macos_x86_64=0,
        macos_arm64=3,
        windows=0,
        sha256sums=1,
        grand_total=11,
    )


def test_aggregate_v0_naming_normalised(load_fixture: Callable[[str], Any]) -> None:
    rows, totals = aggregate(load_fixture("v0_naming_release.json"))
    assert rows[0] == Row(
        tag="v0.1.0",
        linux_x86_64=5,
        linux_arm64=0,
        macos_x86_64=1,
        macos_arm64=1,
        windows=17,
        sha256sums=0,
        total=24,
    )
    assert totals == Totals(
        linux_x86_64=5,
        linux_arm64=0,
        macos_x86_64=1,
        macos_arm64=1,
        windows=17,
        sha256sums=0,
        grand_total=24,
    )


def test_aggregate_other_assets_dropped() -> None:
    """Assets that classify as 'other' don't contribute to any column."""
    releases = [
        {
            "tag_name": "v9.9.9",
            "assets": [
                {"name": "README.md", "download_count": 99},
                {"name": "go-udap_9.9.9_linux_x86_64.tar.gz", "download_count": 1},
            ],
        }
    ]
    rows, totals = aggregate(releases)
    assert rows == [
        Row(
            tag="v9.9.9",
            linux_x86_64=1,
            linux_arm64=0,
            macos_x86_64=0,
            macos_arm64=0,
            windows=0,
            sha256sums=0,
            total=1,
        )
    ]
    assert totals == Totals(
        linux_x86_64=1,
        linux_arm64=0,
        macos_x86_64=0,
        macos_arm64=0,
        windows=0,
        sha256sums=0,
        grand_total=1,
    )


def test_aggregate_release_without_assets_key() -> None:
    """A release missing the 'assets' key produces a zero-count Row."""
    rows, totals = aggregate([{"tag_name": "v2.0.0"}])
    assert rows == [
        Row(
            tag="v2.0.0",
            linux_x86_64=0,
            linux_arm64=0,
            macos_x86_64=0,
            macos_arm64=0,
            windows=0,
            sha256sums=0,
            total=0,
        )
    ]
    assert totals == Totals(
        linux_x86_64=0,
        linux_arm64=0,
        macos_x86_64=0,
        macos_arm64=0,
        windows=0,
        sha256sums=0,
        grand_total=0,
    )
