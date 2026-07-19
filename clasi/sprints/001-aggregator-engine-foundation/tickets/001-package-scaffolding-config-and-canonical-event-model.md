---
id: '001'
title: Package scaffolding, Config, and canonical Event model
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: 01-aggregator-engine-foundation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Package scaffolding, Config, and canonical Event model

## Description

Stand up the `partner_scrape/` package that every later ticket in this
sprint builds on, and define the canonical `Event` record (sprint
architecture: Event Model + Config modules). This ticket touches nothing
in `dev/`, `scraper/`, or `run_mirrors.py` — it is purely additive.

Scope:
- `partner_scrape/` package skeleton, importable via `pyproject.toml`.
- `partner_scrape/config.py`: the single place that reads
  environment-derived configuration (`SCRAPE_CACHE_DIR`, a default
  site-dir path). No other module in this sprint should call
  `os.environ` directly — later tickets import from here.
- `partner_scrape/model.py`: the canonical `Event` dataclass —
  `kind: Literal["event", "program", "internship"]` (default `"event"`),
  identity fields (`source_id`, `external_id`, `url`), content fields
  (`title`, `description`, `start`, `end`, `all_day`, `location`,
  `latitude`, `longitude`, `cost`, `registration_url`, `image_url`,
  `categories`, `tags`), a `field_provenance: dict[str, Provenance]`
  side-car (see sprint.md Design Rationale for why this shape and not a
  per-field wrapper type), and an `Event.set(field, value, source,
  confidence)` helper that sets a field and its provenance atomically.
- Identity-key derivation: `(source_id, external_id)` when `external_id`
  is present, else `(source_id, normalized_title, start_date)`. This is
  the *acquisition* identity (distinct from the cross-source dedup
  identity built in ticket 006) — it answers "have we already seen this
  exact record from this source," not "is this the same event as one
  from another org."
- `pyproject.toml`: add `pytest` as a dev dependency; create the
  `tests/` tree.

## Acceptance Criteria

- [x] `import partner_scrape` succeeds; the package is declared in
      `pyproject.toml`.
- [x] `Config` exposes `SCRAPE_CACHE_DIR` (from the environment) and a
      default site-dir path (`../stem-ecosystem`, overridable).
- [x] `Event` carries `kind` defaulting to `"event"`, plus the content
      fields listed above.
- [x] `Event.set(field, value, source, confidence)` sets both the field
      value and a `Provenance(source, confidence)` entry in
      `field_provenance[field]`; fields never `.set()` have no
      provenance entry.
- [x] Identity-key derivation returns `(source_id, external_id)` when
      `external_id` is truthy, else `(source_id, normalized_title,
      start_date)`.
- [x] An identity/equality helper (not full dataclass `__eq__`, since
      unrelated fields may differ) reports two Events with the same
      identity key as the same record.
- [x] `pytest` is a declared dev dependency and `uv run pytest` runs
      (even if only this ticket's tests exist yet).

## Implementation Plan

### Approach

Plain `@dataclass` for `Event` — no new validation library needed at
this layer since most fields are optional/free-form and adapters (not
this ticket) are responsible for populating them correctly. `Config`
is a thin module-level set of functions/constants reading `os.environ`
once, not a class — there's nothing stateful about it yet. Normalize
`title` for identity-key purposes with a small shared helper (lowercase,
strip punctuation, collapse whitespace) that ticket 006 will reuse for
cross-source dedup — put it in `model.py` next to identity-key
derivation since both are "how do we recognize the same thing" logic.

### Files to Create/Modify

- `pyproject.toml` — add `pytest` (dev dependency group); confirm
  `partner_scrape` is packaged.
- `partner_scrape/__init__.py`
- `partner_scrape/config.py`
- `partner_scrape/model.py`
- `tests/__init__.py`
- `tests/test_model.py`
- `tests/test_config.py`

### Documentation Updates

None required this ticket — there is nothing runnable yet to document.
The README gets a "running the engine" section in ticket 008, once the
CLI exists.

## Testing

- **Existing tests to run**: none — no test suite exists before this
  ticket.
- **New tests to write**: `tests/test_model.py` (field/provenance
  setting via `.set()`, identity-key derivation with and without
  `external_id`, `kind` defaulting, the identity/equality helper);
  `tests/test_config.py` (env var reading via monkeypatched environment,
  default site-dir when unset).
- **Verification command**: `uv run pytest`
