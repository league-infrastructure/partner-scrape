---
id: '001'
title: 'Fix currency filter: bound the deadline-first undated-deadline rule to a recency
  window'
status: done
use-cases:
- SUC-020
depends-on: []
github-issue: ''
issue: 61-undated-end-events-survive-currency-filter.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix currency filter: bound the deadline-first undated-deadline rule to a recency window

## Description

`export/writer.py`'s `is_current_or_upcoming()` has a `DEADLINE_FIRST_TYPES`
branch (`WORK_BASED_LEARNING_TYPE`, `"Competitions"`) that, when
`date_end` is unset, unconditionally returns `True`. That rule exists
(sprint 006 Design Rationale, generalized sprint 015 ticket 007) because
`date_start` for these types is a posting-observed date, routinely in
the past for a still-open, rolling-admission record — the ordinary
`date_end or date_start >= today` rule would wrongly expire it. The bug
(issue 61): the rule has no upper bound on how stale that posting date
can be. A genuinely one-time past event that happens to lack a recorded
deadline — the reported case, "2nd Innovation in Women's Health Pitch
Competition" (`opportunity_type="Competitions"`, `date_start`
2024-12-01, no `date_end`, confirmed via the live `stem-ecosystem`
`opportunities.json`) — is ~21 months stale and still exports as
current.

`_span()` (`normalize/collapse.py`) is NOT implicated — issue 61's own
diagnosis (1 of 350 live records affected) confirms it already handles
the general "next-occurrence" case correctly. Do not modify `_span()` or
`collapse_recurring()`.

The fix must NOT simply drop the no-deadline-still-open rule for
`DEADLINE_FIRST_TYPES` — an existing regression test,
`test_competitions_no_deadline_with_past_start_is_included`
(`tests/test_export.py`, `TestDeadlineFirstCurrentUpcomingFilterGeneralization`,
30-day-old posting), locks in the legitimate case that rule protects,
and it must keep passing unmodified. Instead, bound the rule: when
`date_end` is unset for a `DEADLINE_FIRST_TYPES` record, it counts as
"still open" only if `date_start` is within a recency window of `today`
— older than that, treat it as closed/excluded, on the reasoning that a
genuinely still-open program would have been re-posted or re-observed
more recently. Introduce this as a named constant (e.g.
`_DEADLINE_FIRST_STALE_POSTING_DAYS = 365`), not a bare magic number —
365 days is this sprint's recommendation (comfortably above the existing
30-day-old test cases, comfortably below the ~638-day-old reported
outlier); see sprint.md Open Questions for why this exact value isn't
tightly calibrated.

## Acceptance Criteria

- [x] `is_current_or_upcoming()`'s `DEADLINE_FIRST_TYPES` branch, when
      `date_end` is unset, excludes a record whose `date_start` is older
      than the new named staleness-window constant, and still includes
      one within it.
- [x] A new regression fixture, shaped exactly like the reported case
      (`opportunity_type="Competitions"`, `date_start` far enough in the
      past to exceed the window, no `date_end`), asserts exclusion via
      `export_opportunities()` (matching this file's existing
      `tmp_path`/explicit-`today` test convention).
- [x] Every existing test in `TestDeadlineFirstCurrentUpcomingFilterGeneralization`
      and `TestInternshipCurrentUpcomingFilter` continues to pass
      unmodified — in particular
      `test_competitions_no_deadline_with_past_start_is_included` and
      `test_no_deadline_internship_with_past_start_is_included` (both
      30-day-old postings) still assert inclusion.
- [x] A record with a set `date_end` (either `DEADLINE_FIRST_TYPES` or
      ordinary) is unaffected — no behavior change on that path.
- [x] Ordinary (non-`DEADLINE_FIRST_TYPES`) records are unaffected —
      `TestCurrentUpcomingFilter` and `TestDSTBoundaryPartitioning`
      continue to pass unmodified.
- [x] `_span()` / `normalize/collapse.py` and `tests/test_normalize_collapse.py`
      are untouched by this ticket.

## Implementation Plan

**Approach**: add a module-level named constant in `export/writer.py`
(e.g. `_DEADLINE_FIRST_STALE_POSTING_DAYS = 365`, with a docstring
explaining the reported case and the existing regression tests it must
not break). In `is_current_or_upcoming()`'s `DEADLINE_FIRST_TYPES`
branch, replace the unconditional `if not opportunity.date_end: return
True` with a comparison of `date_start` against
`today - timedelta(days=_DEADLINE_FIRST_STALE_POSTING_DAYS)`. Keep the
existing dated-`date_end` comparison on that branch unchanged. Update
the function's docstring to describe the new bound (it currently
documents the unconditional-`True` behavior this ticket changes).

**Files to modify**:
- `partner_scrape/export/writer.py` (`is_current_or_upcoming()`, new
  constant, docstring update)

**Files to create**: none.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_export.py -q`
  (full file — confirms every existing currency-filter class still
  passes), then the full suite (`uv run pytest -q`).
- **New tests to write**: in `tests/test_export.py`'s
  `TestDeadlineFirstCurrentUpcomingFilterGeneralization`, add a case
  reproducing the exact reported record shape (title "2nd Innovation in
  Women's Health Pitch Competition" or an equivalent fixture,
  `opportunity_type="Competitions"`, `date_start` far enough before
  `today` to exceed the staleness window, `date_end=""`) and assert
  `export_opportunities([...]) == []`. Consider also a boundary-day case
  (just inside vs. just outside the window) if it clarifies the fix
  without over-testing an unvalidated exact threshold.
- **Verification command**: `uv run pytest -q`
