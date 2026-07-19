---
id: '005'
title: Per-source fetch strategy wiring and end-to-end flagship verification
status: done
use-cases:
- SUC-016
depends-on:
- '001'
- '002'
- '004'
github-issue: ''
issue:
- 06-flagship-adapters-fleet-birch.md
- 10-js-rendered-site-support.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Per-source fetch strategy wiring and end-to-end flagship verification

## Description

Two small, related pieces of wiring, plus this sprint's final
integration proof:

1. **Registry schema**: add `"fetch_strategy": "static"` to
   `partner_scrape/registry/schema.py`'s `_ACQUISITION_POLICY_DEFAULTS`
   dict (one line, additive — every existing source with no
   `fetch_strategy` key in its TOML resolves to `"static"`, today's exact
   behavior, no TOML edits needed anywhere).
2. **Pipeline per-source Fetcher selection**: in `pipeline.py`'s source
   enumeration loop (`run()`), read
   `source.acquisition_policy.get("fetch_strategy", "static")` per
   source and pass either the existing default `Fetcher` or a headless
   `Fetcher` (ticket 001's `PlaywrightFetcher`, wrapped in
   `PoliteFetcher` exactly as the default fetcher is) to
   `adapters.run(source, fetcher)`. Construct the headless-wrapping
   `PoliteFetcher` lazily — at most once per run, and only if at least
   one active source is flagged `headless` — never eagerly. A source
   flagged `headless` when `playwright` isn't installed should fail only
   that source's `adapters.run(...)` call; the *existing* per-source
   try/except around that call (already in `pipeline.py`, SUC-008's
   error flow) already catches and logs it — no new error-handling code
   should be needed here, just confirm it via a test.
3. **End-to-end verification**: a fixture-driven Pipeline test proving
   both flagship sources' events survive the full chain into exported
   opportunities, and that pre-existing sources' fetch behavior is
   unaffected.

See sprint.md's Architecture > Pipeline/CLI (extended) and Design
Rationale ("Headless fetch strategy is selected by Pipeline...") for the
full reasoning: fetch-strategy selection is a Pipeline/Registry concern,
never something any `Adapter` implementation needs to know about.

## Acceptance Criteria

- [x] `_ACQUISITION_POLICY_DEFAULTS` gains `"fetch_strategy": "static"`.
- [x] Pipeline selects the per-source `Fetcher` based on
      `source.acquisition_policy.get("fetch_strategy", "static")`; a
      pre-existing (sprint 001/002-era) fixture source with no
      `fetch_strategy` key uses the same default `Fetcher` path as before
      this ticket (byte-identical behavior — no observable change).
- [x] The headless-wrapping `Fetcher` is constructed at most once per
      `run()` call, and only when at least one active source is flagged
      `headless` (verify via a test asserting it is never constructed
      when no source needs it — e.g. by injecting a spy/counter in place
      of the real construction path).
- [x] A source flagged `headless` whose adapter call fails (e.g.
      `playwright` unavailable) is caught by the existing per-source
      try/except, logged, and does not prevent other sources — including
      the other flagship source — from producing output.
- [x] An end-to-end fixture-driven test runs `pipeline.run()` over a
      small registry containing: a `localist` source (Birch, ticket 002),
      a `listing_html` source (Fleet, ticket 004), a pre-existing
      adapter-type source with no `fetch_strategy` set (regression
      check), and one fixture source with
      `acquisition_policy.fetch_strategy = "headless"` (using ticket
      001's fixture `page_factory` double — no real browser). The test
      asserts the final `opportunities.json`-shaped output includes
      events attributed to both Fleet Science Center and Birch Aquarium.
- [x] Running `partner-scrape --source birch-aquarium --dry-run` and
      `partner-scrape --source fleet-science-center --dry-run` against
      the real registered sources (manual/CLI-level check, not part of
      the automated fixture suite) produces a non-empty dry-run payload
      for each — this is the sprint's Success Criteria check, worth
      doing once by hand even though it isn't a `pytest` assertion.
- [x] The whole test suite (including every test this sprint adds across
      all five tickets) runs with no network access, no real browser
      launch, and no `ANTHROPIC_API_KEY`/`playwright` requirement.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_pipeline_e2e.py
  tests/test_pipeline_e2e_enrichment.py tests/test_registry.py` (confirm
  no regression to existing Pipeline/registry behavior).
- **New tests to write**: extend or add to
  `tests/test_pipeline_e2e.py` — the per-source fetch-strategy selection
  tests and the flagship-sources end-to-end fixture test described
  above.
- **Verification command**: `uv run pytest`, plus the two manual
  `--dry-run` invocations noted in Acceptance Criteria.
