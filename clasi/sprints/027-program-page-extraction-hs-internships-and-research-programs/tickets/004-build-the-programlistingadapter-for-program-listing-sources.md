---
id: '004'
title: Build the ProgramListingAdapter for program-listing sources
status: open
use-cases: [SUC-032]
depends-on: ['002', '003']
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build the ProgramListingAdapter for program-listing sources

## Description

Build the `program_listing` adapter type: given a listing page (or
pages), discover every matching program card/detail link, then run
each one through the exact same fetch→LLM-extract flow ticket 003
built — one independent `Event` per discovered program, not one
blended record for the whole listing. This is what SUC-032 (the UCSD
Summer Program Finder, the SIO research-internships table) needs.

Depends on ticket 003 because it reuses that ticket's `extract()`
implementation (the fetch+cache+LLM-extract+map-to-Event logic is
identical once a URL is in hand — only `discover()` differs, mirroring
`generic_html.py`/`listing_html.py`'s existing relationship). Depends
on ticket 002 directly as well, for the same `ProgramLLMClient`/
`ProgramExtractionCache` constructor-injection shape.

## Fix shape

1. **`partner_scrape/adapters/program_page.py`** (extend, same file as
   ticket 003 — one cohesive "program-page extraction" module, per
   `adapters-DESIGN.md`'s own framing):
   - Factor `ProgramPageAdapter.extract()`'s body into a shared
     module-level helper (or a shared base/mixin), e.g.
     `_extract_one_program(raw, source, llm_client, cache) -> list[Event]`,
     so both adapter classes call the identical logic — mirroring
     `generic_html.py`/`listing_html.py` sharing `extract.ladder.
     extract_fields()` as their common extraction step.
   - `ProgramListingAdapter(llm_client=None, cache=None)` — same
     constructor-injection shape as `ProgramPageAdapter`.
   - `discover(source, fetcher) -> list[EventRef]` — delegates to
     `discovery.listing.discover_via_listing(source, fetcher)`, the
     exact mechanism `listing_html` already uses (deferred import at
     call time, matching `ListingHtmlAdapter.discover()`'s existing
     import-cycle workaround). Requires `source.config["listing_urls"]`
     and `source.config["site_url"]`, the identical config shape
     `listing_html` sources already use.
   - `fetch()`/`extract()` — identical to `ProgramPageAdapter`'s
     (via the shared helper above).
2. **`partner_scrape/adapters/__init__.py`**: register
   `ADAPTERS["program_listing"] = ProgramListingAdapter`.

## Acceptance Criteria

- [ ] A fixture listing page with N card links (using
      `tests/fixtures/program_pages/`'s listing sample from ticket 002)
      yields N distinct `EventRef`s from `discover()`.
- [ ] Each discovered ref, run through `extract()` with a
      `FixtureProgramLLMClient` keyed per-URL, yields N distinct
      `Event`s, each with its own independently-extracted
      audience/grade/deadline/eligibility — not one shared value across
      all N.
- [ ] A card whose target page fetch returns non-200 is skipped
      (logged), and the remaining cards still yield their `Event`s —
      per-record isolation, matching every other adapter's convention.
- [ ] `ProgramPageAdapter` and `ProgramListingAdapter` share the exact
      same extraction logic (verified by a test asserting both produce
      an identical `Event` from the same raw response/source, modulo
      the `EventRef` that reached them) — proves the refactor in
      ticket 003's file didn't fork behavior between the two adapter
      types.
- [ ] `ADAPTERS["program_listing"]` resolves via `get_adapter(...)`.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite, especially
  `tests/test_adapters_program_page.py` (ticket 003's tests — must
  still pass unmodified after the shared-helper refactor).
- **New tests to write**: `tests/test_adapters_program_listing.py` —
  per Acceptance Criteria above, following
  `tests/test_adapters_listing_html.py`'s existing structure for the
  discovery half.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Refactor ticket 003's `extract()` into a shared helper
first (with ticket 003's own tests as the regression guard that the
refactor is behavior-preserving), then add `ProgramListingAdapter` as a
thin `discover()`-only addition on top of it — mirroring
`listing_html.py`'s own relationship to `generic_html.py`.

**Files to modify**:
- `partner_scrape/adapters/program_page.py` — shared helper extraction,
  new `ProgramListingAdapter` class.
- `partner_scrape/adapters/__init__.py` — one-line `ADAPTERS`
  registration.
- `tests/test_adapters_program_page.py` — verify unaffected by the
  refactor.
- `tests/test_adapters_program_listing.py` (new).
- `tests/fixtures/program_pages/` — add a listing-page HTML fixture
  with multiple card links, plus per-card detail-page fixtures.

**Testing plan**: see Testing above.

**Documentation updates**: None — `adapters-DESIGN.md`'s sprint 027
section already documents both adapter types together.
