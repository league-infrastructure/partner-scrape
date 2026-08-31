---
id: '002'
title: Partner roster housekeeping
status: in-progress
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: 32-partner-roster-expansion-and-housekeeping.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Partner roster housekeeping

## Description

Fix the known defects in the existing 153-row partner roster before
tickets 003/004 add ~65 more rows on top of it. Edit both
`site/src/data/partners.json` (this repo's beta checkout, the working
roster for this sprint per sprint.md's Design Rationale) and
`data/partners_viable.csv` in parallel — they must stay in 1:1 sync by
`id` (verified 153/153 matching before this ticket starts).

**Hijacked/dead URLs:**
- `batiquitosfoundation.org` is hijacked (spam) — remove/replace with
  the real site, `batiquitoslagoon.org`, on the Batiquitos Lagoon
  Foundation entry (also being newly added by ticket 003 — coordinate
  so the housekeeping fix and the new registration don't create a
  duplicate). Audit every other partner URL for the same hijack
  pattern (a domain resolving but serving unrelated/spam content, not
  a 404) — this is a live-check, not a static grep.
- `mep.sdsu.edu` → `mesa.sdsu.edu` (mep.sdsu.edu 301s today).
- Water Conservation Garden's URL → `thegarden.org` (working TEC REST
  endpoint per sprint 014 ticket 004's own registration of this org's
  event feed under the same corrected URL).

**Duplicate CSV rows** (also present in the JSON, confirmed 153/153
row-for-row match with the CSV before this ticket): Living Coast ×2,
EIS ×2, GSDSEF ×2, SDRPF ×2, Fleet ×2, Viasat ×2, Media Arts ×2, Ocean
Connectors ×2, SD Futures ×2, Salk ×2. Dedupe to one row per org in
both files. `normalize/partners.py`'s `find_partner()` joins by
normalized *name* (`normalize_org_name()`), not by numeric `id` —
confirmed by reading `load_partners()`/`find_partner()` during
planning — so removing a duplicate `id` row is safe as long as the
surviving row's name is preserved exactly; verify this explicitly
rather than assuming it.

**Bad coordinates:**
- 7 entries carry exactly `36.778261, -119.417932` — Google's geocoder
  centroid for the bare string `"California"` (known good San Diego
  orgs, including Olivewood Gardens, San Diego Automotive Museum,
  Media Arts Center San Diego, and iFLY San Diego, per sprint 011's
  own finding). Replace each with a real, curated coordinate for the
  organization's actual address, or blank `latitude`/`longitude`
  entirely if no confident address is available — never leave the
  bare-California centroid in place.
