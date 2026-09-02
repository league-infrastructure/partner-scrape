---
id: '002'
title: Build the program-page LLM extraction client and cache
status: done
use-cases:
- SUC-031
depends-on: []
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build the program-page LLM extraction client and cache

## Description

Build the reusable extraction engine both new adapters (tickets 003,
004) will call: an injectable LLM client that turns a fetched program
page's raw body into a structured `ProgramExtractionResult` (program
name, audience/grades, date range, application window/deadline,
paid/cost, eligibility, open/closed status), plus a content-hash cache
keyed by URL so an unchanged page is never re-sent to the LLM on a
later run. This ticket has no dependency on ticket 001 and can be built
in parallel with it — it produces no `Event`, only the raw extraction
result and its caching, both independently unit-testable.

Mirrors `enrich/llm_client.py`'s shape (injectable Protocol, JSON
schema generated from the result dataclass's own annotations, a real
Anthropic-backed client, a fixture client for tests) and
`enrich/cache.py`'s shape (one JSON file per key), without importing
either — see `adapters-DESIGN.md`'s sprint 027 section ("Deliberately
mirrors, never imports, `enrich/llm_client.py`") for the full
rationale, which mirrors `teams/sponsor_llm.py`'s sprint 013 precedent.

## Fix shape

1. **`partner_scrape/adapters/program_llm.py`** (new):
   - `ProgramExtractionResult` — a dataclass with the fields the issue
     names: `program_name: str`, `audience_grades: list[str]`,
     `date_start: str` (ISO date or empty — the application window's
     open date), `date_end: str` (ISO date or empty — the deadline),
     `cost: str`, `eligibility: str`, `is_open: bool`,
     `opportunity_type: str` (one of the existing controlled
     vocabulary values — see `enrich/llm_client.py`'s
     `_OPPORTUNITY_TYPE_VALUES` for the list to mirror, duplicated here
     deliberately per this module's own "mirrors, never imports" rule).
   - A JSON-schema builder generated from `ProgramExtractionResult`'s
     annotations, mirroring `enrich/llm_client.py`'s
     `_build_enrichment_json_schema()`/`_field_json_schema` shape.
   - `ProgramLLMClient` Protocol: `extract_program(url: str, body: str)
     -> ProgramExtractionResult`.
   - `AnthropicProgramLLMClient` — real implementation, constructs
     `anthropic.Anthropic()` with no explicit `api_key` (SDK resolves
     `ANTHROPIC_API_KEY`), matching `enrich/llm_client.py`'s exact
     credential convention. A dedicated system prompt for program-page
     extraction (distinct from `enrich/llm_client.py`'s recovery/
     classification prompt).
   - `FixtureProgramLLMClient` — test double, canned responses keyed by
     a caller-supplied function of `(url, body)`, records `.calls`.
   - `PROGRAM_LLM_SOURCE`/`PROGRAM_LLM_CONFIDENCE` constants (mirrors
     `enrich/llm_client.py`'s `LLM_SOURCE`/`LLM_CONFIDENCE`) for the
     `Event.set(...)` provenance the adapters (tickets 003/004) will
     record.
2. **`partner_scrape/adapters/program_cache.py`** (new):
   - `ProgramExtractionCache(cache_dir=None)` — one JSON file per
     `(url, content_hash)` under `{SCRAPE_CACHE_DIR}/
     program_extraction_cache/`, mirroring `enrich/cache.py`'s on-disk
     shape and filename-sharding convention (URLs, like `Event`
     identity keys, can contain path-unsafe characters).
   - `.lookup(url, body) -> ProgramExtractionResult | None` — a miss on
     no entry or a content-hash mismatch (the page changed since it was
     last cached).
   - `.store(url, body, result) -> None`.
   - A `content_hash(body) -> str` function, analogous to
     `enrich/cache.py`'s `content_hash(event)` but over raw page text
     rather than an `Event`'s enrichable fields.

## Acceptance Criteria

- [x] `ProgramExtractionResult`'s JSON schema is generated from its own
      dataclass annotations (no hand-maintained schema literal),
      matching `enrich/llm_client.py`'s pattern.
- [x] `FixtureProgramLLMClient` returns canned results keyed by
      `(url, body)` and records every call made to it.
- [x] `AnthropicProgramLLMClient` is never constructed or called by any
      test — production-only, verified by the absence of any live
      network/API call across the test suite for this module.
- [x] `ProgramExtractionCache.lookup()` returns `None` for an unseen
      URL, and the cached result after a matching `.store()` call.
- [x] A changed `body` (different content hash) for the same URL is
      treated as a cache miss, not stale-hit.
- [x] No test in this ticket touches the network or the real Anthropic
      API — `FixtureProgramLLMClient` and a `tmp_path`-based cache
      directory only.
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (no existing module is
  modified by this ticket, so this is a regression check only).
- **New tests to write**: `tests/test_adapters_program_llm.py`,
  `tests/test_adapters_program_cache.py` — per Acceptance Criteria
  above, following `tests/test_enrich_llm_client.py`/
  `tests/test_enrich_cache.py`'s existing structure as a template.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Build `program_llm.py` first (the schema/Protocol/
dataclass shape), then `program_cache.py` (which only depends on
`body`/`url` strings, not on anything in `program_llm.py`). Neither
module is wired into `adapters/__init__.py`'s `ADAPTERS` dispatch table
yet — that's ticket 003/004's job, once a real adapter exists to
construct these as its constructor defaults.

**Files to create**:
- `partner_scrape/adapters/program_llm.py`
- `partner_scrape/adapters/program_cache.py`
- `tests/test_adapters_program_llm.py`
- `tests/test_adapters_program_cache.py`
- `tests/fixtures/program_pages/` (a directory of saved program-page
  HTML/text fixtures for later tickets' tests to reuse — a couple of
  representative samples, e.g. one prose program page and one listing
  card page, seeded here so tickets 003/004/005/006 don't each start
  from scratch).

**Testing plan**: see Testing above.

**Documentation updates**: None — this sprint's `design/` overlay
(`adapters-DESIGN.md`) already documents this module's shape and
rationale in full during planning.
