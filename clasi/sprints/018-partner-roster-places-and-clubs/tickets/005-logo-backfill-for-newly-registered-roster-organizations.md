---
id: '005'
title: Logo backfill for newly-registered roster organizations
status: in-progress
use-cases:
- SUC-002
depends-on:
- '003'
- '004'
github-issue: ''
issue: 32-partner-roster-expansion-and-housekeeping.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Logo backfill for newly-registered roster organizations

## Description

Tickets 003 and 004 registered roughly 65 new roster organizations with
`logo_src` left empty by design. This ticket makes a best-effort pass
to fetch a logo for each of them — a small, dedicated step, separate
from the bulk data-entry work, per this sprint's constraint that "logo
fetching may be its own small ticket step; missing logo is acceptable."

For each newly-added org: check the org's own site for a favicon or an
obvious header/logo image, following whatever convention the existing
roster's `logo_src` values already use (relative paths under
`../../../sites/default/files/...` for the inherited Drupal-era assets
— confirm whether that convention still applies to new entries or
whether new entries should use a different path scheme; this is a
one-time judgment call to make and record, not re-litigate per org).
A logo that requires guessing, low-confidence cropping, or scraping
behind a login is skipped, not forced.

## Acceptance Criteria

- [x] Every org registered by tickets 003/004 has been checked for an
      obtainable logo; each either has a `logo_src` value or is left
      blank with no error.
- [x] No `logo_src` value points at a broken/404 URL — spot-check a
      sample after the pass.
- [x] The path convention used for any new logo assets is recorded in
      this ticket's Notes (even if the answer is "left as an external
      URL, no local asset convention adopted this sprint").
- [x] `partners.json` and `partners_viable.csv` remain in 1:1 sync
      after this ticket's edits (only `logo_src` values change; no row
      additions/removals).
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write**: none expected — this is a data-only,
  best-effort enrichment pass with no new code path.
- **Verification command**: `uv run pytest`, plus a manual spot-check
  of a handful of the newly-set `logo_src` URLs actually resolving.

## Notes (ticket 005 completion, 2026-08-31)

