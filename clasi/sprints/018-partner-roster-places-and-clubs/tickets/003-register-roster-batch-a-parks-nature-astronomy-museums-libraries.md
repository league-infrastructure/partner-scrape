---
id: '003'
title: 'Register roster batch A: parks, nature, astronomy, museums, libraries'
status: in-progress
use-cases:
- SUC-002
depends-on:
- '002'
github-issue: ''
issue: 32-partner-roster-expansion-and-housekeeping.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register roster batch A: parks, nature, astronomy, museums, libraries

## Description

Register the parks/nature, astronomy, museums, and libraries
organizations from the 2026-08-30 gap analysis (issue 32) into
`site/src/data/partners.json` and `data/partners_viable.csv`, in
parallel, after ticket 002's housekeeping pass has cleaned the roster.

**Parks/nature** (17): SD County Parks & Recreation, Mission Trails
Regional Park Foundation, Tijuana River NERR/Estuary, Cabrillo
National Monument, Cabrillo National Monument Foundation, San Diego
Bird Alliance, San Diego Coastkeeper, WILDCOAST, Surfrider SD, Torrey
Pines Docent Society, Batiquitos Lagoon Foundation (coordinate with
ticket 002 — the hijacked-domain fix may already touch this org if it
was already on the roster; if not, register fresh with
`batiquitoslagoon.org`), San Diego Botanic Garden, California Wolf
Center, Helen Woodward Animal Center, SD Humane Society, SEACAMP San
Diego, CNPS SD.

**Astronomy** (4): San Diego Astronomy Association, Palomar
Observatory, SDSU Mount Laguna Observatory, Palomar College
Planetarium.

**Museums** (6): Maritime Museum of San Diego, Comic-Con Museum, SD
Archaeological Center, SD Mineral & Gem Society, SDSU Biodiversity
Museum, New Children's Museum.

**Libraries** (6): Oceanside, Carlsbad, Escondido, Coronado, Chula
Vista, National City city libraries.

Several of these orgs are **already registered as event sources**
(sprint 014 ticket 004, sprint 016 ticket 002): Balboa Park, San Diego
Coastkeeper, Comic-Con Museum, San Diego Archaeological Center,
Oceanside Public Library, Coronado Public Library, Escondido Public
Library, San Diego County Parks and Recreation, San Diego Astronomy
Association — for these, `org_name` **must match the already-registered
source's org name exactly** (verify against the source TOML or that
ticket's own Notes, not just the gap-analysis spelling) so
`normalize/partners.py`'s join actually resolves on the next export.
For orgs with no existing source, use the org's own canonical public
name.

