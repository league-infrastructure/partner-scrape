---
id: '002'
title: Register county-parks and sd-astronomy-association feeds
status: in-progress
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
      `swe-san-diego` TOMLs' shape from sprint 015 ticket 005.
      **Partially met — see Notes.** `sd-astronomy-association.toml`
      committed in this shape. `county-parks.toml` was authored in
      this shape, live-verified to still return zero, and per the AC
      below was **not** committed (removed from disk, not just left
      unstaged, since the registry loader globs every `*.toml` file
      in `sources/` regardless of git tracking status).
- [x] Each is live-verified via `partner-scrape --dry-run --no-enrich
      --source <id>` through the real `ical` adapter to return
      non-zero, dated output before commit. Both were run; see Notes
      for the per-source result (one passed, one still fails).
- [x] If either still returns zero at dry-run time (ticket 001's fix
      did not fully resolve it), that TOML is **not** committed and
      this ticket records why in its Notes, per sprint 015 ticket
      005's own withholding convention — this ticket does not close
      as fully done in that case; it is left `open` with the finding
      recorded, matching that same precedent. **Applies to
      `county-parks`** — see Notes for the precise, newly-identified
      root cause (distinct from the one ticket 001 fixed).
- [x] `org_name` is checked against `site/src/data/partners.json`;
      neither is expected to match (both remain issue 32
      roster-expansion candidates per sprint 014 ticket 004's original
      list), so this is a check, not an expected force-match.
      Confirmed: neither "San Diego County Parks and Recreation" nor
      "San Diego Astronomy Association" appears in `partners.json`.
- [x] Full test suite stays green (registry loader tests already cover
      generic `ical` TOML parsing; no new hermetic tests expected
      purely from adding data-only TOML files). 1546 passed, matching
      the ticket-001 baseline exactly (one new TOML committed, zero
      new hermetic tests, per this ticket's own Testing plan).

## Notes (ticket 002, 2026-08-30/31)

**Registered (1 of 2): `sd-astronomy-association`.** Ticket 001's fix
(multi-RRULE first-rule salvage in `_extract_component`, plus widening
`extract()`'s per-VEVENT catch from `(ValueError, TypeError, KeyError)`
to `Exception`) fully resolves the bug sprint 015 ticket 005 hit. Live
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

**Not registered: `county-parks`.** Ticket 001's `X-PUBLISHED-TTL`
pre-parse strip was necessary but **not sufficient** for this feed.
Live dry-run still returns zero:

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

— and ticket 001's `_X_PUBLISHED_TTL_RE` strip only targets the first.
`icalendar.Calendar.from_ical()` still raises `InvalidCalendar: Invalid
iCalendar duration: P15M` on `REFRESH-INTERVAL`, which this adapter
also never reads, aborting the whole feed exactly as `X-PUBLISHED-TTL`
did before ticket 001. Confirmed diagnostically (not shipped — no
adapter code was touched by this ticket, per its dispatch instruction
not to patch adapters on a ticket-001-uncovered parser issue): stripping
both `X-PUBLISHED-TTL:...` and `REFRESH-INTERVAL:...` lines before
`from_ical()` lets the calendar parse cleanly, all 553 VEVENTs
readable. `county-parks.toml` was authored (same shape as the
committed sources) but is **not committed** — removed from disk rather
than left unstaged, since `registry/loader.py` globs every `*.toml`
under `sources/` regardless of git tracking status, and a
zero-yield/`[ERROR]`-logging file left on disk would be picked up by
every subsequent pipeline run and test collection. Flagging for a
follow-up ticket: a small generalization of ticket 001's fix (strip
both known non-standard `X-`/`REFRESH-INTERVAL` duration properties,
or a more general tolerant-duration pre-parse) would unlock this feed,
the single highest-yield source in the sprint 015 issue 38 batch (553
raw VEVENTs, the countywide ranger-program calendar).

**`partners.json` check.** Neither "San Diego County Parks and
Recreation" nor "San Diego Astronomy Association" appears in
`site/src/data/partners.json`; both remain issue 32 roster-expansion
candidates, per sprint 014 ticket 004's original list. Not
force-matched.

**Test suite.** `uv run pytest` — 1546 passed, matching the ticket-001
baseline exactly (one new data-only TOML committed; no new hermetic
tests needed, per this ticket's own Testing plan — the registry loader
tests already generically cover `ical`-adapter TOML parsing).

**Documentation.** `partner_scrape/registry/DESIGN.md` §1 Purpose gets
a sprint-016-ticket-002 paragraph recording the 1-of-2 registration and
the `county-parks` `REFRESH-INTERVAL` root cause.

**Status left `in-progress`, not moved to `done`**, per this ticket's
own AC #3 precedent (sprint 015 ticket 005's "leave open, not done, on
a partial result" convention) and this ticket's dispatch instructions
— the `county-parks` finding warrants team-lead review/routing before
closing (issue 40 was framed as unlocking both feeds; only one is
unlocked).

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
