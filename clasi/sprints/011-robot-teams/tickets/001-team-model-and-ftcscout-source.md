---
id: '001'
title: Team model and FTCScout source
status: open
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: robot-teams-scrape-locate-and-publish-san-diego-first-teams.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Team model and FTCScout source

## Description

Lay the foundation of the new `partner_scrape/teams/` subsystem: the
`Team` record, the `TeamSource` protocol every acquisition source
implements, and the first concrete source (FTCScout — free, no
credential, 152 San Diego FTC teams). This is the first of two tickets
implementing the issue's increment 1 ("Model + FTCScout + export +
subcommand" — split here because model+source and pipeline+export+CLI
are each a focused unit of work on their own). This ticket produces
`Team` objects from fixtures; it does not yet wire them into a
pipeline, export them, or expose a CLI command — that is ticket 002.

Also creates the subsystem's design doc, `partner_scrape/teams/DESIGN.md`,
since this is the ticket that first creates the `partner_scrape/teams/`
directory (see Documentation below).

Implements SUC-001 (partially — the acquisition half; ticket 002
completes it end to end).

## Acceptance Criteria

- [ ] `partner_scrape/teams/model.py` defines a `Team` dataclass with:
      `team_id` (`"{league}-{number}"`), `league`, `program`, `number`,
      `name`, `organization`, `org_type`, `city`, `postal_code`,
      `latitude`, `longitude`, `location_precision`
      (`school|zip|city|none`), `in_region`, `website`,
      `website_status`, `organization_website`, `rookie_year`,
      `active`, `last_season`, `sponsors`, `org_key`,
      `sibling_team_ids`, `sources`. **No `email` field** — this is a
      structural guarantee, not an omission to remember; there must be
      nowhere to put one.
- [ ] `partner_scrape/teams/sources/base.py` defines a `TeamSource`
      Protocol (`discover`/`fetch`/`extract` → `Team` objects), parallel
      in shape to `adapters.base.Adapter` but **not** registered with
      `adapters.base.ADAPTERS` and not importable as one — verified by
      a test asserting `teams.sources` has no reference into
      `adapters.base`.
- [ ] `partner_scrape/teams/sources/ftcscout.py` implements `TeamSource`
      against FTCScout's REST search endpoint
      (`GET api.ftcscout.org/rest/v1/teams/search?region=USCASD`),
      producing one `Team` per FTC team with `league="FTC"`,
      city-level data at minimum, `organization`/`org_type` from the
      `schoolName` field where present (62% of records).
- [ ] `partner_scrape/teams/registry/ftc-sd.toml` registers the
      FTCScout source, reusing `registry.schema.SourceConfig`/
      `registry.loader.load_active_sources` verbatim (no new schema).
- [ ] `fetch.PoliteFetcher` is the only network path `ftcscout.py` uses
      — no direct `urllib`/`requests` call.
- [ ] Against a canned fixture, `ftcscout.py` produces 152 `Team`
      objects (the issue's measured count) with no network access.
- [ ] `partner_scrape/teams/DESIGN.md` exists at its co-located path,
      following the bootstrap-design subsystem template (see
      Documentation below).

## Implementation Plan

**Approach**: Start from the drafted content at
`clasi/sprints/011-robot-teams/design/new-subsystem/teams-DESIGN.md`
(sprint planning's forward-looking spec) for the module layout, then
build `model.py` → `sources/base.py` → `sources/ftcscout.py` →
`registry/ftc-sd.toml` in that order, since each depends on the one
before it. Study `partner_scrape/adapters/leaguesync.py` as the
reference implementation for a credentialed structured-API source's
shape (`discover`/`fetch`/`extract` split, per-record error isolation)
even though FTCScout itself needs no credential — the *shape* is what
to reuse, not the auth. Use FTCScout's REST endpoint, not GraphQL: the
`Fetcher` protocol is GET-only, and adding `post()` would ripple into
every `FixtureFetcher` test double in the suite for one source's
benefit.

**Files to create**:
- `partner_scrape/teams/__init__.py`
- `partner_scrape/teams/model.py`
- `partner_scrape/teams/sources/__init__.py`
- `partner_scrape/teams/sources/base.py`
- `partner_scrape/teams/sources/ftcscout.py`
- `partner_scrape/teams/registry/ftc-sd.toml`
- `partner_scrape/teams/DESIGN.md`

**Files to modify**: none — this ticket only adds new files.

## Documentation

Write `partner_scrape/teams/DESIGN.md` using
`clasi.design.store.subsystem_template()`'s section structure (Purpose,
Orientation, Constraints and Invariants, Design, Interfaces, Open
Questions/Known Limitations). Start from
`clasi/sprints/011-robot-teams/design/new-subsystem/teams-DESIGN.md`'s
content, but **verify and refresh it against the actual code you
write** in this ticket and note where later tickets (002-005) will
extend it further (merge.py, geo.py, export.py, pipeline.py, the site
pages) rather than presenting the whole subsystem as already built.
This is bootstrap-design's "describe reality, not aspiration" rule —
do not copy the draft verbatim. Run `clasi design validate` after
writing it and fix anything it flags.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — confirms no
  regression; nothing in `partner_scrape/teams/` is imported by any
  existing module).
- **New tests to write**:
  - `tests/teams/test_model.py` — `Team` dataclass construction and
    field defaults; a test asserting no field named or resembling
    `email` exists on the dataclass.
  - `tests/teams/test_sources_ftcscout.py` — extraction against a
    canned FTCScout fixture (`tests/fixtures/teams/ftcscout_search.json`,
    a trimmed but realistic capture of the real endpoint's shape) using
    `FixtureFetcher`; asserts 152 teams, correct `league`/`org_type`
    mapping, and per-record isolation (one malformed record in the
    fixture is skipped, logged, and does not abort the batch).
  - A test asserting `partner_scrape.teams.sources` imports nothing
    from `partner_scrape.adapters.base`.
- **Verification command**: `uv run pytest tests/teams/ && uv run pytest`
