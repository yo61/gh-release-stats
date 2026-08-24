# gh-release-stats v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `gh-release-stats` v1 CLI as designed in `../specs/2026-05-11-gh-release-stats-design.md` — a `gh` extension that prints GitHub release-asset download stats as either an aligned text table or JSON.

**Architecture:** A single Python module `release_stats.py` containing all logic (pure functions for classify/aggregate/render, side-effecting wrappers around `gh` for resolve/fetch, and a `main()` orchestrator). A 4-line executable entry script `gh-release-stats` at the repo root makes it discoverable to `gh extension install`. The only mock boundary in tests is `run_gh()`.

**Tech Stack:** Python 3.13 stdlib only at runtime (`argparse`, `json`, `subprocess`, `dataclasses`, `datetime`, `sys`). `pytest`, `ruff`, `ty` for dev. `prek` for git hooks. GitHub Actions for CI. `uv` for dev-environment management.

---

## File structure

```
gh-release-stats/
├── gh-release-stats              # executable entry: shebang + import + main()
├── release_stats.py              # all logic
├── pyproject.toml                # tool config + dev deps via PEP 735 [dependency-groups]
├── uv.lock
├── .gitignore
├── .pre-commit-config.yaml
├── .github/workflows/ci.yaml
├── LICENSE                       # MIT
├── README.md
├── tests/
│   ├── conftest.py               # shared fixtures
│   ├── fixtures/
│   │   ├── yo61_go-udap_releases.json   # captured real gh api output
│   │   ├── single_release.json          # one release, one asset
│   │   ├── empty_releases.json          # []
│   │   └── v0_naming_release.json       # v0.1.0-style asset names
│   ├── test_classify.py
│   ├── test_aggregate.py
│   ├── test_format.py
│   └── test_release_stats.py
└── docs/superpowers/
    ├── specs/2026-05-11-gh-release-stats-design.md   # already committed
    └── plans/2026-05-11-gh-release-stats-v1.md       # this file
```

## Branch strategy

The spec is committed on `docs/initial-spec`. Implementation work happens on `feat/v1-implementation`, branched from `main`. Plan ends with the user pushing to GitHub.

---

## Task 0: Branch setup

**Goal:** Get the local repo into a sensible state to start implementation. Currently the only commits are on `docs/initial-spec`; `main` does not exist yet.

**Files:** none — git operations only.

- [ ] **Step 0.1: Create `main` from the spec branch**

  Run from `/Users/robin/code/github/yo61/gh-release-stats`:

  ```bash
  git branch main docs/initial-spec
  git switch main
  git log --oneline
  ```

  Expected: 3 commits visible, all tagged `docs(spec)`.

- [ ] **Step 0.2: Create the implementation branch**

  ```bash
  git switch -c feat/v1-implementation
  git status
  ```

  Expected: `On branch feat/v1-implementation`, working tree clean.

---

## Task 1: Repo bootstrap & CI scaffolding

**Goal:** Land the static project scaffolding — `.gitignore`, `LICENSE`, `pyproject.toml`, pre-commit config, CI workflow, README skeleton — so subsequent code tasks have somewhere to land and CI is ready to run on the first push to GitHub.

