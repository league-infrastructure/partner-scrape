---
id: '002'
title: 'Source Registry: schema, TOML loader, and seed data'
status: done
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
issue: 01-aggregator-engine-foundation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Source Registry: schema, TOML loader, and seed data

## Description

Build the Source Registry module: the data-driven catalog of
organizations and how to reach their events (sprint architecture:
Source Registry). Adding a source must be a data edit (one new TOML
file), not a code change.

Scope:
- `SourceConfig` schema: `source_id`, `org_name`, `adapter_type`
  (`"tec_rest"` | `"wp_rest"` | `"ical"` this sprint), `config` (an
  adapter-specific table — e.g. `api_base` for `tec_rest`, `feed_url`
  for `ical`), `taxonomy_defaults` (optional hints normalize can fall
  back on), `acquisition_policy` (`rate_limit_seconds`,
  `respect_robots`, `discovered_via`), `enabled`.
- A loader that globs `partner_scrape/registry/sources/*.toml`, parses
  each with the stdlib `tomllib` (zero new dependency — see sprint.md
  Design Rationale for why TOML/stdlib over YAML/JSON), validates
  required fields, and returns the list of valid `SourceConfig`
  objects. A malformed or missing-required-field file is logged and
  skipped — never fatal to the whole load.
- Seed data: one TOML file per known TEC site, reusing the exact
  `organization` names and `api_base` URLs already verified working in
  `dev/fetch_tec_api.py`'s `TEC_SITES` list (coastalrootsfarm.org,
  thelivingcoast.org, eefkids.org, cleansd.org/ilacsd, oceanconnectors.org,
  visitcmod.org/sdcdm.org) — see sprint.md Open Question 1; this ticket
  proceeds on the "seed with real data" resolution.

## Acceptance Criteria

- [x] Loading `partner_scrape/registry/sources/` returns one validated
      `SourceConfig` per well-formed file.
- [x] A source file missing a required field (e.g. no `adapter_type`) is
      skipped with a logged warning; loading the rest of the directory
      still succeeds.
- [x] `enabled: false` entries are excluded from the loader's default
      "active sources" result but are still parseable (so disabling a
      source is a one-line edit, not a file deletion).
- [x] The seed directory contains six TOML files for the known TEC
      sites, each with the correct `organization`/`api_base` pair
      carried over from `dev/fetch_tec_api.py`.
- [x] Loading the real seed directory produces six valid, enabled
      `SourceConfig` objects with `adapter_type == "tec_rest"`.

## Implementation Plan

### Approach

`tomllib.load()` per file (binary mode, as `tomllib` requires); build
`SourceConfig` as a `@dataclass` mirroring the schema, with a small
`from_toml(path) -> SourceConfig` constructor that raises a specific
`InvalidSourceConfig` exception on a missing required field, which the
directory-level loader catches, logs, and skips — so "one bad file
doesn't break the load" is enforced at the loader level, not left to
each caller. Keep `config`/`taxonomy_defaults`/`acquisition_policy` as
plain `dict`s (not further-typed sub-schemas) — different
`adapter_type`s need different shapes there, and over-typing it now
would need revisiting the moment a fourth adapter type arrives.

### Files to Create/Modify

- `partner_scrape/registry/__init__.py`
- `partner_scrape/registry/schema.py` (`SourceConfig`,
  `InvalidSourceConfig`)
- `partner_scrape/registry/loader.py` (directory loader)
- `partner_scrape/registry/sources/coastalrootsfarm.toml`
- `partner_scrape/registry/sources/thelivingcoast.toml`
- `partner_scrape/registry/sources/eefkids.toml`
- `partner_scrape/registry/sources/cleansd.toml`
- `partner_scrape/registry/sources/oceanconnectors.toml`
- `partner_scrape/registry/sources/visitcmod.toml`
- `tests/test_registry.py`
- `tests/fixtures/registry/` (a small directory of synthetic
  well-formed and malformed TOML files, separate from the real seed
  data, so loader tests don't depend on the production registry's exact
  contents)

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (ticket 001's suite — must
  keep passing).
- **New tests to write**: `tests/test_registry.py` against
  `tests/fixtures/registry/` — valid-directory load, malformed-file
  skip-and-continue, `enabled: false` exclusion from the active list;
  plus one test loading the real `partner_scrape/registry/sources/`
  directory and asserting six enabled `tec_rest` sources come back.
- **Verification command**: `uv run pytest`
