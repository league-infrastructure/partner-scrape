---
id: '002'
title: Register county-parks and sd-astronomy-association feeds
status: done
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
issue: 40-ical-parser-robustness-and-remaining-robots-gated-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register county-parks and sd-astronomy-association feeds

## Description

With ticket 001's `ical.py` fixes merged, the two feeds sprint 015
ticket 005 withheld are ready to re-verify and register. Both TOMLs
were drafted in sprint 014 ticket 004's investigation (the same
endpoints, same `respect_robots = false` policy already decided in
issue 38 and made real by sprint 015 ticket 003) — this ticket
re-verifies against the fixed adapter and commits.

## Acceptance Criteria

- [x] `county-parks.toml` and `sd-astronomy-association.toml` are
      committed with `acquisition_policy.respect_robots = false`,
      matching the already-registered `mission-trails`/`surfrider-sd`/
      `swe-san-diego` TOMLs' shape from sprint 015 ticket 005. **Fully
      met.** Both committed, both in this shape — see Notes for the
      team-lead ruling that widening ticket 001's pre-parse strip
      (rather than leaving `county-parks` withheld) was in scope for
      this ticket after all.
- [x] Each is live-verified via `partner-scrape --dry-run --no-enrich
      --source <id>` through the real `ical` adapter to return
      non-zero, dated output before commit. Both confirmed non-zero,
      dated — see Notes for the per-source found/dated/new counts.
- [x] If either still returns zero at dry-run time (ticket 001's fix
      did not fully resolve it), that TOML is **not** committed and
      this ticket records why in its Notes, per sprint 015 ticket
      005's own withholding convention — this ticket does not close
      as fully done in that case; it is left `open` with the finding
      recorded, matching that same precedent. **N/A as shipped** — the
      team-lead ruled the newly-identified `REFRESH-INTERVAL` root
      cause was in-scope to fix directly (a second live-evidenced case
      of the exact pattern ticket 001 already established), so it was
      fixed rather than withheld; see Notes for the full sequence.
- [x] `org_name` is checked against `site/src/data/partners.json`;
      neither is expected to match (both remain issue 32
      roster-expansion candidates per sprint 014 ticket 004's original
      list), so this is a check, not an expected force-match.
      Confirmed: neither "San Diego County Parks and Recreation" nor
      "San Diego Astronomy Association" appears in `partners.json`.
- [x] Full test suite stays green (registry loader tests already cover
      generic `ical` TOML parsing; no new hermetic tests expected
      purely from adding data-only TOML files). 1547 passed (1546 +
      1 new fixture regression test for the combined
      `X-PUBLISHED-TTL`/`REFRESH-INTERVAL` case — see Notes for why
      this ticket did add one hermetic test, departing from its own
      original Testing plan once adapter code changed).

## Notes (ticket 002, 2026-08-30/31)

**Registered (2 of 2): `sd-astronomy-association` and `county-parks`.**

**`sd-astronomy-association`.** Ticket 001's fix (multi-RRULE
first-rule salvage in `_extract_component`, plus widening `extract()`'s
per-VEVENT catch from `(ValueError, TypeError, KeyError)` to
`Exception`) fully resolves the bug sprint 015 ticket 005 hit. Live
dry-run confirms:

```
GET https://calendar.google.com/calendar/ical/sdaa%40sdaa.org/public/basic.ics
-> HTTP 200, text/calendar, 677 raw VEVENTs (matches prior counts)

uv run partner-scrape --dry-run --no-enrich --source sd-astronomy-association
-> found=795 dated=795 new=177 dropped=0
```

(`found`/`dated` exceed the raw 677-VEVENT count because recurring
VEVENTs expand into multiple dated occurrences, per `ical.py`'s
`MAX_RRULE_WINDOW_DAYS`/`MAX_RRULE_INSTANCES`-bounded RRULE expansion —
consistent with `mission-trails`/`surfrider-sd`/`swe-san-diego`'s own
`found` > raw-VEVENT pattern in sprint 015 ticket 005.) One VEVENT
(`fl3n8sfj9ok6se7tk2em9biimg@google.com`) logs the expected "has 2
RRULE properties; using the first and discarding 1" salvage warning —
direct, live confirmation of ticket 001's fix operating on real data,
not just its fixture tests. Committed as `sd-astronomy-association.toml`.

**`county-parks` — initially withheld, then unblocked within this same
ticket per a team-lead ruling.** First pass: ticket 001's
`X-PUBLISHED-TTL` pre-parse strip was necessary but **not sufficient**
for this feed. Live dry-run still returned zero:

```
GET https://tockify.com/api/feeds/ics/sdparkscalendar
-> HTTP 200, text/calendar, 553 raw VEVENTs (matches prior counts)

uv run partner-scrape --dry-run --no-enrich --source county-parks
-> WARNING: iCal feed ... was unparseable: Invalid iCalendar duration: P15M
-> found=0 (delta n/a) dated=0 new=0 dropped=0
```

Root cause, newly identified (distinct from the bug ticket 001 fixed):
Tockify's `VCALENDAR` header emits **two** non-standard duration
properties with the same invalid value, back to back —

