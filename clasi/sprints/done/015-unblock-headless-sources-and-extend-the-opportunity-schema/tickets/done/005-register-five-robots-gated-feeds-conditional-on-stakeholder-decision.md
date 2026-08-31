---
id: '005'
title: Register five robots-gated feeds (conditional on stakeholder decision)
status: done
use-cases:
- SUC-006
depends-on:
- '003'
github-issue: ''
issue: 38-acquisition-policy-threading-and-feed-robots.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register five robots-gated feeds (conditional on stakeholder decision)

## Description

**This ticket is conditional and gated on a stakeholder decision that
was pending as of sprint planning.** Five live, high-yield,
well-formed feeds are blocked solely by host `robots.txt`: SD County
Parks (Tockify ICS, ~553-677 events measured live in sprint 014),
Mission Trails Regional Park Foundation (~164), Surfrider SD (~2313),
San Diego Astronomy Association, and SWE San Diego (an existing
partner with no other event source today) — all `calendar.google.com`
or `tockify.com` ICS subscription URLs. Registration TOMLs for all
five were drafted during sprint 014 ticket 004's investigation and
deliberately not committed.

Whether `partner-scrape` treats an explicitly-published ICS
subscription URL (designed to be polled by calendar clients) as
feed-client traffic — fetching it politely while ignoring robots.txt
for that specific URL class — or keeps strict robots compliance is a
policy call for the stakeholder, not an engineering one. Do not
register any of the five without a recorded decision.

This ticket depends on ticket 003: without acquisition-policy
threading actually working, setting
`acquisition_policy.respect_robots = false` in these TOMLs would be
dead configuration, exactly the gap ticket 003 fixes.

## Acceptance Criteria

- [x] **Gate check first**: confirm a stakeholder decision on the
      robots-policy question is recorded (where the team-lead directs —
      e.g. a `clasi/issues/38-...md` update or an explicit sprint note)
      before writing or committing any of the five TOMLs. *Cleared —
      issue 38's "Stakeholder decision" section: Eric decided
      2026-08-30 to treat published ICS subscription URLs as
      feed-client traffic.*
- [x] If the decision is "treat as feed-client traffic, ignore robots
      for this URL class": all five TOMLs are committed with
      `acquisition_policy.respect_robots = false`, each live-verified
      to return non-zero, dated output via `partner-scrape --dry-run
      --source <id>` before commit. **3 of 5 committed, not all 5 —
      see Notes.** `county-parks` and `sd-astronomy-association` were
      live dry-run-verified to return **zero** events each, from two
      distinct pre-existing `ical.py` bugs unrelated to the
      robots-policy question (unparseable `X-PUBLISHED-TTL` duration;
      an uncaught `AttributeError` on a multi-`RRULE` VEVENT) — withheld
      per this ticket's own dispatch instruction ("if a feed turns out
      dead or returns zero events at dry-run time, do NOT commit that
      TOML"). `mission-trails`, `surfrider-sd`, and `swe-san-diego` are
      committed, each confirmed non-zero/dated via the real dry-run.
- [x] *(N/A — the other decision branch.)* If the decision is "keep
      strict robots compliance," or does not land during this sprint:
      no TOML is committed, and this ticket is left `open` (not
      `done`) with a note explaining the gate state, to roll to a
      future sprint rather than block this sprint's close. Does not
      apply: the decision was the opposite (see above).
- [x] If shipped, `org_name` matches `partners.json`'s existing `name`
      field where the org is already a partner (SWE San Diego); the
      other four are noted as candidates for the roster-expansion
      issue, not force-matched. `swe-san-diego.toml`'s `org_name`
      ("Society of Women Engineers - San Diego") matches exactly.
      `mission-trails` and `surfrider-sd` (committed) and `county-parks`
      and `sd-astronomy-association` (not committed) all remain issue
      32 roster-expansion candidates, not force-matched.
- [x] Full test suite stays green if any TOML is committed. 1541
      passed (same as the HEAD baseline).

## Notes (ticket 005 completion, 2026-08-30)

**Gate check.** Cleared: issue 38's "Stakeholder decision" section
records Eric's 2026-08-30 decision to treat published ICS subscription
URLs as feed-client traffic — poll politely, ignore host `robots.txt`
for this URL class. Ticket 003 (already `done`) makes
`acquisition_policy.respect_robots = false` real (threaded into
`PoliteFetcher.get()` via `adapters.base.acquisition_kwargs`), not the
dead configuration it was when sprint 014 ticket 004 investigated
these same five feeds.

**Registered (3 of 5 candidates), each committed with
`acquisition_policy.respect_robots = false` and live-verified via
`uv run partner-scrape --dry-run --no-enrich --source <id>` through
the real `ical` adapter — not just a raw HTTP fetch — immediately
before commit:**

