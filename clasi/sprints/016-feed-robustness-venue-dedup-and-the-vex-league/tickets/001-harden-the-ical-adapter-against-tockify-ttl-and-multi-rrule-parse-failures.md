---
id: '001'
title: Harden the ical adapter against Tockify TTL and multi-RRULE parse failures
status: in-progress
use-cases:
- SUC-001
- SUC-002
depends-on: []
github-issue: ''
issue: 40-ical-parser-robustness-and-remaining-robots-gated-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Harden the ical adapter against Tockify TTL and multi-RRULE parse failures

## Description

Sprint 015 ticket 005 live-verified that `county-parks` (Tockify, 553
raw VEVENTs) and `sd-astronomy-association` (Google Calendar, 677 raw
VEVENTs) — the two highest-yield feeds in the robots-gated batch — both
return zero events, from two genuine, previously-undiscovered
`partner_scrape/adapters/ical.py` bugs unrelated to the robots-policy
question that ticket resolved:

1. **Tockify's `X-PUBLISHED-TTL:P15M`** fails `icalendar`'s strict
   duration parser (`P15M` reads as 15 months under ISO-8601; Tockify
   means 15 minutes, `PT15M`) — `icalendar.Calendar.from_ical()` raises
   `InvalidCalendar` before a single VEVENT is read.
2. **A VEVENT with more than one `RRULE` property** makes
   `component.get("rrule")` return a Python `list`; `_extract_component`
   calls `.to_ical()` on it assuming a single `vRecur`, raising
   `AttributeError: 'list' object has no attribute 'to_ical'`.
   `extract()`'s per-VEVENT catch (`ValueError, TypeError, KeyError`)
   does not contain this exception type, so it propagates out of the
   per-VEVENT loop and aborts the whole source instead of skipping one
   record.

Both fixes stay entirely inside `adapters/ical.py`. See
`clasi/sprints/016-.../sprint.md`'s Architecture > Design Rationale for
the full reasoning behind each choice (targeted pre-parse strip, not a
general X-property sanitizer; salvage via the first RRULE, not a
dropped record; widen the catch to `Exception`, matching this module's
own top-level precedent and `adapters/DESIGN.md`'s per-record isolation
invariant).

## Acceptance Criteria

- [ ] `ICalAdapter.extract()` pre-parses the raw ICS body and strips the
      `X-PUBLISHED-TTL:` line (or otherwise sanitizes it) before calling
      `icalendar.Calendar.from_ical()`, so a body carrying
      `X-PUBLISHED-TTL:P15M` parses successfully.
- [ ] `_extract_component` handles a list-valued `rrule_prop` by using
      its first element and logging a warning naming how many
      additional rules were discarded, instead of raising
      `AttributeError`.
- [ ] `extract()`'s per-VEVENT `except` clause is widened from
      `(ValueError, TypeError, KeyError)` to catch any `Exception`,
      matching the module's own top-level `except Exception` around
      `Calendar.from_ical()` and `adapters/DESIGN.md`'s per-record
      isolation invariant.
- [ ] A fixture `.ics` body built from the real `county-parks`
      `X-PUBLISHED-TTL:P15M` line parses without raising and yields the
      fixture's VEVENTs; a fixture with no `X-PUBLISHED-TTL` property
      is unaffected (no regression for every other registered `ical`
      source).
- [ ] A fixture feed containing one multi-RRULE VEVENT alongside several
      normal VEVENTs yields events for all of them, including a
      salvaged (first-rule) expansion for the multi-RRULE one.
- [ ] A regression fixture proves the exact pre-fix crash inputs (the
      TTL body; the multi-RRULE VEVENT) no longer abort `extract()`.
- [ ] Full test suite stays green (1541+ passed).

## Testing

- **Existing tests to run**: `uv run pytest`, especially
  `tests/test_adapters_ical.py` (or equivalent) in full.
- **New tests to write**: the TTL-tolerant-parse fixture, the
  multi-RRULE-salvage fixture, and a widened-exception-isolation
  regression fixture — all three built from this ticket's own live
  evidence (the real `X-PUBLISHED-TTL:P15M` line; a synthesized
  multi-RRULE VEVENT matching the shape `sd-astronomy-association`
  exhibited).
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Two independent, small fixes inside one module, plus a
widened catch clause that is a direct consequence of the second fix's
own lesson (the existing tuple was already narrower than the module's
top-level precedent).

**Files to modify**:
- `partner_scrape/adapters/ical.py` — TTL pre-parse strip,
  list-valued-RRULE handling in `_extract_component`, widened
  `extract()` per-VEVENT catch.
- The corresponding `ical` adapter test module — new fixture cases.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/adapters/DESIGN.md` gets a
short sprint-016 addendum describing both fixes and why the catch
clause widened, matching this file's existing per-sprint convention
for documenting adapter-level behavior changes.
