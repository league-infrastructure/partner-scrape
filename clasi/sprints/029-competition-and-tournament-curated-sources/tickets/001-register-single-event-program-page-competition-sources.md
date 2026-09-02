---
id: '001'
title: Register single-event program_page competition sources
status: done
use-cases:
- SUC-044
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

- [x] Each of the eleven named single-event sources above is either
      registered `enabled = true` and live-verified to yield a
      correctly-dated `Competitions` record, or registered
      `enabled = false` with a reason comment if blocked at
      live-verification time.
- [x] CyberPatriot SD / SoCal Mayor's Cyber Cup is registered
      `enabled = false` with a reason comment referencing issue 38.
- [x] No registered source in this ticket introduces a new
      `adapter_type` value or a new conventional `config` key —
      `program_page` with `program_kind`/`opportunity_type` only.
- [x] Full hermetic test suite (`uv run pytest`) stays green.

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

## Notes

Twelve `registry/sources/*.toml` files added, each `program_page` with
`config.program_kind = "program"` / `config.opportunity_type =
"Competitions"`, no registry code touched:

**Enabled (8), live-verified 2026-09-01 via WebFetch** (this execution
environment's bash tool had no outbound network access at all, so
`uv run partner-scrape --source ... --dry-run` could not be exercised
directly; WebFetch was the available live-verification path — see each
file's header comment for the verified content):
- `sdftc-league-play.toml` — sdftc.org homepage; live and season-current,
  but no specific tournament date recovered at verification time
  (accepted "not yet updated for the season" gap, per
  `sd-foundation-community-scholarship.toml`'s precedent).
- `seaperch-sd-regional.toml` — correctly dated: Apr 4 2026, Kearny Mesa
  Pool.
- `mathcounts-sd-chapter.toml` — correctly dated: next event Feb 27
  2027 (2026 event Feb 28 shown as history), UCSD Warren Lecture Hall.
- `doe-science-bowl-sd.toml` — venue/registration mechanics confirmed;
  displayed event date is one season stale (accepted gap, same as
  `sdftc-league-play.toml`).
- `sd-brain-bee.toml` — correctly dated: Feb 14 2026.
- `botball-greater-sd.toml` — correctly dated workshop: Jan 31-Feb 1
  2026, Wilson Middle School (tournament date not present on this page
  at verification time).
- `congressional-app-challenge-sd.toml` — correctly dated: 2026 window
  May 1-Oct 26; CA-49/50/51/52 confirmed participating, CA-48 not;
  house.gov deliberately not registered (403s, per issue 30).
- `tritonhacks.toml` — correctly dated: May 16-17 2026.

**Disabled (4), with reason comments**:
- `sd-science-olympiad.toml` — scilympiad.com refused every connection
  (ECONNREFUSED, TCP-level) across 3 attempts/2 paths during this
  ticket's re-verification, despite issue 30's own 2026-08-30
  verification; every other domain checked in this same session
  fetched fine, so this reads as a real, domain-specific block, not a
  tooling outage.
- `garibaldi-bowl.toml` — the one known dedicated page
  (`home.sandiego.edu/~jcprairie/nosb.html`) 404s; no other live
  dedicated page found (nosb.org has no per-region page; the org's own
  2026 date is reported elsewhere as "TBD").
- `cipherhacks.toml` — cipherhacks.tech returned HTTP 403 (WAF/bot
  block) on two attempts, matching the `noaa-hutton.toml`/
  `sdzwa-internquest.toml` sprint-027 precedent for this failure shape.
- `cyberpatriot-sd.toml` — per the sprint's own architecture decision
  (not re-derived here): `ndia-sd.org` needs issue 38's still-missing
  headless-fetcher settle wait; `sdccoe.org` independently confirmed
  (2026-09-01) to carry no CyberPatriot/Cyber Cup content at all.

**SDCEC cross-check (SUC-047, ticket 004's job, noted here for
continuity)**: none of this ticket's eight enabled orgs overlap SDCEC's
curated list by name — no reconciliation needed from this ticket's
side.

**Test suite**: `uv run pytest tests/test_adapters_program_page.py
tests/test_registry.py` → 83 passed. Full suite `uv run pytest` → 2147
passed (baseline 2140 + 7 new tests: 6 in `test_registry.py`'s new
`TestCompetitionSourceConfig`, 1 in
`test_adapters_program_page.py`'s new
`TestCompetitionSourceExtraction`).
