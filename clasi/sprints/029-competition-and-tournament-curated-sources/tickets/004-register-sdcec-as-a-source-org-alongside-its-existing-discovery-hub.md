---
id: '004'
title: Register SDCEC as a source org alongside its existing discovery hub
status: open
use-cases: [SUC-047]
depends-on: ["001", "002", "003"]
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register SDCEC as a source org alongside its existing discovery hub

## Description

SDCEC (San Diego County Engineering Council, sandiegoengineers.org/stem)
already has `registry/hubs/sdcec-stem.toml`, a discovery-only hub from
sprint 024. This ticket registers SDCEC as an actual org source,
`registry/sources/sdcec.toml`, `adapter_type = "program_page_multi"`
against the same `/stem` page, extracting its hand-curated youth STEM
list (including the Feb 20 2026 Engineers Week awards) into N
independently-typed `Event`s. **Leave the existing hub file completely
unmodified** — a hub and a source for the same org are two different,
already-separate catalogs (`registry/DESIGN.md` §3's physical-separation
invariant); this is not the same-org-registered-twice-*within*-`sources/`
risk this sprint avoids elsewhere. Set no `config.opportunity_type`
override, matching ticket 003's reasoning: SDCEC's list mixes
competitions with other opportunity types.

**Cross-check** (depends on tickets 001-003 landing first): compare
SDCEC's curated `/stem` list against every source this sprint registers
(tickets 001-003) for accidental overlap — the same failure mode sprint
027's COSMOS/OPTIMUS/ENLACE Open Question names for the program-page
family generally. Record the result in this ticket's Notes even if no
overlap is found.

## Acceptance Criteria

- [ ] `registry/sources/sdcec.toml` is registered, live-verified, and
      yields at least the Engineers Week awards as a dated record.
- [ ] `registry/hubs/sdcec-stem.toml` is unmodified (verify with `git
      diff` before finishing this ticket).
- [ ] The cross-check against tickets 001-003's registrations is
      performed and its result (overlap found and reconciled, or none
      found) is recorded in this ticket's Notes.
- [ ] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_page_multi.py
  tests/test_registry.py tests/test_registry_hub_schema.py` (the hub
  schema/loader tests must show no change in behavior for
  `sdcec-stem.toml`).
- **New tests to write**: a fixture test with a saved `/stem` page
  proving multiple independently-typed `Event`s extract, including the
  Engineers Week awards, per SUC-047's acceptance criteria.
- **Verification command**: `uv run pytest`
