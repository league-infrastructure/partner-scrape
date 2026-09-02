---
id: 008
title: Add selector-based listing discovery and multi-record page extraction to the
  program-page mechanism
status: done
use-cases:
- SUC-032
depends-on:
- '002'
- '004'
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add selector-based listing discovery and multi-record page extraction to the program-page mechanism

## Description

Ticket 006's required live-verification step found that
`ProgramListingAdapter.discover()`'s sole discovery signal —
`discovery.listing.discover_via_listing`'s `EVENT_PATH_RE` match against
raw `<a href>` targets — fits neither of this sprint's two headline
listing sources' real markup, and threw a ticket exception (see the
exception frontmatter this ticket's sibling registration ticket, 006,
carried before this revision). The team-lead reclassified the
exception's surface from `user-visible` to `internal` and dispatched
this architecture revision; see `design/adapters-DESIGN.md`'s Revision
note (2026-09-02) for the full finding and design rationale — this
ticket implements that design.

Two independent, additive mechanism changes, plus one small
observability improvement:

1. **Selector-based listing discovery** — a `config.link_selector` CSS
   selector as an alternative to `EVENT_PATH_RE` path-pattern matching,
   for a listing whose card links are identified by markup structure/
   attributes rather than URL path shape (the UCSD Summer Program
   Finder's `<li data-grade="High School">…<a class="learnmore">`
   cards).
