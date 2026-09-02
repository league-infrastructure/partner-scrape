---
id: '004'
title: Register verified nonprofit/institutional camp marketing-page providers
status: done
use-cases:
- SUC-038
- SUC-041
depends-on:
- '003'
github-issue: ''
issue: 29-camp-session-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register verified nonprofit/institutional camp marketing-page providers

## Description

Registers the verified institutional/nonprofit camp marketing-page
providers named in issue 29 as `program_page_multi` sources (sprint 027's
"one page, N inline records" adapter type), each with `config.program_kind
= "program"` and `config.opportunity_type = "Camps"` — the same
operator-curated-override convention `sd-foundation-community-
scholarship.toml` already established for `"Funding Opportunities"`. No
new adapter code; this is a pure "onboarding is a data edit" ticket,
following sprint 027 ticket 005's precedent for registering many
individual pages in one ticket.

**Providers to register** (live-verify each; register `enabled = false`
with a reason comment, per sprint 027 tickets 005/006's precedent, for any
that turn out blocked):
- San Diego Zoo per-program pages (`zoo.sandiegozoo.org/kids-programs/*`)
  — register each of the 9 program pages individually (the exact URL list
  is confirmed live during this ticket, not enumerated in advance);
  per-page live verification determines whether `program_page` (one
  continuous session) or `program_page_multi` (N weekly sessions) is the
  right `adapter_type` for each.
- Living Coast (`thelivingcoast.org/camps`)
- Coastal Roots Farm (`coastalrootsfarm.org/farm-camp`)
- Elementary Institute of Science (`eisca.org/camps`)
- SD Model Railroad Museum (`sdmrm.org/summer-camps`) — this page's
  documented sold-out flags make it the natural live-verification target
  for ticket 003's sold-out-via-description mapping.
- Camp Invention per-program pages (`invent.org/program-search/...`) —
  same per-page live-verification approach as SD Zoo.
- CMOD (`visitcmod.org/camps` + seasonal pages)
- Southwestern College Y.E.S. (XenDirect, server-rendered)
- Birch's newsroom page (dates/prices; the main site 403s per issue 23,
  out of scope here)
- Fleet's marketing page — register `enabled = true` year-round (ticket
  003's empty-list handling covers the off-season case; do **not** gate
  this behind a disabled flag pending "season").

**Explicitly excluded from this ticket** (do not register):
- **Camp Galileo SD** — the commercial "Galileo" studio brand named in the
  roadmap `sprint.md`'s commercial-chain exclusion list, despite appearing
  in issue 29's own marketing-page list. See `sprint.md`'s "Camp Galileo
  tension" note.
- **Air & Space Museum** and **Helen Woodward** — registered only via the
  `activenet_camps` adapter (ticket 005), never also as a
  `program_page_multi` marketing-page source, to avoid the
  dual-registration risk `adapters/DESIGN.md` documents (two adapters
  covering the same org, both bypassing cross-source dedup by design).

## Acceptance Criteria

- [x] Every listed provider (excluding Camp Galileo SD, Air & Space
      Museum, and Helen Woodward) is registered as a `program_page`/
      `program_page_multi` source with `config.opportunity_type =
      "Camps"`, live-verified to yield at least one correctly-dated,
      correctly-priced session record — or registered `enabled = false`
      with a documented reason if blocked.
- [x] `registry/sources/` contains no Camp Galileo SD entry.
- [x] `registry/sources/` contains no marketing-page (`program_page`/
      `program_page_multi`) entry for Air & Space Museum or Helen
      Woodward.
- [x] At least one registered source exercises the sold-out-via-
      `description` mapping from ticket 003 (SD Model Railroad Museum is
      the expected candidate).
- [x] Fleet is registered `enabled = true`.
- [x] A dry-run check confirms every newly-registered `enabled = true`
      source yields correctly-shaped `Camps` records before this ticket
      is marked done.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite).
- **New tests to write**: one fixture-based test per registered provider
  (saved HTML fixture + `FixtureProgramLLMClient`), following the existing
  per-source test convention — at minimum, one exercising a multi-session
  page (N week-rows) and one exercising a sold-out row.
- **Verification command**: `uv run pytest`, plus live dry-run commands
  for each newly-registered source (not part of the hermetic suite).

## Notes (execution)

**Registered `enabled = true` (15 sources, all live dry-run confirmed
`uv run partner-scrape --source <id> --dry-run -v`, correctly-dated,
correctly-priced `Camps` records):**

