---
id: '001'
title: Classify opportunity_type during LLM enrichment
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
depends-on: []
github-issue: ''
issue: 13-classify-opportunity-type-in-enrichment.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Classify opportunity_type during LLM enrichment

## Description

Every exported `Opportunity` is currently stamped with a blind default
(`"Out-of-school Programs"`) unless its title happens to match one of
`normalize/taxonomy.py`'s narrow keyword rules — the LLM enrichment
step already classifies `areas_of_interest`, `age_grade_level`,
`cost_range`, and `time_of_day`, but not `opportunity_type`, so 7 of
the site's 8 type filters are effectively always empty (issue 13).

This ticket adds `opportunity_type` to the LLM classification pass,
following the exact same shape the four existing classification fields
already use end to end: dataclass field → prompt guidance →
schema-generated JSON output → applied via `Event.set(...)` → selected
in `normalize/run.py` by `field_provenance` presence, falling back to
the existing keyword classifier when enrichment didn't run. It also
closes a latent cache-correctness gap: `EnrichmentCache`'s
`content_hash` is computed over *input* fields, so adding an *output*
field to `EnrichmentResult` would otherwise make every pre-existing
cache entry either silently omit the new field forever or fail to
deserialize. An explicit cache schema version fixes that.

See the sprint's `design/enrich-DESIGN.md` and `design/normalize-DESIGN.md`
overlay docs for the full rationale (in particular: why
`opportunity_type` always has a value, unlike `cost_range`'s `""` for
unknown; and why no `"Funding Opportunities"` keyword rule is added to
the fallback classifier).

## Acceptance Criteria

- [x] `Event` (`model.py`) gains an `opportunity_type: str = ""` field
      alongside the other classification fields.
- [x] `EnrichmentResult` (`enrich/llm_client.py`) gains an
      `opportunity_type: str = ""` field; `ENRICHMENT_JSON_SCHEMA`
      includes it automatically via the existing dataclass-introspection
      schema generator — no hand-maintained schema literal is touched.
- [x] The LLM system prompt documents the controlled vocabulary
      (`Out-of-school Programs`, `Online`, `Professional Development /
      Conferences`, `School Programs`, `Career Connections`,
      `Volunteering`, `Funding Opportunities`) and instructs the model
      to use `Out-of-school Programs` as the general default when
      nothing more specific applies — `opportunity_type` is never
      empty, unlike `cost_range`.
- [x] `enrich/enricher.py`'s `_apply_result` applies `opportunity_type`
      the same way as the other `_CLASSIFICATION_FIELDS` (unconditional
      `Event.set(...)`, same `source`/`confidence` as its siblings).
- [x] `enrich/enricher.py`'s `_fallback_result` (the fail-open path on
      any LLM/API failure) also derives `opportunity_type`, via
      `normalize.taxonomy.classify_opportunity_type(event.title)` —
      matching every other classification field's existing fallback.
- [x] `enrich/cache.py` gains an explicit `_CACHE_SCHEMA_VERSION`
      constant, written into every stored entry. `EnrichmentCache.lookup`
      treats a missing or mismatched `schema_version` as a cache miss,
      exactly like a `content_hash` mismatch — a pre-sprint-009 cache
      entry (no `schema_version` key at all) must not raise on
      deserialization, and must re-enrich exactly once.
- [x] `normalize/run.py`'s `_to_opportunity` selects `opportunity_type`
      via the same `field_provenance`-presence precedence pattern
      already used for `cost_range`/`areas_of_interest`/
      `age_grade_level`/`time_of_day`: LLM/fallback value when
      `"opportunity_type" in event.field_provenance`, else
      `classify_opportunity_type(event.title)` directly (covers
      `--no-enrich` and any other enrichment-skipped path).
      Internships remain forced to `WORK_BASED_LEARNING_TYPE` by `kind`,
      checked before this precedence logic, unchanged.
- [x] `normalize/taxonomy.py`'s `OPPORTUNITY_TYPE_KEYWORDS` is **not**
      changed — no `"Funding Opportunities"` rule is added, preserving
      its documented false-positive rationale. Only the LLM path
      produces that value.
- [x] `store/event_store.py`'s `_event_to_dict`/`_event_from_dict` gain
      parity for `opportunity_type` (serialize/deserialize it like the
      other classification fields), so this new field does not become
      a second instance of the pre-existing, out-of-scope
      `Event.trusted` serialization gap.
- [x] A regression test confirms a title like "Bird Walk at Grant Park"
      does not classify as `Funding Opportunities` via either the LLM
      prompt's documented vocabulary or the keyword fallback.

## Implementation Plan

**Approach**: Thread the new field through the existing classification
pipeline exactly the way `cost_range` etc. already work — no new
architectural shape is introduced, only a new field following an
established recipe. Do the cache-versioning change first (or
together), since it's what makes the field addition safe against stale
cache entries.

**Files to modify**:
- `partner_scrape/model.py` — add `opportunity_type` to `Event`.
- `partner_scrape/enrich/llm_client.py` — add `opportunity_type` to
  `EnrichmentResult`; add the controlled vocabulary constant and prompt
  guidance.
- `partner_scrape/enrich/cache.py` — add `_CACHE_SCHEMA_VERSION`;
  write/check it in `store`/`lookup`; extend
  `_result_to_jsonable`/`_result_from_jsonable` for the new field.
- `partner_scrape/enrich/enricher.py` — add `"opportunity_type"` to
  `_CLASSIFICATION_FIELDS`; add it to `_fallback_result`'s derivation
  (import `classify_opportunity_type` from `normalize.taxonomy`
  alongside the existing taxonomy imports).
- `partner_scrape/normalize/run.py` — add the `opportunity_type`
  precedence branch in `_to_opportunity`.
- `partner_scrape/store/event_store.py` — add `opportunity_type` to
  `_event_to_dict`/`_event_from_dict`.

**No files to create.**

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — this ticket
  touches shared classification machinery every other classification
  field's tests already exercise).
- **New tests to write**:
  - `enrich/llm_client.py`'s test module: schema generation includes
    `opportunity_type`; `FixtureLLMClient` responses can set it;
    response parsing round-trips it.
  - `enrich/cache.py`'s test module: a stored entry from before this
    ticket (no `schema_version`) is treated as a miss, not a
    deserialization error; a fresh entry round-trips and does not
    trigger repeated re-enrichment.
  - `enrich/enricher.py`'s test module: `_apply_result` sets
    `opportunity_type` with the right source/confidence; the fail-open
    path (LLM raises) derives it via `classify_opportunity_type`.
  - `normalize/run.py`'s test module: the precedence branch — LLM/
    fallback value wins when `field_provenance` is set; direct
    `classify_opportunity_type(title)` when it is not (e.g.
    `--no-enrich`); internship's forced `Work-based Learning` is
    unaffected either way.
  - `store/event_store.py`'s test module: round-trip includes
    `opportunity_type`.
  - Regression case: "Bird Walk at Grant Park" (or an equivalent
    text containing "grant") does not classify as `Funding
    Opportunities` under the keyword fallback.
- **Verification command**: `uv run pytest`

## Documentation updates

None beyond this sprint's `design/enrich-DESIGN.md`,
`design/normalize-DESIGN.md`, and `design/store-DESIGN.md` overlays
(already written; merge into the canonical `docs/design/` doc set
happens at sprint close, per the `close-sprint` skill).
