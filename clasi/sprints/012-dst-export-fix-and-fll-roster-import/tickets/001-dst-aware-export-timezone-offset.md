---
id: '001'
title: DST-aware export timezone offset
status: open
use-cases: [SUC-001]
depends-on: []
github-issue: ''
issue: 19-dst-aware-timezone-offset-in-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# DST-aware export timezone offset

## Description

`partner_scrape/normalize/run.py`'s `_iso()` appends a hard-coded
`_TZ_OFFSET = "-07:00"` (Pacific Daylight Time) to every naive datetime
on its way into `Opportunity.date_start`/`date_end`. San Diego is
Pacific Standard Time (`-08:00`) from early November to mid-March, so
every event exported during that roughly four-month window carries an
offset one hour off from true local time — a real correctness bug in
the published data contract (`site/src/data/opportunities.json`, the
`public/data/` export, and every consumer of either), not a display
nicety. This ticket replaces the constant with a real per-datetime
timezone resolution.

See `clasi/issues/19-dst-aware-timezone-offset-in-export.md` for the
full write-up and `clasi/sprints/012-dst-export-fix-and-fll-roster-import/design/normalize-DESIGN.diff.md`
for the approved design (the "(Sprint 012)" additions to `normalize/
run.py`'s Design and Open Questions sections).

## Acceptance Criteria

- [ ] `_iso()` resolves each naive `datetime`'s UTC offset from
      `zoneinfo.ZoneInfo("America/Los_Angeles")` at serialization time,
      replacing the `_TZ_OFFSET` constant. `-07:00` for Daylight Time
      dates, `-08:00` for Standard Time dates.
- [ ] A naive `datetime` that is already aware (`tzinfo is not None`) is
      left untouched — no change to that branch's existing behavior.
- [ ] The DST-transition fold convention documented in the design
      overlay is implemented: `fold=0` (the stdlib default, since no
      adapter in this codebase ever sets `fold` explicitly) governs both
      edge cases — the repeated 1am-2am hour in November resolves to its
      earlier (Daylight Time) occurrence; the skipped 2am-3am hour in
      March resolves to `zoneinfo`'s own pre-transition-offset
      convention for a nonexistent local time. No new convention is
      invented beyond what `zoneinfo`/`fold` already provide.
- [ ] `_TZ_OFFSET`'s module-level docstring/comment is removed or
      updated to no longer describe a hard-coded literal.
- [ ] No change to any other function in `normalize/run.py`,
      `collapse.py`, `dedup.py`, or `taxonomy.py`.
- [ ] No change to `export/writer.py` — confirmed in this sprint's
      Architecture that `is_current_or_upcoming` and every other
      date-based filter there reads only `date_str[:10]` (the date
      portion), never the offset suffix, so this fix changes no
      `export/` behavior, only its output's correctness.

## Testing

- **Existing tests to run**: `uv run pytest tests/normalize/` and
  `uv run pytest tests/export/` — both must stay green with no
  modification to any existing test.
- **New tests to write**:
  - `tests/normalize/test_run.py`: a naive `datetime` in July serializes
    with `-07:00`; a naive `datetime` in January serializes with
    `-08:00`; an already-aware `datetime`'s offset is left untouched
    (regression); a naive `datetime` at `1:30am` on the November
    fall-back date and a naive `datetime` at `2:30am` on the March
    spring-forward date each serialize with the offset the design
    overlay's documented `fold` convention specifies — assert the exact
    offset string, not just that serialization doesn't raise.
  - `tests/export/test_writer.py`: a new regression test constructing an
    `Opportunity` whose `date_end` sits exactly on a DST boundary date
    and asserting `is_current_or_upcoming` still partitions it correctly
    relative to a `today` on each side of that boundary — this is
    verification that the already-existing date-portion-only comparison
    is unaffected by the offset fix, per this sprint's Architecture
    "Out of Scope" note.
- **Verification command**: `uv run pytest` (full suite, ~1190 tests,
  must stay green).
