---
id: '005'
title: Enrichment cache and LLMEnricher (relevance gate)
status: done
use-cases:
- SUC-011
- SUC-012
depends-on:
- '003'
- '004'
github-issue: ''
issue: 04-llm-enrichment-relevance-gate.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Enrichment cache and LLMEnricher (relevance gate)

## Description

Implement the Enrichment Cache and the `LLMEnricher` (sprint.md
Architecture > Enrichment Cache, LLM Enricher, SUC-011/SUC-012) — the
keystone ticket of issue 04. This is the first real implementation of
`pipeline.Enricher`'s deferred seam; no change to `pipeline.py` is needed
or expected.

Scope:
- `partner_scrape/enrich/cache.py`: a persisted `identity_key ->
  (content_hash, last EnrichmentResult, enriched_at)` map under
  `SCRAPE_CACHE_DIR` (via `Config.get_scrape_cache_dir()`). Content hash
  is computed over an Event's enrichable fields (title, description,
  location, cost, start, end — whatever the LLM call actually reads), not
  the whole Event, so unrelated field changes (e.g. `field_provenance`
  bookkeeping) don't force spurious re-enrichment.
- `partner_scrape/enrich/enricher.py`: `LLMEnricher` implementing
  `pipeline.Enricher.enrich(events: list[Event]) -> list[Event]`:
  1. For each Event, compute `identity_key()` (sprint 001's model helper)
     and the content hash.
  2. Cache hit (same hash) → reapply the cached `EnrichmentResult` to the
     Event via `Event.set(...)`, no LLM call.
  3. Cache miss or changed hash → call `LLMClient.enrich_event(event)`,
     apply the result to the Event via `Event.set(...)`, write a fresh
     cache entry.
  4. LLM call raises → log a warning, fall back to
     `normalize.taxonomy`'s keyword derivation for that Event's
     classification fields, set `relevant=True` (fail-open — sprint.md
     Design Rationale), and do **not** write a cache entry (so the next
     run retries the LLM rather than caching a degraded result).
  5. Filter the returned list: exclude any Event with `relevant is
     False`. A source's other Events are unaffected by one Event being
     gated.

## Acceptance Criteria

- [x] Given a fixture Event with a missing date and a mocked
      `FixtureLLMClient` response supplying one, the Event returned by
      `enrich(...)` has that date set with `source="llm_enrichment"`.
- [x] Given two `enrich(...)` calls over the same Event content (same
      `tmp_path` cache directory across both calls), the fixture
      `LLMClient`'s call count increases by exactly one call in total —
      the second call is a cache hit and makes zero LLM calls.
- [x] Given a fixture Event whose enrichable content changed between two
      `enrich(...)` calls, the second call invokes the LLM again rather
      than reusing the stale cache entry.
- [x] Given a `FixtureLLMClient` configured to raise, the Event survives
      in `enrich(...)`'s returned list with `taxonomy.py`-derived
      classification and `relevant=True`, a warning is logged, and no
      cache entry is written for that Event.
- [x] Given a fixture Event with a mocked `relevant=False` response, that
      Event is absent from `enrich(...)`'s returned list.
- [x] Given a mixed batch (some relevant, some not, some erroring), only
      the relevant/fallback-relevant Events are returned, and one Event's
      gating/error doesn't affect any other Event in the same batch.

## Implementation Plan

### Approach

`LLMEnricher` takes an `LLMClient` (ticket 004's protocol) and an
`EnrichmentCache` (this ticket) as constructor arguments — both
injectable, matching sprint 001's dependency-injection convention for
`Fetcher`. The fail-open fallback imports `normalize.taxonomy`'s pure
functions directly (`derive_areas_of_interest`, `derive_age_grade_level`,
`map_cost`, `derive_time_of_day`) rather than reimplementing keyword
classification — this is exactly what those functions already are, a
pure "text/value in, tags out" layer designed to be called from anywhere,
per their own module docstring.

### Files to Create/Modify

- `partner_scrape/enrich/cache.py`
- `partner_scrape/enrich/enricher.py`
- `tests/test_enrich_cache.py`
- `tests/test_enrich_enricher.py`

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite through ticket
  004 — no regressions expected; nothing existing calls `LLMEnricher`
  yet).
- **New tests to write**: `tests/test_enrich_cache.py` (hash/read/write
  round-trip against a `tmp_path` cache dir) and
  `tests/test_enrich_enricher.py` covering every Acceptance Criterion
  above, using ticket 004's `FixtureLLMClient` with call-count assertions
  and a `tmp_path`-based cache directory (never the real
  `SCRAPE_CACHE_DIR`).
- **Verification command**: `uv run pytest`
