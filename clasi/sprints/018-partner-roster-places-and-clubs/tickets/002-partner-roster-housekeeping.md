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

- [ ] `batiquitosfoundation.org` does not appear anywhere in
      `partners.json` or `partners_viable.csv`.
- [ ] Every other partner URL has been live-checked for the same
      hijack pattern; any additional hits found are fixed and listed
      in this ticket's Notes.
- [ ] `mep.sdsu.edu` no longer appears; `mesa.sdsu.edu` does, on the
      same (SDSU MESA) entry.
- [ ] The Water Conservation Garden entry's URL is `thegarden.org`.
- [ ] Each of the 10 named duplicate orgs has exactly one row in
      `partners.json` and exactly one row in `partners_viable.csv`,
      with matching `id`s across both files, and the surviving row's
      `name` is verified to still match what `normalize/partners.py`'s
      join expects (spot-checked against at least one already
      registered source for orgs that have one).
- [ ] None of the 7 known bare-California-centroid entries still
      carries `36.778261, -119.417932`.
- [ ] Every entry in both files either falls inside `SD_BOUNDS` or has
      no `latitude`/`longitude` at all.
- [ ] `partners.json` and `partners_viable.csv` have the same row
      count and the same set of `id` values after this ticket (1:1
      sync preserved).
- [ ] Defunct/paused orgs are recorded as a negative-signal note (this
      ticket's Notes and/or a roster-file comment), not registered.
- [ ] Full test suite stays green.

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
