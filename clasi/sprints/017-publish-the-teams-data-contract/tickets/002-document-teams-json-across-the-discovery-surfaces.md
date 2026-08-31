---
id: '002'
title: Document teams.json across the discovery surfaces
status: open
use-cases: [SUC-001]
depends-on: ['001']
github-issue: ''
issue: 42-publish-teams-json-and-llms-mention.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Document teams.json across the discovery surfaces

## Description

Once `teams.json` is part of the public `public/data/` contract (ticket
001), the three existing discovery surfaces sprint 010 built need to
describe it, so the `llms.txt` → data-access/for-agents promise of "no
other data source needed" stays true for a consumer who arrives via
those pages:

1. **`site/public/llms.txt`** — add a Data bullet for `teams.json`,
   following the existing `partners.json` bullet's format: a one-line
   description ("FIRST/VEX robotics teams directory for San Diego
   County: id, league, grade band, organization, location w/ precision,
   status, sponsors") and its absolute URL,
   `https://league-infrastructure.github.io/partner-scrape/data/teams.json`
   (matching `DATA_ORIGIN` in `for-agents.astro` and the existing
   `partners.json` bullet's URL convention).
2. **`site/src/pages/data-access.astro`** — add a new section (after the
   existing event field reference, before the Worked Example section, or
   as its own "File 3" section following the page's existing "File 1" /
   "File 2" numbering convention) documenting: the envelope shape
   (`meta.generated`, `meta.total`, `meta.by_league`,
   `meta.by_location_precision`, `meta.out_of_region`) and the full
   `Team` field reference (every name in
   `partner_scrape.teams.export.TEAMS_SCHEMA_FIELDS`), in the same
   two-column table format the existing event field reference uses. A
   short worked example (one trimmed `teams.json` entry) is optional but
   recommended for consistency with the page's existing worked-example
   convention — keep it small, do not pad.
3. **`site/src/pages/for-agents.astro`** — add a third fetch step to the
   Data section's code block: `GET {DATA_ORIGIN}/data/teams.json` with
   its one-line envelope shape, matching the terse style of the existing
   two `partners.json`/events steps. Per the page's own Design Rationale
   D2 ("never duplicate the field table"), do **not** repeat the full
   `Team` field list here — link to `/data-access` for it, matching how
   the existing steps already defer to that page.

This ticket is documentation-only — no `partner_scrape/` Python changes
beyond what ticket 001 already made (this ticket only *reads*
`TEAMS_SCHEMA_FIELDS` for its test).

## Acceptance Criteria

- [ ] `site/public/llms.txt` lists `teams.json` under `## Data` with the
      absolute URL above and a one-line description matching issue 42's
      language.
- [ ] `site/src/pages/data-access.astro` documents the `teams.json`
      envelope fields and every name in
      `partner_scrape.teams.export.TEAMS_SCHEMA_FIELDS`.
- [ ] `site/src/pages/for-agents.astro`'s Data code block includes a
      `teams.json` fetch step and does not repeat the full field list
      (still links to `/data-access` for it).
- [ ] A new hermetic test, mirroring `tests/test_site_data_access_page.py`'s
      existing `SITE_SCHEMA_FIELDS` guard, asserts every
      `TEAMS_SCHEMA_FIELDS` name appears in `data-access.astro`'s source
      text.
- [ ] Lightweight hermetic tests confirm `llms.txt` and `for-agents.astro`
      each mention `teams.json` (substring-level; no new test
      infrastructure beyond the existing per-page precedent).
- [ ] Full test suite green (`uv run pytest`).

## Testing

- **Existing tests to run**: `uv run pytest tests/test_site_data_access_page.py`
  and the full suite (`uv run pytest`).
- **New tests to write**:
  - Extend or add alongside `tests/test_site_data_access_page.py`: every
    `partner_scrape.teams.export.TEAMS_SCHEMA_FIELDS` name appears in
    `data-access.astro`'s source text (same pattern as the existing
    `SITE_SCHEMA_FIELDS` guard — read the file, assert substring
    presence for each field name).
  - A test asserting `site/public/llms.txt`'s source text contains
    `"teams.json"` and the exact published URL.
  - A test asserting `site/src/pages/for-agents.astro`'s source text
    contains `"teams.json"`.
- **Verification command**: `uv run pytest`
