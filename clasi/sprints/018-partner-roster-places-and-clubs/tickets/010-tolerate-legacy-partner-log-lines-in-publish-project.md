---
id: '010'
title: Tolerate legacy partner-log lines in publish.project()
status: in-progress
use-cases: []
depends-on: []
github-issue: ''
issue: 45-publish-legacy-jsonl-tolerance.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tolerate legacy partner-log lines in publish.project()

## Description

`partner_scrape/export/publish.py`'s `_to_opportunity()` reconstructs an
`Opportunity` from a persisted `.jsonl` line by dict-subscripting every
current `Opportunity` dataclass field name out of the stored entry
(`kwargs: dict[str, Any] = {name: entry[name] for name in
_OPPORTUNITY_FIELD_NAMES}`, `publish.py:132`). The per-partner log
(`export/partner_log.py`) is strictly append-only and never migrated:
any line recorded before a given field existed on `Opportunity` lacks
that key. `eligibility` was added to `Opportunity` in sprint 015
(`b0570aa`), so every log line recorded before that sprint now raises
`KeyError('eligibility')` when `publish.project()` collapses and
reconstructs it — which is every line, since the store predates sprint
015. Root-caused in sprint 018 ticket 001 (see that ticket's Notes for
the full reproduction and traceback); ticket 001 made the failure loud
(wrapped the `cli.py` call in try/except, logged, non-zero exit) but
deliberately left `_to_opportunity()` itself unfixed, out of its file
scope. Consequence: `publish.project()` has failed on every run since
sprint 015 merged, and `public/data/` (the partner roster + per-partner
event files issue 15's `llms.txt` contract advertises) has been
silently stale until ticket 001's exit-code fix made it loud, and stays
functionally broken until this ticket lands.

The `.jsonl` log's entire append-only design assumes old lines stay
readable as the schema grows (see `export/DESIGN.md`'s "append-only"
invariant) — tolerating a missing key on reconstruction restores an
already-intended property, not a new behavior.

## Acceptance Criteria

- [ ] `_to_opportunity()` defaults any field missing from a persisted
      log `entry` from `Opportunity`'s own dataclass field defaults
      (`dataclasses.fields(Opportunity)` — already imported as
      `_OPPORTUNITY_FIELD_NAMES`'s source), by iterating dataclass
      fields generically. No per-field special case for `eligibility`
      or any other single field name — the fix must equally tolerate a
      *future* field addition with no code change here.
- [ ] A field present in `entry` is used verbatim (current behavior,
      unchanged); only an absent field falls back to the dataclass
      default. A field whose dataclass default is itself required
      (no `default`/`default_factory` — i.e. `Opportunity`'s
      non-defaulted fields) is never actually missing in practice for
      any real log line, since `partner_log.record()` always writes
      every field that existed on `Opportunity` at record time; this AC
      only needs to hold for fields added *after* a line was written.
- [ ] Regression test: a fixture `.jsonl` line built from a real
      pre-sprint-015 shape (missing `eligibility`) reconstructs via
      `_to_opportunity()` without raising, and the resulting
      `Opportunity.eligibility` equals the dataclass default (`""`).
- [ ] Regression test: a fixture `.jsonl` line missing several newer
      fields at once (not just `eligibility`) reconstructs correctly,
      each missing field taking its dataclass default.
- [ ] Regression test: `publish.project()` run end-to-end (via
      `tmp_path` fixtures, not the real store) over a partner log
      containing a mix of legacy (missing-field) and current-schema
      lines succeeds and produces correct output for both eras of line.
- [ ] Live verification: run `publish.project()` (or the `uv run
      partner-scrape` path that calls it) against this repo's real
      accumulated `partner_log/` store and confirm it completes without
      raising and regenerates `public/data/` — the same store ticket
      001's Notes used to reproduce the original `KeyError`. Record the
      command run and its outcome in this ticket's Notes.
- [ ] Full test suite stays green (`uv run pytest`).

## Testing

- **Existing tests to run**: `uv run pytest`, in particular any
  existing `tests/` coverage of `export/publish.py` (`_to_opportunity`,
  `_collapse_last_line_wins`, `project`) and `export/partner_log.py`,
  to confirm no regression to current-schema (non-legacy) reconstruction.
- **New tests to write**: the four regression tests in Acceptance
  Criteria — one missing-single-field fixture line, one
  missing-several-fields fixture line, one mixed-era `project()`
  end-to-end run, and (implicitly covered by the mixed-era test) a
  same-partner log containing both a legacy and a current-schema line
  collapsing correctly via `_collapse_last_line_wins`'s existing
  last-line-wins logic.
- **Verification command**: `uv run pytest`, plus the live verification
  step in Acceptance Criteria (a real `publish.project()` invocation
  against this repo's actual `partner_log/` store, confirming
  `public/data/` regenerates and the process exits cleanly).

## Implementation Plan

**Approach**: Systematic, narrow fix confined to `_to_opportunity()`'s
reconstruction logic. Replace the current dict-comprehension's plain
`entry[name]` subscript with a lookup that iterates
`dataclasses.fields(Opportunity)` (already available via the module's
existing `fields` import and `_OPPORTUNITY_FIELD_NAMES` derivation) and
falls back to each field's own `default`/`default_factory` when `name`
is absent from `entry`, rather than hardcoding `eligibility`'s specific
default. Keep the existing `sources` list→`frozenset` round-trip
unchanged (it already assumes `entry["sources"]` is present — legacy
lines predate the `sources` field's own introduction only insofar as
that field already existed when the log was first written; if a fixture
shows `sources` can also be legacy-missing, default it via the same
generic mechanism rather than a special case). Do not touch
`_collapse_last_line_wins`, `_split_current_and_past`, `project()`'s
outer structure, or anything in `cli.py` (ticket 001 already fixed the
caller-side wiring there) — this ticket's scope is `_to_opportunity()`
and its direct test coverage only.

**Files to modify**:
- `partner_scrape/export/publish.py` — `_to_opportunity()`'s
  field-reconstruction logic.
- `tests/` (wherever existing `export/publish.py` tests live, following
  this codebase's existing per-module test-file convention) — new
  regression tests per Acceptance Criteria.

**Testing plan**: see Testing above.

**Documentation updates**: none anticipated — `export/DESIGN.md` already
documents the append-only log's tolerance-for-drift intent; this ticket
restores actual conformance to that documented intent rather than
changing the intent itself. If implementation reveals `DESIGN.md`
understated this gap, add a brief note to its Open Questions or
Constraints section, but only to describe what was actually found.
