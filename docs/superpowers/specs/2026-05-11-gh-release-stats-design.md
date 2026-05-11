# gh-release-stats — Design

| | |
|---|---|
| **Date** | 2026-05-11 |
| **Status** | Approved — pending implementation plan |
| **Repo** | `yo61/gh-release-stats` (to be created) |
| **Author** | robin@yo61.com (with Claude Opus 4.7) |

## 1. Context

`yo61/go-udap` releases ship as multi-platform tarballs/zips via `goreleaser`. To
sanity-check actual usage we want to count GitHub release-asset downloads
across every release. A bash helper currently lives in that repo
(`scripts/release-stats.sh`) and produces a Markdown table via `gh api` + `jq`
+ `awk`. Its limitations are why this project exists:

- Markdown-only output is awkward in a terminal.
- No JSON output for piping into other tooling.
- Asset-name normalisation logic in `awk` is hard to test.
- Lives inside the project it reports on, instead of being reusable.

This design replaces it with a standalone `gh` extension written in Python.

## 2. Goals

1. Drop-in functional replacement for the bash helper.
2. Two output formats: aligned **plain-text table** (default) and **JSON**
   (`--json`).
3. Distributable as a `gh` extension installable via
   `gh extension install yo61/gh-release-stats`.
4. Defaults to the current repo (via `gh repo view`); accepts an explicit
   `[owner/repo]` positional override.
5. Zero runtime dependencies beyond Python ≥ 3.13 and `gh` itself.
6. Every code path tested at the function boundary; `subprocess` is the only
   thing mocked.

## 3. Non-goals (v1)

- Homebrew-tap clone/view stats (deferred — see §11).
- General-purpose GitHub repo analytics toolbox.
- Output-format plumbing beyond `--json` (no `--jq`, `--template`, CSV, TSV).
- A `--verbose`/`--debug` flag (use `GH_DEBUG=api` for raw HTTP visibility).
- Telemetry, caching, or persistent state of any kind.
- Per-asset breakdown beyond the seven normalised columns.

## 4. Repo layout

```
gh-release-stats/
├── gh-release-stats              # 4-line entry: shebang + import + main()
├── release_stats.py              # all logic, stdlib only
├── pyproject.toml                # tool config + dev deps via PEP 735 [dependency-groups]
├── uv.lock                       # pins dev deps; no runtime deps to lock
├── tests/
│   ├── fixtures/
│   │   ├── yo61_go-udap_releases.json   # captured real gh api output
│   │   └── ...                          # small synthetic edge-case fixtures
│   ├── test_classify.py
│   ├── test_aggregate.py
│   ├── test_format.py
│   └── test_release_stats.py
├── .pre-commit-config.yaml
├── .github/workflows/ci.yaml
├── .gitignore
├── LICENSE                       # MIT, matching go-udap
├── README.md
└── docs/superpowers/specs/2026-05-11-gh-release-stats-design.md
```

Notes on the layout:

- The executable is a single file at the repo root with no `.py` extension —
  this is what `gh extension install` looks for and runs.
- Real logic lives in `release_stats.py` so pytest can `import release_stats`
  directly. The entry script is intentionally trivial: shebang, docstring,
  `from release_stats import main; main()`.
- No `[build-system]` table in `pyproject.toml`. Nothing is built or
  pip-installed; `gh extension install` clones the repo and invokes the
  entry script in-place.
- `uv.lock` exists for reproducible *dev tool* installs (pytest, ruff, ty)
  via `uv sync --group dev`. Runtime has nothing to lock.
- This layout deliberately *trades* the user's preferred `src/` package
  layout for direct gh-extension compatibility; this trade-off was approved
  on 2026-05-11.

## 5. Components & data flow

```
                ┌──────────────────────────────────────────────┐
                │ main(argv)                                   │
                │   parse args → resolve repo → fetch → render │
                └──────────────────────────────────────────────┘
                          │           │           │           │
                ┌─────────▼──┐  ┌─────▼─────┐  ┌──▼──────┐  ┌─▼──────────────┐
                │ parse_args │  │ resolve_  │  │ fetch_  │  │ render_text /  │
                │ (argparse) │  │ repo()    │  │ releases│  │ render_json    │
                └────────────┘  └───────────┘  └─────────┘  └────────────────┘
                                      │             │
                                      ▼             ▼
                                ┌──────────┐   ┌──────────┐
                                │ run_gh() │   │ run_gh() │
                                └──────────┘   └──────────┘
                                       │
                                       ▼
                                  classify_asset(name) → column key
                                  aggregate(releases)  → rows + totals
```

