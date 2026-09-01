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

- [ ] `run_directory()` calls `validate_roster.check_partner_references(
      )` after `_apply_geo_fallback()` and before `export_directory()`,
      whenever at least one `Place` has a non-`None`
      `related_partner_id`.
- [ ] When no `Place` in the run has a `related_partner_id` set,
      `partners.json` is never read, and the run succeeds even if no
      such file exists at the resolved `site_dir`.
- [ ] A dangling `related_partner_id` (one with no matching row in the
      loaded roster) makes `run_directory()` raise, before
      `export_directory()` writes `places.json`, naming both the
      offending `place_id` and the invalid `partner_id`.
- [ ] A missing `partners.json` when at least one reference needs it
      raises with an actionable message (not a bare, unexplained
      `FileNotFoundError`).
- [ ] `site_dir` is resolved identically to `export_directory()`'s own
      resolution — no independent, potentially-divergent resolution
      logic.
- [ ] **Required pre-close live validation**: run `partner-scrape
      directory --dry-run -v --site-dir ../stem-ecosystem` (or the
      resolved default if this machine's sibling checkout has moved)
      against the real sibling checkout and the real committed
      `directory/data/places.toml`, confirm it completes without
      raising, and record in this ticket's Notes how many
      `related_partner_id` references were checked (sprint.md's
      planning-time check found 17 set, all resolving — confirm this at
      execution time rather than assuming it is unchanged).
- [ ] Optional, low-risk hygiene: `tests/test_roster_housekeeping.py`'s
      module docstring currently claims logo-backfill checks are
      "tracked for recovery ... in issue 48" — they are not (see
      sprint.md Scope > Out of Scope). If touching that docstring is
      convenient while this ticket is in progress, correct it; if not,
      leave it — not required for this ticket's completion.

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
