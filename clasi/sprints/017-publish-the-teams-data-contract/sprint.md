---
id: '017'
title: Publish the Teams Data Contract
status: executing
branch: sprint/017-publish-the-teams-data-contract
use-cases: []
issues:
- 42-publish-teams-json-and-llms-mention.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 017: Publish the Teams Data Contract

## Goals

Publish the existing `teams.json` dataset into the same statically-served,
self-describing public data contract (`public/data/`) that `partners.json`
and per-partner events already use, and make it discoverable through the
existing `llms.txt`/data-access/for-agents discovery surfaces — so an
external consumer never needs source code or tribal knowledge to find San
Diego's FIRST/VEX robotics teams data.

## Problem

`teams/export.py` writes `teams.json` only to `{site_dir}/src/data/teams.json`
— a build-time input the Astro site consumes, not a publicly fetchable
file. The statically-served public contract (`public/data/` — `partners.json`
+ per-partner events, built by `export/publish.py`, issue 15) does not
include teams at all, and the discovery surfaces sprint 010 built
(`site/public/llms.txt`, `data-access.astro`, `for-agents.astro`) describe
only partner/event data. A consumer who follows the documented discovery
path today never learns `teams.json` exists.

## Solution

Teach `teams/export.py` a second write target — `{site_dir}/public/data/teams.json`,
the identical payload already written to `src/data/teams.json` — and extend
the three discovery surfaces to describe it. `site/` (this repo's beta
checkout) only; the sibling production checkout's parity is issue 41.

## Success Criteria

- A `partner-scrape teams` run against `site/` writes an identical payload
  to both `src/data/teams.json` and `public/data/teams.json`.
- `site/public/llms.txt`'s Data section lists `teams.json` with its
  absolute URL.
- `site/src/pages/data-access.astro` documents the `teams.json` envelope
  and every `Team` field.
- `site/src/pages/for-agents.astro`'s fetch sequence includes `teams.json`,
  deferring the field list to `/data-access` (no duplication, matching its
  existing Design Rationale D2).
- All new/changed behavior covered by hermetic tests; full suite green.

## Scope

### In Scope

- `partner_scrape/teams/export.py`: second write target,
  `{site_dir}/public/data/teams.json`.
- `site/public/llms.txt`: a Data bullet for `teams.json`.
- `site/src/pages/data-access.astro`: a new section documenting the
  `teams.json` envelope and the full `Team` field reference.
- `site/src/pages/for-agents.astro`: `teams.json` added to the fetch
  sequence, linking to `/data-access` for the field list.
- Hermetic tests for all of the above.

### Out of Scope

- Sibling production `stem-ecosystem` repo parity (issue 41).
- Any change to `teams.json`'s payload shape, envelope, or field set —
  already self-describing per sprint 011's `meta` envelope; no new
  envelope work needed (per issue 42).
- Any change to `export/publish.py`, `export/writer.py`, or `mirror.py` —
  the new file rides `mirror.py`'s existing recursive `public/data/` copy
  unchanged (see Architecture below).
- Joining `teams.json` to the curated partner directory — an open product
  question (`docs/design/design.md` §6), unrelated to this sprint.

## Test Strategy