- San Diego Zoo, all 9 `kids-programs/*` pages (`sd-zoo-classic-camp-*`,
  `sd-zoo-little-artists-camp`, `sd-zoo-animal-art-explorers-camp`,
  `sd-zoo-adventures-art-camp`) — each $525/week; the kindergarten page
  extracted all 8 individual weekly sessions, the other 8 pages
  extracted 1-2 spanning per-theme records (an LLM extraction-
  granularity choice on this page shape's ambiguity between "8 weekly
  sessions" and "2 four-week themed programs" — both interpretations
  are correctly dated/priced; see each file's own comment).
- `living-coast-camps` — 3 named sessions (Birds of a Feather, Tortoise
  Trek, Coastal Champs), all dated/priced.
- `eisca-camps` — 2 records (the 8-week summer program collapsed to one
  spanning record, plus a separate Spring Nature Explorers Camp,
  `is_open=false`).
- `sd-model-railroad-museum-camps` — **the sold-out target**: 9 records,
  7 of 8 weekly sessions `is_open=false` ("SOLD OUT!" on the live page),
  exercising ticket 003's sold-out-via-`Event.description` mapping.
- `cmod-summer-camp` — 2 records (Little/Big Explorers Camp), both
  `is_open=false` (page-wide "Registration Closed"), a second live
  sold-out/closed example.
- `birch-aquarium-summer-camps` — the newsroom article (not the main
  camps page, which the main-site-403 exclusion covers); 8 named camps,
  all dated/priced.
- `fleet-science-center-camps` — live dry-run confirmed **found=0, no
  exception**: the real page is currently off-season ("Registration
  will open in February... Upcoming Camps are currently being
  scheduled"), exactly SUC-040's empty-list case. Registered
  `enabled = true` year-round per the ticket's instruction.

**Registered `enabled = false` (3 sources, documented reason in each
file, sprint 027 tickets 005/006 precedent):**

- `coastal-roots-farm-camp` — the page's "Upcoming Camp Sessions" table
  is clean and unambiguous once reduced to text, but two separate live
  `extract_programs()` calls both collapsed its 3 distinct dated/priced
  sessions into one blended, dateless record (`found=1 dated=0`) — a
  reproduced LLM-extraction-quality gap for this page's specific
  flattened-table shape, not a registry/config problem this data-only
  ticket can fix.
- `camp-invention-morning-creek` — the only confirmed San Diego County
  Camp Invention location page (`ca13/16935`; two other search-result
  URLs that looked local, `sd35/21002` and `ca37/11485`, turned out on
  inspection to be Rapid City, SD and Rancho Santa Margarita, CA/Orange
  County) currently reads "Preregister for Summer 2027 — this site has
  not locked in all the site details" — a price ($405) and eligibility
  are live but no session dates are published yet.
- `southwestern-college-yes-academy` — the XenDirect course search
  (`registration.xendirect.com/swccd/search.cfm`) is POST-only; a plain
  GET against both the landing page and `searchResults.cfm` (with the
  Y.E.S. Academy session's own query params) returns only the search-
  form shell, no session data, and no SU27 YESAcademy session is posted
  yet regardless.

**Explicitly not registered (per ticket scope):** Camp Galileo SD
(commercial-chain exclusion) and Air & Space Museum / Helen Woodward
(ActiveNet-only, ticket 005) — verified absent from `registry/sources/`
by `test_registry.py`'s `TestCampMarketingPageProviders` class.

**Newly-discovered, non-blocking coexistence notes** (documented in the
affected TOML files' own comments, not resolved in this data-only
ticket): `fleet-science-center-camps.toml`/`eisca-camps.toml`/
`living-coast-camps.toml`/`cmod-summer-camp.toml` each register a
camp-specific marketing page for an org that already has an unrelated,
pre-existing general-purpose source (`fleet-science-center.toml`
`listing_html`, `eisca.toml` `generic_html`, `thelivingcoast.toml`/
`visitcmod.toml` `tec_rest`) — a different category of overlap than the
Air & Space Museum/Helen Woodward dual-registration this sprint
forbids (one camp-specific adapter vs one general-purpose scraper, not
two camp-specific adapters), live-checked to confirm no actual camp
content currently appears in the general-purpose feeds. Fleet's case is
the closest to a real future risk (its `listing_html` source's own
comment notes `/events/camps` — the exact URL registered here — has
previously yielded a generic ladder-extracted event) and is flagged for
a future architecture pass.

**Tests added:** `tests/test_registry.py::TestCampMarketingPageProviders`
(8 tests covering every new source's config/enabled state, the
Galileo/Air & Space/Helen Woodward exclusions, and the SD Zoo/Fleet/
SDMRM specifics); `tests/test_adapters_program_page_multi.py`'s
`TestSDMRMSoldOutCampSessions` and `TestMultiWeekThemedCampPage` (2
adapter-level fixture tests using saved HTML fixtures
`sdmrm_camp_sessions_page.html`/`multi_week_camp_page.html` +
`FixtureProgramLLMClient`, per the ticket's "at minimum, one
multi-session page, one sold-out row" bar). Full suite: 2108 passed
(baseline 2098 + 10).
