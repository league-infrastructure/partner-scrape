---
id: '005'
title: Build the activenet_camps adapter for campscui.active.com
status: open
use-cases:
- SUC-042
depends-on:
- '003'
github-issue: ''
issue: 29-camp-session-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build the activenet_camps adapter for campscui.active.com

## Description

Builds the first of issue 29's two in-scope platform adapters:
`activenet_camps`, for organizations whose camps are hosted on
`campscui.active.com` (ActiveNet). New module,
`adapters/activenet_camps.py`, defining `ActiveNetCampsAdapter`:

- `discover()`/`fetch()`: identical to `ProgramPageAdapter`'s shape — one
  registered `config.url` per organization (the platform's per-org
  camp-listing endpoint), one `EventRef`, no probe-then-paginate step.
- `extract()`: first attempts a deterministic parse of the platform's
  response into one `ProgramExtractionResult` per session found
  (`CONFIDENCE_STRUCTURED_PLATFORM = 1.0`, mirroring the Structured API
  family's own confidence convention). **Live-verify at the start of this
  ticket** whether `campscui.active.com` actually exposes a parseable JSON
  response (issue 29 calls it "HTML-ish," not confirmed) — if it does not,
  fall back to `extract.reduce_html_to_text()` (ticket 001) plus
  `ProgramLLMClient.extract_programs()`, the exact same call
  `program_page_multi` already makes, reusing `_SYSTEM_PROMPT_MULTI`
  unchanged. Either path produces a `list[ProgramExtractionResult]`, mapped
  onto `Event`s via the existing `_map_result_to_event` — no new mapping
  code.
- Constructor: `ActiveNetCampsAdapter(llm_client=None, cache=None)`,
  matching the `program_page` family's constructor-injection deviation
  (`adapters/DESIGN.md`'s §3), for the LLM-fallback path's testability. The
  deterministic-parse path does not need the injected client but the
  constructor shape stays uniform.
- Register in `adapters/__init__.py`'s `ADAPTERS` dispatch table as
  `"activenet_camps"`.
- Set `config.opportunity_type = "Camps"` on every registered source, same
  override convention as every other camp source this sprint.

**Register at least Air & Space Museum and Helen Woodward** (issue 29's
named ActiveNet-hosted orgs) via this adapter — and confirm neither is
also registered via the marketing-page path (ticket 004 explicitly
excludes them; this ticket is where they actually land).

If live verification finds `campscui.active.com` needs an API key/token
this project doesn't have, follow the `robotevents`/sprint-016-ticket-004
precedent: design and register against the best available evidence
(published docs, browser network-tab inspection), document the credential
gap in the adapter's module docstring, and add the `config.py` accessor
pair only if/when a credential is actually confirmed necessary.

## Acceptance Criteria

- [ ] `adapters/activenet_camps.py` defines `ActiveNetCampsAdapter`
      (`discover`/`fetch`/`extract`), registered as `"activenet_camps"` in
      `adapters/__init__.py`.
- [ ] `extract()` supports both the deterministic-parse and LLM-fallback
      paths, both producing `ProgramExtractionResult` and reusing
      `_map_result_to_event` for the final `Event` mapping.
- [ ] A fixture-based test proves the adapter maps a saved ActiveNet
      response/page into correctly-dated, correctly-priced `Event`s, with
      no live network or LLM call (use `FixtureProgramLLMClient` for the
      fallback path if the platform turns out not to expose clean JSON).
- [ ] A sold-out session on a fixture page maps to a sold-out
      `Event.description` (ticket 003's mechanism).
- [ ] At least Air & Space Museum and Helen Woodward are registered with
      `adapter_type = "activenet_camps"` and live-verified.
- [ ] Neither Air & Space Museum nor Helen Woodward has a
      `program_page`/`program_page_multi` marketing-page registration.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite, to confirm no
  regression to the existing `program_page` family or the dispatch table).
- **New tests to write**: `tests/adapters/test_activenet_camps.py` —
  fixture-based, covering both the deterministic-parse path (if confirmed
  live) and the LLM-fallback path, a sold-out session, and a non-200 fetch
  (logged and skipped, matching every other adapter's convention).
- **Verification command**: `uv run pytest`, plus a live dry-run for each
  newly-registered source.
