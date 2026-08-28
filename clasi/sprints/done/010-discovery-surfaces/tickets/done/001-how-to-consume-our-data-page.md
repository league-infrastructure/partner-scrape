---
id: '001'
title: Data-access page - how to consume our data
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: 16-llms-txt-and-agent-discovery-pages.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Data-access page - how to consume our data

## Description

Create `site/src/pages/data-access.astro`, a human-and-agent-readable
page documenting the shape of sprint 009's published `public/data/`
contract (`partners.json` roster plus per-partner `events.json`/
`past-events.json`) and the "given `partners.json` plus a partner's
event files, no other data source is needed" reconstruction contract.
This is the canonical schema documentation the other three tickets'
pages link to rather than duplicate (sprint.md Architecture > Design
Rationale D2, D3). Implements SUC-002.

## Acceptance Criteria

- [x] `site/src/pages/data-access.astro` exists at `/data-access`, uses
      `BaseLayout` (`title`/`description` props) matching
      `about.astro`'s/`contact.astro`'s existing structure.
- [x] Documents the two-file shape: `public/data/partners.json`
      (`generated_at`/`partner_count` envelope; each partner's `slug`,
      `events_url`, `past_events_url`) and per-partner
      `partners/<slug>/events.json` / `past-events.json` (each with a
      `generated_at`/`partner_slug`/`kind`/`event_count`/`events`
      envelope).
- [x] Documents every field name in `export.writer.SITE_SCHEMA_FIELDS`
      (the event record shape) — verified by the new pytest guard (see
      Testing).
- [x] States the reconstruction contract explicitly in prose: given
      `partners.json` plus each referenced partner's event files, no
      other data source is needed to reproduce the site's opportunity
      data.
- [x] Includes one hand-authored, static worked example of a trimmed
      `partners.json` entry and a matching `events.json` entry — never
      a live client-side fetch (Design Rationale D3).
- [x] Page renders correctly under both `just dev` and `just build`.

## Implementation Plan

**Approach**: Follow `about.astro`'s existing structure (`BaseLayout` +
`.container`-wrapped sections with `<h2>` subheadings) for visual
consistency — no new layout/component is needed. Read
`partner_scrape/export/writer.py`'s `SITE_SCHEMA_FIELDS` and
`partner_scrape/export/publish.py`'s envelope shapes directly (do not
guess) to write an accurate schema description. Hand-author one small,
realistic worked-example JSON snippet per file kind — do not attempt to
read a real generated file; `site/public/data/` does not currently
exist in this checkout (confirmed during sprint planning).

**Files to create**:
- `site/src/pages/data-access.astro`

**Files to modify**: none (the footer link is added in ticket 004,
after this page's URL is settled).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — confirms
  nothing in `partner_scrape/` regresses; none should, since no
  production code changes).
- **New tests to write**: a new test (e.g.
  `tests/test_site_data_access_page.py`) that reads
  `site/src/pages/data-access.astro`'s source text and asserts every
  name in `partner_scrape.export.writer.SITE_SCHEMA_FIELDS` appears in
  it as a substring — the sprint's one schema-drift guard (sprint.md's
  Test Strategy).
- **Verification command**: `uv run pytest tests/test_site_data_access_page.py`
  plus `just build` (or `cd site && npm run build -- --base /partner-scrape`)
  to confirm the page builds.
