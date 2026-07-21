---
id: '004'
title: Fix flagship museum date extraction per ticket 003's diagnosis
status: open
use-cases: [SUC-003]
depends-on: ["003"]
github-issue: ''
issue: 14-flagship-museum-date-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix flagship museum date extraction per ticket 003's diagnosis

## Description

Implements the fix half of issue `14-flagship-museum-date-extraction.md`
and sprint 007's SUC-003. **Depends on ticket 003** — read its
"Findings" section first; it names, per source, which of the three
mechanisms below applies. Do not re-diagnose from scratch; do not
guess if ticket 003's findings are incomplete — re-open ticket 003
instead of proceeding on a guess.

See sprint.md's Architecture (Source Registry entries, Generic HTML
Extractor / ladder, Sitemap Discovery — Step 3 module table) and Design
Rationale ("reuse the existing `fetch_strategy = 'headless'` config
flag...") for the constraints this fix must respect.

**Apply, per source, whichever ticket 003 recommends**:

1. **JS-rendering hides the date from a raw HTTP fetch** → set
   `fetch_strategy = "headless"` in that source's
   `[acquisition_policy]` table in its registry TOML
   (`partner_scrape/registry/sources/{sdnhm,sandiego-air-space,fleet-science-center}.toml`).
   This routes the source through Pipeline's existing lazy
   `PlaywrightFetcher` (`partner_scrape/pipeline.py`,
   `HEADLESS_FETCH_STRATEGY`, `_build_default_headless_fetcher`) — no
   code change needed, this mechanism already exists end-to-end
   (sprint 005) and is simply unused today. Confirm the `playwright`
   optional dependency group is installed in the environment you test
   with (`uv sync --extra headless` or equivalent) since it's not a
   base dependency.
2. **Discovery finds no/wrong candidate URLs** (e.g. Air & Space's dead
   sitemap paths) → either set an explicit `config.sitemap_url`
   override in that source's TOML if ticket 003 found the real sitemap
   at a non-standard path, or change `adapter_type = "listing_html"`
   (mirroring `fleet-science-center.toml`'s shape: `listing_urls =
   ["/events"]` or whatever real listing page ticket 003 identified) if
   no usable sitemap exists at all. Do not invent a new discovery
   mechanism — these two options exhaust what the current architecture
   supports.
3. **The ladder selects the wrong/no date on a page that has one**
   (e.g. SDNHM's multi-date category pages) → make a **targeted**
   adjustment to the relevant rung in
   `partner_scrape/extract/ladder.py` — e.g. tightening
   `_extract_body_regex`'s date selection for pages with multiple date
   matches in the scanned text, or fixing `_extract_time_tags`'s
   attribute-format assumption if ticket 003 found a mismatch. Do
   **not** reorder the ladder's priority sequence, change its
   confidence-tier constants, or add a new rung category — this must
   stay a narrow fix to existing rung logic. Add a unit test in
   whatever test module already covers `extract/ladder.py`
   demonstrating the specific case ticket 003 found (e.g. a fixture
   page with a stale date early in the body and a real upcoming date
   later).

**Explicitly out of scope** (per sprint.md Scope and Design Rationale):
Birch Aquarium / `localist.py` (not part of this issue); any change to
the ladder's general priority order or confidence scheme; bespoke
per-site scraper code beyond what ticket 003's diagnosis calls for;
auto-detection of JS-rendering (the explicit `fetch_strategy` flag is
reused as-is).

**Regression guard**: any `extract/ladder.py` change must not change
behavior for the ~10 other registered `generic_html`/`listing_html`
sources that already rely on it — run the full yield check (all
sources, not just the three flagship ones) as part of verification.

**Files** (exact set depends on ticket 003's findings — expect a subset
of):
- `partner_scrape/registry/sources/sdnhm.toml`
- `partner_scrape/registry/sources/sandiego-air-space.toml`
- `partner_scrape/registry/sources/fleet-science-center.toml`
- `partner_scrape/extract/ladder.py` (only if ticket 003 found a
  ladder-level cause)
- `partner_scrape/discovery/sitemap.py` (only if ticket 003 found a
  gap in discovery's pattern matching itself, as opposed to a
  per-source config fix)
- Corresponding test file(s) under `tests/` for whatever module
  changed

## Acceptance Criteria

- [ ] SDNHM, Air & Space, and Fleet Science Center each contribute a
      realistic count of dated, upcoming events — not 0-1 — verified
      by a before/after yield check:
      `uv run partner-scrape --source {sdnhm,sandiego-air-space,fleet-science-center} --no-enrich --dry-run -v`
      run once before this ticket's changes (baseline, matching issue
      14's reported 0/0/1) and once after, with the exported/dated
      counts recorded in this ticket.
- [ ] No other registered `generic_html`/`listing_html` source's yield
      regresses — verified by running the same command (or a full
      `--limit`-less run) across all sources before/after and
      confirming no source's count drops.
- [ ] `uv run pytest` passes — full suite (~845 existing tests) plus
      any new tests added for the specific fix.
- [ ] Birch Aquarium / `localist.py` is untouched.
- [ ] The ladder's rung priority order and confidence-tier constants
      (`CONFIDENCE_JSON_LD` through `CONFIDENCE_BODY_REGEX`) are
      unchanged, unless ticket 003's findings explicitly justified
      otherwise (call this out explicitly if so).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite, ~845 tests) —
  must pass with zero regressions. Specifically re-check any existing
  tests covering `extract/ladder.py`, `discovery/sitemap.py`,
  `discovery/listing.py`, and registry loading
  (`registry/schema.py`), since those are the modules most likely
  touched.
- **New tests to write**: unit test(s) covering whichever specific fix
  was applied — e.g. a `ladder.py` test with a fixture page containing
  multiple dates (reproducing SDNHM's pattern) asserting the correct
  date is selected, or a `discovery/sitemap.py` / registry-loading test
  covering the config change, matching this project's existing
  per-module test file convention (see `tests/` for the existing
  layout).
- **Verification command**: `uv run pytest`, plus the before/after
  yield-check commands in Acceptance Criteria above.
- **Documentation**: update the affected source TOML's header comment
  (each currently documents its own discovery/extraction assumptions —
  e.g. `fleet-science-center.toml`'s comment claiming no `<time>`
  markup exists, which ticket 003's live check contradicted) so it
  reflects the corrected understanding, not the stale sprint-003
  assumption.
