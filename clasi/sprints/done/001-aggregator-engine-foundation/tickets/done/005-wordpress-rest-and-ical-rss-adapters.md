---
id: '005'
title: WordPress REST and iCal/RSS adapters
status: done
use-cases:
- SUC-003
depends-on:
- '004'
github-issue: ''
issue: 02-adapter-framework-structured-apis.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# WordPress REST and iCal/RSS adapters

## Description

Add the remaining two structured-API adapters from issue 02, following
the `Adapter` protocol established in ticket 004. Per sprint.md Open
Question 2, neither adapter has a confirmed production target site in
this sprint's source material (only TEC does) — both are built
generically and fixture-tested, with live registry entries deferred to
sprint 2.

Scope:
- **WordPress REST adapter** (`adapter_type == "wp_rest"`): queries
  `/wp-json/wp/v2/posts` (and optionally `/pages`), mapping
  `title.rendered`, `content.rendered`/`excerpt.rendered`, `link` into
  a canonical `Event`. WP REST has no structured event date/venue field
  the way TEC does, so date/location fields are left unset (no
  provenance entry) rather than guessed — this adapter's `Event`s are
  lower-quality than TEC's by design, and that should be visible in
  what fields carry provenance, not in a fabricated confidence number.
- **iCal/RSS adapter** (`adapter_type == "ical"`): fetches a `.ics`
  feed (many TEC sites expose one at `?ical=1`, per
  `dev/SCRAPER_GUIDELINES.md` §5) and parses it with the `icalendar`
  library (new runtime dependency — hand-parsing RFC 5545 is a
  correctness trap not worth taking on, see sprint.md Design
  Rationale). Each non-recurring `VEVENT` becomes one `Event`. A
  `VEVENT` with an `RRULE` is expanded into its occurrences using
  `python-dateutil` (new runtime dependency), **bounded** to the next
  180 days or 52 instances, whichever is smaller — an unbounded RRULE
  (e.g. `FREQ=DAILY` with no `COUNT`/`UNTIL`) must never produce
  unbounded output. This bound is a deliberate, documented scope cut,
  not a silently-missing feature.

## Acceptance Criteria

- [x] Given a recorded WordPress REST `posts` fixture, the adapter
      emits one `Event` per post with `title`/`description`/`url` set
      and `provenance="wp_rest"`; `start`/`location` are left unset
      (no provenance entry), not guessed from post content.
- [x] Given a recorded `.ics` fixture containing at least one
      non-recurring `VEVENT` and one recurring `VEVENT` with a bounded
      `RRULE` (e.g. `COUNT=5`), the adapter emits one `Event` for the
      non-recurring `VEVENT` and five `Event`s (one per occurrence) for
      the recurring one, all with `provenance="ical"`.
  - [x] A `VEVENT` with an unbounded `RRULE` (no `COUNT`/`UNTIL`) is
        expanded only up to the 180-day/52-instance cap — verified by a
        fixture asserting the emitted count never exceeds the cap.
- [x] A malformed `.ics` file (unparseable) or an empty WP REST
      response yields zero Events and a logged warning, not an
      exception that kills the source.
- [x] `pyproject.toml` gains `icalendar` and `python-dateutil` as
      runtime dependencies.
- [x] Both adapters are registered in ticket 004's dispatch registry
      under `"wp_rest"` and `"ical"`.

## Implementation Plan

### Approach

Both adapters follow ticket 004's `Adapter` protocol exactly — this
ticket should not need any change to `base.py`'s dispatch mechanism,
which is itself a check on ticket 004's interface design. For iCal,
use `icalendar.Calendar.from_ical()` to parse, then for each `VEVENT`
check for an `rrule` property; if present, build a
`dateutil.rrule.rrulestr(...)` from it seeded at `DTSTART`, and iterate
occurrences with an explicit `count=52` cap combined with a manual
"stop past `DTSTART + 180 days`" check (whichever bound triggers
first) — do not rely on the RRULE's own `COUNT`/`UNTIL` alone, since
the whole point of the cap is to protect against the case where those
are absent.

### Files to Create/Modify

- `pyproject.toml` — add `icalendar`, `python-dateutil`.
- `partner_scrape/adapters/wordpress.py`
- `partner_scrape/adapters/ical.py`
- `tests/test_adapters_wordpress.py`
- `tests/test_adapters_ical.py`
- `tests/fixtures/wordpress/posts.json`
- `tests/fixtures/ical/simple.ics` (non-recurring + bounded-recurring
  VEVENTs), `tests/fixtures/ical/unbounded_rrule.ics`

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (tickets 001-004's
  suites, especially the dispatch-registry tests from ticket 004 —
  confirm adding these two adapters doesn't require touching `base.py`).
- **New tests to write**: `tests/test_adapters_wordpress.py`,
  `tests/test_adapters_ical.py` per the acceptance criteria above,
  including the unbounded-RRULE cap test.
- **Verification command**: `uv run pytest`