| source_id | raw VEVENTs (curl) | dry-run `found` | dry-run `new` | caveat |
|---|---|---|---|---|
| `mission-trails` | 164 | 138 | 67 | some recurring VEVENTs skipped (pre-existing `ical.py` RRULE/timezone limitation, below) |
| `surfrider-sd` | 2313 | 2188 | 994 | same limitation, larger absolute count |
| `swe-san-diego` | 285 | 280 | 225 | same limitation, plus one VEVENT with no SUMMARY |

**Dropped after live dry-run (2 of 5 candidates) — NOT committed,**
per this ticket's own dispatch instruction ("if a feed turns out dead
or returns zero events at dry-run time, do NOT commit that TOML"):

- **`county-parks`** (SD County Parks, Tockify) — the raw fetch
  succeeds (`GET https://tockify.com/api/feeds/ics/sdparkscalendar` →
  HTTP 200, 553 raw VEVENTs, matching sprint 014 ticket 004's original
  measurement), but the *entire* feed is unparseable by the
  `icalendar` library: its `X-PUBLISHED-TTL:P15M` property is not a
  valid ISO-8601 duration under `icalendar`'s strict parser (`P15M`
  reads as 15 months per the ISO-8601 grammar; Tockify evidently
  intends 15 minutes, which would need `PT15M`), so
  `icalendar.Calendar.from_ical()` raises `InvalidCalendar` before a
  single VEVENT is read. `--dry-run --source county-parks` confirms:
  `found=0`. Reproduced directly: `icalendar.Calendar.from_ical(...)`
  → `icalendar.error.InvalidCalendar: Invalid iCalendar duration:
  P15M`.
- **`sd-astronomy-association`** (SDAA, Google Calendar) — the raw
  fetch succeeds (`GET https://calendar.google.com/calendar/ical/
  sdaa%40sdaa.org/public/basic.ics` → HTTP 200, 677 raw VEVENTs,
  matching sprint 014 ticket 004's original measurement), but
  `--dry-run --source sd-astronomy-association` crashes:
  `AttributeError: 'list' object has no attribute 'to_ical'` in
  `ical.py`'s `_extract_component`, when `component.get("rrule")`
  returns a Python `list` (a VEVENT with more than one `RRULE`
  property) instead of a single `vRecur`. This `AttributeError` is not
  among `extract()`'s existing per-record-isolation catch types
  (`ValueError`, `TypeError`, `KeyError`), so it propagates out of the
  per-VEVENT loop and aborts the *entire* source rather than skipping
  just the one malformed VEVENT — yield report shows `found=0
  [ERROR]`.

Both are genuine, previously-undiscovered `ical.py` bugs, newly
surfaced by this ticket's live verification (sprint 014's own
investigation never reached this far — it was blocked earlier, at the
robots.txt/dead-config stage, before ticket 003 fixed the threading).
Neither is the robots-policy question this ticket exists to resolve;
fixing either is adapter code, out of this data-only registration
ticket's scope. Flagging both for a follow-up issue/ticket —
`county-parks` in particular would otherwise be the single
highest-yield feed in this batch (553 events, matching the countywide
ranger-program calendar).

**`partners.json` check.** `swe-san-diego.toml`'s `org_name` ("Society
of Women Engineers - San Diego") matches `site/src/data/
partners.json`'s existing `name` field exactly — SWE San Diego is an
existing partner with no other registered event source today.
`mission-trails` and `surfrider-sd` (committed) plus `county-parks`
and `sd-astronomy-association` (not committed) have no `partners.json`
match; all four remain issue 32 roster-expansion candidates per
sprint 014 ticket 004's original list, not force-matched.

**Test suite.** `uv run pytest` — 1541 passed, matching the HEAD
baseline exactly. The registry loader tests already generically cover
`ical`-adapter TOML parsing, so the three new well-formed files needed
no new tests, per this ticket's Testing plan.

**Documentation.** `partner_scrape/registry/DESIGN.md` §1 Purpose gets
a sprint-015-ticket-005 paragraph recording the 3-of-5 registration and
the two dropped feeds' root causes.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`); registry
  loader tests to confirm every new TOML parses, if any are committed.
- **New tests to write**: none expected purely from adding data-only
  TOML files.
- **Verification command**: `uv run pytest`, plus a `--dry-run` per
  source if shipped.

## Implementation Plan

**Approach**: Gate check first, then (only if cleared) per-feed TOML
authoring against the endpoints already verified live in sprint 014
ticket 004, exactly as drafted there.

**Files to modify** (only if the gate clears):
- `partner_scrape/registry/sources/{county-parks,sd-astronomy-
  association,mission-trails,surfrider-sd,swe-san-diego}.toml` (exact
  filenames per the drafted sprint 014 versions).

**Testing plan**: see Testing above.

**Documentation updates**: none unless shipped, in which case
`partner_scrape/registry/DESIGN.md` gets a one-line sprint-015 note
matching its existing per-sprint registry-growth convention.
