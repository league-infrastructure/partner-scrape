---
id: '002'
title: Roster validation primitives module and fixture tests
status: in-progress
use-cases:
- SUC-025
- SUC-026
depends-on: []
github-issue: ''
issue: 48-pipeline-level-roster-data-quality-validation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Roster validation primitives module and fixture tests

## Description

Create the shared validation module this sprint's tickets 003 and 004
both wire in. This ticket is the primitives and their own unit tests
only — no wiring into `pipeline.run()` or `directory.pipeline.py` (that
is tickets 003/004, each depending on this one).

**New file: `partner_scrape/registry/validate_roster.py`.** Three
functions plus one exception class (see sprint.md's Architecture >
Design Rationale for why each design choice below was made — read it
before implementing, it explains the *why*, not just the *what*):

1. `RosterValidationError(Exception)` — the raised type for every
   hard-fail check below. Collect every offender found across every
   check into one combined, actionable message before raising once
   (mirror `export/publish.py`'s and `directory/export.py`'s existing
   `RuntimeError` message style: state what's wrong, name the offending
   row(s), and where possible say what to check) — do not raise on the
   first offender found; a real bad-data run should surface the full
   picture in one failure, not one fix-and-rerun cycle per offender.

2. `validate_roster(partners: list[dict[str, Any]]) -> None` — checks
   the **raw** partner list (a plain `json.loads()` of `partners.json`,
   *not* `normalize.partners.load_partners()`'s name-deduplicated
   `partners_by_norm` dict — see sprint.md's Design Rationale for why:
   `load_partners()`'s `setdefault()` means a colliding second row never
   enters that dict, so a check built on it would be blind to issue 46's
   exact failure mode). Raises `RosterValidationError` if any row:
   - Has coordinates matching the bare-California geocoder centroid,
     `(36.778261, -119.417932)` (round to 6 decimal places before
     comparing, matching the deleted test's own convention).
   - Has a coordinate outside San Diego County's bounding box
     (`latMin: 32.4, latMax: 33.5, lngMin: -117.7, lngMax: -116.0` —
     ported from the deleted test's `SD_BOUNDS`, itself mirroring
     `stem-ecosystem`'s `site/src/pages/partners/index.astro`'s
     `SD_BOUNDS` constant; note that file now lives one repo away from
     this one — keep the constant here, in sync by hand, same as
     before) or is malformed (exactly one of `latitude`/`longitude` set
     with the other `None`, or either value not numeric). A row with
     both `latitude` and `longitude` absent/`None` is not an offender —
     that is the documented "no coordinate yet" state, not bad data.
   - Has a `website` containing a known-hijacked domain. Seed the set
     with exactly `batiquitosfoundation.org` (the deleted test's own
     real incident), as a small `frozenset` so a future hijacked domain
     is a one-line addition.
   - Shares its `model.slugify(name)` result with any other row in the
     same list (issue 46's incident — two exact-duplicate rows under
     different ids silently overwrote each other's published directory
     in `export/publish.py`'s `project()`). Use
     `partner_scrape.model.slugify` — the exact function
     `export/publish.py` already uses to derive each partner's
     published slug — not `normalize.partners.normalize_org_name`
     (a different normalization used for a different purpose, the
     source↔roster join).

3. `find_unresolved_active_sources(sources: list[SourceConfig],
   partners_by_norm: dict[str, dict[str, Any]]) -> list[str]` — for each
   `source` in `sources`, calls `normalize.partners.find_partner(
   source.org_name, partners_by_norm)`; returns the list of `org_name`s
   with no match. **Does not raise** — the caller decides what to do
   with the result (ticket 003 logs it as a warning; see sprint.md's
   Design Rationale for why this is deliberately non-raising: live
   production data has a real, currently-nonzero gap here, 9 of 93
   active sources today, so a raising version would be a regression
   guard that breaks every real run rather than one that catches an
   actual regression).

4. `check_partner_references(references: list[tuple[str, int]],
   partners: list[dict[str, Any]]) -> None` — generic id-reference
   join-integrity check. `references` is a list of
   `(referencer_id, partner_id)` pairs (already filtered to exclude any
   `None` partner_id by the caller); raises `RosterValidationError`
   naming every pair whose `partner_id` is not among `partners`' real
   `id` values. Written generically (not `Place`-typed or
   `directory`-specific) per issue 48's own instruction to reuse "the
   same validation primitive" for the places.toml case (ticket 004) —
   do not special-case it to `Place`.

**Tests: `tests/test_registry_validate_roster.py`** (new file, matching
this project's flat `tests/test_registry_*.py` naming for the
`registry/` package — see `tests/test_registry.py`,
`tests/test_registry_candidates.py`). Every test uses small, hand-built
in-memory fixtures (dicts/dataclasses constructed directly in the test —
no TOML files, no JSON fixture files, no disk I/O). Per check: one test
proving it fires on a bad fixture (assert `RosterValidationError` is
raised, and that the offending row's identifying info — id or name — is
named in the message), and one proving a clean fixture passes without
raising. Also:

- A dedicated test for the duplicate-slug check using **three** rows —
  two colliding, one distinct — proving all offenders are reported
  together, not just the first pair found.
- A dedicated test proving `validate_roster()` operates on the raw list:
  construct two colliding rows that would collapse under
  `normalize.partners.load_partners()`'s own dedup (i.e. they'd produce
  the same `normalize_org_name()` result too), confirm
  `find_partner`/`load_partners` alone would hide the second row, and
  confirm `validate_roster()` still catches the slug collision anyway.
- A `find_unresolved_active_sources()` test with a mix of resolving and
  non-resolving fixture sources, asserting the returned list contains
  exactly the non-resolving ones' `org_name`s (and is empty when every
  source resolves).
- A `check_partner_references()` test with a mix of valid and dangling
  references, asserting the raised message names every dangling
  `(referencer_id, partner_id)` pair, and a clean-references test that
  doesn't raise.

## Acceptance Criteria

- [ ] `partner_scrape/registry/validate_roster.py` exists with
      `RosterValidationError`, `validate_roster()`,
      `find_unresolved_active_sources()`, and
      `check_partner_references()`, matching the shapes above.
- [ ] `validate_roster()` checks the raw partner list, never a
      name-deduplicated view — proven by a dedicated test (see above).
- [ ] Every one of the four content checks (bare-California centroid,
      out-of-bounds/malformed coordinate, hijacked domain, duplicate
      slug) has both a fires-on-bad-data test and a
      passes-on-clean-data test.
- [ ] The duplicate-slug check reports every colliding pair when more
      than one exists in a single call, not just the first found.
- [ ] `find_unresolved_active_sources()` returns (never raises) the
      correct subset of unresolved `org_name`s.
- [ ] `check_partner_references()` raises `RosterValidationError` naming
      every dangling `(referencer_id, partner_id)` pair, and does not
      raise when every reference resolves.
- [ ] `RosterValidationError`'s message, for a multi-offender case,
      names every offender in one raised exception — not one exception
      per offender.
- [ ] No change to `pipeline.py`, `directory/pipeline.py`, or `cli.py`
      in this ticket — wiring is tickets 003/004.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_registry.py
  tests/test_registry_candidates.py` (confirm no collision/regression
  in the `registry/` package's existing test suite), then the full
  suite.
- **New tests to write**: `tests/test_registry_validate_roster.py`, as
  described above — fully hermetic, no fixture files needed beyond
  in-memory Python data structures.
- **Verification command**: `uv run pytest`
