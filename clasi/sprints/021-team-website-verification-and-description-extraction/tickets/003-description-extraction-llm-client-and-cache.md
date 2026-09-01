---
id: '003'
title: Description extraction LLM client and cache
status: in-progress
use-cases:
- SUC-023
depends-on:
- '002'
github-issue: ''
issue: 44-team-website-links-and-descriptions.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Description extraction LLM client and cache

## Description

This ticket builds the injectable LLM-summarization infrastructure
ticket 004's orchestration will call — no orchestration logic here, only
the client protocol, its real and fixture implementations, and the
content-hash cache. Mirrors `teams/sponsor_llm.py`/`teams/sponsor_cache.py`
in shape, exactly (JSON-schema-from-dataclass structured output, no
explicit `api_key` on SDK construction, schema-version-guarded cache
entries) — never by import, matching this subsystem's now-twice-
established "mirror, don't import" convention for LLM-backed concerns
(`sponsor_llm.py`'s own docstring already explains why: `teams/` has a
standing, tested invariant of zero edges into `enrich/`, `adapters/`,
`normalize.run()`, or `pipeline.run()`, and each LLM-backed concern in
this subsystem gets its own small, self-contained client/cache pair
rather than a shared abstraction).

**The client's contract is summarization of given text, never
open-ended generation.** `DescriptionLLMClient.summarize_description(
content: str, context: dict[str, Any]) -> DescriptionExtractionResult`
receives only ticket 002's bounded, already-gathered content string —
never raw HTML, never the live page. The system prompt instructs the
model to summarize *only* the given text into a short (1-2 sentence)
description, to never state a fact not present in that text, and —
**no-email guard, layer 2 of 3** — to never include any contact
information (email address, phone number, physical address) in its
response. If the given text contains no substantive information about
the team, the model is instructed to return an empty string rather than
inventing filler — mirroring `sponsor_llm.py`'s own "an empty result is
correct and expected... do not select a candidate you are unsure about"
instruction, adapted from selection to summarization.

`DescriptionCache` mirrors `SponsorCache` exactly: keyed on
`(team_id, content_hash(content))`, schema-version-guarded, one JSON
file per key under `SCRAPE_CACHE_DIR`. Keying on the gathered content's
own hash (not the raw page body's) means unrelated page changes
(a footer copyright year) never force re-summarization — identical to
`sponsor_cache.py`'s own stated design.

## Acceptance Criteria

- [x] `DescriptionLLMClient` is a `Protocol` with one method,
      `summarize_description(content, context) -> DescriptionExtractionResult`,
      mirroring `SponsorLLMClient.classify_sponsors()`'s shape.
- [x] `DescriptionExtractionResult` is a small dataclass carrying at
      least `description: str` (empty string is a valid, expected value,
      not an error).
- [x] `AnthropicDescriptionLLMClient` constructs `anthropic.Anthropic()`
      with no explicit `api_key` (SDK resolves `ANTHROPIC_API_KEY`
      itself), uses the Haiku-tier model ID (matching
      `sponsor_llm.MODEL_ID`'s cost/quality tradeoff rationale), and
      sends a structured-output JSON schema built from
      `DescriptionExtractionResult`'s dataclass fields (mirroring
      `sponsor_llm.py`'s `_build_sponsor_extraction_json_schema()`
      pattern).
- [x] The system prompt explicitly instructs: summarize only the given
      text; never state a fact not present in it; never include contact
      information; return an empty string if nothing substantive is
      present.
- [x] `FixtureDescriptionLLMClient` is a test double (mirroring
      `FixtureSponsorLLMClient`) that returns canned results with no
      network/API call, recording every call made.
- [x] `DescriptionCache.lookup()`/`.store()` mirror `SponsorCache`'s
      exact contract: a schema-version mismatch or missing entry is a
      miss; a hit returns the cached `DescriptionExtractionResult`
      without any LLM call.
- [x] Malformed LLM response handling (bad JSON, missing required field,
      no text content block) raises a dedicated
      `DescriptionClassificationError`-style exception, mirroring
      `SponsorClassificationError`'s role — distinguishable from an
      unrelated programming error.
- [x] Fixture test: a cache hit for the same `(team_id, content_hash)`
      makes zero calls to the injected LLM client.

## Implementation Plan

**Approach**: Two new modules,
`partner_scrape/teams/description_llm.py` and
`partner_scrape/teams/description_cache.py`, structurally parallel to
`sponsor_llm.py`/`sponsor_cache.py` (same JSON-schema-builder helper
duplicated locally rather than imported — accepted cost, matching
`sponsor_llm.py`'s own Design Rationale for the identical tradeoff).

**Files to create/modify**:
- `partner_scrape/teams/description_llm.py` (new) —
  `DescriptionLLMClient` protocol, `DescriptionExtractionResult`,
  `AnthropicDescriptionLLMClient`, `FixtureDescriptionLLMClient`,
  `DescriptionClassificationError`.
- `partner_scrape/teams/description_cache.py` (new) — `DescriptionCache`,
  mirroring `SponsorCache`.
- `tests/teams/test_description_llm.py` (new) — mirrors
  `tests/teams/test_sponsor_llm.py`'s structure.
- `tests/teams/test_description_cache.py` (new) — mirrors
  `tests/teams/test_sponsor_cache.py`'s structure.

**Testing plan**: see Acceptance Criteria. Entirely hermetic — the real
`AnthropicDescriptionLLMClient` is constructed in at most one test
proving it builds without raising given a fake/absent API key context
(matching `sponsor_llm.py`'s own test convention of never actually
calling the network); every behavioral test uses
`FixtureDescriptionLLMClient`. Cache tests always pass an explicit
`tmp_path`, never the real `SCRAPE_CACHE_DIR`.

**Documentation updates**: module docstrings explaining the
mirror-not-import relationship to `sponsor_llm.py`/`sponsor_cache.py`
and the summarize-not-generate contract — matching the level of detail
those modules' own docstrings set.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/`.
- **New tests to write**: `tests/teams/test_description_llm.py`,
  `tests/teams/test_description_cache.py` per Acceptance Criteria above.
- **Verification command**: `uv run pytest`
