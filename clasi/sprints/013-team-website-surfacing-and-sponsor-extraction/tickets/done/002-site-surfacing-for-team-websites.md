---
id: '002'
title: Site surfacing for team websites
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: 21-scrape-team-sites-for-sponsors.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Site surfacing for team websites

## Description

Issue 21's first ask: today, `TeamCard.astro` declares `website`/
`website_status`/`organization_website` in its Props interface but
renders none of them, and `TeamFilters.astro` has no website facet — a
visitor has to open all 278 team pages one at a time to find the 53
worth clicking. Ticket 001 makes `website_status` a real, populated
field (`confirmed`/`unverified`/`none`); this ticket surfaces it.

Add a website indicator to `site/src/components/TeamCard.astro`, using
the existing `SocialIcon` component's `website` platform (do not add a
new icon asset), shown **only** when `team.website_status === 'confirmed'`.
Add a "Has a Website" facet to `site/src/components/TeamFilters.astro`,
following its existing build-time `tally()`/derived-count pattern (the
same shape `inRegionCount` already uses for a derived boolean facet, not
the generic `tally()` helper, since `website_status === 'confirmed'` is
a derived condition, not a raw field value to count directly).

Also gate `site/src/pages/teams/[slug].astro`'s existing Team Website
field: render a clickable `<a>` only when `confirmed`; when
`unverified`, render the bare URL as plain text with a short note (e.g.
"link not yet verified") rather than a link — issue 21 is explicit that
"a broken link published on a public directory is worse than no link."
This is a small, in-scope addition beyond the issue's literal
TeamCard/TeamFilters ask, directly serving that same stated concern at
low cost.

See `sprint.md`'s SUC-002 for the full acceptance criteria and Design
Rationale for why the badge/facet/link-gating all key off
`website_status` rather than raw `website` truthiness.

## Acceptance Criteria

- [x] `TeamCard.astro` renders a `SocialIcon` `website`-platform badge
      if and only if `team.website_status === 'confirmed'`.
- [x] `TeamCard.astro` carries a `data-website` attribute (or equivalent)
      reflecting confirmed-status for `TeamFilters`' facet to match
      against.
- [x] `TeamFilters.astro` has a "Has a Website" checkbox facet with a
      build-time count of teams whose `website_status === 'confirmed'`;
      checking it narrows the visible list correctly.
- [x] `teams/[slug].astro`'s Team Website field is a clickable `<a>`
      only when `confirmed`; renders plain unlinked text with a note
      when `unverified`; renders nothing when `none` (existing behavior,
      unchanged).
- [x] `just build` succeeds; the `/teams` page count still equals the
      team count in the `teams.json` it was built against.
- [x] No existing `TeamCard`/`TeamFilters`/detail-page test or fixture
      needs an unrelated change — this ticket is additive to those
      components.

## Testing

- **Existing tests to run**: whatever this project's existing Astro/
  site build check is (`just build`, or an equivalent site test command
  if one exists) against the current fixture `teams.json`.
- **New tests to write**: a fixture `teams.json` (or an extension of the
  existing one used for `/teams` build checks) containing at least one
  team each at `confirmed`/`unverified`/`none` `website_status`.
  Assert: the badge appears only for the `confirmed` fixture team; the
  "Has a Website" facet count matches the `confirmed` count in that
  fixture; filtering by it narrows the visible cards correctly; the
  detail page emits a clickable `<a>` only for the `confirmed` team and
  plain text for `unverified`.
- **Verification command**: `just build` (or this project's established
  site-build/test command), confirming the `/teams` page count is
  unchanged in cardinality from before this ticket.