2. **`program_page_multi`: one page, N inline program records** — a
   third adapter type for a page whose N programs are inline sections
   on the page itself, not links to N detail pages (the SIO
   research-internships page's `<div class="page-section">` blocks).
   This is the reusable surface sprints 029 (competitions) and 030
   (educator pages) are expected to register against directly.
3. **Zero-discovered-refs is no longer silent** — a generic warning log
   in `adapters/base.py`'s `run()`, for every adapter type.

## Fix shape

1. **`discovery/listing.py`**: add `discover_via_selector(source,
   fetcher) -> list[EventRef]`, a sibling to the existing
   `discover_via_listing`. Factor the shared per-listing-page fetch loop
   (resolve `config.listing_urls` against `config.site_url`, GET via
   `acquisition_kwargs`, log-and-skip a non-200 page) so the two
   functions differ only in how links are picked from the parsed tree:
   `EVENT_PATH_RE.search()` over every `<a href>` (unchanged, existing
   function) versus `lxml`'s `tree.cssselect(link_selector)`, reading
   each matched element's own `href` (new function). Dedup by absolute
   URL, preserving document order, matching the existing function's
   convention. No domain restriction in either function (matches
   existing, already-documented behavior — see `discovery/DESIGN.md`'s
   Revision note).
2. **`adapters/program_page.py`**: `ProgramListingAdapter.discover()`
   calls `discover_via_selector` when `source.config.get("link_selector")`
   is set, else falls back to today's `discover_via_listing` call
   unchanged — a source with no `link_selector` key sees no behavior
   change at all.
3. **`adapters/program_llm.py`**: add `extract_programs(url, body) ->
   list[ProgramExtractionResult]` to the `ProgramLLMClient` Protocol,
   implemented on both `AnthropicProgramLLMClient` (a second
   structured-output JSON schema wrapping the existing per-record object
   shape in `{"programs": [...]}`, built the same
   dataclass-introspection way as the existing schema) and
   `FixtureProgramLLMClient` (extend the test double so it can also
   return a canned list, keyed the same way as the existing
   `responses`/`key_fn` mechanism — do not build a second test-double
   class).
4. **`adapters/program_cache.py`**: add `lookup_many(url, body) ->
   list[ProgramExtractionResult] | None` / `store_many(url, body,
   results)`, the list-valued counterpart to `lookup`/`store`, same
   URL+content-hash keying. Bump `_CACHE_SCHEMA_VERSION` once for the
   new entry shape (a version-forced cache miss on any pre-existing
   entry is a one-time, harmless re-extraction, not a data-loss risk —
   matches this cache's own existing stale-version-is-a-miss contract).
5. **`adapters/program_page.py`**: add `ProgramPageMultiAdapter`,
   sharing `ProgramPageAdapter.discover()`/`fetch()` verbatim (one
   configured URL, no probe-then-paginate). Its `extract()` calls
   `llm_client.extract_programs(...)` (via the cache's `lookup_many`/
   `store_many`) and maps each returned `ProgramExtractionResult` onto
   its own `Event`, reusing the existing per-result field-mapping logic
   `_extract_one_program` already applies (refactor the shared
   value-to-`Event` mapping into a helper both the single- and
   multi-record paths call, rather than duplicating it). All N `Event`s
   from one page share the page's `url`/`source_id`; do not invent a
   synthetic per-record URL or `external_id` — `Event.identity_key()`
   already falls back to `(source_id, normalized_title, start_date)`
   when `external_id` is unset, which is sufficient to keep same-page
   records distinct (verified directly against `model.py` during this
   revision's design; add a test asserting this explicitly, per
   Acceptance Criteria).
6. **`adapters/__init__.py`**: register `program_page_multi` ->
   `ProgramPageMultiAdapter` in `ADAPTERS`, the one-line addition the
   dispatch table's existing convention expects.
7. **`adapters/base.py`**: in `run()`, immediately after `refs =
   list(adapter.discover(source, fetcher))`, log a `logger.warning` (not
   raise) naming `source.source_id`, `source.adapter_type`, and the zero
   count when `refs` is empty — applies to every adapter type, not only
   the two program families.

## Acceptance Criteria

- [x] `discover_via_selector` is unit-tested against a fixture HTML page
      reproducing the UCSD card shape (`data-grade` attribute, an
      `a.learnmore` link to a cross-domain URL with no `/program(s)?`
      path segment) — proves it returns the matched links and that
      `EVENT_PATH_RE`-based `discover_via_listing` would not have.
- [x] `discover_via_listing` (no `link_selector` configured) is
      unaffected — its existing fixture tests pass unmodified.
- [x] `ProgramListingAdapter.discover()` routes to `discover_via_selector`
      only when `config.link_selector` is set; a fixture test proves
      both branches.
- [x] A `FixtureProgramLLMClient` test proves `extract_programs()`
      returning N results maps to N distinct `Event`s from
      `ProgramPageMultiAdapter.extract()`, each with its own title/
      dates/eligibility, sharing the same `url`/`source_id`.
- [x] A test proves the N same-`url` `Event`s from one
      `program_page_multi` page have N distinct `identity_key()` values
      (no collision), using at least one pair of records with the same
      `start_date` but different titles.
- [x] A cache-hit test proves an unchanged page's second
      `program_page_multi` run makes no further `extract_programs` call
      (`lookup_many` hit).
- [x] A fixture test proves `adapters.run()` logs a warning (does not
      raise) when a source's `discover()` returns zero refs, for at
      least one non-program adapter type (proving the change is
      generic, not program-family-specific) — check via `caplog`, not a
      raised exception.
- [x] `AnthropicProgramLLMClient.extract_programs()`'s JSON schema is
      built via the same dataclass-introspection mechanism as the
      existing schema (no hand-maintained duplicate schema dict).
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite, especially
  `tests/test_discovery_listing.py` (or equivalent),
  `tests/test_adapters_program_page.py`,
  `tests/test_adapters_program_llm.py`, `tests/test_adapters_base.py`
  (adjust to this codebase's actual test-file names).
- **New tests to write**: see Acceptance Criteria above — all hermetic,
  fixture-based; no live network or live Anthropic API calls anywhere in
  this ticket's test suite (`FixtureProgramLLMClient` and a fixture
  `Fetcher`/HTML body only).
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Land the discovery-side change (`discover_via_selector`)
and the extraction-side change (`program_page_multi`) as independently
reviewable, but land both in this one ticket since they share the same
exception root cause and the same revised architecture doc — splitting
them would leave the mechanism half-implemented against the design.

**Files to create**: none (no new module — all changes land in existing
`discovery/listing.py`, `adapters/program_page.py`,
`adapters/program_llm.py`, `adapters/program_cache.py`,
`adapters/__init__.py`, `adapters/base.py`).

**Files to modify**: the six files named in the Fix shape above, plus
their corresponding test files.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/adapters/DESIGN.md`,
`partner_scrape/discovery/DESIGN.md`, `partner_scrape/registry/DESIGN.md`,
and `docs/design/design.md` are already updated in this sprint's `design/`
overlay (this revision's own architecture work, done ahead of ticket
execution per this project's opt-in `design_docs` convention) — this
ticket's job is to make the code match what the overlay already
documents, not to write documentation itself. If implementation reveals
a detail the overlay got wrong (e.g. an actual UCSD/SIO markup
particular this ticket's own live-verification turns up differently
than this revision's), correct the overlay in place and note the
correction in this ticket's Notes.
