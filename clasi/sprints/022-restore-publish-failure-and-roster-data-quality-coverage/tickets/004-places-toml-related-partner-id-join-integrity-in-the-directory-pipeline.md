---
id: '004'
title: places.toml related_partner_id join-integrity in the directory pipeline
status: in-progress
use-cases:
- SUC-026
depends-on:
- '002'
github-issue: ''
issue: 48-pipeline-level-roster-data-quality-validation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# places.toml related_partner_id join-integrity in the directory pipeline

## Description

Recover the `related_partner_id` join-integrity guard
`tests/directory/test_dataset_validity.py`'s `TestRelatedPartnerIdJoin
Integrity` class used to provide (removed by sprint 019 ticket 002 —
that file's own current docstring already says this is "tracked for
recovery ... in issue 48"), as real pipeline-level validation rather
than a test reading a re-copied `partners.json`.

**Unlike ticket 003's `run` command, `directory.pipeline.
run_directory()` does not read `partners.json` at all today** —
`Place.related_partner_id` is a hand-copied value with "no automatic
cross-reference join" by original design (sprint 018 ticket 007). This
ticket *adds* a new read, conditionally.

**Where to wire it**: inside `run_directory()`
(`partner_scrape/directory/pipeline.py`), after `places =
_apply_geo_fallback(places, data_dir=geo_data_dir)` produces the final
`Place` list and **before** `export_directory(places, clubs=clubs,
site_dir=site_dir, dry_run=dry_run)` is called.

**Implementation shape:**

1. Build `references = [(place.place_id, place.related_partner_id) for
   place in places if place.related_partner_id is not None]`.
2. If `references` is empty, skip straight to `export_directory(...)` —
   **do not** read or require `partners.json` to exist. A
   `directory`-only environment with no sibling `stem-ecosystem`
   checkout's `partners.json` must still be able to run cleanly when no
   `Place` references one. This is the one behavioral difference from
   ticket 003's unconditional read — get it right, it's explicitly
   called out in sprint.md's SUC-026.
3. Otherwise, resolve `site_dir` the same way `export_directory()`
   already does (`Path(site_dir) if site_dir is not None else
   get_site_dir()` — check `directory/export.py`'s own resolution to
   match it exactly, not reinvent a third variant), read
   `{resolved_site_dir}/src/data/partners.json`
   (`json.loads(...read_text(encoding="utf-8"))`), and call
   `validate_roster.check_partner_references(references, partners)`.
   Let `RosterValidationError` propagate uncaught — same "structural
   problem is fatal" convention as ticket 003, not per-source isolated
   (contrast with this same function's own per-source
   try/except-and-continue for a flaky third-party fetch, which this is
   **not** — a hand-copy typo in a curated, ~19-row dataset is not a
   flaky source).
4. If `partners.json` doesn't exist at the resolved `site_dir` *and*
   `references` is non-empty, the resulting `FileNotFoundError` (or
   whatever `Path.read_text()` raises) should surface with an actionable
   message — consider catching it and re-raising as
   `RosterValidationError` (or a plain `RuntimeError`, matching
   `export_directory()`'s and `publish.project()`'s own "site_dir does
   not exist, check --site-dir" message convention) rather than letting
   a bare `FileNotFoundError` propagate with no guidance. Use your
   judgment on the exact exception type; the message quality is what
   matters.

## Acceptance Criteria

- [x] `run_directory()` calls `validate_roster.check_partner_references(
      )` after `_apply_geo_fallback()` and before `export_directory()`,
      whenever at least one `Place` has a non-`None`
      `related_partner_id`.
- [x] When no `Place` in the run has a `related_partner_id` set,
      `partners.json` is never read, and the run succeeds even if no
      such file exists at the resolved `site_dir`.
- [x] A dangling `related_partner_id` (one with no matching row in the
      loaded roster) makes `run_directory()` raise, before
      `export_directory()` writes `places.json`, naming both the
      offending `place_id` and the invalid `partner_id`.
- [x] A missing `partners.json` when at least one reference needs it
      raises with an actionable message (not a bare, unexplained
      `FileNotFoundError`).
- [x] `site_dir` is resolved identically to `export_directory()`'s own
      resolution — no independent, potentially-divergent resolution
      logic.
- [x] **Required pre-close live validation**: run `partner-scrape
      directory --dry-run -v --site-dir ../stem-ecosystem` (or the
      resolved default if this machine's sibling checkout has moved)
      against the real sibling checkout and the real committed
      `directory/data/places.toml`, confirm it completes without
      raising, and record in this ticket's Notes how many
      `related_partner_id` references were checked (sprint.md's
      planning-time check found 17 set, all resolving — confirm this at
      execution time rather than assuming it is unchanged).
- [x] Optional, low-risk hygiene: `tests/test_roster_housekeeping.py`'s
      module docstring currently claims logo-backfill checks are
      "tracked for recovery ... in issue 48" — they are not (see
      sprint.md Scope > Out of Scope). If touching that docstring is
      convenient while this ticket is in progress, correct it; if not,
      leave it — not required for this ticket's completion.

## Notes

**Implementation**: Added `_check_related_partner_references()` to
`partner_scrape/directory/pipeline.py`, called from `run_directory()`
immediately after `_apply_geo_fallback()`/`_apply_club_geocoding()` and
before `export_directory(...)`. Builds `references` from `places`
exactly as specified; returns immediately (no read) when empty.
Otherwise resolves `site_dir` with the identical expression
`export_directory()` uses (`Path(site_dir) if site_dir is not None else
get_site_dir()`), reads `{resolved_site_dir}/src/data/partners.json`,
and calls `check_partner_references(references, raw_partners)`,
letting `RosterValidationError` propagate uncaught. A missing/unreadable
`partners.json` when references exist is caught (`OSError`) and
re-raised as a `RuntimeError` with an actionable message, matching
`export_directory()`'s/`publish.project()`'s "check --site-dir or
SITE_DIR" convention — chosen over `RosterValidationError` because this
is an infrastructure/missing-file problem, not a content defect in the
roster itself.

**Regression discovered and fixed**: wiring this in as unconditional
(matching ticket 003's "runs regardless of --dry-run" convention)
exposed 12 pre-existing tests across `tests/directory/test_pipeline.py`,
`tests/directory/test_club_dataset_validity.py`, and
`tests/test_cli_directory.py` that exercise the *real* committed
`places.toml`/registry against a nonexistent or empty `site_dir` — the
real data already carries 17 `related_partner_id` references, so those
tests now need a `partners.json` fixture to keep passing. Fixed by
adding a small per-file helper that derives the fixture's `id` set by
parsing `related_partner_id = N` out of the real `places.toml` text
(never hand-listed, so it can't drift from the real data) and writes a
minimal `partners.json` at each test's `site_dir`. One test,
`test_dry_run_reports_19_places_with_no_network_and_no_disk_write` in
`tests/test_cli_directory.py`, previously asserted `not
site_dir.exists()` after a `--dry-run` invocation against a
`site_dir` that was never created; since the join-integrity read now
needs a real `partners.json` to exist even under `--dry-run` (this
check runs before `export_directory()`, unconditionally — dry_run only
governs whether `export_directory()` itself writes), that assertion is
no longer achievable in the same run. Narrowed the assertion from "the
whole `site_dir` was never created" to "no `places.json`/`clubs.json`
was ever written" — the substantive guarantee `--dry-run` actually
makes — while pre-populating a fixture `partners.json` as the test's own
setup step (not something the code under test writes).

**Live validation** (2026-08-31, against the real sibling
`../stem-ecosystem` checkout and the real committed
`directory/data/places.toml`):

```
$ partner-scrape directory --dry-run -v --site-dir ../stem-ecosystem
INFO partner_scrape.directory.pipeline: Club source 'hack-club-sd' yielded 4 club(s)
INFO partner_scrape.directory.pipeline: Place source 'places-sd' yielded 19 place(s)
partner-scrape directory: wrote 19 places and 4 clubs (dry run -- nothing written).
```

Completed without raising. Verified programmatically: the real
`places.toml` carries **17** `Place` records with a non-`None`
`related_partner_id` (16 unique partner ids — id 85 is referenced by
two places), and every one of the 17 resolves against the real
`../stem-ecosystem/src/data/partners.json`'s `id` values (zero
dangling). This matches sprint.md's planning-time count of "17 set, all
resolving" exactly — unchanged at execution time.

**Test results**: `uv run pytest tests/directory/ -q` — 175 passed.
`uv run pytest -q` (full suite) — 1934 passed, zero regressions.

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/` (full
  directory subsystem — confirm `test_dataset_validity.py`,
  `test_pipeline.py`, and every source/model test still pass), then the
  full suite.
- **New tests to write**: in `tests/directory/test_pipeline.py`
  (alongside its existing `run_directory()` wiring tests):
  - A fixture `Place` (via a fixture `PlaceSource`, or by monkeypatching
    the source dispatch — follow whatever pattern
    `test_pipeline.py`'s existing tests already use for injecting
    `Place`s) with a `related_partner_id` absent from a small fixture
    `partners.json` written to `tmp_path`'s `src/data/partners.json` —
    asserts `run_directory()` raises, naming both ids.
  - The same shape with a `related_partner_id` present in the fixture
    roster — asserts no raise.
  - A fixture run where no `Place` sets `related_partner_id` at all —
    asserts `run_directory()` succeeds even when `tmp_path`'s
    `src/data/partners.json` does not exist.
- **Verification command**: `uv run pytest`, plus the required pre-close
  live-run command above (record its actual output in this ticket's
  Notes before moving it to done).