**Files:**
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `pyproject.toml`
- Create: `uv.lock` (generated)
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/ci.yaml`
- Create: `README.md`

- [ ] **Step 1.1: Write `.gitignore`**

  Create `.gitignore` with:

  ```gitignore
  # Python
  __pycache__/
  *.py[cod]
  *$py.class
  .pytest_cache/
  .ruff_cache/
  .ty_cache/
  .coverage
  coverage.xml
  htmlcov/

  # uv / venv
  .venv/

  # macOS
  .DS_Store

  # IDE
  .vscode/
  .idea/
  ```

- [ ] **Step 1.2: Write `LICENSE` (MIT)**

  Create `LICENSE` with the standard MIT text. Use the same text as `/Users/robin/code/github/yo61/go-udap/LICENSE` for consistency. Update the year to `2026` and the copyright holder to `Robin Bowes`.

- [ ] **Step 1.3: Write `pyproject.toml`**

  Look up the current stable versions of `pytest`, `ruff`, `ty`, and `pytest-cov` on PyPI before pinning. Create `pyproject.toml`:

  ```toml
  [project]
  name = "gh-release-stats"
  version = "0.1.0"
  description = "Print GitHub release-asset download stats as a text table or JSON."
  requires-python = ">=3.13"
  authors = [{ name = "Robin Bowes" }]
  license = "MIT"

  [dependency-groups]
  dev = [
      "pytest==<latest>",
      "pytest-cov==<latest>",
      "ruff==<latest>",
      "ty==<latest>",
  ]

  [tool.ruff]
  target-version = "py313"
  line-length = 100

  [tool.ruff.lint]
  select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF"]

  [tool.ruff.lint.per-file-ignores]
  "tests/**" = ["S101"]  # asserts are fine in tests

  [tool.ty.rules]
  # strict by default; relax only if a specific rule fires false positives during dev

  [tool.pytest.ini_options]
  testpaths = ["tests"]
  addopts = "-q --strict-markers --strict-config"
  ```

  Replace each `<latest>` with the actual current version. Per the user's standards, use exact `==` pins (no `>=` or `~=`).

- [ ] **Step 1.4: Generate `uv.lock`**

  ```bash
  uv sync --group dev
  ```

  Expected: a `.venv/` is created, `uv.lock` is written, and the dev dependencies install cleanly. Verify with `uv pip list | head` — should show pytest, ruff, ty.

- [ ] **Step 1.5: Write `.pre-commit-config.yaml`**

  Look up the current `rev` tag for `astral-sh/ruff-pre-commit` on
  GitHub before writing (e.g. via
  `gh api repos/astral-sh/ruff-pre-commit/releases/latest -q .tag_name`).

  ```yaml
  repos:
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v5.0.0
      hooks:
        - id: trailing-whitespace
        - id: end-of-file-fixer
        - id: check-yaml
        - id: check-added-large-files
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.<latest>
      hooks:
        - id: ruff-check
          args: [--fix]
        - id: ruff-format
  ```

  No shellcheck hook — the entry script `gh-release-stats` is Python,
  not bash, so ruff covers it.

- [ ] **Step 1.6: Install pre-commit hooks via prek**

  ```bash
  prek install
  ```

  Expected: `pre-commit installed at .git/hooks/pre-commit`. (`prek` writes the hook the same way `pre-commit` does.)

- [ ] **Step 1.7: Write `.github/workflows/ci.yaml`**

  Look up current SHA pins for `actions/checkout` and `astral-sh/setup-uv` before writing.

  ```yaml
  name: CI

  on:
    push:
      branches: [main]
    pull_request:

  permissions:
    contents: read

  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@<full-sha>  # v4.<latest>
          with:
            persist-credentials: false
        - uses: astral-sh/setup-uv@<full-sha>  # v<latest>
          with:
            python-version: "3.13"
        - run: uv sync --group dev --frozen
        - run: uv run ruff check
        - run: uv run ruff format --check
        - run: uv run ty check release_stats.py
        - run: uv run pytest -q --cov=release_stats --cov-fail-under=95
  ```

  Replace each `<full-sha>` with the actual commit SHA from the action's release. Comment with the version tag for human reference.

- [ ] **Step 1.8: Write skeleton `README.md`**

  ```markdown
  # gh-release-stats

  Print GitHub release-asset download stats as an aligned text table or JSON.

  Distributed as a [`gh` extension](https://cli.github.com/manual/gh_extension).

  ## Install

  ```bash
  gh extension install yo61/gh-release-stats
  ```

  Requires Python 3.13+ on `PATH`.

  ## Usage

  See `gh release-stats --help`. Detailed examples will be added once the implementation lands.

  ## Development

  See `docs/superpowers/specs/2026-05-11-gh-release-stats-design.md` for the design.

  ## License

  MIT
  ```

- [ ] **Step 1.9: Verify pyproject is parseable and ruff is happy on the (still-empty) tree**

  ```bash
  uv run python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"
  uv run ruff check
  uv run ruff format --check
  ```

  Expected: silent / `All checks passed!` for ruff (no .py files yet to check is fine).

- [ ] **Step 1.10: Commit the bootstrap**

  ```bash
  git add .gitignore LICENSE pyproject.toml uv.lock .pre-commit-config.yaml .github/workflows/ci.yaml README.md
  git status
  ```

  Verify the staged set matches that list exactly. Then:

  ```bash
  git commit -m "$(cat <<'EOF'
  chore: bootstrap repo with pyproject, CI, pre-commit, README skeleton

  Pure-Python project (stdlib runtime, dev deps via PEP 735 dependency
  groups). CI workflow runs ruff, ty, pytest with 95% coverage gate on
  ubuntu-latest with Python 3.13. README is a skeleton; full usage docs
  land in Task 11.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 2: `classify_asset()`

**Goal:** Implement and test the pure function that maps an asset filename to one of seven column keys.

**Files:**
- Create: `release_stats.py`
- Create: `tests/__init__.py` (empty — to keep `tests/` importable as a package for some test runners)
- Create: `tests/test_classify.py`

- [ ] **Step 2.1: Create the `tests/` directory and an empty `__init__.py`**

  ```bash
  mkdir -p tests
  touch tests/__init__.py
  ```

- [ ] **Step 2.2: Write the failing test**

  Create `tests/test_classify.py`:

  ```python
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
  ```

- [ ] **Step 2.3: Run the test, see it fail**

  ```bash
  uv run pytest tests/test_classify.py -v
  ```

  Expected: `ModuleNotFoundError: No module named 'release_stats'`.

- [ ] **Step 2.4: Implement `classify_asset()` in `release_stats.py`**

  Create `release_stats.py`:

  ```python
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
  ```

- [ ] **Step 2.5: Run the tests, see them pass**

  ```bash
  uv run pytest tests/test_classify.py -v
  ```

  Expected: all 13 parametrised cases pass.

- [ ] **Step 2.6: Lint and type-check**

  ```bash
  uv run ruff check release_stats.py tests/
  uv run ruff format --check release_stats.py tests/
  uv run ty check release_stats.py
  ```

  Expected: clean. Fix anything reported before continuing.

- [ ] **Step 2.7: Commit**

  ```bash
  git add release_stats.py tests/__init__.py tests/test_classify.py
  git commit -m "$(cat <<'EOF'
  feat: add classify_asset() with regex-based normalisation

  Maps asset filenames from both the v0.1.0 (darwin-amd64) and v1.x
  (macos_x86_64) goreleaser naming schemes to a fixed set of seven
  column keys (lx86/larm/mx86/marm/win/sha/other).

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 3: `Row`, `Totals`, and `aggregate()`

**Goal:** Two immutable dataclasses + the pure aggregation function that turns a raw GitHub releases list into per-tag rows + a totals object in one pass.

**Files:**
- Modify: `release_stats.py` (add types and `aggregate()`)
- Create: `tests/test_aggregate.py`
- Create: `tests/fixtures/single_release.json`
- Create: `tests/fixtures/empty_releases.json`
- Create: `tests/fixtures/v0_naming_release.json`
- Create: `tests/conftest.py`

- [ ] **Step 3.1: Create the small synthetic fixtures**

  Create `tests/fixtures/empty_releases.json`:
  ```json
  []
  ```

  Create `tests/fixtures/single_release.json`:
  ```json
  [
    {
      "tag_name": "v1.0.0",
      "assets": [
        { "name": "go-udap_1.0.0_linux_x86_64.tar.gz", "download_count": 7 },
        { "name": "go-udap_1.0.0_macos_arm64.tar.gz", "download_count": 3 },
        { "name": "SHA256SUMS", "download_count": 1 }
      ]
    }
  ]
  ```

  Create `tests/fixtures/v0_naming_release.json`:
  ```json
  [
    {
      "tag_name": "v0.1.0",
      "assets": [
        { "name": "go-udap-darwin-amd64.zip", "download_count": 1 },
        { "name": "go-udap-darwin-arm64.zip", "download_count": 1 },
        { "name": "go-udap-linux-amd64.zip", "download_count": 5 },
        { "name": "go-udap-windows-amd64.exe.zip", "download_count": 17 }
      ]
    }
  ]
  ```

- [ ] **Step 3.2: Write `tests/conftest.py`**

  ```python
  """Shared pytest fixtures for gh-release-stats tests."""

  from __future__ import annotations

  import json
  from pathlib import Path
  from typing import Any

  import pytest

  FIXTURES_DIR = Path(__file__).parent / "fixtures"


  @pytest.fixture
  def load_fixture() -> callable:
      """Return a function that loads a named JSON fixture."""

      def _load(name: str) -> Any:
          return json.loads((FIXTURES_DIR / name).read_text())

      return _load
  ```

- [ ] **Step 3.3: Write the failing test**

  Create `tests/test_aggregate.py`:

  ```python
  """Tests for aggregate(): raw releases → (rows, totals)."""

  from __future__ import annotations

  from release_stats import Row, Totals, aggregate


  def test_aggregate_empty(load_fixture) -> None:
      rows, totals = aggregate(load_fixture("empty_releases.json"))
      assert rows == []
      assert totals == Totals(0, 0, 0, 0, 0, 0, 0)


  def test_aggregate_single_release(load_fixture) -> None:
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


  def test_aggregate_v0_naming_normalised(load_fixture) -> None:
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
      assert totals.grand_total == 24


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
      assert rows[0].total == 1
      assert totals.grand_total == 1
  ```

- [ ] **Step 3.4: Run the tests, see them fail**

  ```bash
  uv run pytest tests/test_aggregate.py -v
  ```

  Expected: `ImportError: cannot import name 'Row'` (or similar — none of the symbols exist yet).

- [ ] **Step 3.5: Add `Row`, `Totals`, `aggregate()` to `release_stats.py`**

  Append to `release_stats.py`:

  ```python
  from dataclasses import dataclass
  from typing import Any


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
  ```

- [ ] **Step 3.6: Run the tests, see them pass**

  ```bash
  uv run pytest tests/test_aggregate.py -v
  ```

  Expected: all 4 tests pass.

- [ ] **Step 3.7: Run the full suite**

  ```bash
  uv run pytest -q
  ```

  Expected: 17 tests pass (13 from Task 2 + 4 from Task 3).

- [ ] **Step 3.8: Lint, format, type-check**

  ```bash
  uv run ruff check
  uv run ruff format --check
  uv run ty check release_stats.py
  ```

  Expected: clean.

- [ ] **Step 3.9: Commit**

  ```bash
  git add release_stats.py tests/conftest.py tests/test_aggregate.py tests/fixtures/
  git commit -m "$(cat <<'EOF'
  feat: add Row, Totals, and aggregate() to fold raw releases

  aggregate() walks the GitHub releases payload once and produces one
  Row per release plus a Totals object. Assets that classify as 'other'
  are dropped silently from the column-based view.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 4: `render_text()`

**Goal:** Aligned plain-text table renderer.

**Files:**
- Modify: `release_stats.py` (add column spec + `render_text`)
- Create: `tests/test_format.py`

- [ ] **Step 4.1: Write the failing test**

  Create `tests/test_format.py`:

  ```python
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
  ```

- [ ] **Step 4.2: Run, see it fail**

  ```bash
  uv run pytest tests/test_format.py -v
  ```

  Expected: `ImportError: cannot import name 'render_text'`.

- [ ] **Step 4.3: Implement `render_text` in `release_stats.py`**

  Append:

  ```python
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
  ```

- [ ] **Step 4.4: Run, see it pass**

  ```bash
  uv run pytest tests/test_format.py -v
  ```

  Expected: all 3 tests pass. If the expected snapshot in `EXPECTED_SINGLE` is off by a space, fix the expected string (the algorithm is more authoritative than the test snapshot here — but verify the spacing matches §7.1 of the spec).

- [ ] **Step 4.5: Lint, format, type-check, full suite**

  ```bash
  uv run ruff check && uv run ruff format --check
  uv run ty check release_stats.py
  uv run pytest -q
  ```

- [ ] **Step 4.6: Commit**

  ```bash
  git add release_stats.py tests/test_format.py
  git commit -m "$(cat <<'EOF'
  feat: add render_text() for aligned plain-text table output

  Column widths are computed from the data; tag column is left-aligned,
  numbers are right-aligned. ASCII-only, byte-identical across TTY,
  pipe, and file outputs.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 5: `render_json()`

**Goal:** JSON renderer producing the schema in §7.2 of the spec.

**Files:**
- Modify: `release_stats.py`
- Modify: `tests/test_format.py`

- [ ] **Step 5.1: Add the failing test**

  Append to `tests/test_format.py`:

  ```python
  import json

  from release_stats import render_json


  def test_render_json_schema() -> None:
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
      out = render_json("yo61/go-udap", rows, totals, fetched_at="2026-05-11T14:32:00Z")
      doc = json.loads(out)
      assert doc["repo"] == "yo61/go-udap"
      assert doc["fetched_at"] == "2026-05-11T14:32:00Z"
      assert doc["releases"] == [
          {
              "tag": "v1.0.0",
              "linux_x86_64": 7,
              "linux_arm64": 0,
              "macos_x86_64": 0,
              "macos_arm64": 3,
              "windows": 0,
              "sha256sums": 1,
              "total": 11,
          }
      ]
      assert doc["totals"] == {
          "linux_x86_64": 7,
          "linux_arm64": 0,
          "macos_x86_64": 0,
          "macos_arm64": 3,
          "windows": 0,
          "sha256sums": 1,
          "grand_total": 11,
      }


  def test_render_json_ends_with_newline_and_is_pretty() -> None:
      out = render_json("a/b", [], Totals(0, 0, 0, 0, 0, 0, 0), fetched_at="2026-05-11T14:32:00Z")
      assert out.endswith("\n")
      assert "\n  " in out  # indent=2 is in effect
  ```

- [ ] **Step 5.2: Run, see it fail**

  ```bash
  uv run pytest tests/test_format.py::test_render_json_schema -v
  ```

  Expected: `ImportError: cannot import name 'render_json'`.

- [ ] **Step 5.3: Implement `render_json`**

  Append to `release_stats.py`:

  ```python
  import json
  from dataclasses import asdict


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
  ```

- [ ] **Step 5.4: Run, see pass**

  ```bash
  uv run pytest tests/test_format.py -v
  ```

- [ ] **Step 5.5: Lint, format, type-check, full suite**

  ```bash
  uv run ruff check && uv run ruff format --check
  uv run ty check release_stats.py
  uv run pytest -q
  ```

- [ ] **Step 5.6: Commit**

  ```bash
  git add release_stats.py tests/test_format.py
  git commit -m "$(cat <<'EOF'
  feat: add render_json() with pretty-printed schema per spec §7.2

  Emits {repo, fetched_at, releases[], totals} with snake_case keys and
  a trailing newline. fetched_at is injected by main(); the renderer
  itself is pure.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 6: `run_gh()` — the subprocess seam

**Goal:** Single function that calls the real `gh` binary. Tests monkeypatch this; nothing else in the module touches subprocess.

**Files:**
- Modify: `release_stats.py`
- Create: `tests/test_release_stats.py`

- [ ] **Step 6.1: Write the failing test for the happy path**

  Create `tests/test_release_stats.py`:

  ```python
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
  ```

- [ ] **Step 6.2: Run, see fail**

  ```bash
  uv run pytest tests/test_release_stats.py -v
  ```

  Expected: failures around missing `run_gh` and `GhError`.

- [ ] **Step 6.3: Implement `run_gh()` and `GhError`**

  Append to `release_stats.py`:

  ```python
  import subprocess


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
  ```

- [ ] **Step 6.4: Run, see pass**

  ```bash
  uv run pytest tests/test_release_stats.py -v
  ```

- [ ] **Step 6.5: Lint, type-check, full suite**

  ```bash
  uv run ruff check && uv run ruff format --check
  uv run ty check release_stats.py
  uv run pytest -q
  ```

- [ ] **Step 6.6: Commit**

  ```bash
  git add release_stats.py tests/test_release_stats.py
  git commit -m "$(cat <<'EOF'
  feat: add run_gh() subprocess seam plus GhError for non-zero exits

  Single point of contact with the gh binary. All higher-level functions
  go through this; tests monkeypatch it. GhError carries gh's stderr
  for surfacing in user-facing error messages.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 7: `resolve_repo()`

**Goal:** Return the repo argument if given; otherwise ask `gh` for the current repo.

**Files:**
- Modify: `release_stats.py`
- Modify: `tests/test_release_stats.py`

- [ ] **Step 7.1: Add failing tests**

  Append to `tests/test_release_stats.py`:

  ```python
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
  ```

- [ ] **Step 7.2: Run, see fail**

  ```bash
  uv run pytest tests/test_release_stats.py::test_resolve_repo_returns_arg_unchanged -v
  ```

- [ ] **Step 7.3: Implement `resolve_repo()`**

  Append to `release_stats.py`:

  ```python
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
  ```

- [ ] **Step 7.4: Run, see pass; lint; commit**

  ```bash
  uv run pytest -q
  uv run ruff check && uv run ruff format --check
  uv run ty check release_stats.py
  git add release_stats.py tests/test_release_stats.py
  git commit -m "$(cat <<'EOF'
  feat: add resolve_repo() with current-repo detection via gh repo view

  If REPO is passed, returns it unchanged; otherwise asks gh for the
  current repo. All edge cases (cwd detection, GH_REPO env, remote
  preference) are inherited from gh.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 8: `fetch_releases()`

**Goal:** Pull paginated release JSON for a given repo via `gh api`.

**Files:**
- Modify: `release_stats.py`
- Modify: `tests/test_release_stats.py`
- Create: `tests/fixtures/yo61_go-udap_releases.json` (real captured fixture)

- [ ] **Step 8.1: Capture the real fixture**

  ```bash
  gh api repos/yo61/go-udap/releases --paginate \
    > tests/fixtures/yo61_go-udap_releases.json
  ```

  Verify it parses:

  ```bash
  uv run python -c "import json; print(len(json.load(open('tests/fixtures/yo61_go-udap_releases.json'))))"
  ```

  Expected: a number ≥ 1 (the count of releases on the repo).

  Note: `gh api --paginate` concatenates pages. Check that the file is a single JSON array, not multiple arrays. If it's multiple, re-capture using `--paginate --slurp` (newer gh) or pipe through `jq -s 'add'`.

- [ ] **Step 8.2: Add failing tests**

  Append to `tests/test_release_stats.py`:

  ```python
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
  ```

- [ ] **Step 8.3: Run, see fail**

- [ ] **Step 8.4: Implement `fetch_releases()`**

  Append to `release_stats.py`:

  ```python
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
  ```

- [ ] **Step 8.5: Run, see pass; lint; commit**

  ```bash
  uv run pytest -q
  uv run ruff check && uv run ruff format --check
  uv run ty check release_stats.py
  git add release_stats.py tests/test_release_stats.py tests/fixtures/yo61_go-udap_releases.json
  git commit -m "$(cat <<'EOF'
  feat: add fetch_releases() and ship a real-world test fixture

  fetch_releases() wraps `gh api repos/<repo>/releases --paginate` and
  parses the JSON. The bundled fixture (yo61/go-udap) is captured live
  from the GitHub API so tests exercise the real wire format.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 9: `main()` orchestrator

**Goal:** Parse args, resolve repo, fetch, render, write to stdout. Translate every expected failure mode from spec §8 into a clean stderr line + exit code.

**Files:**
- Modify: `release_stats.py`
- Modify: `tests/test_release_stats.py`

- [ ] **Step 9.1: Add failing tests covering happy path + each error class**

  Append to `tests/test_release_stats.py`:

  ```python
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
  ```

- [ ] **Step 9.2: Run, see fails**

- [ ] **Step 9.3: Implement `main()` and helpers**

  Append to `release_stats.py`:

  ```python
  import argparse
  import sys
  from datetime import UTC, datetime


  def _die(msg: str) -> int:
      """Write ``error: <msg>`` to stderr and return exit code 2."""
      print(f"error: {msg}", file=sys.stderr)
      return 2


  def _parse_args(argv: list[str] | None) -> argparse.Namespace:
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
  ```

- [ ] **Step 9.4: Run, see pass**

  ```bash
  uv run pytest -q
  ```

  Expected: all tests pass. Coverage should comfortably exceed 95%.

- [ ] **Step 9.5: Lint, type-check, coverage check**

  ```bash
  uv run ruff check && uv run ruff format --check
  uv run ty check release_stats.py
  uv run pytest -q --cov=release_stats --cov-report=term-missing --cov-fail-under=95
  ```

  Expected: coverage ≥ 95%. If a specific line is uncovered, either add a test for it or document why (e.g. argparse-internal SystemExit on `--help`).

- [ ] **Step 9.6: Commit**

  ```bash
  git add release_stats.py tests/test_release_stats.py
  git commit -m "$(cat <<'EOF'
  feat: add main() orchestrator with full error handling per spec §8

  Wires parse_args → resolve_repo → fetch_releases → aggregate → render
  → stdout, with each expected failure mode (gh missing, gh errors,
  malformed JSON, no releases, broken pipe, Ctrl-C) translated to the
  exact stderr line + exit code from §8 of the design spec.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 10: Entry script + smoke test

**Goal:** Add the executable `gh-release-stats` entry script that `gh extension install` invokes; verify it works end-to-end against the real GitHub API.

**Files:**
- Create: `gh-release-stats` (executable)

- [ ] **Step 10.1: Write the entry script**

  Create `gh-release-stats` (no `.py` extension):

  ```python
  #!/usr/bin/env python3
  """gh-release-stats: GitHub release-asset download stats.

  Entry point for the gh extension. All real logic lives in release_stats.py.
  """

  import sys

  from release_stats import main

  if __name__ == "__main__":
      sys.exit(main(sys.argv[1:]))
  ```

- [ ] **Step 10.2: Mark it executable**

  ```bash
  chmod +x gh-release-stats
  ls -l gh-release-stats
  ```

  Expected: permissions include `x` (e.g. `-rwxr-xr-x`).

- [ ] **Step 10.3: Smoke test — text output against the real API**

  ```bash
  ./gh-release-stats yo61/go-udap
  ```

  Expected: an aligned text table, structurally identical to the one printed by `task release:stats` in the go-udap repo. If columns drift or numbers look wrong, debug — do not move on.

- [ ] **Step 10.4: Smoke test — JSON output**

  ```bash
  ./gh-release-stats yo61/go-udap --json | uv run python -c "import sys, json; d = json.load(sys.stdin); print(d['repo'], d['totals']['grand_total'])"
  ```

  Expected: a line like `yo61/go-udap 51` (or whatever the current grand total is).

- [ ] **Step 10.5: Smoke test — current-repo default**

  From inside `/Users/robin/code/github/yo61/go-udap`:

  ```bash
  /Users/robin/code/github/yo61/gh-release-stats/gh-release-stats
  ```

  Expected: same output as the explicit-arg test in 10.3.

- [ ] **Step 10.6: Smoke test — error handling**

  ```bash
  ./gh-release-stats nonexistent/repo-that-does-not-exist
  echo "exit: $?"
  ```

  Expected: a single `error: ...` line on stderr and exit code 2.

- [ ] **Step 10.7: Commit**

  ```bash
  git add gh-release-stats
  git update-index --chmod=+x gh-release-stats  # belt-and-braces: stage the executable bit
  git commit -m "$(cat <<'EOF'
  feat: add gh-release-stats executable entry script

  Four-line entry point that gh extension install picks up: shebang,
  import, call main(). All logic remains in release_stats.py for
  testability.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 11: README polish

**Goal:** Replace the README skeleton with a real one — install, usage, examples, exit codes.

**Files:**
- Modify: `README.md`

- [ ] **Step 11.1: Rewrite `README.md`**

  ```markdown
  # gh-release-stats

  Print GitHub release-asset download stats as an aligned text table or JSON.

  Distributed as a [`gh` extension](https://cli.github.com/manual/gh_extension).

  ## Install

  ```bash
  gh extension install yo61/gh-release-stats
  ```

  Requires Python ≥ 3.13 on `PATH`. The tool itself has no Python
  dependencies; everything is stdlib.

  ## Usage

  ```bash
  # current repo (auto-detected via `gh repo view`)
  gh release-stats

  # specific repo
  gh release-stats yo61/go-udap

  # JSON output for piping
  gh release-stats yo61/go-udap --json | jq '.totals'
  ```

  ### Output format

  Text (default):

  ```
  Tag        linux x86_64   linux arm64   macos x86_64   macos arm64   windows   SHA256SUMS    Total
  --------   ------------   -----------   ------------   -----------   -------   ----------   ------
  v1.3.9                1             0              0             2         0            0        3
  ...
  --------   ------------   -----------   ------------   -----------   -------   ----------   ------
  Total                21             0              1             9        19            1       51
  ```

  JSON (`--json`):

  ```json
  {
    "repo": "yo61/go-udap",
    "fetched_at": "2026-05-11T14:32:00Z",
    "releases": [{ "tag": "v1.3.9", "linux_x86_64": 1, ... }],
    "totals": { "linux_x86_64": 21, ..., "grand_total": 51 }
  }
  ```

  ### Exit codes

  | Code | Meaning |
  |---|---|
  | 0 | Success |
  | 2 | Any expected failure (gh missing, not authenticated, repo not found, no releases, malformed JSON, network error). One human-readable line on stderr. |
  | 130 | Ctrl-C |

  ## Development

  ```bash
  uv sync --group dev      # install dev deps in .venv/
  uv run pytest -q         # run tests
  uv run ruff check        # lint
  uv run ruff format       # format
  uv run ty check release_stats.py  # type-check
  prek install             # install pre-commit hooks
  ```

  Design and decisions live in [`docs/superpowers/specs/2026-05-11-gh-release-stats-design.md`](docs/superpowers/specs/2026-05-11-gh-release-stats-design.md).

  ## License

  MIT.
  ```

- [ ] **Step 11.2: Commit**

  ```bash
  git add README.md
  git commit -m "$(cat <<'EOF'
  docs(readme): full install, usage, output, and dev sections

  Replaces the bootstrap skeleton with real install instructions, usage
  examples, output samples for both text and JSON, exit-code table, and
  a dev-environment quick-start.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 12: GitHub repo creation & first push (user-driven)

**Goal:** Hand off to the user to create the upstream GitHub repo and push. This task is intentionally not automated — creating a GitHub repo is a shared-state action that needs explicit confirmation.

**Files:** none — git/gh operations only.

- [ ] **Step 12.1: Verify the local repo is in a good state**

  ```bash
  git status
  git log --oneline
  ```

  Expected: working tree clean; commit history shows the spec commits + bootstrap + Task 2-11 commits in order.

- [ ] **Step 12.2: Pause for user confirmation**

  Show the user the commit log and confirm they want to create the
  GitHub repo. Wait for an explicit "yes, create the repo" before
  running anything in 12.3 — `gh repo create` is a shared-state action.

- [ ] **Step 12.3: Switch to `main` so it becomes the default branch**

  ```bash
  git switch main
  git log --oneline   # 3 spec commits
  ```

  This ensures the first push lands `main` as the GitHub default branch
  (rather than `feat/v1-implementation`).

- [ ] **Step 12.4: Create the upstream repo and push `main`**

  ```bash
  gh repo create yo61/gh-release-stats \
    --public \
    --description "Print GitHub release-asset download stats as a text table or JSON." \
    --source . \
    --remote origin \
    --push
  ```

  Verify:

  ```bash
  gh repo view yo61/gh-release-stats --json url,defaultBranchRef
  ```

  Expected: default branch is `main`. CI runs on this push (the workflow
  is in the spec branch's history, which `main` was branched from).

- [ ] **Step 12.5: Push the implementation branch and open a PR**

  ```bash
  git switch feat/v1-implementation
  git push -u origin feat/v1-implementation
  gh pr create --base main --head feat/v1-implementation \
      --title "feat: initial implementation of gh-release-stats v1" \
      --body "$(cat <<'EOF'
  Implements the design at docs/superpowers/specs/2026-05-11-gh-release-stats-design.md.

  ## Summary
  - Pure-Python release-stats CLI (stdlib only at runtime)
  - Text + JSON output formats (--json flag)
  - Auto-detects current repo via gh; accepts owner/name override
  - 95% test coverage, ruff + ty + pre-commit gates, GitHub Actions CI

  ## Test plan
  - [x] `uv run pytest -q` passes locally
  - [x] CI passes on push
  - [x] `./gh-release-stats yo61/go-udap` produces the expected text table
  - [x] `./gh-release-stats yo61/go-udap --json | jq '.totals.grand_total'` returns the right number

  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  EOF
  )"
  ```

  Note: `docs/initial-spec` is not pushed to the remote. Its commits are
  already in `main`'s history (we branched `main` from it in Task 0); the
  branch was a local-only scaffold.

- [ ] **Step 12.6: Verify CI runs**

  Watch the CI workflow on the PR. If it goes green, merge the PR. If it goes red, fix forward — do not skip the gates.

- [ ] **Step 12.7: Install the extension on the local machine and verify**

  ```bash
  gh extension install yo61/gh-release-stats
  gh release-stats yo61/go-udap
  ```

  Expected: same output as the local smoke test in Task 10.3.

---

## Out of plan

These appear in the spec's §11 (future work) and are explicitly not scoped here:

- Homebrew tap distribution
- Compiled binary releases via PyInstaller / Nuitka
- `--jq` and `--template` flags
- Mutation testing
- Homebrew-tap clone/view stats subcommand

If any of these get prioritised, they each deserve their own design doc and plan.
