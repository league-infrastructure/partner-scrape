---
id: '001'
title: Prune orphaned opportunity images via backfill_missing_images.py --prune
status: done
use-cases: []
depends-on: []
github-issue: ''
issue: 48-repo-cleanup-stale-cruft.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Prune orphaned opportunity images via backfill_missing_images.py --prune

## Description

`data/images/opportunities/` holds 562 files / 336 MB; only 485 are
referenced by `data/opportunities.json` or any
`data/partners/*/{events,past-events}.json`. The other 77 (35 MB) are
referenced by nothing.

`dev/backfill_missing_images.py` already computes both referenced sets
for its check mode (`_referenced_from_partners`,
`_referenced_from_opportunities`) and the existing-files set
(`_existing_images`). Add a `--prune` mode that computes the same sets
and deletes any existing file whose name is in neither referenced set
(the inverse of the existing missing-file computation), instead of
writing a separate throwaway script. Filenames are content-hashed, so
deleting a file whose event later reappears just costs one refetch, not
data loss — this is a low-stakes prune.

This script is explicitly out of scope as a *subsystem* (issue 48: "not
cruft... whose check-only mode is a reusable integrity gate") — only its
argument surface grows. It stays a standalone, stdlib-only, hand-run
script per its existing docstring convention (never imported by runtime
code, no network access).

## Acceptance Criteria

- [x] `dev/backfill_missing_images.py` gains a `--prune` flag (usable
      standalone or combined with the existing check-only default; no
      change to the existing `--source-dir`/backfill behavior).
- [x] `--prune` computes `existing - (referenced_from_partners |
      referenced_from_opportunities)` and deletes exactly that set from
      `data/images/opportunities/`.
- [x] `--prune --dry-run` reports what would be deleted (filenames and
      count) without deleting anything.
- [x] Without `--dry-run`, `--prune` prints each deleted filename and a
      summary count, then re-runs the existing check and reports it
      (mirroring the existing `--source-dir` after-check pattern).
- [x] Running `uv run python dev/backfill_missing_images.py` (check-only,
      no flags) against the real `data/` tree after pruning reports 0
      missing for both the partners-derived and opportunities-derived
      checks.
- [x] Running the prune against the real repo's `data/images/opportunities/`
      removes exactly the 77 currently-orphaned files (confirm count
      before and after) and leaves `git status` showing only deletions
      under that directory (no unrelated changes).
- [x] The script's module docstring is updated to document `--prune`
      alongside the existing check-only and backfill modes.
- [x] No test or manual run touches the network or writes outside a
      pytest `tmp_path` fixture directory — never point a test at the
      real `data/` tree.

## Implementation Plan

**Approach**: Add a `prune()` function parallel to the existing
`backfill()` function, reusing `_existing_images`,
`_referenced_from_partners`, and `_referenced_from_opportunities`. Wire
a `--prune` `argparse` flag into `main()`, mutually usable alongside the
existing `--source-dir`/`--dry-run` flags (mutual exclusivity isn't
required — pruning and backfilling from a source dir are independent
concerns — but `--prune` should run its own before/after check exactly
like `--source-dir` does today).

**Files to modify**:
- `dev/backfill_missing_images.py` — add `prune()`, extend `main()`'s
  argparse and control flow, update the module docstring.

**Testing plan**: Add unit tests (new or extended test file under
`tests/`, matching this repo's existing test layout for `dev/` scripts
if one exists, otherwise `tests/dev/test_backfill_missing_images.py`)
that build a fixture data directory under `tmp_path` with a small
`opportunities.json`, a `partners/<slug>/events.json`, and an
`images/opportunities/` directory containing: referenced-by-opportunities
files, referenced-by-partners files, and orphaned files. Assert
`--prune --dry-run` reports orphans without deleting, and `--prune`
(no dry-run) deletes exactly the orphaned set and leaves referenced
files untouched. Also add/extend a test asserting the existing
check-only default behavior is unaffected by the new flag.

**Documentation updates**: Module docstring in
`dev/backfill_missing_images.py` gets a `--prune` usage example
alongside the existing check-only and `--source-dir` examples. Record
in issue 48 (item 1) that the prune ran against the real repo, with the
before/after file counts.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite; baseline 2531
  passing must not regress). Any existing tests for
  `dev/backfill_missing_images.py`'s check mode must continue passing
  unchanged.
- **New tests to write**: fixture-based tests for `--prune` and
  `--prune --dry-run` as described in the Implementation Plan, entirely
  under `tmp_path` — never against the real `data/` tree.
- **Verification command**: `uv run pytest`, plus a manual run of
  `uv run python dev/backfill_missing_images.py --prune` against the
  real repo (recorded in issue 48), followed by
  `uv run python dev/backfill_missing_images.py` to confirm 0 missing.

## Notes

Implemented as planned: `prune()` added parallel to `backfill()`,
reusing `_existing_images`/`_referenced_from_partners`/
`_referenced_from_opportunities`; `--prune` wired into `main()` with
its own before/after check, independent of `--source-dir`. New tests
in `tests/dev/test_backfill_missing_images.py` (7 tests, fixture-only
under `tmp_path`).

Real-repo run: `data/images/opportunities/` went from 562 files / 322M
to 485 files / 288M — exactly 77 files removed (~34M). `--prune
--dry-run` first confirmed the 77-file count matched the survey.
Post-prune check-only run: `partners: 457 referenced, 457 present, 0
missing`; `opportunities.json: 145 referenced, 145 present, 0 missing`.
`git status` after the prune showed only 77 deletions under
`data/images/opportunities/`, no unrelated changes.

Full suite: 2538 passed (2531 baseline + 7 new).