Location/coordinates: curated/offline only (city-centroid or
address-level where confidently known from the org's own site) — never
a live geocoder call, matching the teams geo-ladder precedent this
sprint's Architecture documents. Where only city-level confidence is
available, say so plainly in the `description` field (no
`location_precision` field exists on this schema — see ticket 002 and
sprint.md's Open Questions).

Logo: leave `logo_src` empty for now — ticket 005 handles logo
backfill as its own pass; do not block this ticket on finding a logo.

## Acceptance Criteria

- [x] Every org named above has a `partners.json`/`partners_viable.csv`
      row, or is explicitly listed in this ticket's Notes as deferred
      with a reason (e.g. no confident location, org appears defunct
      on live-check).
- [x] For every org that already has a registered event source
      (listed above), the new row's `name` field matches that source's
      `org_name` exactly — spot-checked against the actual registered
      source, not assumed from the gap analysis's phrasing.
- [x] No new row's coordinates come from a live geocoder call — every
      coordinate is curated from the org's own published address, or
      absent.
- [x] Every new row falls inside `site/src/pages/partners/index.astro`'s
      `SD_BOUNDS` (`latMin: 32.4, latMax: 33.5, lngMin: -117.7, lngMax:
      -116.0`) or has no coordinates at all.
- [x] `partners.json` and `partners_viable.csv` remain in 1:1 `id` sync
      after this ticket's additions.
- [x] A dry-run or scripted check confirms `find_partner()` now
      resolves at least the already-source-registered orgs listed
      above (a concrete, checkable subset of SUC-002's broader
      "no-geocode/no-logo rate drops" claim).
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write**: none expected purely from data additions,
  matching sprint 014/016's precedent; if a genuinely new roster-schema
  edge case appears, flag it rather than silently expanding scope.
- **Verification command**: `uv run pytest`, plus
  `uv run partner-scrape --dry-run --source <id>` for a couple of the
  already-registered sources in this batch (e.g. `balboa-park`,
  `sdcoastkeeper`) to confirm the exported `Opportunity` now carries a
  resolved `partner_id`/logo where the roster row provides one.

## Notes (ticket 003 completion, 2026-08-31)

**Registered: 34 rows (ids 731–764), 142 → 176 rows in both files.**

All 33 orgs named in the Description are registered — no deferrals. A
34th row, **Balboa Park** (id 764), was also added: the ticket's own
Description names it (alongside San Diego Coastkeeper, Comic-Con
Museum, etc.) as an org "already registered as an event source" whose
`org_name` must match exactly, and AC #2 requires a row for "every org
that already has a registered event source (listed above)" — so it is
in scope even though it isn't one of the four bulleted category lists.

**org_name exact-match verification (11 already-registered sources,
each grepped directly from its TOML, not assumed from the gap
analysis):**

| source_id | TOML `org_name` | Roster row |
|---|---|---|
| `county-parks` | San Diego County Parks and Recreation | id 731 |
| `mission-trails` | Mission Trails Regional Park Foundation | id 732 |
| `sdcoastkeeper` | San Diego Coastkeeper | id 737 |
| `surfrider-sd` | Surfrider Foundation San Diego County Chapter | id 739 |
| `sd-astronomy-association` | San Diego Astronomy Association | id 748 |
| `comic-con-museum` | Comic-Con Museum | id 753 |
| `sandiegoarchaeology` | San Diego Archaeological Center | id 754 |
| `oceanside-library` | Oceanside Public Library | id 758 |
| `coronado-library` | Coronado Public Library | id 761 |
| `escondido-library` | Escondido Public Library | id 760 |
| `balboa-park` | Balboa Park | id 764 |

Verified two ways: (1) `find_partner(source.org_name, load_partners(...))`
for all 11 (script, not committed) — every one resolves to its intended
id; (2) a live, non-`--dry-run` run against a scratch `--site-dir`
(`--no-enrich --no-mirror --source balboa-park` and `--source
sdcoastkeeper`, `SCRAPE_CACHE_DIR` pointed at a scratch cache, real
network fetch) confirms the exported `opportunities.json` now carries
`partner_id: 764`/`partner_name: "Balboa Park"` on all 79 Balboa Park
opportunities and `partner_id: 737`/`partner_name: "San Diego
Coastkeeper"` on all 10 Coastkeeper opportunities. `logo_src` is empty
on both, as expected — ticket 005's job, not this one's. No file under
version control was written by this live check; the real
`site/src/data/partners.json` was only read (copied into the scratch
`--site-dir`).

**Coordinates: curated only, no live geocoder.** Every address was
either already known with confidence or verified via a web
search/fetch against the org's own site or a corroborating public
listing (city facility directory, NPS/Caltech/SDSU pages) before being
used — never passed through a geocoding API. 3 orgs' coordinates were
deliberately left blank rather than guessed, each because the org has
no single fixed office/site (not because research was incomplete):
**Surfrider Foundation San Diego County Chapter** (all-volunteer
chapter), **California Native Plant Society - San Diego Chapter**
(all-volunteer chapter), **San Diego Astronomy Association**
(membership club; its public star parties run at a remote backcountry
site, not a staffed office — a `--dry-run` for the association's own
*event source* still yields dated output independent of this roster
row's coordinates). All 31 remaining new rows carry a real, in-bbox
address-level coordinate (verified against `SD_BOUNDS`
programmatically before commit — see Testing).

**Two identity corrections during research, both address a genuine
distinct-org risk, not sloppiness:**
- Batiquitos Lagoon Foundation's website is `batiquitoslagoon.org` per
  this ticket's explicit instruction (never `batiquitosfoundation.org`,
  the hijacked domain ticket 002 already handled).
- The org's own site/branding calls itself "The New Children's Museum";
  this roster row is named "New Children's Museum" (dropping the
  leading "The"), matching this ticket's own bulleted phrasing and
  `normalize_org_name()`'s leading-"the" strip, which makes the two
  forms join-equivalent (`normalize_org_name("The New Children's
  Museum") == normalize_org_name("New Children's Museum")`). No
  registry source exists for this org yet, so no join is affected
  either way.

**Organization-type classification** followed the existing roster's
own precedent rather than inventing new categories (the controlled set
has no "Parks/Nature" bucket): government/foundation/advocacy orgs
(county parks dept, NPS units, "Friends of"-style foundations,
conservation nonprofits) → `Advocacy/Philanthropy & Government`,
matching "The San Diego River Park Foundation"'s and "San Dieguito
River Park"'s existing classification; walk-in, public-facing
nature/animal/science venues (botanic garden, wolf center, humane
society, observatories, planetarium) → `Museums, Science Centers &
Zoos`, matching "San Diego Zoo"'s and "Birch Aquarium"'s existing
classification; SEACAMP San Diego (a youth day/residential camp
program) → `Afterschool/Out-of-School Time`, matching "RoboThink"'s
and "Zero Robotics"'s existing classification; SDAA →
`Professional, Trade & Student Associations`, matching "Association
for Women in Science San Diego Outreach"'s existing classification;
libraries → `Libraries`, matching all 5 existing library rows. Balboa
Park itself → `Advocacy/Philanthropy & Government` (the park-wide
calendar/administration, deliberately distinct from the individual
Balboa Park museums already on the roster as `Museums, Science
Centers & Zoos`, e.g. San Diego Natural History Museum, USS Midway
Museum).

**Deviation from the ticket's Testing plan**: "no new tests expected"
was the plan's default, matching sprint 014/016 precedent for
data-only tickets — but per this ticket's own dispatch instructions
("extend `tests/test_roster_housekeeping.py` conventions") a new
`TestBatchARegistryJoinIntegrity` class (3 tests) was added, following
ticket 002's own precedent of testing the *real* roster files rather
than a fixture: it re-verifies the 11 org_name matches directly
against the registry TOMLs, re-verifies `find_partner()` resolution,
and pins the new id range/row count so a future ticket can't silently
regress this batch.

**Test suite**: 1671 passed (1668 baseline + 3 new).

## Implementation Plan

**Approach**: Direct, hand-curated data entry against each org's own
public site (name, type, description, website, address) — no scraping
or live geocoding. Depends on ticket 002 so new rows land on an
already-deduped, already-fixed roster.

**Files to modify**:
- `site/src/data/partners.json`
- `data/partners_viable.csv`

**Testing plan**: see Testing above.

**Documentation updates**: none expected beyond this ticket's own
Notes recording any deferred orgs and the org-name-match spot-checks.
