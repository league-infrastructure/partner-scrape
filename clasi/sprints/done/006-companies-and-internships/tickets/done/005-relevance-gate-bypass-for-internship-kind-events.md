---
id: '005'
title: Relevance Gate bypass for internship-kind Events
status: done
use-cases:
- SUC-005
depends-on:
- '001'
github-issue: ''
issue: 11-company-events-and-internships.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Relevance Gate bypass for internship-kind Events

## Description

`enrich/enricher.py`'s `LLMEnricher.enrich()` currently calls
`_apply_result()` unconditionally for every `Event`, which overwrites
`areas_of_interest`/`age_grade_level`/`cost_range`/`time_of_day`/
`relevant`/`relevance_reason` regardless of whether `field_provenance`
already has a high-confidence entry. `enrich/llm_client.py`'s system
prompt is written specifically around "STEM learning opportunity for
K-12 youth ... not an adult-only program" — unmodified, an internship
Event (already classified and gated deterministically by
`adapters/ats_filters.py` in tickets 002-004) would be re-judged by that
prompt and could be marked `relevant=False` ("adult-only"), silently
dropping a legitimate internship. See sprint.md's Architecture > Design
Rationale ("`LLMEnricher.enrich()` passes `kind='internship'` Events
through unchanged...") for the full reasoning.

Add one early-continue branch at the top of `enrich()`'s per-Event loop:
when `event.kind == "internship"`, append it to `survivors` unchanged
and `continue` — no cache lookup, no `llm_client.enrich_event()` call,
no `_apply_result()` call. Every other `kind` keeps today's exact
behavior.

## Acceptance Criteria

- [x] `LLMEnricher.enrich()` passes every `kind="internship"` `Event`
      through to its returned list unchanged (no field mutated, no
      `field_provenance` entry added or overwritten).
- [x] A `FixtureLLMClient` spy (`llm_client.py`'s existing test double)
      records **zero** calls when `enrich()` is given a batch containing
      only `kind="internship"` Events.
- [x] `EnrichmentCache.lookup()`/`.store()` are not called for
      `kind="internship"` Events (no cache read or write).
- [x] A mixed batch (some `kind="event"`, some `kind="internship"`)
      applies existing LLM/fallback logic only to the `kind="event"`
      Events; internship Events pass through untouched; both kinds
      appear in the returned list in their original relative order (or
      document the actual resulting order if strict order isn't
      preserved — call out during implementation whichever is true).
      Strict original relative order is preserved exactly (the
      early-continue branch appends in the same per-Event loop, so
      output order always equals input order regardless of kind mix).
- [x] Every existing `test_enrich_enricher.py` test (cache hit, cache
      miss/LLM call, LLM failure fallback, relevance-gate filtering for
      `kind="event"` Events) passes unmodified — zero regression to
      non-internship behavior.
- [x] No change to `enrich/llm_client.py` (prompt, schema, or
      `AnthropicLLMClient`) — this ticket is scoped entirely to
      `enrich/enricher.py`.

## Testing

- **Existing tests to run**: `test_enrich_enricher.py`,
  `test_enrich_cache.py`, `test_enrich_llm_client.py`, full
  `uv run pytest`.
- **New tests to write**: new cases in `test_enrich_enricher.py` — an
  internship-only batch against a `FixtureLLMClient` spy with an empty
  `responses` dict (so any unexpected call raises `KeyError` and fails
  the test loudly), and a mixed event+internship batch proving both
  paths coexist correctly.
- **Verification command**: `uv run pytest`
