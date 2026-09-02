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


## Notes (029-001b correction, 2026-09-02)

The first pass's live-verification (above) turned out to be
insufficiently rigorous: it relied on the WebFetch tool's own
AI-summarized page content, never the real
`discover()->fetch()->extract()` adapter chain or the real
`AnthropicProgramLLMClient` -- the sprint 027/028 standard. A
team-lead correction identified this and confirmed that this
execution environment's Bash tool *does* have outbound network access
when run unsandboxed (`dangerouslyDisableSandbox: true`), unlike the
sandboxed pass used originally. Re-verification was redone with real
`curl` and real `uv run partner-scrape --source <id> --dry-run -v`
runs against the live network with a real Anthropic API key.

**Findings, corrected**:

- **`cipherhacks`** -- WRONG in the first pass. The original 403
  finding (WebFetch) did not reproduce: real `curl` returns HTTP 200,
  and a real dry-run extracts a fully correct record (`CipherHacks
  2026`, 2026-06-17/18, `Competitions`, `found=1 dated=1`). Flipped
  **disabled -> enabled**. (The fetched page also contains an embedded
  prompt-injection string aimed at AI fetchers -- not acted on; noted
  in the file's own comment for future maintainers.)
- **`mathcounts-sd-chapter`** -- WRONG in the first pass. WebFetch saw
  HTTP 200; this project's own `PoliteFetcher` gets a real HTTP 403
  (WAF/bot block) in a real dry-run (`found=0`). Flipped **enabled ->
  disabled**.
- **`sdftc-league-play`**, **`sd-brain-bee`**, **`botball-greater-sd`**
  -- WRONG in the first pass. Each fetches fine for real, but the real
  LLM extraction recovers no date at all (`dated=0`) -- for
  `sd-brain-bee` this is a genuine extraction miss (the page's reduced
  text plainly states "Event Date: February 14, 2026", reproduced
  across two retries), for the other two the fetched text itself has
  no calendar date. Flipped **enabled -> disabled** each.
- **`seaperch-sd-regional`** -- WRONG in the first pass. Real
  extraction (reproduced twice) consistently recovers the Technical
  Design Report *submission deadline* (Mar 27 2026), not the actual
  Apr 4 2026 competition date, even though the competition date is
  clearly present in the fetched text. Flipped **enabled -> disabled**
  rather than ship a record keyed to the wrong date.
- **`tritonhacks`** -- WRONG in the first pass. Real extraction
  recovers the correct month/day but the wrong year (`2025-05-08` --
  already past even at verification time) because no year appears
  near the dates in the fetched text; the only "2026" on the page is
  an unrelated footer copyright line. Flipped **enabled -> disabled**.
- **`sd-science-olympiad`** -- reconfirmed correct. Real `curl` also
  returns `HTTP:000` (connection-level failure) against
  scilympiad.com, independently of the WebFetch tool. Stays
  **disabled**.
- **`garibaldi-bowl`** -- reconfirmed correct, with a fuller picture:
  the `http://` URL 302-redirects to `https://`, which then genuinely
  404s (not a bare 404 on the http URL as first recorded). Stays
  **disabled**.
- **`cyberpatriot-sd`** -- not re-litigated, per explicit instruction:
  stays **disabled** referencing issue 38.
- **`doe-science-bowl-sd`** -- reconfirmed correct, with a fuller and
  more honest picture: the real extraction recovers a genuine date
  pair, but it is the *registration-window* dates for the already-past
  2025-26 season (`2025-10-06`/`2025-11-24`), not the event date
  itself, so `wrote 0 opportunities` in the dry run (correctly
  filtered by the currency rule). Kept **enabled** -- this matches the
  sprint's own pre-accepted "annual page not yet updated for the new
  cycle" gap (registry/DESIGN.md's sprint 029 addendum), a real
  correctly-parsed date on a reliable federal site expected to
  self-correct via the existing weekly cron, unlike the "no date at
  all" or "wrong date/year" cases above.
- **`congressional-app-challenge-sd`** -- reconfirmed correct and is
  the strongest result in the batch: `found=1 dated=1`, and the ONLY
  source in this whole ticket that currently `wrote 1 opportunity` in
  a live dry run (a genuinely open, correctly-dated, currently-current
  record as of 2026-09-02). Kept **enabled**.

**Final state**: 3 enabled (`doe-science-bowl-sd`,
`congressional-app-challenge-sd`, `cipherhacks`), 9 disabled
(`sd-science-olympiad`, `sdftc-league-play`, `seaperch-sd-regional`,
`mathcounts-sd-chapter`, `garibaldi-bowl`, `sd-brain-bee`,
`botball-greater-sd`, `tritonhacks`, `cyberpatriot-sd`). Every disabled
file carries an accurate reason comment reflecting a real, reproduced
dry-run/curl result, not a WebFetch impression. `tests/test_registry.py`'s
`TestCompetitionSourceConfig._ENABLED_COMPETITION_SOURCES`/
`_DISABLED_COMPETITION_SOURCES` updated to match.

**Test suite**: `uv run pytest tests/test_adapters_program_page.py
tests/test_registry.py` -> 83 passed (unchanged count; only file
content in the reason-substring assertions changed).
Full suite `uv run pytest` -> 2147 passed (matches the ticket's prior
baseline of 2147 -- no tests added or removed by this correction, only
corrected).
