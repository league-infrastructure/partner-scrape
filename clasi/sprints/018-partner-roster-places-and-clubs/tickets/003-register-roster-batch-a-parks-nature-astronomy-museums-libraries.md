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

- [ ] Every org named above has a `partners.json`/`partners_viable.csv`
      row, or is explicitly listed in this ticket's Notes as deferred
      with a reason (e.g. no confident location, org appears defunct
      on live-check).
- [ ] For every org that already has a registered event source
      (listed above), the new row's `name` field matches that source's
      `org_name` exactly — spot-checked against the actual registered
      source, not assumed from the gap analysis's phrasing.
- [ ] No new row's coordinates come from a live geocoder call — every
      coordinate is curated from the org's own published address, or
      absent.
- [ ] Every new row falls inside `site/src/pages/partners/index.astro`'s
      `SD_BOUNDS` (`latMin: 32.4, latMax: 33.5, lngMin: -117.7, lngMax:
      -116.0`) or has no coordinates at all.
- [ ] `partners.json` and `partners_viable.csv` remain in 1:1 `id` sync
      after this ticket's additions.
- [ ] A dry-run or scripted check confirms `find_partner()` now
      resolves at least the already-source-registered orgs listed
      above (a concrete, checkable subset of SUC-002's broader
      "no-geocode/no-logo rate drops" claim).
- [ ] Full test suite stays green.

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