| Function | Responsibility | Pure? |
|---|---|---|
| `classify_asset(name) -> str` | Map asset filename to one of `lx86 / larm / mx86 / marm / win / sha / other`. Encapsulates the v0.1.0 (`darwin-amd64`) vs v1.x (`macos_x86_64`) naming-scheme normalisation. | yes |
| `aggregate(releases) -> tuple[list[Row], Totals]` | Group asset downloads by tag and column; compute per-row sums and the cross-release totals object. | yes |
| `render_text(rows, totals) -> str` | Aligned text table (column widths from data, totals row at bottom). | yes |
| `render_json(repo, rows, totals) -> str` | JSON document per §7.2. | yes |
| `run_gh(args) -> str` | Thin wrapper around `subprocess.run(["gh", *args], …)`. **Single seam for tests to mock.** | side-effecting |
| `resolve_repo(arg) -> str` | If `arg` given, return it. Else `run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])`. | side-effecting |
| `fetch_releases(repo) -> list[dict]` | `run_gh(["api", f"repos/{repo}/releases", "--paginate"])` → parse JSON. | side-effecting |
| `main(argv=None) -> int` | Orchestrator. Returns process exit code. | side-effecting |

### 5.1 Key types

Two `@dataclass(frozen=True, slots=True)` types, both immutable:

- **`Row`** — `tag: str` plus seven int fields, one per column
  (`linux_x86_64`, `linux_arm64`, `macos_x86_64`, `macos_arm64`, `windows`,
  `sha256sums`, `total`). One per release.
- **`Totals`** — the same seven int fields with `total` renamed to
  `grand_total` to match the JSON schema (§7.2). No `tag`. One per
  invocation.

`aggregate()` computes both in a single pass and returns
`(list[Row], Totals)`. Both renderers consume the same tuple, so the text
table and the JSON output cannot drift.

### 5.2 Mock-boundary discipline

Only `run_gh` is monkeypatched in tests. Every other function operates on
real (in-memory) data. This satisfies the "mock boundaries, not logic" rule
from the user's global standards.

## 6. CLI surface

**Usage:**

```
gh release-stats [REPO] [--json] [-h|--help]
```

| Arg | Type | Default | Notes |
|---|---|---|---|
| `REPO` | positional, optional | current repo via `gh repo view` | `owner/name` format. If omitted and `gh repo view` fails, exit 2. |
| `--json` | flag | false | Emit JSON to stdout; suppresses the text table. |
| `-h`, `--help` | flag | — | argparse default. |

**Current-repo detection** is fully delegated to `gh repo view --json
nameWithOwner -q .nameWithOwner`. This means `cwd`-based detection,
`GH_REPO` env-var override, and remote-name handling are inherited from
gh — we add no parsing of our own.

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Any failure: usage error (argparse), gh missing, gh unauthenticated, not in a repo and no `REPO` given, repo not found, no releases, network failure, malformed JSON. |
| 130 | `KeyboardInterrupt` (Ctrl-C) |

**Output streams:** structured output (table or JSON) to **stdout**; everything
diagnostic to **stderr**. Identical bytes whether stdout is a TTY or a pipe.

## 7. Output formats

### 7.1 Plain-text table (default)

ASCII-only, fixed-width, right-aligned numbers, left-aligned tag,
separator rules using `-`. Totals row separated by a second rule. Column
widths computed as `max(label_width, max(data_width))`.

```
Tag        linux x86_64   linux arm64   macos x86_64   macos arm64   windows   SHA256SUMS    Total
--------   ------------   -----------   ------------   -----------   -------   ----------   ------
v1.3.9                1             0              0             2         0            0        3
v1.3.8                1             0              0             0         0            0        1
...
v0.1.0                5             0              1             1        17            0       24
--------   ------------   -----------   ------------   -----------   -------   ----------   ------
Total                21             0              1             9        19            1       51
```

No box-drawing characters, no colour, no Unicode. Output is byte-identical
across terminals, pipes, and files.

### 7.2 JSON (`--json`)

```json
{
  "repo": "yo61/go-udap",
  "fetched_at": "2026-05-11T14:32:00Z",
  "releases": [
    {
      "tag": "v1.3.9",
      "linux_x86_64": 1,
      "linux_arm64": 0,
      "macos_x86_64": 0,
      "macos_arm64": 2,
      "windows": 0,
      "sha256sums": 0,
      "total": 3
    }
  ],
  "totals": {
    "linux_x86_64": 21,
    "linux_arm64": 0,
    "macos_x86_64": 1,
    "macos_arm64": 9,
    "windows": 19,
    "sha256sums": 1,
    "grand_total": 51
  }
}
```

- `repo` and `fetched_at` (UTC, ISO-8601) for traceability when output is
  saved to a file.
- Field names are stable JSON keys (snake_case, full words). The text-table
  column labels are display-only and may change without breaking the JSON
  contract.
- Pretty-printed with `indent=2`. Use `jq -c` for compact form.
- UTF-8, no BOM, trailing newline.
- Deterministic key order (insertion-order-preserving via Python dicts).
- `releases` is an **ordered list**, newest first, matching GitHub's API
  shape. Lookup by tag is a one-line `jq` reduction; ordering would be lost
  in a hash and dot-access on `v1.3.9` is awkward in jq.

## 8. Error handling

Single principle: **fail fast, one human-readable line on stderr, exit 2**.
No tracebacks for expected failures. No retries.

