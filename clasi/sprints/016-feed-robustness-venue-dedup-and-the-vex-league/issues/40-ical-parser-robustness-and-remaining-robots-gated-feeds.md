---
status: in-progress
sprint: '016'
tickets:
- 016-001
- 016-002
---

# ical.py parser robustness: unlock county-parks and sd-astronomy-association feeds

## Description

Sprint 015 ticket 005 registered three of the five robots-gated ICS
feeds cleared by the stakeholder's 2026-08-30 feed-client decision
(recorded in sprint 015 issue 38). The other two — the two
highest-yield feeds in the batch — are blocked by two genuine,
previously-undiscovered bugs in `partner_scrape/.../ical.py`, found
during ticket 005's mandatory live dry-run verification:

1. **Tockify feeds fail entirely on `X-PUBLISHED-TTL`.**
   `county-parks` (Tockify ICS, 553 raw VEVENTs) emits
   `X-PUBLISHED-TTL:P15M`, which `icalendar`'s strict duration parser
   rejects — `icalendar.Calendar.from_ical()` raises `InvalidCalendar`
   before any VEVENT is read, so the whole source yields zero.
   Reproduced directly against the live feed.

2. **Multiple `RRULE` properties on one VEVENT crash extraction.**
   `sd-astronomy-association` (Google Calendar ICS, 677 raw VEVENTs)
   contains at least one VEVENT with more than one `RRULE`; icalendar
   returns a list, and `_extract_component` calls `.to_ical()` on it —
   `AttributeError: 'list' object has no attribute 'to_ical'`. The
   per-record isolation in `extract()` only catches
   `(ValueError, TypeError, KeyError)`, so one bad record aborts the
   entire source instead of being skipped.

## Fix shape

- Harden the ical ingest path against both cases (tolerant pre-parse or
  sanitization for non-standard `X-` duration properties; handle
  list-valued properties per record; widen or restructure the
  per-record isolation so one malformed VEVENT never kills a source).
- Then register the `county-parks` and `sd-astronomy-association`
  TOMLs with `acquisition_policy.respect_robots = false` — drafts in
  sprint 014 ticket 004's Notes; the recorded robots decision already
  covers both. Live-verify non-zero dated output per source before
  commit, per the established AC convention.

## References

- Reproduction detail: sprint 015 ticket 005 Notes
  (`clasi/sprints/015-.../tickets/done/005-...md`)
- Policy record: sprint 015 issue 38 "Stakeholder decision" section
- TOML drafts: sprint 014 ticket 004 Notes
