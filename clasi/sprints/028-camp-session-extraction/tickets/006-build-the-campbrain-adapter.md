---
id: '006'
title: Build the campbrain adapter
status: open
use-cases:
- SUC-043
depends-on:
- '004'
- '005'
github-issue: ''
issue: 29-camp-session-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build the campbrain adapter

## Description

Builds the second of issue 29's two in-scope platform adapters:
`campbrain`, for organizations whose camps are hosted on CampBrain. New
module, `adapters/campbrain.py`, defining `CampBrainAdapter`, structurally
identical to ticket 005's `ActiveNetCampsAdapter` (same `discover()`/
`fetch()` single-configured-endpoint shape, same deterministic-parse-then-
LLM-fallback `extract()` shape, same constructor-injection signature, same
`_map_result_to_event` reuse, same `config.opportunity_type = "Camps"`
convention). Register in `adapters/__init__.py`'s `ADAPTERS` dispatch table
as `"campbrain"`.

**Registration scope**: issue 29 names Coastal Roots Farm and Watersports
Camp as CampBrain-hosted. Coastal Roots Farm is already registered via its
marketing page in ticket 004 (`program_page_multi`, full session table
already available there) — do **not** also register it via `campbrain`;
that would repeat the exact dual-registration risk this sprint's
`adapters/DESIGN.md` documents for Air & Space Museum/Helen Woodward.
Register **Watersports Camp** (or whichever CampBrain-hosted organization
in scope has no marketing-page equivalent) via this adapter, live-verified.

If live verification finds Coastal Roots Farm's marketing-page coverage is
in fact incomplete or unreliable compared to its CampBrain data, that is a
judgment call this ticket may resolve by switching Coastal Roots Farm's
registration from `program_page_multi` to `campbrain` (not by adding a
second registration) — document the reasoning in this ticket's Notes if
so.

## Acceptance Criteria

- [ ] `adapters/campbrain.py` defines `CampBrainAdapter`
      (`discover`/`fetch`/`extract`), registered as `"campbrain"` in
      `adapters/__init__.py`.
- [ ] A fixture-based test proves the adapter maps a saved CampBrain
      response/page into correctly-dated, correctly-priced `Event`s, with
      no live network or LLM call.
- [ ] At least one CampBrain-hosted organization not already covered by a
      marketing page (e.g. Watersports Camp) is registered and
      live-verified.
- [ ] Coastal Roots Farm is registered via at most one path total across
      this sprint (its ticket-004 marketing-page registration, unless this
      ticket's live verification finds cause to switch it — never both).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite).
- **New tests to write**: `tests/adapters/test_campbrain.py` — fixture-based,
  mirroring `test_activenet_camps.py`'s coverage shape (deterministic-parse
  path if confirmed live, LLM-fallback path, sold-out session, non-200
  fetch).
- **Verification command**: `uv run pytest`, plus a live dry-run for each
  newly-registered source.
