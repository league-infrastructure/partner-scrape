---
id: '005'
title: Logo backfill for newly-registered roster organizations
status: in-progress
use-cases:
- SUC-002
depends-on:
- '003'
- '004'
github-issue: ''
issue: 32-partner-roster-expansion-and-housekeeping.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Logo backfill for newly-registered roster organizations

## Description

Tickets 003 and 004 registered roughly 65 new roster organizations with
`logo_src` left empty by design. This ticket makes a best-effort pass
to fetch a logo for each of them — a small, dedicated step, separate
from the bulk data-entry work, per this sprint's constraint that "logo
fetching may be its own small ticket step; missing logo is acceptable."

For each newly-added org: check the org's own site for a favicon or an
obvious header/logo image, following whatever convention the existing
roster's `logo_src` values already use (relative paths under
`../../../sites/default/files/...` for the inherited Drupal-era assets
— confirm whether that convention still applies to new entries or
whether new entries should use a different path scheme; this is a
one-time judgment call to make and record, not re-litigate per org).
A logo that requires guessing, low-confidence cropping, or scraping
behind a login is skipped, not forced.

## Acceptance Criteria

- [ ] Every org registered by tickets 003/004 has been checked for an
      obtainable logo; each either has a `logo_src` value or is left
      blank with no error.
- [ ] No `logo_src` value points at a broken/404 URL — spot-check a
      sample after the pass.
- [ ] The path convention used for any new logo assets is recorded in
      this ticket's Notes (even if the answer is "left as an external
      URL, no local asset convention adopted this sprint").
- [ ] `partners.json` and `partners_viable.csv` remain in 1:1 sync
      after this ticket's edits (only `logo_src` values change; no row
      additions/removals).
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write**: none expected — this is a data-only,
  best-effort enrichment pass with no new code path.
- **Verification command**: `uv run pytest`, plus a manual spot-check
  of a handful of the newly-set `logo_src` URLs actually resolving.

## Implementation Plan

**Approach**: Best-effort, org-by-org manual/scripted logo lookup
against each org's own public site. No new scraping infrastructure —
this is a one-time enrichment pass over a known, small (~65-row) set,
not a repeatable pipeline stage.

**Files to modify**:
- `site/src/data/partners.json`
- `data/partners_viable.csv`

**Testing plan**: see Testing above.

**Documentation updates**: none expected beyond this ticket's own
Notes recording the path-convention decision and any orgs left without
a logo.
