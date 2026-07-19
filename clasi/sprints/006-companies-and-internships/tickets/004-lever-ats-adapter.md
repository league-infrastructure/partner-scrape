---
id: '004'
title: Lever ATS adapter
status: done
use-cases:
- SUC-002
depends-on:
- '002'
github-issue: ''
issue: 11-company-events-and-internships.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Lever ATS adapter

## Description

New `partner_scrape/adapters/lever.py` (`LeverAdapter`, registered as
`adapter_type = "lever"`), mirroring `adapters/tec.py`'s structure the
same way ticket 003's `GreenhouseAdapter` does. **Lever's public
postings endpoint is also not paginated** (confirmed live during sprint
planning against `api.lever.co/v0/postings/shieldai?mode=json` — 8
postings returned in one response) — `discover()` returns exactly one
`EventRef`.

Real response shape (confirmed live): a **top-level JSON array**, not an
object with a `jobs` key (the one structural difference from
Greenhouse/TEC/Localist worth flagging explicitly in the implementation
— a bare `json.loads(raw.body)` result to iterate directly, not
`.get("jobs", [])`):
```json
[{"id": "41468aca-...", "text": "Aerostructures Design Engineer II",
  "categories": {"location": "United States",
    "commitment": "Full Time Employee", "team": "...", "department": "..."},
  "descriptionPlain": "...", "hostedUrl": "https://...",
  "applyUrl": "https://...", "createdAt": 1234567890000}]
```

Field mapping: `external_id` <- `id`; `title` <- `text`; `description`
<- `descriptionPlain`; `start` <- `createdAt` (epoch **milliseconds** —
divide by 1000 before `datetime.fromtimestamp`); `location` <-
`categories.location`; `registration_url` <- `applyUrl`, falling back to
`hostedUrl` if `applyUrl` is absent. `categories.commitment` is an
**additional** internship signal to pass into
`ats_filters.classify_posting` alongside the title (Lever's `commitment`
field often says "Intern"/"Internship" directly, a stronger signal than
title-regex alone — see sprint.md's SUC-002 Main Flow step 2). Every
field this adapter sets is high-trust (`CONFIDENCE = 1.0`).

Call `adapters.ats_filters.classify_posting(...)` (ticket 002) before
constructing an `Event`; only construct+emit for a match. Same
`age_grade_level`/`time_of_day` defaults as ticket 003; do **not** set
`cost`/`cost_range`.

`SourceConfig.config` for a `lever` source needs one new key: `company`
(the Lever company slug, e.g. `"shieldai"`); optionally
`location_keywords`.

## Acceptance Criteria

- [x] `LeverAdapter` implements `Adapter` and is registered in
      `adapters/__init__.py`'s `ADAPTERS["lever"]`.
- [x] `discover()` returns exactly one `EventRef` for
      `{api_base or default Lever postings URL}/{company}?mode=json`.
- [x] `extract()` correctly parses a **top-level JSON array** response
      (not a `{"jobs": [...]}` wrapper) — a fixture test specifically
      proves this, since it's the one shape difference from every other
      adapter in this codebase.
- [x] A fixture board JSON with a mix of internship/full-time (via
      `categories.commitment`), STEM/non-STEM, and San-Diego/non-San-
      Diego postings yields `Event`s only for postings matching all
      three.
- [x] Every emitted `Event` has `kind="internship"`,
      `source_id=source.source_id`, correct `external_id`/`title`/
      `start` (correctly converted from millisecond epoch)/`location`/
      `registration_url`/`description`.
- [x] A non-200 or unparseable JSON response is logged and yields zero
      Events, never raises past `extract()`.
- [x] A malformed individual posting record (missing `text`/title) is
      skipped, not fatal to the rest of the response.
- [x] `applyUrl` is preferred over `hostedUrl` when both are present; a
      posting with only `hostedUrl` still gets a usable
      `registration_url`.
- [x] `SourceConfig.config["company"]` is required; a `location_keywords`
      override is honored when present.
- [x] No test performs a live HTTP call.

## Testing

- **Existing tests to run**: `test_adapters_tec.py` (pattern reference),
  full `uv run pytest`.
- **New tests to write**: `tests/test_adapters_lever.py` mirroring
  `test_adapters_tec.py`'s structure, backed by a new
  `tests/fixtures/lever/` directory (a realistic recorded top-level-array
  board JSON with matching and non-matching postings, including at least
  one posting with `categories.commitment` explicitly containing
  "Intern"), plus a fixture-`Fetcher` non-200/malformed-JSON case.
- **Verification command**: `uv run pytest`
