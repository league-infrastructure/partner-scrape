---
id: '004'
title: Candidate review queue + relevance-gated candidate pipeline + CLI wiring
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '003'
github-issue: ''
issue: 09-aggregator-as-discovery-not-source.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Candidate review queue + relevance-gated candidate pipeline + CLI wiring

## Description

Wire ticket 003's `hub_scan` into a complete, runnable discovery flow:
relevance-filter candidates through the existing gate, persist survivors
for human review, and expose it via the CLI. This ticket is where
issue 09's central mandate — "never ingest the aggregator's records as
our data" — becomes independently testable end-to-end, not just true of
each piece in isolation.

1. **`partner_scrape/registry/candidates.py`** — persists `OrgCandidate`s
   (ticket 003's shape) as review-marked TOML stub files under a new
   `partner_scrape/registry/candidates/` directory. A stub deliberately
   contains only `org_name`, `candidate_url` (as a comment/field for
   operator reference), `discovered_via` (the hub id), and
   `evidence_text` — **no** `adapter_type`/`config` — so that even a
   misdirected attempt to load it via `registry.loader.load_sources()`
   fails `SourceConfig.from_toml`'s required-field check (`InvalidSourceConfig`)
   rather than silently succeeding. `registry/loader.py` itself is
   **not** modified — this directory is never in its scan path. Also
   provide a small `list_candidates(directory) -> list[...]` helper for
   an operator to inspect the queue.
2. **`partner_scrape/discovery/candidate_pipeline.py`** — sequences
   discovery: `discover_candidates(hubs: list[HubConfig], fetcher:
   Fetcher, enricher) -> list[OrgCandidate]`. For each hub, call
   `hub_scan.scan_hub(...)`; for each resulting candidate, build a
   synthetic `partner_scrape.model.Event` (`title=org_name`,
   `description=evidence_text`, `source_id=f"hub:{hub_id}"`) and run it
   through the injected `enricher`; keep only candidates whose synthetic
   Event's `relevant is not False` after enrichment; write survivors via
   `registry.candidates`. **Dependency-direction note** (sprint.md's
   Design Rationale): this module must depend on `enrich.enricher
   .LLMEnricher` directly (or a small local `Protocol` this module
   defines itself, matching `LLMEnricher`'s `.enrich(events) ->
   events` shape structurally) — it must **not** import `Enricher` from
   `pipeline.py`, which would create a backwards `discovery -> pipeline`
   dependency edge.
3. **`cli.py`** — add a `discover-candidates` subcommand
   (`--hubs-dir`, default `registry/hub_schema.DEFAULT_HUBS_DIR`;
   `--candidates-dir`, default the new `registry/candidates/`; reuses the
   existing `--no-enrich` precedent's spirit but for this subcommand,
   e.g. an equivalent flag or reuse of the same enricher-construction
   code path as `main()`'s existing `run` command) that calls
   `discover_candidates(...)` and prints a summary (hub count, candidate
   count written). This is purely additive — the existing `run`
   subcommand's flags and behavior are untouched.

## Acceptance Criteria

- [x] `registry/candidates.py` writes one stub TOML per surviving
      candidate, containing `org_name`, `candidate_url`,
      `discovered_via`, `evidence_text`, and omitting `adapter_type`/
      `config`.
- [x] A stub written by this ticket, if passed directly to
      `SourceConfig.from_toml`, raises `InvalidSourceConfig` (missing
      required fields) — confirming the safety property, not just
      asserting it in prose.
- [x] `registry/loader.py` is unmodified; `load_sources()`/
      `load_active_sources()` continue to see exactly the same directory
      (`registry/sources/`) as before this sprint.
- [x] Given a fixture hub with candidates that are STEM-relevant and
      candidates that are not (per a `FixtureLLMClient`-driven relevance
      verdict), only the relevant ones are written to the candidates
      directory.
- [x] **Central acceptance criterion**: running
      `discover_candidates()` end-to-end against a fixture hub never
      calls `normalize.run()` or `export_opportunities()`, and
      `opportunities.json` is never written by this flow — assert this
      directly (e.g. via a spy/mock on those functions, or by asserting
      the fixture site directory's `opportunities.json` is untouched
      after the run).
- [x] `discovery/candidate_pipeline.py` imports from `enrich.enricher`
      (or defines its own local Protocol) and does **not** import
      anything from `pipeline.py`.
- [x] `partner-scrape discover-candidates` runs end-to-end against a
      fixture hubs directory and fixture registry, with no live network
      call, and prints a summary.
- [x] The existing `partner-scrape` (no subcommand / `run`) CLI behavior,
      flags, and output are unchanged.

## Testing

- **Existing tests to run**: `tests/test_cli.py`,
  `tests/test_enrich_enricher.py`, `tests/test_registry.py`.
- **New tests to write**:
  - `tests/test_registry_candidates.py` — round-trips writing and
    listing candidate stubs; asserts a written stub fails
    `SourceConfig.from_toml`.
  - `tests/test_discovery_candidate_pipeline.py` — the central
    "never republishes" test described above, using
    `enrich.llm_client.FixtureLLMClient` to control which synthetic
    candidate-Events are verdicted relevant; asserts `registry/
    candidates/` receives only the relevant survivors.
  - An addition to `tests/test_cli.py` covering the new
    `discover-candidates` subcommand against fixtures (mirrors the
    existing `run` subcommand's fixture-based test pattern).
- **Verification command**: `uv run pytest`
