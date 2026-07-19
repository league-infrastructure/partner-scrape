---
id: '004'
title: Injectable LLM client (Anthropic)
status: done
use-cases:
- SUC-011
depends-on:
- '003'
github-issue: ''
issue: 04-llm-enrichment-relevance-gate.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Injectable LLM client (Anthropic)

## Description

Implement the LLM Client (sprint.md Architecture > LLM Client, SUC-011):
the injectable interface to one LLM enrichment call, and its one real
implementation. This is "the one thin, mockable place" the sprint brief
requires — every other module that needs LLM enrichment (ticket 005's
`LLMEnricher`) depends on the `LLMClient` protocol, never on the `anthropic`
SDK directly.

Scope:
- `LLMClient` protocol (mirrors the `Fetcher` protocol pattern from sprint
  001) with one method, something like `enrich_event(event: Event) ->
  EnrichmentResult`, taking the Event's currently-known fields (title,
  description, whatever date/location/cost is already present) and
  returning a structured result.
- `EnrichmentResult`: recovered date/time/location/cost/registration
  fields (whichever the Event is missing), `areas_of_interest`/
  `age_grade_level`/`cost_range`/`time_of_day` classification, and
  `relevant`/`relevance_reason`.
- `AnthropicLLMClient`: thin wrapper over the `anthropic` SDK using
  structured output (`output_config.format` with a JSON schema matching
  `EnrichmentResult`, per current Anthropic API guidance) so the response
  is guaranteed to parse. Constructs `anthropic.Anthropic()` with **no**
  explicit `api_key` argument — the SDK resolves `ANTHROPIC_API_KEY` (or
  another configured credential) itself; `partner_scrape/config.py` gains
  no new accessor (see sprint.md's Impact on Existing Components note on
  why this isn't a `config.py` boundary violation).
- Model ID is a single named constant, defaulting to `claude-opus-4-8`
  (see sprint.md Open Question 1 — this is the current-guidance default,
  not a final cost decision; keep it a one-line change to revisit).
- Add `anthropic` to `pyproject.toml`.
- A `FixtureLLMClient` test double (canned `EnrichmentResult`s, no
  network) — this ticket defines it since this ticket owns the interface
  it implements; ticket 005 reuses it.

## Acceptance Criteria

- [x] `LLMClient` protocol and `EnrichmentResult` are defined; `AnthropicLLMClient`
      implements the protocol.
- [x] `AnthropicLLMClient` constructs `anthropic.Anthropic()` with no
      explicit API key argument (verified by a test that mocks/monkeypatches
      the `anthropic` SDK's client class itself, not the network — no test
      in this ticket's suite requires `ANTHROPIC_API_KEY` to be set).
- [x] Given a mocked Anthropic SDK response matching the structured-output
      schema, `AnthropicLLMClient.enrich_event(...)` returns a correctly
      parsed `EnrichmentResult` with every field mapped.
- [x] Given a mocked response that violates the schema (malformed JSON, a
      field of the wrong type), `AnthropicLLMClient.enrich_event(...)`
      raises a clear, specific exception — not a silently wrong-shaped
      result — so ticket 005's fail-open path has something concrete to
      catch.
- [x] The model ID used in every real request is a single named module
      constant, not inlined at more than one call site.
- [x] `anthropic` is declared in `pyproject.toml`.
- [x] `FixtureLLMClient` exists, returns canned `EnrichmentResult`s per a
      simple lookup (e.g. by Event title or identity key), and never opens
      a socket.

## Implementation Plan

### Approach

Keep `AnthropicLLMClient.enrich_event` a single method with no
statefulness beyond the constructed SDK client — no retry/backoff logic
here (the `anthropic` SDK already retries 429/5xx per its own defaults,
per current guidance) and no caching (that's ticket 005's Enrichment Cache,
a different module with a different reason to change). Build the
structured-output JSON schema directly from `EnrichmentResult`'s shape so
the two can't drift silently.

### Files to Create/Modify

- `partner_scrape/enrich/__init__.py`
- `partner_scrape/enrich/llm_client.py`
- `pyproject.toml` (add `anthropic` dependency)
- `tests/test_enrich_llm_client.py`
- `tests/fixtures/llm/full_classification.json`,
  `tests/fixtures/llm/not_relevant.json`,
  `tests/fixtures/llm/malformed.json` (recorded/synthesized Anthropic
  structured-output response shapes)

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite through ticket
  003 — no regressions expected; nothing existing imports `enrich/`).
- **New tests to write**: `tests/test_enrich_llm_client.py` covering every
  Acceptance Criterion above, with the `anthropic` SDK itself mocked at
  the client-construction boundary (not a real request under any
  circumstance) plus a `FixtureLLMClient` sanity check (returns what it's
  told to return, records calls).
- **Verification command**: `uv run pytest`
