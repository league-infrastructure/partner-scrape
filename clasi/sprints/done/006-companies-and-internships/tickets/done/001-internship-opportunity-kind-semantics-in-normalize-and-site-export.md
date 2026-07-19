---
id: '001'
title: Internship opportunity-kind semantics in Normalize and Site Export
status: done
use-cases:
- SUC-004
- SUC-006
depends-on: []
github-issue: ''
issue: 11-company-events-and-internships.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Internship opportunity-kind semantics in Normalize and Site Export

## Description

Foundation ticket for the sprint: give `kind="internship"` Events correct
handling through `normalize/run.py` and `export/writer.py` *before* any
adapter produces real internship Events, using synthetic `Event(kind=
"internship", ...)` fixtures. Later tickets (003, 004 — the Greenhouse
and Lever adapters) depend on this being correct so their own end-to-end
tests can assert real `opportunities.json` output.

`model.py`'s `Kind` literal already includes `"internship"` (since
sprint 001) — no model change is needed here. See sprint.md's
Architecture > Design Rationale ("kind='internship' Events bypass both
`collapse_recurring` and `dedup_cross_source`", "reuse `date_start`/
`date_end`/`availability`...", and the `_is_current_or_upcoming` branch
decision) for the full reasoning behind every behavior below.

## Acceptance Criteria

- [x] `normalize/run.py` defines `WORK_BASED_LEARNING_TYPE = "Work-based
      Learning"` (the site's existing `opportunity_type` enum value for
      internships) as a module-level constant, importable by
      `export/writer.py`.
- [x] `run()` partitions incoming `events` by `kind == "internship"`
      before calling `collapse_recurring`/`dedup_cross_source`;
      internship Events are each wrapped 1:1 into their own `Instance`
      (`repeat_count=1`, `sources=frozenset({event.source_id})`,
      `last_seen` from `event.start.date()` if set) and concatenated
      with the collapsed/deduped non-internship Instances before the
      `_to_opportunity` mapping loop.
- [x] Two `Event(kind="internship")` with the same normalized title, same
      `source_id`, distinct `external_id` both produce distinct
      `Opportunity` records (collapse bypass proven).
- [x] Two `Event(kind="internship")` with the same normalized title, same
      date, same location text, but different `source_id` both produce
      distinct `Opportunity` records (dedup bypass proven).
- [x] `_to_opportunity()` sets `opportunity_type = WORK_BASED_LEARNING_TYPE`
      when `event.kind == "internship"`, else the existing
      `DEFAULT_OPPORTUNITY_TYPE` behavior is unchanged.
- [x] For an internship `Event` with `event.end` set (a known deadline):
      `date_end` is the ISO deadline and `availability` reads
      `"Apply by <date>"`.
- [x] For an internship `Event` with `event.end` unset (no known
      deadline): `date_end` is `""` and `availability` reads
      `"Rolling — apply anytime"`.
- [x] `cost_range` is left `""` for an internship `Opportunity` unless the
      upstream `Event` explicitly set `cost`/`cost_range` — this ticket
      must not introduce a `"Free"` (or any other) forced default; that
      would produce a misleading cost badge (sprint.md's Architecture
      self-review note).
- [x] `export/writer.py`'s `_is_current_or_upcoming` gains a branch: a
      `Opportunity` with `opportunity_type == WORK_BASED_LEARNING_TYPE`
      is current if `date_end` is unset or still in the future (checked
      against the function's existing `today` parameter); every other
      `opportunity_type` keeps today's exact `date_end or date_start >=
      today` rule, unchanged.
- [x] A `"Work-based Learning"` `Opportunity` with `date_start` 30 days in
      the past and no `date_end` is included by the export filter (would
      be wrongly excluded under the pre-ticket rule).
- [x] A `"Work-based Learning"` `Opportunity` with a past `date_end` is
      excluded.
- [x] Every existing `kind="event"`/`"program"` behavior in both modules
      is provably unchanged — the full existing `test_normalize_run.py`,
      `test_normalize_collapse.py`, `test_normalize_dedup.py`, and
      `test_export.py` suites pass with zero modifications to their
      existing test bodies.

## Testing

- **Existing tests to run**: `test_normalize_run.py`,
  `test_normalize_collapse.py`, `test_normalize_dedup.py`,
  `test_export.py`, full `uv run pytest` (no regression anywhere else).
- **New tests to write**: synthetic-`Event`-fixture tests (no adapter
  dependency) in `test_normalize_run.py` for the collapse/dedup bypass,
  `opportunity_type` mapping, and deadline/rolling
  `date_end`/`availability` mapping; new cases in `test_export.py` for
  the `_is_current_or_upcoming` internship branch (no-deadline-past-start
  included, past-deadline excluded, ordinary event unaffected).
- **Verification command**: `uv run pytest`
