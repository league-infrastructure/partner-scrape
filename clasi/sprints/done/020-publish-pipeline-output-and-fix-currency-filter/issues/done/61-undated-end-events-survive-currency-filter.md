---
status: done
sprint: '020'
tickets:
- 020-001
---

# Undated-end events with a past start date survive the current/upcoming export filter

## Description

Found by the stem-ecosystem-side session verifying its own
`docs/issues/005-no-past-dates-shown.md` (a fix already mostly landed
via `normalize/collapse.py`'s `_span()` next-occurrence logic — live
data is down to 1 of 350 records showing a past `date_start`). The
residual case: "2nd Innovation in Women's Health Pitch Competition",
`date_start` 2024-12-01, **no `date_end` at all**, still present in the
export.

## Cause

`_span()`'s next-occurrence clamping only fires when a recurring
instance's *last* date reaches today — a record with no `date_end`
never gets a "last date" to clamp against, so it keeps its original
2024 `date_start` unchanged and apparently still passes
`export/writer.py`'s `is_current_or_upcoming` filter. Worth checking
whether that filter's undated-`date_end` branch is treating "no end
date" as "still ongoing" (reasonable for a genuinely undated program)
when this specific record is actually a one-time past event that
happens to lack an end date, not an ongoing program.

## Proposed fix

Investigate `_span()` (`normalize/collapse.py`) and
`is_current_or_upcoming()` (`export/writer.py`) together — the fix
likely belongs in the currency filter itself: a record with a past
`date_start`, no `date_end`, and no recurrence signal should not be
treated as perpetually current. Add a regression fixture from this
exact case.

## Verification

Fixture test: a record shaped like the pitch-competition case (past
start, no end) is excluded from `is_current_or_upcoming`; existing
undated-but-genuinely-ongoing cases (if any exist in the fixture suite)
remain included.

## References

stem-ecosystem/docs/issues/005-no-past-dates-shown.md (original report);
partner_scrape/normalize/collapse.py `_span()`;
partner_scrape/export/writer.py `is_current_or_upcoming`.
