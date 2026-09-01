---
id: '007'
title: Publish yield-history.json into data/ from cli.py
status: in-progress
use-cases:
- SUC-019
depends-on:
- '002'
github-issue: ''
issue: 60-publish-pipeline-output-in-well-known-data-directory.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Publish yield-history.json into data/ from cli.py

## Description

`yield-history.json` is the one artifact in scope for issue 60 that
isn't owned by a data-contract export module — it's saved directly from
`cli.py`'s `main()` via `observability.snapshot.save_snapshot(yield_history_path,
report)`, guarded by `if not args.dry_run:` (only reached when
`yield_reporter is not None`, i.e. `--no-report` was not given). Unlike
tickets 003-006, this ticket does NOT change `save_snapshot()`'s
signature — it already just writes a given path; no new parameter is
needed there. Instead, `cli.py`'s `main()` gains a second call to it,
writing the same already-built `report` a second time to
`config.get_own_data_dir() / "yield-history.json"`, immediately
alongside the existing call, under the same `if not args.dry_run:`
guard. Depends only on ticket 002 for `get_own_data_dir()`; independent
of tickets 003-006.

Directory auto-creation: `save_snapshot()`'s own existing behavior for a
missing parent directory should be checked (read its implementation
first) — if it does not already create missing parents, this ticket
must either add that (consistent with every other own-repo write in
this sprint auto-creating its target) or explicitly create
`config.get_own_data_dir()` before calling it a second time.

## Acceptance Criteria

- [x] A non-dry-run `run` invocation with reporting enabled (the
      default; `--no-report` not given) writes
      `data/yield-history.json` in partner-scrape's own repo, with
      content identical to the `SITE_DIR`/`--yield-history` copy.
- [x] `--dry-run` writes to neither location (unchanged for `SITE_DIR`,
      extended to the new own-repo path).
- [x] `--no-report` skips both writes entirely (unchanged existing
      behavior for `SITE_DIR`, extended to the new own-repo path — no
      `yield_reporter`, nothing to report, nothing written anywhere).
- [x] A missing own-repo `data/` directory does not raise — created
      automatically, matching every other own-repo write in this
      sprint.
- [x] Existing CLI wiring tests (`--yield-history` override,
      `--no-report`, dry-run) continue to pass unmodified.

## Implementation Plan

**Approach**: read `observability/snapshot.py`'s `save_snapshot()`
first to confirm its missing-parent-directory behavior before deciding
whether `cli.py` needs an explicit `mkdir` before the second call.
Add the second `save_snapshot()` call in `main()`, directly after the
existing one, inside the same `if not args.dry_run:` block — resolve
the own-repo yield-history path once
(`config.get_own_data_dir() / "yield-history.json"`), matching how
`yield_history_path` (the `SITE_DIR`/`--yield-history` target) is
already resolved earlier in `main()`.

**Files to modify**:
- `partner_scrape/cli.py` (`main()`)
- Whatever test file already covers CLI yield-history wiring (`grep -rl
  "yield_history\|yield-history" tests/` to locate it).

**Files to create**: none.

## Testing

- **Existing tests to run**: the located CLI yield-history test file,
  then the full suite.
- **New tests to write**: a case confirming
  `data/yield-history.json` is written (in a `tmp_path`-backed own-repo
  stand-in, with `config.get_own_data_dir` monkeypatched — never touch
  the real repo `data/` in a test) on a normal run, skipped under
  `--dry-run` and under `--no-report`.
- **Verification command**: `uv run pytest -q`