Hermetic, matching project convention (no network). `tests/teams/test_export.py`
gains coverage for the second write target: payload identity between the
two written files, directory creation when `public/data/` doesn't yet
exist in a checkout, `dry_run` touching neither file, and a fail-loud
`RuntimeError` on an unwritable `public/data` path — without disturbing
the existing byte-identical-`opportunities.json`/`scrape-meta.json`
regression tests. A new schema-drift guard test, mirroring
`tests/test_site_data_access_page.py`'s existing precedent for
`SITE_SCHEMA_FIELDS`, asserts every `TEAMS_SCHEMA_FIELDS` name appears in
`data-access.astro`'s new section. Lightweight substring assertions
confirm `llms.txt` and `for-agents.astro` mention `teams.json` — no new
test infrastructure, following the existing per-page precedent (issue 42's
own verification note: "content assertions if the existing test suite
covers those pages").

## Architecture

**Compact** — one module changed (`teams/export.py` gains a second write
target); the remaining changes are static documentation content
(`llms.txt`, two Astro pages), not code modules. No new cross-module
dependency, no dependency-direction change, no data-model change.

### Architecture Overview

`export_teams()` (`partner_scrape/teams/export.py`) is already `teams/`'s
single publish entry point and already builds the full `{"meta": ...,
"teams": [...]}` payload before writing it once, to `{site_dir}/src/data/teams.json`.
This sprint adds one more write of that same, already-built payload to
`{site_dir}/public/data/teams.json`, inside the same function call —
"one publish, two paths," not a new responsibility. Unlike the existing
`src/data` write (which assumes the directory already exists and fails
loudly if not), the new `public/data` write creates its target directory
if missing (`mkdir(parents=True, exist_ok=True)`), since `public/data/`
is not guaranteed to exist in every checkout until the opportunities
pipeline's `export/publish.py::project()` has run at least once there
(the same gap `data-access.astro`'s own Design Rationale D3 already
documents). No other module changes: `export/publish.py`, `export/writer.py`,
and `mirror.py` are untouched. `mirror.py` already recursively copies the
entire `public/data/` tree into extra site checkouts (sprint 009); the new
`public/data/teams.json` rides that existing copy with zero `mirror.py`
change — separate from, and not to be confused with, `mirror.py`'s existing
flat `MIRRORED_DATA_FILES` entry for `teams.json` (sprint 011), which
still governs the unrelated `src/data/teams.json` copy.

### Design Rationale

**Decision: where the public copy of `teams.json` gets written.**

**Context:** Issue 42 flags that `teams.json` already exists as a
build-time input but is absent from the publicly-served, self-describing
`public/data/` contract `export/publish.py` builds for partners/events.
Any fix must respect the existing structural invariant both `teams/DESIGN.md`
and `export/DESIGN.md` state today: `teams/` and `export/` share no import
in either direction (`teams/` reuses only `registry/`, `fetch/`, `config.py`,
and one `normalize/partners.py` function; `export/` depends only on
`normalize/`).

**Alternatives considered:**
1. *Project it at publish time, inside `export/publish.py`* — mirroring
   how `project()` already assembles `partners.json`/`events.json`. This
   was rejected: getting `Team` data into `publish.py` would need either
   (a) importing `teams/` internals, a genuinely new dependency edge
   (`export/` → `teams/`) that has never existed and that both subsystems'
   docs describe as deliberately absent; or (b) having `publish.py` read
   and re-copy the already-written `src/data/teams.json` file off disk,
   which avoids a Python import but adds a silent *ordering* dependency
   (a stale or missing `teams.json` if `publish.project()` runs before
   any `teams` run has ever populated `site_dir`) and duplicates the
   "copy this file by name" responsibility `mirror.py` already owns. It
   also runs at the wrong cadence: `publish.project()` is sequenced after
   the weekly opportunities `run`, while teams data refreshes roughly
   yearly — coupling the public teams write to the opportunities cadence
   would mean a stale-teams-data run silently re-publishing nothing new,
   or worse, a `public/data/teams.json` that only updates when someone
   happens to run the unrelated opportunities pipeline afterward.
2. *Teach `teams/export.py` a second write target* (chosen). `export_teams()`
   already owns the payload and is `teams/`'s sole publish entry point;
   writing it to both locations in the same call keeps the public write
   atomic with the one process that actually produces fresh team data,
   adds no cross-module dependency in either direction, and gets automatic
   mirroring for free (see Architecture Overview).

**Why this choice:** Option 2 preserves the load-bearing structural
independence both subsystem docs assert, keeps "publish" a single,
atomic operation scoped to the process that owns the data, and requires
zero changes to `export/`. Option 1 would have made `export/` reach into
a subsystem it structurally never has, or invented a same-named
file-copy responsibility `mirror.py` already discharges — coupling for
no benefit.

**Consequences:** `export/publish.py` and `export/DESIGN.md` need no
changes at all this sprint. The only downside is that `export_teams()`
now has two side effects instead of one; this is judged acceptable
because both effects are "write the same finished payload," not two
different judgments, and the function's docstring already frames it as
"the Teams pipeline's single publish entry point" — this sprint makes
that entry point publish to both of its two legitimate audiences (the
Astro build, and the public internet) rather than adding a second entry
point.

### Migration Concerns

None for existing data or consumers. `src/data/teams.json`'s existing
consumers (the Astro build, `site/src/pages/teams/*`) are unaffected —
same payload, same location, unchanged. `public/data/teams.json` is a
purely additive new file; a checkout whose `public/data/` directory does
not yet exist gets it created on the next `teams` run rather than
failing. No data migration, no schema change, no backward-compatibility
concern — `teams.json`'s shape (envelope + fields) is byte-for-byte the
same as what already ships today.

## Use Cases

### SUC-001: Consumer fetches the published teams data contract
Parent: UC-006

- **Actor**: External developer, script, or LLM agent consuming the
  site's public data contract (the same class of actor SUC-002/SUC-003 in
  sprint 010 already serve for partner/event data).
- **Preconditions**: `partner-scrape teams` has run at least once against
  this `site_dir`.
- **Main Flow**:
  1. Consumer reads `site/public/llms.txt`'s Data section (or arrives
     directly at `/data-access` or `/for-agents`).
  2. Consumer `GET`s `{DATA_ORIGIN}/data/teams.json`.
  3. Consumer receives the self-describing `meta` + `teams[]` payload —
     identical to the existing `src/data/teams.json` build input, with no
     other data source needed to interpret it.
- **Postconditions**: Consumer has reconstructed the full teams directory
  (id, league, grade band, organization, location + precision, status,
  sponsors) with no source code, API key, or tribal knowledge — matching
  the existing partners/events promise.
- **Acceptance Criteria**:
  - [ ] `public/data/teams.json` exists after a `teams` run and is
        byte-identical to `src/data/teams.json`.
  - [ ] `site/public/llms.txt`'s Data section lists `teams.json` with its
        absolute URL.
  - [ ] `site/src/pages/data-access.astro` documents the envelope and the
        full `Team` field list.
  - [ ] `site/src/pages/for-agents.astro`'s fetch sequence includes
        `teams.json`, without duplicating the field list already on
        `/data-access`.

## GitHub Issues

(None linked yet — this sprint tracks CLASI issue 42 only.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Publish teams.json into the public data contract | — |
| 002 | Document teams.json across the discovery surfaces | 001 |

Tickets execute serially in the order listed.
