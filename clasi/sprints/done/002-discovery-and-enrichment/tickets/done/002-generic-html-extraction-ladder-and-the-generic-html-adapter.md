---
id: '002'
title: Generic HTML extraction ladder and the generic_html adapter
status: done
use-cases:
- SUC-009
- SUC-010
depends-on:
- '001'
github-issue: ''
issue: 03-sitemap-discovery-generic-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Generic HTML extraction ladder and the generic_html adapter

## Description

Implement the Generic HTML Extractor (sprint.md Architecture > Generic HTML
Extractor, SUC-010) and the `generic_html` Adapter that composes it with
ticket 001's Sitemap Discovery (SUC-009). This is the second half of issue
03 and completes the first real `Adapter.discover()` implementation end to
end.

Scope:
- Extraction priority ladder, tried in order, each rung only filling
  fields still missing from an earlier rung: JSON-LD `Event` schema (via
  `<script type="application/ld+json">`) → `<time datetime>` elements →
  OpenGraph meta tags → URL/slug-embedded date patterns → body-text date
  regex. Port `dev/extract_events.py`'s proven logic (`extract_json_ld`,
  `extract_time_elements`, `extract_generic`, and the useful parts of its
  BiblioCommons/Drupal/title-date site-specific extractors) as ladder
  strategies in this one module — not bespoke per-site scripts. Use
  `lxml` for HTML parsing (already a declared dependency since sprint 001,
  previously used only by `dev/` — this ticket is what makes it a real
  `partner_scrape` dependency).
- The module returns field values + a confidence tier per field (which
  rung supplied it), not an `Event` — `Event` construction stays the
  adapter's job.
- `partner_scrape/adapters/generic_html.py`: `GenericHtmlAdapter`
  implementing `discover()` (delegates to
  `discovery.sitemap.discover_changed_urls`), `fetch()` (standard
  `fetcher.get(ref.url)`), `extract()` (delegates to the ladder, then
  constructs a canonical `Event` via `Event.set(field, value,
  source="generic_html", confidence=<rung-specific>)` for each recovered
  field). No usable title → drop the record (per-record isolation,
  matching sprint 001's TEC adapter convention).
- Register `ADAPTERS["generic_html"] = GenericHtmlAdapter` in
  `adapters/__init__.py` — the existing one-line extension point, no
  change to `adapters/base.py`.

## Acceptance Criteria

- [x] A JSON-LD fixture page yields a fully-dated Event with every JSON-LD
      field at the highest confidence tier.
- [x] A page with only `<time datetime>` (no JSON-LD) yields a dated Event
      at a lower confidence tier than the JSON-LD case.
- [x] A page with only OpenGraph meta yields title/description but no
      date, at whatever confidence the OG rung sets.
- [x] A page with a URL-embedded date and no other structured signal
      yields a dated Event from the URL pattern alone.
- [x] A page with none of the above but a recognizable body-text date
      string yields a dated Event at the lowest confidence tier.
- [x] A page with no usable title anywhere in the ladder is dropped — not
      emitted as a blank/near-empty Event.
- [x] `ADAPTERS["generic_html"]` resolves via `get_adapter("generic_html")`
      with no change to `adapters/base.py`'s dispatch mechanism.
- [x] Given a fixture sitemap (ticket 001's fixtures or equivalent) plus
      fixture HTML pages, `adapters.run(source, fetcher)` produces the
      expected canonical Events end to end through
      `discover → fetch → extract`.

## Implementation Plan

### Approach

Structure the ladder as an ordered list of strategy functions, each
`(tree, url) -> dict[str, tuple[value, confidence]]` (or equivalent),
applied in priority order with a "fill only what's still empty" merge —
matching `dev/extract_events.py`'s actual `extract_generic` behavior (try
JSON-LD first and return early if it alone is sufficient, else fall
through and fill gaps) rather than a strict first-match-wins. Confidence
values are tier constants (e.g. one constant per rung), not per-field
tuning — stay close to what the ticket's acceptance criteria can actually
distinguish. `GenericHtmlAdapter` itself should stay thin glue, per
sprint.md's Design Rationale on why discovery/extraction are separate
modules from the adapter.

### Files to Create/Modify

- `partner_scrape/extract/__init__.py`
- `partner_scrape/extract/ladder.py`
- `partner_scrape/adapters/generic_html.py`
- `partner_scrape/adapters/__init__.py` (register `generic_html`)
- `tests/test_extract_ladder.py`
- `tests/test_adapters_generic_html.py`
- `tests/fixtures/html/json_ld_event.html`,
  `tests/fixtures/html/time_tag_only.html`,
  `tests/fixtures/html/opengraph_only.html`,
  `tests/fixtures/html/url_date_only.html`,
  `tests/fixtures/html/body_regex_only.html`,
  `tests/fixtures/html/no_title.html`

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite including ticket
  001's new tests — no regressions expected; `adapters/__init__.py`'s
  one-line addition doesn't change existing adapter dispatch).
- **New tests to write**: `tests/test_extract_ladder.py` (one test per
  ladder rung, isolated per the Acceptance Criteria above) and
  `tests/test_adapters_generic_html.py` (adapter-level
  discover→fetch→extract integration using a fixture `Fetcher`, plus
  `ADAPTERS` registration).
- **Verification command**: `uv run pytest`
