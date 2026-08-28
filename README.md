# gh-release-stats

Print GitHub release-asset download stats as an aligned text table or JSON.

Distributed as a [`gh` extension](https://cli.github.com/manual/gh_extension).

## Install

```bash
gh extension install yo61/gh-release-stats
```

Requires Python ≥ 3.11 on `PATH`. The tool itself has no Python
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
┌──────────┬──────────────┬─────────────┬──────────────┬─────────────┬─────────┬────────────┬───────┐
│ Tag      │ linux x86_64 │ linux arm64 │ macos x86_64 │ macos arm64 │ windows │ SHA256SUMS │ Total │
├──────────┼──────────────┼─────────────┼──────────────┼─────────────┼─────────┼────────────┼───────┤
│ v1.3.9   │            1 │           0 │            0 │           2 │       0 │          0 │     3 │
│ ...      │              │             │              │             │         │            │       │
├──────────┼──────────────┼─────────────┼──────────────┼─────────────┼─────────┼────────────┼───────┤
│ Total    │           21 │           0 │            1 │           9 │      19 │          1 │    51 │
└──────────┴──────────────┴─────────────┴──────────────┴─────────────┴─────────┴────────────┴───────┘
```

JSON (`--json`):

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

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Any expected failure (gh missing, not authenticated, repo not found, no releases, malformed JSON, network error). One human-readable line on stderr. |
| 130 | Ctrl-C |

## Development

[mise](https://mise.jdx.dev) is required for development. It supplies the uv
version `pyproject.toml` pins via `[tool.uv] required-version` (uv refuses to
run outside `>=0.12,<0.13`), it supplies `task`, and it sets `UV_FROZEN=1`.
Without it you get a uv that may refuse to run, no `task`, and no protection
against an accidental relock.

```bash
mise trust               # first time only, in this directory
mise install             # uv 0.12.x and task, per mise.toml
```

`prek` is not supplied by mise — install it separately (`brew install prek`).

```bash
uv sync --group dev      # install dev deps in .venv/
uv run pytest -q         # run tests
uv run ruff check        # lint
uv run ruff format       # format
uv run ty check release_stats.py    # type-check
prek install             # install pre-commit hooks
```

`mise.toml` sets `UV_FROZEN=1`, so none of the above rewrites `uv.lock` as a
side effect. When you change dependencies or the project version, re-lock
explicitly:

```bash
task uv:lock             # the deliberate way to change uv.lock
```

Use the task rather than plain `uv lock`: under `UV_FROZEN=1` that silently
no-ops and still exits 0, and so does `uv lock --check`.

CI runs `uv sync --group dev --locked`, which fails if `uv.lock` and
`pyproject.toml` disagree — so an un-relocked dependency change is caught at
PR time rather than merged silently.

## License

MIT.
