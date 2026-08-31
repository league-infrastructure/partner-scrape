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

- [x] `ICalAdapter.extract()` pre-parses the raw ICS body and strips the
      `X-PUBLISHED-TTL:` line (or otherwise sanitizes it) before calling
      `icalendar.Calendar.from_ical()`, so a body carrying
      `X-PUBLISHED-TTL:P15M` parses successfully.
- [x] `_extract_component` handles a list-valued `rrule_prop` by using
      its first element and logging a warning naming how many
      additional rules were discarded, instead of raising
      `AttributeError`.
- [x] `extract()`'s per-VEVENT `except` clause is widened from
      `(ValueError, TypeError, KeyError)` to catch any `Exception`,
      matching the module's own top-level `except Exception` around
      `Calendar.from_ical()` and `adapters/DESIGN.md`'s per-record
      isolation invariant.
- [x] A fixture `.ics` body built from the real `county-parks`
      `X-PUBLISHED-TTL:P15M` line parses without raising and yields the
      fixture's VEVENTs; a fixture with no `X-PUBLISHED-TTL` property
      is unaffected (no regression for every other registered `ical`
      source).
- [x] A fixture feed containing one multi-RRULE VEVENT alongside several
      normal VEVENTs yields events for all of them, including a
      salvaged (first-rule) expansion for the multi-RRULE one.
- [x] A regression fixture proves the exact pre-fix crash inputs (the
      TTL body; the multi-RRULE VEVENT) no longer abort `extract()`.
- [x] Full test suite stays green (1541+ passed).

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

## Notes (implementation, 2026-08-30)

**All three code changes landed in `partner_scrape/adapters/ical.py`
exactly as scoped:**

1. A module-level `_X_PUBLISHED_TTL_RE` regex, applied in `extract()`
   before `icalendar.Calendar.from_ical()`, strips any
   `X-PUBLISHED-TTL:` line (case-insensitive, either line-ending style).
2. `_extract_component` now checks `isinstance(rrule_prop, list)`,
   salvages via `rrule_prop[0]`, and logs a warning naming the VEVENT's
   UID, the total RRULE count, and the discarded count.
3. `extract()`'s per-VEVENT catch widened from
   `(ValueError, TypeError, KeyError)` to `except Exception`.

**Environment note on the TTL repro.** Reproducing sprint 015 ticket
005's exact live crash (`icalendar.error.InvalidCalendar: Invalid
iCalendar duration: P15M`) directly against this checkout's pinned
`icalendar==7.2.0` did not raise — `X-PUBLISHED-TTL` is an unregistered
`X-` property in this version's type table and decodes as a plain
`vText`, not a duration, so no strict-duration parse is attempted on
it. `grep` over the installed `icalendar` package confirms no
`PUBLISHED-TTL` special-case and no "Invalid iCalendar duration"
message exists in this version's source at all. The multi-RRULE bug
reproduces exactly as described (`component.get("rrule")` returns a
list of `vRecur`; `.to_ical()` on a list raises `AttributeError`) —
confirmed directly via a standalone repro script before writing any
fixture. The TTL fix ships anyway, per the sprint plan's already-
decided design (a harmless, evidenced, targeted pre-parse strip); the
new fixture tests prove the strip's presence and its no-op-on-absence
behavior, not a live crash-to-pass transition, since none was
reproducible in this exact dependency environment. Flagging this
discrepancy rather than silently treating the AC as "obviously
satisfied" — worth a note if a future ticket revisits whether the
strip is still load-bearing against a different `icalendar` pin.

**Tests added** (`tests/test_adapters_ical.py`, +5 tests, all new
fixtures under `tests/fixtures/ical/`):
- `TestTockifyTTLTolerance` (2 tests) — `tockify_ttl.ics` (built from
  the real `X-PUBLISHED-TTL:P15M` line) parses and yields both fixture
  VEVENTs; `simple.ics` (no TTL property) is unaffected.
- `TestMultiRruleSalvage` (1 test) — `multi_rrule.ics`'s VEVENT carries
  two structurally different RRULEs (`FREQ=WEEKLY;COUNT=3` then
  `FREQ=DAILY;COUNT=10`) so a wrong salvage choice is numerically
  distinguishable from the correct one; asserts exactly 3 weekly
  occurrences (first rule) and that the feed's other VEVENTs are
  unaffected; asserts the discard-count warning is logged.
- `TestTtlAndMultiRruleRegression` (1 test) — `ttl_and_multi_rrule_
  regression.ics` combines both crash triggers plus a normal VEVENT in
  one feed; proves none of it aborts `extract()`.
- `TestWidenedExceptionIsolation` (1 test) — monkeypatches
  `_extract_component` to raise the exact `AttributeError` message
  sprint 015 measured on the first VEVENT of `simple.ics`, delegating
  to the real method for the rest; proves the widened catch isolates an
  exception type outside the original three-tuple without relying on
  the RRULE fix itself (which now prevents that specific
  `AttributeError` from ever reaching this catch in production).

**Documentation.** `partner_scrape/adapters/DESIGN.md` gained a
"`ical.py` hardening against two live-measured parse failures. (Sprint
016 ticket 001)" paragraph in §4 Design, describing both fixes and the
catch-widening rationale, matching the file's existing per-sprint
addendum convention. `docs/design/design.md`'s subsystem map (§4) was
left unchanged — it stays adapter-count/description-generic and this
ticket adds no new adapter type or pipeline-shape change.

**Test suite.** `uv run pytest -q` — 1546 passed (1541 baseline + 5 new
tests), 0 failed. `tests/test_adapters_ical.py` alone: 22 passed (17
baseline + 5 new).

**Deviations from plan.** None. All three code changes, the fixture
set, and the documentation update match the ticket's Implementation
Plan and the sprint's Design Rationale exactly.