- ~15 entries fall outside the site's map bounding box
  (`site/src/pages/partners/index.astro`'s `SD_BOUNDS`: `latMin: 32.4,
  latMax: 33.5, lngMin: -117.7, lngMax: -116.0`) and are silently
  dropped by that page's own `return` guard. For each, either correct
  the coordinate to the org's real San Diego-area location, or blank
  it — a genuinely out-of-region org (if any) should have no
  coordinate at all rather than a coordinate the map silently discards
  with no indication anything is missing.
- `partners.json` does not currently have a `location_precision` field
  (confirmed absent from every existing entry during planning) and
  this ticket does not add one — that's an explicit Open Question in
  sprint.md, out of this sprint's scope. Note precision plainly in the
  `description` field's prose instead, where a coordinate is
  necessarily approximate.

**Negative signals (documented, not registered):**
- Defunct, do not register: EarthFair, Maker Faire San Diego, Fab Lab
  SD, SD Makers Guild, SD Science Alliance, KidzToPros.
- Paused/canceled, do not register blind: Academic Connections
  (canceled 2026), JCVI La Jolla internships (paused 2026).
- Record these as a short dated note in this ticket's own Notes section
  and/or a comment in the roster file itself, so a future sprint
  doesn't need to re-discover and re-verify these are dead.

## Acceptance Criteria

- [x] `batiquitosfoundation.org` does not appear anywhere in
      `partners.json` or `partners_viable.csv`.
- [x] Every other partner URL has been live-checked for the same
      hijack pattern; any additional hits found are fixed and listed
      in this ticket's Notes.
- [x] `mep.sdsu.edu` no longer appears; `mesa.sdsu.edu` does, on the
      same (SDSU MESA) entry.
- [x] The Water Conservation Garden entry's URL is `thegarden.org`.
- [x] Each of the 10 named duplicate orgs has exactly one row in
      `partners.json` and exactly one row in `partners_viable.csv`,
      with matching `id`s across both files, and the surviving row's
      `name` is verified to still match what `normalize/partners.py`'s
      join expects (spot-checked against at least one already
      registered source for orgs that have one).
- [x] None of the 7 known bare-California-centroid entries still
      carries `36.778261, -119.417932`.
- [x] Every entry in both files either falls inside `SD_BOUNDS` or has
      no `latitude`/`longitude` at all.
- [x] `partners.json` and `partners_viable.csv` have the same row
      count and the same set of `id` values after this ticket (1:1
      sync preserved).
- [x] Defunct/paused orgs are recorded as a negative-signal note (this
      ticket's Notes and/or a roster-file comment), not registered.
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: `uv run pytest` — this is a data-only
  change, but run the full suite to confirm nothing (e.g. a fixture
  that happened to reference a duplicate row or a bad coordinate)
  silently depended on the broken state.
- **New tests to write**: none expected purely from data edits, unless
  this ticket's URL/hijack audit or dedup pass reveals a genuinely new
  edge case worth a fixture regression test (matching sprint 014/016's
  own precedent for data-only tickets).
- **Verification command**: `uv run pytest`, plus a manual/scripted
  check (e.g. a small one-off Python snippet, not committed) confirming
  `partners.json`/`partners_viable.csv` id-set equality and that no
  entry carries the bad centroid or falls outside `SD_BOUNDS`.

## Notes

**2026-08-31, implementation.**

Roster went from 153 -> 142 rows in both `partners.json` and
`partners_viable.csv` (11 duplicate rows removed: the 10 named in this
ticket's Description, plus one more found during the audit — see
below).

**Live hijack-domain audit** (all 153 pre-existing `website` URLs
fetched directly, `--max-time 15`, browser UA):
- `batiquitosfoundation.org` was already absent from both files before
  this ticket started (nothing to remove) — ticket 003 is clear to
  register Batiquitos Lagoon Foundation under `batiquitoslagoon.org`
  without a pre-existing conflicting row.
- No other partner URL showed the hijack pattern (resolves, but serves
  unrelated/spam content). 5 URLs matched a naive spam-keyword grep
  ("cialis", "generic-") but all 5 were false positives on substrings
  inside legitimate words/CSS ("specialist", "generic-black" as a CSS
  custom property, etc.) — verified by re-fetching and reading the
  surrounding text: AWIS SD (awissd.org), BSD Education, MetaCoders,
  San Diego County Library (sdcl.org), San Diego LabRats.
- 16 URLs returned non-200 on this pass. Individually checked (WebFetch
  content review for the ambiguous ones, `host`/DNS lookup for the
  unresolvable ones) — none show hijack takeover:
  - 6 returned HTTP 403 (EcoVivarium, Fit Kids America, I Love A Clean
    San Diego, North American Marine Environment Protection
    Association, San Diego County Office of Education, Thrive Public
    Schools) — bot/WAF blocking of the scripted request, not a site
    problem; WebFetch confirmed EcoVivarium, Fit Kids America, and
    NAMEPA are legitimate live org sites. I Love A Clean San Diego
    (`ilacsd.org`) 301-redirects to its rebranded domain
    `cleansd.org` — a legitimate redirect, not a hijack; left
    unchanged since it still resolves correctly and updating it is
    out of this ticket's specific hijack-pattern scope.
  - 4 returned DNS `NXDOMAIN` (confirmed via `host`): Design Code
    Build, RoboThink Chula Vista, The Academy of Edible Sciences &
    Ethno-gastronomy, Triton Robosub (`robosub.ucsd.edu`). These are
    dead, unregistered domains — not currently hijacked (hijacking
    requires the domain to resolve to spam content), but each is a
    *future* hijack risk since anyone could register the lapsed name.
    Flagging for a future ticket to review/replace rather than fixing
    here (out of this ticket's scope, which is the live-hijack
    pattern specifically).
  - 2 had TLS failures on the pre-fix domains (`rhfleet.org`,
    `mssmartyplants.org`) — both resolved by this ticket's own dedup/
    URL-fix work (Fleet Science Center's duplicate `rhfleet.org` row
    removed in favor of the `fleetscience.org` row; Water Conservation
    Garden's URL corrected to `thegarden.org`).
  - 2 returned 404 on a deep link, not the domain root: Media Arts
    Center San Diego's duplicate `/youth-media-education/` row
    (removed by dedup, in favor of the row using the working root
    domain) and San Diego-Imperial Counties Community Colleges'
    `cact.org/centers_san_diego.php` (stale deep link, domain itself
    live; not this ticket's scope to fix, no hijack pattern present).
  - 1 returned Cloudflare 526 (invalid origin certificate): Center for
    Ethics in Science and Technology (`ethicscenter.net`) — origin TLS
    misconfiguration, not a hijack signature (a hijacker holding an
    expired domain would show a *working* parking page, not a broken
    cert on what's still the original origin).

**Duplicate dedup decisions** (all 11; each verified via
`normalize/partners.py`'s actual `load_partners()`/`find_partner()`
against the surviving row post-edit — see
`tests/test_roster_housekeeping.py::TestRegistryJoinIntegrity`):

| Org | Kept id | Removed id | Why kept |
|---|---|---|---|
| Living Coast Discovery Center | 46 | 262 | referenced by `site/src/data/opportunities.json` `partner_id`; renamed to the registry's literal `org_name` ("The Living Coast Discovery Center") for clarity — normalizes identically either way |
| Elementary Institute of Science | 165 | 260 | fuller description, real street address, in-bbox coords (near-identical to 260's) |
| Greater San Diego Science and Engineering Fair | 231 | 368 | real street address (368 only has a P.O. box); in-bbox coords |
| The San Diego River Park Foundation | 323 | 345 | referenced by `opportunities.json` `partner_id` |
| Fleet Science Center | 121 | 293 | website matches the registry's `fleet-science-center.toml` `site_url` (`fleetscience.org`); 293's `rhfleet.org` currently fails TLS verification |
| Viasat | 166 | 424 | rows were fully duplicate (same address/coords/website); kept lower id |
| Media Arts Center San Diego | 277 | 558 | 558 carried the bare-California centroid and a 404ing deep-link URL; 277 already had real in-bbox coords and the working root domain |
| Ocean Connectors | 174 | 662 | referenced by `opportunities.json` `partner_id`; has real coords, 662 does not |
| San Diego Futures Foundation | 176 | 607 | has real in-bbox coords, 607 does not |
| Salk Institute Education Outreach | 23 | 636 | matches the registry's `salk.toml` `org_name` literal; has real in-bbox coords (La Jolla), 636 does not |
| San Diego Automotive Museum (found during audit, not in the ticket's named 10) | 551 | 615 | referenced by `opportunities.json` `partner_id`; 615's full street address (`2080 Pan American Plaza, San Diego, CA 92101`) was used to fix 551's bare-California centroid (see below) |

San Diego Automotive Museum was not in the ticket's named
duplicate list but was found during the audit (same normalized name,
two rows) — the same join-ambiguity failure mode, so deduped under the
same rule.

**Bare-California-centroid (7 entries) resolution:**
- Media Arts Center San Diego (558), San Diego Automotive Museum (551)
  — resolved by the dedup above (see table).
- Olivewood Gardens (164) — curated coordinate given: 32.671, -117.098,
  address 2525 N Avenue, National City, CA 91950 (hand-known, not
  live-geocoded; National City neighborhood-level confidence, noted as
  approximate in the description per the ticket's own guidance).
- Association for Women in Science San Diego Outreach (245), National
  Girls Collaborative (126), Zero Robotics (26), iFLY San Diego (214)
  — coordinates blanked, not guessed. AWIS SD and National Girls
  Collaborative are chapter/network organizations with no single
  physical office known; Zero Robotics is an MIT-run program with no
  San Diego location; iFLY San Diego's precise address could not be
  confirmed (WebFetch checked `iflyworld.com`'s STEM-programs and
  San Diego location pages — neither lists a street address) so, per
  the ticket's own "a wrong pin is worse than none" rule, left blank
  rather than guessed.

**Out-of-bbox (~15) resolution:** 7 of the 15 were the bare-California
entries above. The other 8 are real national/regional orgs with real
addresses genuinely outside SD County — coordinates blanked (not
"corrected", since correcting to an SD-area location would be
fabricated): American Society of Naval Engineers (VA), Citizen Schools
(MA), EDforTech (OR), EnCorps Inc (Hermosa Beach, CA), Girls Who Code
(NY), Integrative Biosciences Program at Coastal Marine Biolabs
(Ventura, CA), Intelitek (Roseville/Sacramento, CA), National Inventors
Hall of Fame (OH).

**Negative signals (documented, not registered)** — carried forward
from issue 32's own list, re-confirmed absent from the roster during
this ticket's audit:
- Defunct, do not register: EarthFair, Maker Faire San Diego, Fab Lab
  SD, SD Makers Guild, SD Science Alliance, KidzToPros.
- Paused/canceled, do not register blind: Academic Connections
  (canceled 2026), JCVI La Jolla internships (paused 2026).

**Deviation from the plan**: the ticket's Testing section said "none
expected" for new tests, but the sprint-level task briefing required a
script-level regression check, so `tests/test_roster_housekeeping.py`
(13 tests) was added — it runs against the real
`site/src/data/partners.json`/`data/partners_viable.csv` (not a
fixture, since its whole purpose is guarding the real roster against
regressing on this ticket's fixes) and checks: no bare-California
centroid, no out-of-bbox coordinate, no hijacked domain, JSON/CSV
row-count and id-set parity, no duplicate names, and that every one of
the 11 deduped orgs' registry `org_name` still resolves to its intended
surviving `id` via the actual `find_partner()`/`load_partners()`.

## Implementation Plan

**Approach**: Direct data edits to both roster files, verified by
scripted checks rather than assertion. Do this ticket before 003/004
so new registrations land on a clean, deduped roster.

**Files to modify**:
- `site/src/data/partners.json`
- `data/partners_viable.csv`

**Testing plan**: see Testing above.

**Documentation updates**: none expected — this is a data fix with no
architectural or process change beyond what sprint.md's Architecture
section already documents.
