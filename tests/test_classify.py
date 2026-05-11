"""Tests for classify_asset(): asset filename → column key."""

import pytest

from release_stats import classify_asset


@pytest.mark.parametrize(
    "name,expected",
    [
        # v1.x naming scheme
        ("go-udap_1.3.9_linux_x86_64.tar.gz", "lx86"),
        ("go-udap_1.3.9_linux_arm64.tar.gz", "larm"),
        ("go-udap_1.3.9_macos_x86_64.tar.gz", "mx86"),
        ("go-udap_1.3.9_macos_arm64.tar.gz", "marm"),
        ("go-udap_1.3.9_windows_x86_64.zip", "win"),
        # v0.1.0 legacy naming scheme
        ("go-udap-linux-amd64.zip", "lx86"),
        ("go-udap-linux-arm64.zip", "larm"),
        ("go-udap-darwin-amd64.zip", "mx86"),
        ("go-udap-darwin-arm64.zip", "marm"),
        ("go-udap-windows-amd64.exe.zip", "win"),
        # SHA256SUMS file
        ("SHA256SUMS", "sha"),
        # Anything else
        ("README.md", "other"),
        ("", "other"),
    ],
)
def test_classify_asset(name: str, expected: str) -> None:
    assert classify_asset(name) == expected
