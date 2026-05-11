"""Tests for render_text() and render_json()."""

from __future__ import annotations

from release_stats import Row, Totals, render_text

EXPECTED_SINGLE = """\
Tag      linux x86_64   linux arm64   macos x86_64   macos arm64   windows   SHA256SUMS   Total
------   ------------   -----------   ------------   -----------   -------   ----------   -----
v1.0.0              7             0              0             3         0            1      11
------   ------------   -----------   ------------   -----------   -------   ----------   -----
Total               7             0              0             3         0            1      11
"""


def test_render_text_single_release() -> None:
    rows = [
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
    totals = Totals(7, 0, 0, 3, 0, 1, 11)
    assert render_text(rows, totals) == EXPECTED_SINGLE


def test_render_text_empty_rows_still_has_header_and_totals() -> None:
    out = render_text([], Totals(0, 0, 0, 0, 0, 0, 0))
    assert out.startswith("Tag")
    assert "Total" in out
    assert out.endswith("\n")


def test_render_text_long_tag_widens_first_column() -> None:
    """Tag column expands to fit the longest tag."""
    rows = [
        Row("v1.0.0", 1, 0, 0, 0, 0, 0, 1),
        Row("v999.999.999-very-long", 1, 0, 0, 0, 0, 0, 1),
    ]
    out = render_text(rows, Totals(2, 0, 0, 0, 0, 0, 2))
    header_line = out.splitlines()[0]
    # The Tag column header should be padded so the second column
    # ('linux x86_64') starts after the longest tag width.
    assert header_line.startswith("Tag                   ")  # 22 chars (longest tag len)
