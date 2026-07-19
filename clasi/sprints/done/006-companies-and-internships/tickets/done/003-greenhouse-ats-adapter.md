---
id: '003'
title: Greenhouse ATS adapter
status: done
use-cases:
- SUC-001
depends-on:
- '002'
github-issue: ''
issue: 11-company-events-and-internships.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Greenhouse ATS adapter

## Description

New `partner_scrape/adapters/greenhouse.py` (`GreenhouseAdapter`,
registered as `adapter_type = "greenhouse"` in `adapters/__init__.py`'s
`ADAPTERS` table), mirroring `adapters/tec.py`'s structure (injectable
`Fetcher`, `discover -> fetch -> extract`, per-record error isolation)
but simpler: **Greenhouse's public job-list endpoint is not paginated**
(confirmed live during sprint planning against four real company
boards — `boards-api.greenhouse.io/v1/boards/{token}/jobs` returns every
open job in one response), so `discover()` returns exactly one
`EventRef`, no probe-then-paginate dance like `tec.py`/`localist.py`
need.

Real response shape (confirmed live, e.g.
`https://boards-api.greenhouse.io/v1/boards/gossamerbio/jobs`):
```json
{"jobs": [{"id": 8632329002, "title": "...", "updated_at": "...",
  "location": {"name": "San Diego, California, United States"},
  "absolute_url": "https://...", "content": "<html description>",
  "departments": [{"name": "..."}], "offices": [{"name": "..."}]}]}
```

Field mapping: `external_id` <- `id` (stringified); `title` <- `title`;
`description` <- `content` (HTML — reuse `tec.py`'s `_strip_html`
approach, or extract a shared helper if reuse is clean, but do not
duplicate the regex/entity tables verbatim without checking whether
extracting them to a shared location is warranted — implementer's
call, keep it small); `start` <- parsed `updated_at`; `location` <-
`location.name`; `registration_url` <- `absolute_url`. Every field this
adapter sets is high-trust (`CONFIDENCE = 1.0`), matching `tec.py`'s
convention — it's a structured, first-party feed.

Call `adapters.ats_filters.classify_posting(title, department=...,
location=location.name)` (ticket 002) before constructing an `Event`;
only construct+emit for a match. Apply ticket 002's default
`age_grade_level`/`time_of_day` via `Event.set(...)`; do **not** set
`cost`/`cost_range` (ticket 002's own contract).

`SourceConfig.config` for a `greenhouse` source needs one new key:
`board_token` (e.g. `"gossamerbio"`); optionally `location_keywords`
(list[str], passed through to `ats_filters`).

## Acceptance Criteria

- [x] `GreenhouseAdapter` implements `Adapter` (`discover`, `fetch`,
      `extract`) and is registered in `adapters/__init__.py`'s
      `ADAPTERS["greenhouse"]`.
- [x] `discover()` returns exactly one `EventRef` for
      `{api_base or default board-api URL}/{board_token}/jobs`.
- [x] A fixture board JSON (recorded, not live) with a mix of
      internship/full-time, STEM/non-STEM, and San-Diego/non-San-Diego
      postings yields `Event`s only for postings matching all three
      (via `ats_filters.classify_posting`).
- [x] Every emitted `Event` has `kind="internship"`,
      `source_id=source.source_id`, correct `external_id`/`title`/
      `start`/`location`/`registration_url`/`description`.
- [x] A non-200 or unparseable JSON response is logged and yields zero
      Events, never raises past `extract()` (matches `tec.py`'s
      per-page isolation convention).
- [x] A malformed individual job record (missing title) is skipped, not
      fatal to the rest of the page (matches `tec.py`'s per-record
      isolation).
- [x] `SourceConfig.config["board_token"]` is required; a
      `location_keywords` override is honored when present.
- [x] No test performs a live HTTP call — the fixture JSON is a recorded
      copy of a real response shape (may be adapted from this planning
      pass's live-confirmed `gossamerbio`/`elementbiosciences` boards).

## Testing

- **Existing tests to run**: `test_adapters_tec.py` (pattern reference,
  no behavior overlap — confirms no accidental shared-code regression),
  full `uv run pytest`.
- **New tests to write**: `tests/test_adapters_greenhouse.py` mirroring
  `test_adapters_tec.py`'s structure, backed by a new
  `tests/fixtures/greenhouse/` directory (a realistic recorded board
  JSON with matching and non-matching postings), plus a fixture-`Fetcher`
  non-200/malformed-JSON case.
- **Verification command**: `uv run pytest`