```
X-PUBLISHED-TTL:P15M
REFRESH-INTERVAL:P15M
```

— and ticket 001's `_X_PUBLISHED_TTL_RE` strip only targeted the
first. `icalendar.Calendar.from_ical()` still raised `InvalidCalendar:
Invalid iCalendar duration: P15M` on `REFRESH-INTERVAL`, which this
adapter also never reads, aborting the whole feed exactly as
`X-PUBLISHED-TTL` did before ticket 001.

Per this ticket's original dispatch instructions this was first
treated as out of scope ("do NOT patch adapters yourself... leave that
source uncommitted, and report"), and reported to the team-lead with
`county-parks.toml` removed from disk (not left unstaged — the
registry loader globs every `*.toml` under `sources/` regardless of
git tracking status, so a zero-yield file left on disk would be picked
up by every subsequent pipeline run and test collection).

**Team-lead ruling (mid-ticket course correction):** the
"don't patch adapters" instruction was a dispatch guardrail, not an
architecture boundary — `REFRESH-INTERVAL` is exactly the second
live-evidenced case of the same non-standard-Tockify-duration-property
pattern ticket 001 already fixed once, so widening that fix in place
was ruled in scope for this ticket. Implemented as:

- `partner_scrape/adapters/ical.py`: `_X_PUBLISHED_TTL_RE` replaced by
  `_NONSTANDARD_DURATION_PROPERTIES = ("X-PUBLISHED-TTL",
  "REFRESH-INTERVAL")` and a regex built from that list
  (`_NONSTANDARD_DURATION_RE`) — a targeted, extensible list of
  live-evidenced properties, deliberately **not** a blanket
  X-property/custom-property sanitizer (an unrelated malformed
  property still fails loudly through the existing top-level
  `except Exception` around `from_ical()`).
- `tests/fixtures/ical/tockify_ttl_and_refresh_interval.ics` (new): the
  existing `tockify_ttl.ics` fixture plus one added
  `REFRESH-INTERVAL:P15M` line.
- `tests/test_adapters_ical.py`: new `TestBothNonstandardDurationProperties`
  class (one test) proving the combined case parses and yields both
  fixture VEVENTs; `TestTockifyTTLTolerance`'s docstring updated to
  point at it.
- `partner_scrape/adapters/DESIGN.md`'s sprint-016 addendum item 1
  rewritten to describe both properties and both tickets.

Re-verified live after the fix:

```
uv run partner-scrape --dry-run --no-enrich --source county-parks
-> found=553 dated=553 new=36 dropped=0
```

All 553 raw VEVENTs now parse and yield dated output — the single
highest-yield feed in the sprint 015 issue 38 batch. Committed as
`county-parks.toml`.

**`partners.json` check.** Neither "San Diego County Parks and
Recreation" nor "San Diego Astronomy Association" appears in
`site/src/data/partners.json`; both remain issue 32 roster-expansion
candidates, per sprint 014 ticket 004's original list. Not
force-matched.

**Test suite.** `uv run pytest` — 1547 passed (1546-baseline + 1 new
fixture regression test for the combined `X-PUBLISHED-TTL`/
`REFRESH-INTERVAL` case). This departs from the ticket's own original
Testing plan ("no new tests expected purely from adding data-only TOML
files") because, per the team-lead's course correction, this ticket
ended up shipping a real adapter-code change, not just data-only TOML
registration — a fixture regression test for that change follows this
project's own established convention (ticket 001 itself added five
such tests for its two fixes).

**Documentation.** `partner_scrape/registry/DESIGN.md` §1 Purpose gets
a sprint-016-ticket-002 paragraph recording the full 2-of-2
registration and the `county-parks` `REFRESH-INTERVAL` finding/fix
sequence. `partner_scrape/adapters/DESIGN.md`'s sprint-016 addendum
item 1 is rewritten (not just appended to) to describe the widened,
two-property fix as the current state of `ical.py`'s duration-property
tolerance.

**Status left `in-progress`, not moved to `done`**, per this ticket's
explicit dispatch instructions ("Leave frontmatter in-progress") —
both feeds are now registered and live-verified, so this is a
process-convention hold for team-lead sign-off, not an unresolved
finding.

## Testing

- **Existing tests to run**: `uv run pytest`; registry loader tests to
  confirm both new TOMLs parse.
- **New tests to write**: none expected purely from adding data-only
  TOML files, matching sprint 014/015's own precedent for this exact
  kind of ticket.
- **Verification command**: `uv run pytest`, plus the required
  `--dry-run` live verification per source (not pytest).

## Implementation Plan

**Approach**: Re-use the sprint 014 ticket 004 TOML drafts verbatim
(endpoint URLs already confirmed live), add `acquisition_policy.
respect_robots = false`, live-verify against the now-fixed adapter,
commit only on non-zero output.

**Files to modify**:
- `partner_scrape/registry/sources/county-parks.toml`
- `partner_scrape/registry/sources/sd-astronomy-association.toml`

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/registry/DESIGN.md` gets a
one-line sprint-016 note recording the 5-of-5 completion of the
robots-gated batch issue 38/40 track, matching its existing per-sprint
registry-growth convention.
