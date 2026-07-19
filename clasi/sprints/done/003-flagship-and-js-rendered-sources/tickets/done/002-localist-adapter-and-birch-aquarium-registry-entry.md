---
id: '002'
title: Localist adapter and Birch Aquarium registry entry
status: done
use-cases:
- SUC-013
depends-on: []
github-issue: ''
issue: 06-flagship-adapters-fleet-birch.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Localist adapter and Birch Aquarium registry entry

## Description

Build a new `localist` adapter type (`partner_scrape/adapters/localist.py`)
converting UCSD Localist calendar events, filtered to one `group_id`,
into canonical Events — following `adapters/tec.py`'s proven single-file
shape (trivial discovery = a paginated API probe; no separate discovery
module needed, see sprint.md's Architecture > Localist Adapter). Register
`ADAPTERS["localist"] = LocalistAdapter` in `adapters/__init__.py` (one
line, matching the existing pattern; no change to `adapters/base.py`).

Register the real `birch-aquarium.toml` source under
`partner_scrape/registry/sources/`, using values confirmed live during
sprint planning:
- `org_name = "Birch Aquarium at Scripps"`
- `adapter_type = "localist"`
- `config.api_base = "https://calendar.ucsd.edu/api/2/events"`
- `config.group_id = "49845193640602"`
- `config.days` / `config.pp`: use a generous window (sprint.md proposes
  `days=180, pp=50`, per Open Question 3 — confirm with team-lead/
  stakeholder if a different window is wanted before finalizing) so
  Site Export's own current/upcoming filter does the real date-relevance
  trimming downstream, matching TEC's `start_date=now`-then-filter
  precedent.

**Critical implementation detail — must not be missed**: the Localist API
returns one row per matching *day* for a recurring event, not one row per
event. Confirmed live: a single Birch "Shark Summer" event
(`id=52950294007943`) appeared as 9 separate rows across a `days=180`
window, all sharing that same `id`. `extract()` must deduplicate by the
API's own `id` within one fetched page before constructing Events, or
this adapter will emit many duplicate Events for the same underlying
occurrence. (Normalize & Dedup's existing recurring-instance collapse is
a second line of defense, but this adapter should not rely on it as the
primary mechanism — see sprint.md's Design Rationale.)

Field mapping (structured, first-party feed — use confidence `1.0`,
matching TEC's `CONFIDENCE` convention):
- `title` → `title`
- `description_text` (already plain text, unlike TEC's HTML
  `description` — no HTML-stripping helper needed here) → `description`
- `first_date` / `last_date` (date-only ISO strings) → `start` / `end`
- `location_name` (+ `room_number` if present) → `location`
- `ticket_cost` → `cost`
- `url` (the event's own canonical page; `.strip()` it — a live-captured
  sample had a trailing space) → `registration_url`; if empty, fall back
  to `https://calendar.ucsd.edu/event/{urlname}`
- `id` → `external_id` (as `str`)
- `tags` → `tags`; `keywords` → `categories` (or fold both into `tags` —
  implementer's call, document whichever is chosen)

## Acceptance Criteria

- [x] `LocalistAdapter` implements the `Adapter` protocol
      (`discover`/`fetch`/`extract`) and is registered as
      `ADAPTERS["localist"]`.
- [x] Given a recorded/synthesized Localist API fixture containing the
      same event `id` repeated across multiple daily-occurrence rows
      (mirroring the live-captured shape), `extract()` emits exactly one
      Event for that `id`.
- [x] Given a fixture page, the adapter emits Events with correct
      title/date-range/location/cost/registration-url and
      `field_provenance[...] .source == "localist"`, confidence `1.0`.
- [x] `discover()` paginates using the API's own `page`/`total` fields
      (matching TEC's `total_pages` probe pattern), not a single
      hardcoded page.
- [x] A malformed or empty fixture response yields zero Events and a
      logged warning, not an exception that kills the run (per-source
      isolation, matching every other adapter).
- [x] `birch-aquarium.toml` is added under
      `partner_scrape/registry/sources/`, loads successfully via
      `SourceConfig.from_toml`, and round-trips through
      `registry.load_active_sources()`.
- [x] `pyproject.toml`/existing dependencies are unaffected (this ticket
      needs no new runtime dependency — the Localist API is plain JSON
      over the existing `Fetcher`).

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_tec.py
  tests/test_registry.py` (confirm the established adapter/registry test
  patterns this ticket follows still pass).
- **New tests to write**: `tests/test_adapters_localist.py` — fixture-based
  tests for pagination, field mapping, the id-dedup-within-page
  requirement (the critical case), and malformed/empty-response handling.
  Extend or add to `tests/test_registry.py` to confirm
  `birch-aquarium.toml` loads.
- **Verification command**: `uv run pytest`
