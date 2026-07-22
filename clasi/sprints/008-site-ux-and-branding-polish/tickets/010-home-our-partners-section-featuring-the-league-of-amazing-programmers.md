---
id: '010'
title: Home Our Partners section featuring The LEAGUE of Amazing Programmers
status: done
use-cases:
- SUC-010
depends-on:
- '006'
github-issue: ''
issue: 26-home-our-partners-section-league.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Home Our Partners section featuring The LEAGUE of Amazing Programmers

## Description

Issue 26 (linked to the sprint after initial planning): the home page should have an "Our
Partners" section near the bottom, and The LEAGUE of Amazing Programmers must appear in it.

**Codebase-alignment finding from planning**: `index.astro` already has an "Our Partners" section
(`.logo-grid`, `<h2>Our Partners</h2>`) that picks up to 16 partners with `logo_src` set,
preferring those with active opportunities (`activePartnerNames`). Nothing guarantees any
specific partner appears — including The LEAGUE of Amazing Programmers (partner id `287`,
`logo_src: "the_league_of_amazing.png"` — already has a logo, so this ticket does not depend on
ticket 005 for that specific record, though it benefits generally from 005's work making the
whole section more complete).

**Depends on ticket 006** — the section's final position/style is decided by the home-page
rebuild; this ticket adjusts the *selection logic* on top of whatever structure ticket 006
lands, per `sprint.md` Architecture > Design Rationale ("guarantee The LEAGUE of Amazing
Programmers via an explicit always-include rule layered on top of the existing selection logic,
not by replacing that logic").

## Implementation Plan

### Approach

- Confirm the "Our Partners" section, post-ticket-006, is positioned near the bottom of the home
  page (matching production's placement) — reposition if ticket 006's rebuild moved it elsewhere
  in the section order.
- Add one small, explicit rule to the existing partner-selection query in `index.astro`: find The
  LEAGUE of Amazing Programmers' record (match by `name`, e.g. `p.name === "The LEAGUE of Amazing
  Programmers"` — verify exact casing/string against `partners.json` at implementation time) and
  ensure it is always included in the rendered set, regardless of whether the general
  active-opportunity-preference logic would have selected it. A straightforward implementation:
  filter the League's record out of the general candidate pool, always place it first (or in a
  fixed position), then fill remaining slots (up to the existing 16-partner cap) with the current
  `logoPartners` selection logic, deduplicating so the League isn't double-counted if the general
  logic would have picked it anyway.
- Do **not** redesign the general selection policy (active-opportunity preference, the 16-partner
  cap) — this ticket adds one narrow, explicit exception, not a new algorithm. See `sprint.md`
  Design Rationale for why.
- Link the League's entry the same way every other partner in the section links out (to its
  Partners-page detail entry, `/partners/{id}` — `id: 287`).
- Match production's treatment for the section where applicable (styling is largely ticket 006's
  responsibility; this ticket's job is the selection guarantee and confirming placement).

### Files to Modify

- `site/src/pages/index.astro` — the "Our Partners" section's partner-selection query
  (`logoPartners` or its post-006 equivalent) and, if needed, its position in the page.

### Testing Plan

- No JS test framework in `site/`; verify manually: The LEAGUE of Amazing Programmers' logo
  appears in the "Our Partners" section on a local build; the section sits near the bottom of the
  page; clicking the League's entry navigates to `/partners/287`; the general selection/cap logic
  otherwise behaves as it did after ticket 006 (no unintended regression to which other partners
  appear).
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [x] The "Our Partners" section appears near the bottom of the home page, styled per
      production's treatment (as established by ticket 006).
- [x] The LEAGUE of Amazing Programmers' logo/name appears in the section on every build,
      independent of the general active-opportunity-preference/cap logic.
- [x] The League's entry links to its Partners-page detail entry (`/partners/287`).
- [x] The general partner-selection logic (active-opportunity preference, 16-partner cap) is
      otherwise unchanged for every other partner.
- [x] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by manual visual/link check plus a successful
  build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
