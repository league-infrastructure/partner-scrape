---
id: '004'
title: Adapter framework and The Events Calendar (TEC) REST adapter
status: done
use-cases:
- SUC-003
- SUC-004
depends-on:
- '001'
- '002'
- '003'
github-issue: ''
issue: 02-adapter-framework-structured-apis.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Adapter framework and The Events Calendar (TEC) REST adapter

## Description

Define the pluggable Adapter contract (sprint architecture: Adapter
Framework) and implement the first concrete adapter: The Events
Calendar (TEC) REST API — the highest-quality, best-proven source tier
per `dev/SCRAPER_GUIDELINES.md` (100% dated, structured JSON, no HTML
parsing).

Scope:
- `Adapter` protocol: `discover() -> Iterable[EventRef]`, `fetch(ref) ->
  RawResponse` (delegates to the Fetch & Cache module, ticket 003),
  `extract(raw) -> Event` (constructs a canonical Event, ticket 001's
  model), and a top-level `run(source_config) -> list[Event]` that
  chains the three. For `tec_rest` (and the other structured-API types
  in ticket 005), `discover()` collapses trivially — the API call
  itself is both discovery and fetch, since there's no separate
  "find URLs" step for a REST endpoint (see sprint.md's Deferred Seams:
  this is what leaves `discover()` generalized for future sitemap-diff
  adapters without an interface change).
- A dispatch registry mapping `SourceConfig.adapter_type` to the
  matching `Adapter` implementation.
- The TEC REST adapter itself: probe `{api_base}?per_page=1`,
  paginate via `page`/`total_pages`, map each event's `title`,
  `description`, `start_date`/`end_date`, `venue`, `organizer`, `cost`,
  `categories`, `tags`, `image`, `url`, `all_day` into a canonical
  `Event` via `Event.set(..., source="tec_rest", confidence=...)`.
  Every field this adapter sets gets `confidence=1.0` — TEC's API is
  the highest-trust source this sprint handles.
- Per-record error isolation: a single malformed event in an otherwise
  good API response is logged and skipped, not fatal to the rest of
  that page. (Whole-*source* failure isolation — one source's adapter
  raising an exception — is the Pipeline's job, built in ticket 008;
  this ticket's isolation is at the individual-record level within one
  adapter run.)

## Acceptance Criteria

- [x] `Adapter` protocol and dispatch-by-`adapter_type` registry exist;
      registering a new adapter type is a one-line addition to the
      registry, not a change to the dispatch mechanism.
- [x] Given a recorded TEC API fixture (a realistic multi-page response
      matching the documented shape in `dev/SCRAPER_GUIDELINES.md` §2),
      the TEC adapter emits one `Event` per API event with correct
      `title`, `start`/`end`, `location` (from `venue`), `cost`,
      `registration_url` (from `url`), and `provenance="tec_rest"` with
      `confidence=1.0` on every field it sets.
  - [x] Pagination is followed across `total_pages` until exhausted.
  - [x] `kind` defaults to `"event"` (see sprint.md Open Question 3).
- [x] A malformed individual event record (missing `title`, or
      non-JSON-parseable field) is skipped with a logged warning; the
      rest of that page's events are still emitted.
- [x] An empty API response (`events: []`) yields zero Events and no
      exception.
- [x] All of the above uses the `Fetcher`/cache from ticket 003 with a
      fixture `Fetcher` injected — no real HTTP.

## Implementation Plan

### Approach

`Adapter` as a `typing.Protocol` (mirroring the `Fetcher` protocol
pattern from ticket 003) so the dispatch registry is just
`dict[str, type[Adapter]]`. TEC adapter constructs its `Fetcher` calls
through the injected fetch layer, not directly via `urllib` — this is
what makes it fixture-testable. Reuse the field-mapping knowledge
already proven in `dev/fetch_tec_api.py` (venue/organizer extraction,
`start_date`/`end_date` parsing) as a reference for correctness, but
write it fresh against the canonical `Event` shape rather than the old
flat-dict shape.

### Files to Create/Modify

- `partner_scrape/adapters/__init__.py`
- `partner_scrape/adapters/base.py` (`Adapter` protocol, `EventRef`,
  `RawResponse`, dispatch registry)
- `partner_scrape/adapters/tec.py`
- `tests/test_adapters_base.py` (dispatch registry behavior)
- `tests/test_adapters_tec.py`
- `tests/fixtures/tec/events_page1.json`,
  `tests/fixtures/tec/events_page2.json` (recorded/synthesized TEC API
  response shapes — multi-page, includes one malformed record)

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (tickets 001-003's
  suites).
- **New tests to write**: `tests/test_adapters_base.py` (dispatch by
  `adapter_type`, unknown type raises a clear error);
  `tests/test_adapters_tec.py` (field mapping, pagination, malformed
  record skip, empty response, `kind` default, confidence/provenance
  values).
- **Verification command**: `uv run pytest`