**Path convention decision (AC #3):** every logo this ticket backfilled
uses the *same bare-filename convention `partners.json` already uses*
for its 142 pre-existing non-empty `logo_src` values (a plain filename
under `site/public/images/logos/`, resolved by
`site/src/lib/helpers.ts`'s `getLogoPath()`) — **not** the legacy
Drupal-era relative-path scheme
(`../../../sites/default/files/...`) the pre-existing 142
`partners_viable.csv` rows carry in their own `logo_src` column. That
legacy CSV scheme was never a path this repo's site resolves (only
`partners.json`'s `logo_src` feeds `getLogoPath()`); the CSV column has
always been an archival record of where the Drupal-era image
originated, not a resolvable asset path. Since no such Drupal-era
source exists for these 69 newly-registered orgs, the CSV's `logo_src`
for exactly these rows (ids 731-799) is written as the same bare local
filename `partners.json` uses, keeping the two files' values identical
for every row this ticket touched (verified in
`TestLogoBackfillIntegrity` below). The pre-existing 142 rows in both
files are untouched — their historical convention is out of this
ticket's scope.

**Method:** a one-time script (not committed — this is a one-shot
enrichment pass, not a repeatable pipeline stage, per this ticket's own
Approach) fetched each of the 69 orgs' own homepage over plain
`urllib.request` (stdlib, no new dependency) and extracted candidate
logo URLs in priority order: header `<img>` tagged `logo` in its
class/id/alt/src, `apple-touch-icon`, `og:image`, favicon as last
resort — reusing `partner_scrape/export/images.py`'s existing
`_sniff_dimensions`/`_extension_for` helpers read-only to validate each
candidate is a real, decodable image before accepting it. Concurrency
(8 threads) kept the 69-org pass to a few minutes.

**Deviation from plan — a second, manual visual-review pass was
required.** The automated first pass technically "succeeded" (found *a*
validating image) for several orgs whose actual content was wrong on
inspection: a third-party sponsor/partner badge picked up from the same
page (Charity Navigator for WILDCOAST, "Hunter" for Batiquitos Lagoon
Foundation, Petco Love for SD Humane Society, AT&T/AmerLogic for United
Way, Forever 21 for Boys & Girls Clubs of Greater San Diego), an
unrelated stock/event photo mistaken for `og:image` branding (a tern
photo for SD Bird Alliance, cherry blossoms for Balboa Park, a farm
aerial for 4-H, an awards badge for New Children's Museum), or a
white-on-transparent logo variant that is genuinely invisible against
this site's white card background (SD Botanic Garden, California Wolf
Center, Helen Woodward Animal Center, Boys & Girls Clubs of East
County). Every one of these was caught by downloading and visually
inspecting the actual chosen image (not just trusting "an image was
found") and replaced with a better candidate from the same org's page
where one existed, or left blank where it didn't. This is the reason
the plan's "no new tests... no new code path" held (true — the
discovery script itself was never committed) while still taking
materially more verification effort than a pure scripted pass would
suggest.

**Backfilled: 52 of 69. Left blank: 17 of 69** — an empty slot, not a
wrong logo, per this ticket's Description.

Orgs left blank, with the reason (an honest "checked, nothing usable"
in every case, matching AC #1's "left blank with no error" bar):

- **Site unreachable from this scrape environment** (740 Torrey Pines
  Docent Society, 755 San Diego Mineral & Gem Society, 758 Oceanside
  Public Library, 759 Carlsbad City Library, 762 Chula Vista Public
  Library, 763 National City Public Library, 788 NIWC Pacific,
  793 Barrio Logan College Institute): homepage fetch failed even with
  a relaxed-SSL retry and a browser user-agent fallback.
- **Only wrong-org or sponsor images available** (741 Batiquitos Lagoon
  Foundation — sponsor logo "Hunter", only other candidate a generic
  unbranded 16x16 icon; 766 Boys & Girls Clubs of Greater San Diego —
  every header-logo candidate was a corporate sponsor logo, the real
  SVG logo isn't fetchable by this script's validator, no working
  favicon; 767 Boys & Girls Clubs of San Dieguito — its site mirrors
  the shared `bgcgreatertogether.org` platform and the only extractable
  logo was literally the *Northwest* San Diego chapter's own logo, a
  different, already-registered org — using it would mislabel this
  org).
- **Only a non-logo image available, and cropping the real logo out of
  it would be a low-confidence crop** (754 San Diego Archaeological
  Center — the real logo appears inside a wide photo-collage banner;
  the only other candidate is a 32x32 favicon, too tiny; per this
  ticket's own Description, "a logo that requires... low-confidence
  cropping... is skipped, not forced").
- **Only unrelated stock/event photos or generic badges available**
  (736 San Diego Bird Alliance — bird photo plus a blurry low-quality
  favicon; 757 New Children's Museum — an awards badge and a
  star-rating badge, neither the org's own logo; 796 Nerd Nite San
  Diego — the one favicon candidate found did not validate as a real
  image).
- **Only white-on-white/transparent variant available, unusable on a
  white card, with no other candidate** (765 4-H San Diego (UCCE) — its
  UC ANR parent-org SVG logo is white-fill-only; `og:image` is an
  unrelated stock photo; no working favicon).
- **No logo/icon candidate extracted at all** (760 Escondido Public
  Library — only a favicon link that didn't resolve to a real image).

**Housekeeping alongside the backfill:** one accepted image
(`astronomy_on_tap_san.png`, a legitimate 1032x1681 brand graphic — the
national Astronomy on Tap "pint glass" logo several chapters use) was
2 MB, disproportionate to this roster's ~88 KB median logo size;
downscaled to 368x600 (`sips -Z 600`) to a more proportionate ~360 KB,
matching the existing roster's precedent of small self-hosted images
(no new pipeline/build dependency added — `sips` is a one-off manual
step on this already-manual ticket, not a change to
`partner_scrape/export/images.py`, which deliberately does no pixel
resampling per its own docstring).

**New test**: `tests/test_roster_housekeeping.py`'s
`TestLogoBackfillIntegrity` (3 tests) asserts, for **every** roster row
(not just this ticket's 69), that a non-empty `logo_src` in
`partners.json` points at a file that actually exists under
`site/public/images/logos/`; the same check for the 69 rows'
`partners_viable.csv` `logo_src` values (scoped to ids 731-799, since
the pre-existing 142 rows use the unrelated legacy Drupal-path
convention documented above); and a pinned 52-backfilled/17-blank
count so a future change can't silently regress this pass.

**Test suite**: 1677 passed (1674 baseline + 3 new).

## Implementation Plan

**Approach**: Best-effort, org-by-org manual/scripted logo lookup
against each org's own public site. No new scraping infrastructure —
this is a one-time enrichment pass over a known, small (~65-row) set,
not a repeatable pipeline stage.

**Files to modify**:
- `site/src/data/partners.json`
- `data/partners_viable.csv`

**Testing plan**: see Testing above.

**Documentation updates**: none expected beyond this ticket's own
Notes recording the path-convention decision and any orgs left without
a logo.
