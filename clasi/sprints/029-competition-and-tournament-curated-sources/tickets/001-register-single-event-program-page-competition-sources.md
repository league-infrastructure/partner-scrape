---
id: '001'
title: Register single-event program_page competition sources
status: open
use-cases: [SUC-044]
depends-on: []
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register single-event program_page competition sources

## Description

Register San Diego's static-page, single-event competition/tournament
sources named in issue 30 as `program_page` sources, reusing sprint
027/028's LLM-extraction mechanism verbatim (`adapters/program_page.py`'s
`ProgramPageAdapter`) — no new adapter code, no new `config` key. Each
gets `config.program_kind = "program"` and `config.opportunity_type =
"Competitions"`, the same operator-curated override pattern
`sd-foundation-community-scholarship.toml`'s `"Funding Opportunities"`
already established.

Sources to register (all live-verified 2026-08-30 per the issue; **live
re-verify at execution time**, per sprint 027/028 precedent — a source
that is blocked or yields nothing usable is registered
`enabled = false` with a reason comment, never silently dropped):

- San Diego Regional Science Olympiad — scilympiad.com/sdso
- SDFTC league play — sdftc.org (Weebly)
- SeaPerch San Diego Regional — Classroom of the Future Foundation
- MATHCOUNTS SD chapter — cspeef.org
- DOE National Science Bowl SD regionals
- Garibaldi Bowl (NOSB, USD)
- San Diego Brain Bee
- Botball Greater San Diego (KIPR)
- Congressional App Challenge (CA-48/49/50/51/52) — congressionalappchallenge.us
  (house.gov 403s; do not register that domain)
- TritonHacks (UCSD) and CipherHacks (SD Central Library) — register each
  hackathon's own official page directly, not hackathons.hackclub.com's
  aggregator

Also register CyberPatriot SD (AFA Cardenas chapter) / SoCal Mayor's
Cyber Cup (NDIA SD) as `enabled = false`: `ndia-sd.org` is JS-rendered
(needs issue 38's still-missing headless-fetcher settle wait — do not
attempt to fix the fetcher in this ticket) and `sdccoe.org` carries only
a stale TEC. The reason comment must reference issue 38 by number.

## Acceptance Criteria

- [ ] Each of the eleven named single-event sources above is either
      registered `enabled = true` and live-verified to yield a
      correctly-dated `Competitions` record, or registered
      `enabled = false` with a reason comment if blocked at
      live-verification time.
- [ ] CyberPatriot SD / SoCal Mayor's Cyber Cup is registered
      `enabled = false` with a reason comment referencing issue 38.
- [ ] No registered source in this ticket introduces a new
      `adapter_type` value or a new conventional `config` key —
      `program_page` with `program_kind`/`opportunity_type` only.
- [ ] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_page.py
  tests/test_registry.py` (registry-loader parsing and existing
  `program_page` fixture tests must be unaffected).
- **New tests to write**: a registry-loader parsing test for at least one
  new source file; a `FixtureProgramLLMClient`-based fixture test proving
  at least one of this ticket's pages maps to a correctly-dated,
  `Competitions`-typed `Event` via the existing `_extract_one_program`
  mapping (SUC-044's own acceptance criterion) — one representative fixture
  is sufficient since the mapping logic itself is already covered by
  sprint 027/028's own tests and is unchanged here.
- **Verification command**: `uv run pytest`
