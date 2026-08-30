---
id: '004'
title: Register verified structured feeds
status: in-progress
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

- [ ] Each new TOML's endpoint is live-verified (reachable, returns
      non-zero records) before it is committed.
- [ ] Each new source uses `adapter_type` `tec_rest`, `ical`, or
      `localist` per the list above — no new adapter code is written.
- [ ] `org_name` matches `partners.json`'s `name` field for every org
      already in the roster (checked against `site/src/data/
      partners.json`); orgs without a match are listed in this ticket's
      notes for issue 32, not silently dropped or force-matched.
- [ ] `thegarden.org`'s registration in this ticket is understood as a
      new *source* TOML only — the corresponding partner-roster URL
      fix (same organization, issue 32's housekeeping list) is
      explicitly out of this ticket's scope.
- [ ] `partner-scrape --dry-run --source <id>` run once per new source
      confirms non-zero, dated output before commit.
- [ ] A live/staged export after registering Balboa Park shows at least
      one collapsed cross-source match against an existing Fleet/Nat
      source's own listing for the same event (demonstrating existing
      dedup applies) — and confirms no code change was needed in
      `normalize/collapse.py` or `normalize/dedup.py`.
- [ ] LibCal (Carlsbad, Escondido) and the NPS events API (Cabrillo)
      are registered only if the existing `ical` adapter consumes their
      feeds unchanged (verified by a real dry-run); otherwise explicitly
      noted as deferred, not force-registered against a mismatched
      adapter.
- [ ] No new source registered by this ticket duplicates a source
      ticket 003 already corrected or disabled.
- [ ] Full test suite stays green.

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
