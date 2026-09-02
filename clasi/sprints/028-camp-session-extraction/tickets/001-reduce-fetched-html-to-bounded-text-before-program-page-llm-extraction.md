---
id: '001'
title: Reduce fetched HTML to bounded text before program-page LLM extraction
status: done
use-cases:
- SUC-036
depends-on: []
github-issue: ''
issue: 36-reduce-page-html-before-llm-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Reduce fetched HTML to bounded text before program-page LLM extraction

## Description

Closes the first half of issue 36. `adapters/program_page.py`'s
`_extract_one_program`/`_extract_many_programs` currently send a fetched
page's raw HTML body to the LLM verbatim (`ProgramLLMClient.extract_program`/
`extract_programs`). Two verified sprint-027 failures came from this: the SD
Foundation Community Scholarship's raw HTML (840KB-965KB site-wide) raised
`anthropic.BadRequestError: prompt is too long: 600199 tokens > 200000
maximum`, and a UCSD Summer Program Finder card (`www.rmtlacademy.org`,
612KB) hit the same limit.

Add a new public function to `extract/` — `reduce_html_to_text(html: str,
max_chars: int = 100_000) -> str` — that strips `<script>`/`<style>`/`<nav>`/
`<header>`/`<footer>` elements, walks the remaining tree for visible text
(reusing the existing `_visible_text_parts`/`_visible_body_text` helpers the
body-regex rung already uses, per `extract/DESIGN.md`'s own "no per-site
special cases, no duplicate tree-walking implementation" convention — do not
write a second HTML-to-text pass inside `adapters/`), collapses whitespace,
and truncates to the leading `max_chars` characters. Returns `""` for
unparseable/empty HTML, with a logged warning, never raising — matching
`extract_fields()`'s own contract exactly.

Wire this into `program_page.py`: call `reduce_html_to_text(raw.body)`
immediately after the non-200 status check in both `_extract_one_program`
and `_extract_many_programs`, and use the *reduced* text for the cache
lookup/store (`ProgramExtractionCache.lookup`/`store`/`lookup_many`/
`store_many`) and the LLM call. This changes the cache's effective key from
a hash of the raw fetched body to a hash of the reduced text — a deliberate
improvement (a page's raw HTML changes on every boilerplate edit the
reduction step already discards; hashing the reduced text avoids invalidating
the cache for changes the LLM never sees). Do **not** bump
`ProgramExtractionCache._CACHE_SCHEMA_VERSION` — the entry's on-disk shape is
unchanged, only what gets hashed; a stale stored hash is already a normal,
harmless cache miss under the existing contract.

See `design/extract-DESIGN.md`'s and `design/adapters-DESIGN.md`'s sprint 028
sections for the full architecture write-up and Design Rationale (including
why 100,000 characters, why leading-truncation, and why hashing the reduced
text).

## Acceptance Criteria

- [x] `extract.reduce_html_to_text(html, max_chars=100_000)` is implemented,
      exported from `extract/`, and reuses the existing visible-text-walking
      helpers rather than a new tree-walking implementation.
- [x] A saved ~900KB fixture page (representative of the SD Foundation site's
      template bloat) reduces to well under the 200K-token limit.
- [x] `_extract_one_program`/`_extract_many_programs` call
      `reduce_html_to_text()` on `raw.body` before every cache lookup and LLM
      call.
- [x] A fixture test proves the extraction cache key is derived from the
      *reduced* text: a content-only change to a stripped element (e.g. a
      `<script>` block) does not invalidate an existing cache entry.
- [x] `FixtureProgramLLMClient`-based fixture test proves the reduced ~900KB
      fixture page still yields the correct program/session fields.
- [x] Every existing `program_page`/`program_listing`/`program_page_multi`
      fixture test continues to pass unmodified (reducing an already-small
      page is a no-op on its extracted fields). One exception, documented in
      this ticket's commit and inline in the test itself: `test_adapters_
      program_page_multi.py`'s `test_llm_client_called_once_for_the_whole_
      page` asserted the exact raw body forwarded to the LLM client, an
      implementation detail this ticket's required wiring necessarily
      changes (the call now carries reduced text, not raw HTML); the
      assertion was updated to compare against `reduce_html_to_text(...)`
      of the same fixture, and the underlying behavior it verifies (one
      `extract_programs()` call for the whole page) is unaffected. Every
      other existing fixture test in these three files passed unmodified.
- [x] `_CACHE_SCHEMA_VERSION` is unchanged.

## Testing

- **Existing tests to run**: `uv run pytest tests/adapters/test_program_page.py
  tests/adapters/test_program_llm.py tests/adapters/test_program_cache.py
  tests/extract/` (adjust paths to this repo's actual test-directory layout;
  mirror the existing per-module test convention).
- **New tests to write**:
  - `tests/extract/test_ladder.py` (or a new `test_reduce.py` alongside it):
    `reduce_html_to_text()` against a saved oversized fixture page, an
    ordinary small fixture page (no-op check), and malformed/empty HTML
    (returns `""`, no raise).
  - `tests/adapters/test_program_page.py`: a fixture proving the cache key
    is derived from reduced text, not raw body; a fixture proving the
    ~900KB oversized page now extracts successfully via
    `FixtureProgramLLMClient` where it previously would have raised.
- **Verification command**: `uv run pytest`
