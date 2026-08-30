---
id: '004'
title: Register verified structured feeds
status: done
use-cases:
- SUC-007
- SUC-008
depends-on:
- '002'
- '003'
github-issue: ''
issue: 25-register-verified-structured-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register verified structured feeds

## Description

Register roughly 20 new source TOMLs against the existing `tec_rest`,
`ical`, and `localist` adapters, using each feed's already
live-verified endpoint from issue 25:

- **`tec_rest`**: Balboa Park (park-wide calendar), cafirst.org (FIRST
  California), sdcoastkeeper.org, ymcasd.org, comic-con.org/museum,
  sandiegoarchaeology.org, shpesd.org, navalstem.us, thegarden.org
  (Water Conservation Garden's real site), jasandiego.org (Junior
  Achievement).
- **`ical`**: SD County Parks (Tockify, 553 events), SD Astronomy
  Association (Google Calendar), Mission Trails Regional Park
  Foundation, Surfrider SD, SWE San Diego, California DI, Oceanside
  Public Library, Coronado Public Library, Cabrillo National Monument
  Foundation.
- **`localist`**: additional UCSD group_ids beyond Birch (Physics
  outreach, Extended Studies, Jacobs School, SDSC, Qualcomm Institute),
  plus `type=Volunteer`.
- **Stretch, verify-first**: LibCal (Carlsbad, Escondido) and the NPS
  events API (Cabrillo) — register only if the plain `ical` adapter
  consumes their feeds unchanged; otherwise leave unregistered and note
  as deferred. Do not write a new adapter this sprint.

`org_name` matches `partners.json` where the org is already a partner
(checked against the local `site/src/data/partners.json` copy);
otherwise the org displays with its scraped name and no logo/partner
link (existing, tested `normalize/partners.py` behavior) and is noted
as a candidate for issue 32 (partner-roster expansion), which owns
writing the actual roster — this ticket never touches `partners.json`.

Balboa Park's calendar overlaps organizations already scraped
individually (Fleet, Nat, etc.); no new dedup mechanism is built —
existing cross-source dedup (`normalize/dedup.py`) applies as-is, with
its known title-mismatch limitation accepted (see `design/
normalize-DESIGN.md`).

Depends on ticket 002 (verify against the reactivated ops pipeline) and
ticket 003 (avoid any overlap with triage's own source corrections,
e.g. `sd-river-park-foundation`, which this ticket does not touch).

## Acceptance Criteria

- [x] Each new TOML's endpoint is live-verified (reachable, returns
      non-zero records) before it is committed.
- [x] Each new source uses `adapter_type` `tec_rest`, `ical`, or
      `localist` per the list above — no new adapter code is written.
- [x] `org_name` matches `partners.json`'s `name` field for every org
      already in the roster (checked against `site/src/data/
      partners.json`); orgs without a match are listed in this ticket's
      notes for issue 32, not silently dropped or force-matched.
- [x] `thegarden.org`'s registration in this ticket is understood as a
      new *source* TOML only — the corresponding partner-roster URL
      fix (same organization, issue 32's housekeeping list) is
      explicitly out of this ticket's scope.
- [x] `partner-scrape --dry-run --source <id>` run once per new source
      confirms non-zero, dated output before commit.
- [ ] A live/staged export after registering Balboa Park shows at least
      one collapsed cross-source match against an existing Fleet/Nat
      source's own listing for the same event (demonstrating existing
      dedup applies) — and confirms no code change was needed in
      `normalize/collapse.py` or `normalize/dedup.py`. **Measured, not
      met as literally worded** — see Notes. The "no code change
      needed" half is true (confirmed); zero actual collapses were
      observed in the live measurement, and the root cause is now
      precisely identified (not the anticipated title-mismatch case).
- [x] LibCal (Carlsbad, Escondido) and the NPS events API (Cabrillo)
      are registered only if the existing `ical` adapter consumes their
      feeds unchanged (verified by a real dry-run); otherwise explicitly
      noted as deferred, not force-registered against a mismatched
      adapter. Escondido registered; Carlsbad and NPS deferred — see
      Notes.
- [x] No new source registered by this ticket duplicates a source
      ticket 003 already corrected or disabled.
- [x] Full test suite stays green (1454 passed).

## Notes (ticket 004 completion, 2026-08-30)

**Registered (15 of the ~20 candidates; 13 others live-investigated and
deferred with reasons — see below):**

`tec_rest` (8): `balboa-park`, `sdcoastkeeper`, `ymcasd`,
`comic-con-museum`, `sandiegoarchaeology`, `shpesd`, `thegarden`
(partners.json match), `jasandiego` (partners.json match).

