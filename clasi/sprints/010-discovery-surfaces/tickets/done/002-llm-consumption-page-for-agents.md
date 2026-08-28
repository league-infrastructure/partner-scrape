---
id: '002'
title: LLM consumption page (for-agents)
status: done
use-cases:
- SUC-003
depends-on:
- '001'
- '003'
github-issue: ''
issue: 16-llms-txt-and-agent-discovery-pages.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# LLM consumption page (for-agents)

## Description

Create `site/src/pages/for-agents.astro`, a terse, link-dense landing
page for an LLM/agent that followed `llms.txt`. States the exact data
URLs directly (self-sufficient if reached without `llms.txt`), links to
`/data-access` for the full schema (never duplicates it — Design
Rationale D2), and links to `/publish-events` — satisfying issue 16's
"must link to the publication page" requirement, since issue 17's page
ships in this same sprint (ticket 003). Implements SUC-003.

## Acceptance Criteria

- [x] `site/src/pages/for-agents.astro` exists at `/for-agents`, uses
      `BaseLayout`.
- [x] Opens with a short, dense statement of the site's purpose and
      available data — no marketing prose.
- [x] States the exact data URLs (`partners.json`, the
      `events.json`/`past-events.json` URL pattern) directly on the
      page, matching what `llms.txt`'s Data section states (ticket
      004) — this page must stand alone if reached directly, not only
      via `llms.txt`. NOTE: origin used is
      `https://league-infrastructure.github.io/partner-scrape`, not
      `https://www.sdstemecosystem.org` (sprint.md Design Rationale
      D6's assumption) — verified live that the latter domain serves
      only a 417-byte HTML4 `<frameset>` framing the former; see the
      page's own frontmatter comment and this ticket's completion
      report for the full verification. Flagged for ticket 004 to
      reconcile against `llms.txt`'s own Data-section URLs.
- [x] Links to `/data-access` for the full schema instead of restating
      it.
- [x] Links to `/publish-events`.
- [x] Page renders correctly under both `just dev` and `just build`.

## Implementation Plan

**Approach**: Reuse `data-access.astro`'s (ticket 001) documented
field/URL facts as the single source of truth — do not re-derive them
independently, to avoid the two pages silently disagreeing. Keep prose
minimal; favor link lists over paragraphs, matching the emerging
llms.txt-companion-page convention (Design Rationale D2).

**Files to create**:
- `site/src/pages/for-agents.astro`

**Files to modify**: none.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write**: none — this page makes no independent
  schema-of-truth claim to guard; ticket 001's guard test already
  covers the underlying field list, and this page only links out.
- **Verification command**: `just build` / `just dev`; manual link
  check to `/data-access` and `/publish-events` (the latter lands in
  ticket 003, which precedes this ticket per `sprint.md`'s Tickets
  order, so the link target already exists by the time this ticket's
  work is verified).