| Failure | Detection | Stderr message | Exit |
|---|---|---|---|
| `gh` not on PATH | `FileNotFoundError` from `subprocess.run` | `error: gh CLI not found on PATH; install from https://cli.github.com/` | 2 |
| `gh` not authenticated | `gh` exits non-zero, stderr mentions auth | `error: gh is not authenticated; run 'gh auth login'` | 2 |
| No `REPO` arg, not in a git repo | `gh repo view` exits non-zero | `error: not in a git repository; pass owner/repo as an argument` | 2 |
| Repo doesn't exist / no access | `gh api` returns 404 | `error: repository <repo> not found or not accessible` | 2 |
| Repo has zero releases | `fetch_releases` returns `[]` | `error: <repo> has no releases` | 2 |
| Network failure | `gh` exits non-zero with network error in stderr | passthrough of `gh`'s stderr, prefixed `error: ` | 2 |
| Malformed JSON from gh | `json.JSONDecodeError` | `error: failed to parse gh output: <reason>` | 2 |
| Argparse error | argparse | argparse default | 2 |
| Broken pipe (`head`/`less` exits) | `BrokenPipeError` | (silent) | 0 |
| `KeyboardInterrupt` | caught in `main` | (silent) | 130 |

**Implementation:** all error paths funnel through a `def die(msg: str) ->
NoReturn` helper that writes `f"error: {msg}\n"` to stderr and `sys.exit(2)`.
Exceptions bubble up to `main()` where a top-level `try/except` maps known
exception types to `die()` calls. Unknown exceptions propagate (real bug →
traceback → user reports it).

## 9. Testing strategy

**Stack:** `pytest -q` (Python 3.13). Tests in `tests/` mirror module names.
Configured via `pyproject.toml` `[tool.pytest.ini_options]`.

**Mock boundary:** the *only* function that gets monkeypatched is `run_gh`.
Every other test uses real data flowing through real code.

| File | Covers | Key cases |
|---|---|---|
| `test_classify.py` | `classify_asset()` | v1.x scheme; v0.1.0 scheme; both arm64 variants; SHA256SUMS; unknown name → `other`; case sensitivity; empty string |
| `test_aggregate.py` | `aggregate()` | empty list → empty rows; single release single asset; multi-release totals; `other`-bucket assets dropped from columns |
| `test_format.py` | `render_text`, `render_json` | alignment with varying column widths; long tag names; totals row math; JSON schema; UTF-8 encoding; trailing newline; deterministic key order |
| `test_release_stats.py` | `resolve_repo`, `fetch_releases`, `main` | resolve with arg vs without; fetch parses real fixture; main → exit 0 happy path; main → exit 2 for each error in §8; broken-pipe → exit 0; empty-releases → exit 2 |

**Fixtures:** `tests/fixtures/` contains real captured `gh api` output saved
as JSON files (one large realistic one for `yo61/go-udap`, plus small
hand-written edge-case fixtures).

**No snapshot library.** Expected text-table output is a triple-quoted
string in the test file. If formatting changes, the diff appears in the
test failure directly.

**Static-analysis gates** (run by pre-commit and CI):

- `ruff check` + `ruff format --check`
- `ty check` (strict via `[tool.ty.rules]`)
- `shellcheck` on the entry script
- `pytest -q --cov=release_stats --cov-fail-under=95`

## 10. Build / CI / release

- **CI:** GitHub Actions, single workflow `.github/workflows/ci.yaml`,
  matrix-free (Python 3.13 on `ubuntu-latest` is sufficient — the tool is
  pure Python and OS-agnostic). The workflow runs `ruff check`,
  `ruff format --check`, `ty check`, `shellcheck` on the entry script,
  and `pytest -q --cov=release_stats --cov-fail-under=95`.
- **CI must land in the first push to the upstream GitHub repo** —
  i.e. `.github/workflows/ci.yaml` is committed *before* `gh repo create
  --push`, so GitHub Actions is enabled and the very first build runs
  end-to-end. No "wire up CI later" follow-up.
- **Pre-commit:** `prek install` per the user's global standard. Hooks for
  ruff, ty, shellcheck, basic file hygiene (trailing whitespace, EOF, large
  files, YAML).
- **Distribution:** primary channel is `gh extension install
  yo61/gh-release-stats`, tracking `main`. Homebrew tap is under
  consideration — see §12.
- **Release:** no semver release pipeline for v1. If versioned releases
  become useful later, we can add `release-please` or `semantic-release`
  then.
- **Dependabot:** weekly cooldown, grouped updates, scoped to GH Actions
  and the dev dependency group.

## 11. Future work (not v1)

- Homebrew-tap clone/view stats (`gh api .../traffic/clones`) as a sibling
  subcommand or flag (e.g. `gh release-stats --tap yo61/homebrew-tap`).
- Compiled binary releases per platform (PyInstaller/Nuitka) so the tool
  works without Python on the user's machine.
- Mutation testing audit (`mutmut`) once the codebase stabilises.
- `--jq` and `--template` flags to match gh's wider output convention.

## 12. Open questions

- **Homebrew tap as a second distribution channel?** Pending decision.
  Pro: familiar `brew install` UX. Con: the tool is a `gh` subcommand and
  only useful to `gh` users, who already have `gh extension install` as a
  first-class, auto-discoverable mechanism. Recommendation: skip — single
  channel.