`ical` (3): `oceanside-library`, `coronado-library`, `escondido-library`
(the LibCal stretch item — Escondido's `ical_subscribe.php?cid=16268`
is a clean single static feed URL the plain adapter consumes unchanged,
159 VEVENTs).

`localist` (4): `ucsd-physics`, `ucsd-extended-studies-localist`
(partners.json match — see note below), `ucsd-jacobs-school`,
`ucsd-qualcomm-institute`.

**`ucsd-extended-studies-localist.toml` is a second, additional feed
for an org already registered** (`extendedstudies-ucsd.toml`, a
`generic_html` scrape of the org's own site). Deliberately a distinct
`source_id` (registry/DESIGN.md: `source_id` is the cross-subsystem join
key) — not a duplicate registration; any real overlap between the two
feeds is handled by ordinary cross-source dedup.

**Deferred (live-investigated, not registered):**

- `cafirst.org` (FIRST California, `tec_rest` candidate) — live-checked
  2026-08-30: `wp-json` namespace list has no `tribe/events/v1`; The
  Events Calendar's REST API is not exposed on this site today, contra
  the issue's citation. No adapter fits without site-side changes on
  their end.
- `navalstem.us` (`tec_rest` candidate) — TEC REST endpoint is
  structurally valid and live, but returns `total=0` for the current
  upcoming-events window (all discovered events are already in the
  past relative to 2026-08-30). Not force-registered against a
  currently-empty feed.
- SD County Parks (Tockify), SD Astronomy Association, Mission Trails
  Regional Park Foundation, Surfrider SD, **SWE San Diego** (all `ical`
  Google-Calendar/Tockify candidates) — **every one of these feeds is
  live, well-formed, and high-yield** (verified counts matching or
  close to the issue's own: 554, 677, 164, 2313 VEVENTs respectively),
  but tockify.com and calendar.google.com's `robots.txt` disallow the
  fetch path for `STEM-Calendar-Bot/1.0`. Setting
  `acquisition_policy.respect_robots = false` does **not** help: it is
  dead configuration today — no adapter (`tec.py`, `ical.py`,
  `localist.py`, including `leaguesync.py`, which already sets this
  flag) actually reads `source.acquisition_policy` and threads
  `respect_robots`/`rate_limit_seconds` into `PoliteFetcher.get()`'s
  per-call parameters; every adapter calls `fetcher.get(ref.url)` with
  no override, so `PoliteFetcher`'s hardcoded default (`respect_robots=
  True`) always applies regardless of the TOML. `leaguesync.toml`'s
  existing `respect_robots = false` happens to be harmless only because
  that domain's `robots.txt` 404s live (treated as allow-all
  regardless of the flag) — it was never actually exercised. **This is
  a real, previously-undiscovered gap, out of this ticket's "no new
  adapter code" scope to fix** (the fix would touch `adapters/base.py`
  and/or each adapter's `fetch()`, plus `pipeline.py`'s fetcher
  construction). Flagging for a follow-up ticket/issue — wiring this up
  would unlock all five of these feeds, including SWE San Diego, which
  already has a `partners.json` match and no other event source today.
- California DI (caldi.org) and Cabrillo National Monument Foundation
  (cnmf.org) — both Squarespace; confirmed live that `?format=ical`
  only works per-event (`/events/<slug>?format=ical`), not for the
  calendar collection as a whole. The plain `ical` adapter's
  `discover()` needs exactly one `feed_url`; no single URL exposes the
  full calendar. Matches the issue's own framing for California DI
  ("per-event ICS links"); confirmed the same is true for Cabrillo.
- San Diego Supercomputer Center (SDSC, `localist` group_id
  `50161993952146`) — confirmed live, zero events in the query window
  (180 and 365 days both checked).
- `type=Volunteer` (UCSD Localist sitewide filter) — the existing
  `localist.py` adapter's `_page_url()` hardcodes `group_id` as the
  only filter dimension; there is no config-level way to add a `type`
  filter without an adapter code change, out of scope.
- LibCal Carlsbad (carlsbadca.libcal.com) — confirmed live that,
  unlike Escondido, there is no single site-wide `cid`/`iid` that
  `ical_subscribe.php` accepts for "all events" — the front-end
  aggregates many small per-category `cal_id`s (Cole Library, Dove
  Library, Teen Book Warriors, ...) with no single feed capturing all
  of them. Does not fit the plain adapter's one-`feed_url` contract.
- NPS events API (Cabrillo) — categorically incompatible with the
  `ical` adapter: it is a JSON REST API (confirmed `content-type:
  application/json`, `403` without an API key), not an `.ics` feed;
  `icalendar.Calendar.from_ical()` cannot parse it. Needs its own
  adapter, explicitly out of this ticket's scope.

**issue 32 roster candidates (no `partners.json` match, live-verified
org names):** Balboa Park, San Diego Coastkeeper, YMCA of San Diego
County, Comic-Con Museum, San Diego Archaeological Center, SHPE San
Diego, Oceanside Public Library, Coronado Public Library, Escondido
Public Library, UC San Diego Department of Physics, UC San Diego
Jacobs School of Engineering (distinct from partners.json's "Jacobs
Institute for Innovation in Education, University of San Diego" — a
University of San Diego program, not UC San Diego — not force-matched),
Qualcomm Institute (distinct from partners.json's "Qualcomm
Incorporated" — the company, not the UCSD research institute — not
force-matched). Also worth issue 32's attention if the robots.txt/dead-
config gap above gets fixed: San Diego County Parks and Recreation, San
Diego Astronomy Association, Mission Trails Regional Park Foundation,
Surfrider Foundation San Diego County Chapter.

**Balboa Park dedup measurement (SUC-008).** Ran `balboa-park` live
alongside every individually-registered Balboa Park institution
(`fleet-science-center`, `sdnhm`, `comic-con-museum`,
`japanese-friendship-garden`, `sandiego-air-space`, `sdautomuseum`,
`sdmrm`) through the real adapters and `normalize.run()` directly
(script, not committed). Result: **0 cross-source collapses** in this
run (145 Opportunities, all single-source). Root cause identified
precisely, and it is *not* the anticipated title-mismatch case: Balboa
Park's calendar does carry genuine title+date matches against Fleet's
own listing (`"Educator Open House"`, both sides dated 2026-09-24) —
but `fleet-science-center.toml`'s `listing_html` adapter never
populates `Event.location` (empty string on every one of its 10 raw
events), while Balboa Park's TEC record sets `venue.venue = "Fleet
Science Center"`. `dedup.cross_source_identity()`'s third component
(`normalize_title(event.location)`) therefore differs (`""` vs `"fleet
science center"`), blocking the merge even on an exact title+date hit.
Confirmed **no code change was needed or made** to
`normalize/collapse.py` or `normalize/dedup.py` — this is existing,
correctly-functioning dedup logic behaving exactly as documented
(`normalize-DESIGN.md`'s Open Questions: two orgs describing the same
event with a materially different *venue* will not merge); the register-
and-measure decision in `sprint.md`'s Design Rationale is upheld, the
predicted mechanism just wasn't the exact one observed. Recorded here
per the AC's own "record the result either way" framing — not silently
omitted.

**Status left `in-progress`, not moved to `done`**, per this ticket's
dispatch instructions — the Balboa Park AC is only partially met as
literally worded (see above) and the robots.txt/dead-config finding
affects an existing partner (SWE San Diego); both warrant team-lead
review before closing.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`); registry
  loader tests to confirm every new TOML parses correctly.
- **New tests to write**: like ticket 003, no new hermetic tests are
  expected purely from adding data-only TOML files — `registry/`'s
  existing loader tests already cover generic `tec_rest`/`ical`/
  `localist` parsing. If a genuinely new parsing edge case appears
  (e.g. an iCal feed shape the adapter hasn't seen before), add a
  fixture-based regression test for it.
- **Verification command**: `uv run pytest`, plus the required
  live-verification dry-runs listed in Acceptance Criteria (not
  pytest).

## Implementation Plan

**Approach**: Per-feed TOML authoring against already-verified
endpoints (the issue itself cites each one), one dry-run per source
before commit, no new adapter code.

**Files to modify**:
- `partner_scrape/registry/sources/*.toml` — ~20 new files, one per
  feed listed in Description (fewer if LibCal/NPS are deferred).

**Testing plan**: see Testing above.

**Documentation updates**: This ticket implements `design/
normalize-DESIGN.md`'s sprint 014 Open Questions entries (Balboa Park
dedup, no-partner-match display), already written during planning —
verify the live export actually behaves as documented rather than
re-authoring the design. If a new org's registration reveals a
genuinely new normalize/export interaction not already covered, flag
it rather than silently expanding scope.

**Non-goals reminder**: do not add entries to `site/data/
partners_viable.csv` or `site/src/data/partners.json` — that is issue
32's job. Do not write a new adapter for LibCal/NPS if the plain
`ical` adapter doesn't already fit — defer instead.
