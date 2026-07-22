---
id: '006'
title: Home page rebuild to match production brand
status: open
use-cases: [SUC-006]
depends-on: []
github-issue: ''
issue: 22-home-page-from-sdstemecosystem.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Home page rebuild to match production brand

## Description

Issue 22: rebuild the beta home page (`site/src/pages/index.astro`) to match production
(https://www.sdstemecosystem.org)'s hero background image, shaded/drop-shadowed button
treatment, and two hero cards — adapted to this site's actual pages, not copied 1:1.

**Requires network access** — this ticket downloads production's hero background image once and
self-hosts it. No runtime hotlinking afterward.

This is the structural foundation two other tickets in this sprint depend on: ticket 007 (issue
24, Upcoming Opportunities full-week window) and ticket 010 (issue 26, Our Partners /
The LEAGUE of Amazing Programmers) both build on the page structure this ticket produces — see
`sprint.md` Architecture > Step 1 and Design Rationale.

## Implementation Plan

### Approach

- **Hero**: download production's hero background image, store it under `site/public/`, and use
  it as the home hero's background (replacing the current `.hero-home`'s gradient-only
  background). Match production's fonts/colors/spacing for the hero content where they drive the
  hero itself.
- **Buttons**: replicate production's shaded, drop-shadowed button treatment as the site's
  `.btn`/`.btn-*` style (or a scoped hero-specific variant if a global change is too broad —
  judgment call, but prefer updating the shared `.btn` styling in `global.css` if production's
  treatment is meant to be the site's general button look, matching the issue's framing of
  "replicate ... as the site's button style").
- **Hero cards**: replicate the *style* of production's two cards ("Find Opportunity" / "Get
  Involved") — layout, visual treatment (shadow, spacing, iconography if present) — but adapt the
  *content*:
  - Card 1 "Find Opportunity" → links to `/opportunities` (keep the label, or match production's
    exact wording if close enough).
  - Card 2: reuse the "Get Involved" card's *style* only; change its text to "View Partners" and
    link to `/partners`.
- **Only include sections for pages this site actually has** — Opportunities (List/Calendar/Map)
  and Partners. Do not port over any production section/card/link for a feature this site lacks.
  The existing "Upcoming Opportunities" section, "Why We Build a STEM Ecosystem" info-grid, and
  "Our Partners" logo-grid section may be kept/restyled to match the rebuild's visual language,
  but their *content logic* (which opportunities show, which partners show) is explicitly **out
  of scope for this ticket** — issue 24 (ticket 007) and issue 26 (ticket 010) own those,
  building on top of whatever structure this ticket lands. Do not remove the "Our Partners"
  section; it stays, just restyled/repositioned to match the rebuild — ticket 010 depends on it
  still existing.
- Keep every path base-path-safe (`import.meta.env.BASE_URL`, the existing `base` convention
  already used throughout `index.astro`) and every new asset self-hosted (hero image under
  `site/public/`).

### Files to Modify / Create

- `site/src/pages/index.astro` — hero markup, hero-card markup/links, overall section structure.
- `site/src/styles/global.css` — hero section styles, button style (`.btn`/`.btn-*`), hero-card
  styles.
- `site/public/` — new hero background image asset.

### Testing Plan

- No JS test framework in `site/`; verify manually: hero background image renders and matches
  production's visual treatment; buttons show the shaded/drop-shadowed style; the two hero cards
  read "Find Opportunities" → `/opportunities` and "View Partners" → `/partners`; no section
  references a page this site doesn't have; all links resolve correctly under the site's base
  path (`/partner-scrape` in the CI build).
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [ ] Hero background image, button style, and hero-card style visually match production.
- [ ] The two hero cards read "Find Opportunities" → `/opportunities` and "View Partners" →
      `/partners`.
- [ ] No section references a page this site doesn't have (only Opportunities and Partners
      content survives from production's fuller feature set).
- [ ] The existing "Our Partners" section is preserved (restyled to match, not removed) — ticket
      010 depends on it existing after this ticket.
- [ ] All paths are base-path-safe (`import.meta.env.BASE_URL`); the hero image is self-hosted
      (no runtime remote fetch).
- [ ] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by manual visual comparison against
  production plus a successful build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
