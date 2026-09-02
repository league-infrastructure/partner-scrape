---
id: '003'
title: Build the ProgramPageAdapter for individually-registered program pages
status: done
use-cases:
- SUC-031
depends-on:
- '001'
- '002'
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build the ProgramPageAdapter for individually-registered program pages

## Description

Build the `program_page` adapter type: given one registered program
page URL, fetch it and call the ticket-002 LLM extraction client to
produce a canonical `Event` with deadline-first fields. This is the
end-to-end path SUC-031 describes, exercised by a single-page source
(the ~15 named individual programs in issue 28 — registered by
ticket 005, not this ticket, which only builds and tests the
mechanism against fixtures).

Depends on ticket 001 (needs `PROGRAM_EXTRACTION_KINDS`,
`Event.eligibility` to exist so this adapter can set them correctly)
and ticket 002 (needs `ProgramLLMClient`/`ProgramExtractionCache` to
construct as its defaults).

## Fix shape

1. **`partner_scrape/adapters/program_page.py`** (new):
   - `ProgramPageAdapter(llm_client: ProgramLLMClient | None = None,
     cache: ProgramExtractionCache | None = None)` — constructor
     accepts optional overrides, defaulting to a real
     `AnthropicProgramLLMClient()`/`ProgramExtractionCache()` when
     omitted. See `adapters-DESIGN.md`'s §3 "documented deviation" note
     for why this is safe: `get_adapter()`'s zero-arg construction
     (`base.py`, unchanged) still produces a fully-working production
     instance.
   - `discover(source, fetcher) -> list[EventRef]` — returns exactly
     one `EventRef(url=source.config["url"])`, matching
     `greenhouse.py`/`lever.py`'s "no probe-then-paginate" shape.
   - `fetch(ref, fetcher, source) -> RawResponse` — standard
     `fetcher.get(ref.url, **acquisition_kwargs(source))`, matching
     every other adapter.
   - `extract(raw, source) -> list[Event]` — a non-200 status is
     logged and skipped (returns `[]`), matching `listing_html`'s
     convention. Otherwise: check `self.cache.lookup(raw.ref.url,
     raw.body)`; on a miss, call
     `self.llm_client.extract_program(raw.ref.url, raw.body)` and
     `self.cache.store(...)`. Map the `ProgramExtractionResult` onto a
     new `Event`:
     - `kind` from `source.config["program_kind"]` (`"internship"` or
       `"program"` — required key, raise/log-and-skip on an invalid
       value).
     - `start`/`end` from the result's `date_start`/`date_end` (parsed
       ISO dates; empty string means unset).
     - `eligibility` via `Event.set("eligibility", result.eligibility,
       source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE)`
       when non-empty.
     - `opportunity_type`: if `source.config` sets an explicit
       `opportunity_type` override, use it (via `Event.set(...)`,
       highest confidence — an operator-curated, known value);
       otherwise use `result.opportunity_type` from the LLM extraction
       (via `Event.set(...)`, `PROGRAM_LLM_CONFIDENCE`). Either way,
       `kind == "internship"` still gets its `opportunity_type` forced
       to `Work-based Learning` downstream by `normalize/run.py`,
       unconditionally — this adapter's own `opportunity_type` setting
       only matters for `kind == "program"`.
     - `title`, `description`, `cost`, `registration_url` (=`raw.ref.url`
       unless the result/config supplies a distinct apply link) via
       `Event.set(...)` at `PROGRAM_LLM_CONFIDENCE`.
     - A closed page (`result.is_open is False` and no future
       `date_end`/`date_start` known) is still emitted as an `Event` —
       filtering happens at export time via `is_current_or_upcoming()`,
       not here (this adapter does not re-derive that judgment; see
       `normalize/DESIGN.md`'s sprint 027 addendum).
2. **`partner_scrape/adapters/__init__.py`**: register
   `ADAPTERS["program_page"] = ProgramPageAdapter`, one line, per §3's
   "one-line addition" convention — no change to `base.py`.

## Acceptance Criteria

- [x] `ProgramPageAdapter().discover(source, fetcher)` returns exactly
      one `EventRef` for `source.config["url"]`.
- [x] A `FixtureProgramLLMClient`-backed test proves the full
      discover→fetch→extract chain produces one `Event` with the
      expected `kind`, `start`/`end`, `eligibility`, `opportunity_type`
      fields and correct `field_provenance` entries.
- [x] A second `extract()` call for the same URL+unchanged body makes
      zero further `FixtureProgramLLMClient` calls (cache hit),
      verified via the fixture client's `.calls` count.
- [x] A non-200 fetch is logged and skipped (`extract()` returns `[]`),
      not raised.
- [x] `source.config["program_kind"] = "internship"` produces
      `Event.kind == "internship"`; `"program"` produces
      `Event.kind == "program"`.
- [x] `ADAPTERS["program_page"]` resolves via `get_adapter("program_page")`
      to a working, zero-arg-constructed instance (proves the
      constructor-default deviation doesn't break dispatch).
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite, especially
  `tests/test_adapters_base.py` (dispatch table).
- **New tests to write**: `tests/test_adapters_program_page.py` — per
  Acceptance Criteria above, following `tests/test_adapters_lever.py`/
  `tests/test_adapters_listing_html.py`'s existing structure (direct
  adapter construction and `.extract()` calls, not through
  `adapters.run()`, matching every existing adapter test's own
  convention).
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Build the adapter against ticket 002's already-tested
`ProgramLLMClient`/`ProgramExtractionCache` Protocols using
`FixtureProgramLLMClient` throughout — no live network or API call at
any point in this ticket's own tests.

**Files to create/modify**:
- `partner_scrape/adapters/program_page.py` (new)
- `partner_scrape/adapters/__init__.py` — one-line `ADAPTERS` registration
- `tests/test_adapters_program_page.py` (new)

**Testing plan**: see Testing above.

**Documentation updates**: None — `adapters-DESIGN.md`'s sprint 027
section already documents this adapter's shape in full.

## Notes

- The Fix shape's field list ("title, description, cost,
  registration_url ... via Event.set(...)") names a `description`
  mapping, but ticket 002's already-landed `ProgramExtractionResult`
  (`adapters/program_llm.py`) has no `description` output field — only
  `program_name`, `audience_grades`, `date_start`, `date_end`, `cost`,
  `eligibility`, `is_open`, `opportunity_type`. Since modifying that
  dataclass/schema is outside this ticket's file scope (only
  `program_page.py` and `__init__.py`'s one-line registration) and no
  acceptance criterion tests `Event.description`, this implementation
  leaves `Event.description` unset for a `program_page` record rather
  than inventing a source for it. `title`/`cost`/`registration_url` are
  all set via `Event.set(...)` at `PROGRAM_LLM_CONFIDENCE` as specified.
- `registration_url` supports an optional `source.config["apply_url"]`
  override (falling back to the fetched page's own URL) per the Fix
  shape's "unless the result/config supplies a distinct apply link" —
  no registry ticket currently sets this key; it is forward-looking,
  documented-but-unused surface, harmless to add now.
