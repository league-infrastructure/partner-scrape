---
id: '006'
title: Pipeline/CLI wiring and end-to-end discovery+enrichment test
status: done
use-cases:
- SUC-009
- SUC-010
- SUC-011
- SUC-012
depends-on:
- '002'
- '005'
github-issue: ''
issue:
- 04-llm-enrichment-relevance-gate.md
- 03-sitemap-discovery-generic-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Pipeline/CLI wiring and end-to-end discovery+enrichment test

## Description

Integration ticket closing out both issues: wire the `generic_html`
adapter (issue 03, tickets 001-002) and the `LLMEnricher` (issue 04,
tickets 003-005) into the real `partner-scrape` CLI, and extend the
end-to-end test to prove the whole path works together, matching sprint
001's own closing ticket (008) pattern.

Scope:
- `partner_scrape/cli.py`: by default, instantiate
  `LLMEnricher(AnthropicLLMClient(), EnrichmentCache(...))` and pass it as
  `enrichers=[...]` to `pipeline.run(...)` (per sprint.md Open Question
  5's confirmed default: enrichment on by default, matching issue 04's
  framing as normal production behavior). Add a `--no-enrich` flag that
  passes `enrichers=()` instead — preserving sprint 001's exact original
  behavior for anyone who sets it, and giving local/dry-run usage an
  escape hatch from real API cost and the `ANTHROPIC_API_KEY` requirement.
- Extend the end-to-end test (`tests/test_pipeline_e2e.py`, or a sibling
  file if that keeps the additions readable) with a fixture registry that
  includes at least one `generic_html` source (ticket 001/002's sitemap
  and HTML fixtures) alongside sprint 001's existing structured-API
  fixture sources, and a `FixtureLLMClient`-backed `LLMEnricher` wired
  through `pipeline.run(enrichers=[...])`. Assert the final
  `opportunities.json` reflects both the new extraction path and the
  relevance gate (a fixture event verdicted not-relevant is absent from
  the written file).

## Acceptance Criteria

- [x] `partner-scrape` (no flags) instantiates
      `LLMEnricher(AnthropicLLMClient(), ...)` and passes it to
      `pipeline.run(enrichers=[...])`.
- [x] `partner-scrape --no-enrich` passes `enrichers=()`, and a dedicated
      test (or sprint 001's original e2e test, re-run unmodified)
      confirms output is byte-for-byte unaffected by enrichment when
      disabled.
- [x] An end-to-end test with a fixture registry containing at least one
      `generic_html` source and at least one sprint-001-style structured
      source, run through `pipeline.run(...)` with a `FixtureLLMClient`-
      backed `LLMEnricher`, produces a valid
      `opportunities.json`/`scrape-meta.json` pair reflecting extraction
      from the `generic_html` source.
- [x] The same end-to-end test includes a fixture Event verdicted
      not-relevant by the `FixtureLLMClient`; that Event is absent from
      the written `opportunities.json`, and the source's other
      (relevant) events are present.
- [x] The full test suite — sprint 001's and this sprint's — runs with no
      network access and no `ANTHROPIC_API_KEY` usage.

## Implementation Plan

### Approach

Keep `cli.py`'s change minimal: one new flag, one conditional on which
`enrichers` tuple gets passed to `pipeline.run(...)` — `pipeline.run`
itself needs no change, since `enrichers` was already a parameter sprint
001 built. Reuse ticket 001/002's sitemap and HTML fixtures for the
end-to-end registry rather than authoring a third set — this ticket's
value is proving integration, not inventing new fixture content.

### Files to Create/Modify

- `partner_scrape/cli.py`
- `tests/test_cli.py` (new `--no-enrich` flag test)
- `tests/test_pipeline_e2e.py` (extend) or a new
  `tests/test_pipeline_e2e_enrichment.py`
- `tests/fixtures/registry_generic/*.toml` (a `generic_html`
  `SourceConfig` fixture pointing at ticket 001/002's fixture sitemap/HTML
  set)

### Documentation Updates

None required this ticket — no README/CLI-help text beyond `cli.py`'s own
`argparse` help string for the new flag, which is part of the code change
itself.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite through ticket
  005 — sprint 001's original end-to-end test must still pass unmodified
  when `--no-enrich`/`enrichers=()` is in effect).
- **New tests to write**: `tests/test_cli.py` case for `--no-enrich`;
  the extended/new end-to-end test covering every Acceptance Criterion
  above.
- **Verification command**: `uv run pytest`
