---
id: 009
title: Render event images with logo and placeholder fallback chain (site)
status: done
use-cases:
- SUC-009
depends-on:
- '005'
- 008
github-issue: ''
issue: 19-event-images.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Render event images with logo and placeholder fallback chain (site)

## Description

Issue 19 (site half): cards and the detail page should show an opportunity's own image when one
exists, falling back to its partner's logo, then the generic placeholder, when it doesn't.

**Depends on ticket 008** (needs `Opportunity.image_src` to exist in the schema/exported data)
**and ticket 005** (needs real partner logos filled in so the fallback tier is meaningful and
testable across the full partner set — see `sprint.md` Architecture > Step 2, R9). Per `sprint.md`
Design Rationale, the fallback is resolved through one small shared helper, not duplicated
per-page conditionals — matching sprint 007's precedent (one Markdown renderer, two consumers).

## Implementation Plan

### Approach

- Add a small pure function to `site/src/lib/helpers.ts`, e.g. `resolveImage(opportunity,
  partnerLogoSrc)`, encapsulating the three-tier fallback: `opportunity.image_src` if set, else
  `partnerLogoSrc` (via the existing `getLogoPath()`), else the existing generic default
  placeholder path. Do not duplicate this if/else chain inline in both `OpportunityCard.astro`
  and `[slug].astro`.
- `OpportunityCard.astro`: add `image_src: string` to its `Props.opportunity` interface; call the
  new resolver instead of calling `getLogoPath(opp.logo_src)` directly for the card's top visual.
- `[slug].astro`: same change for its detail-page hero image.
- **Visual layout is an open question this ticket resolves** (per `sprint.md` Open Question 2):
  today's card shows a small 48×48 square partner-logo tile (`.opp-card-logo`); an event's own
  photo is more likely landscape. Decide and implement one of: (a) the event image replaces the
  logo tile at the same size/crop (simplest, least layout risk), or (b) the card gains a new,
  larger top-of-card image slot when an event image is present, with the partner logo shown
  smaller elsewhere (e.g. next to the partner name). Either is acceptable; document the choice
  made and why in this ticket's completion notes, since `sprint.md` deliberately left it open
  rather than pinning a CSS detail with more than one reasonable answer.
- Apply the same resolver on the detail page's hero image area (currently just the small
  `.detail-logo`); same layout-decision latitude as the card.

### Files to Modify

- `site/src/lib/helpers.ts` — new `resolveImage()` (or similarly-named) fallback-chain function.
- `site/src/components/OpportunityCard.astro` — `Props` interface gains `image_src`; card visual
  uses the resolver.
- `site/src/pages/opportunities/[slug].astro` — detail-page hero visual uses the resolver.
- `site/src/styles/global.css` — any new/adjusted styling for the chosen image-slot layout.

### Testing Plan

- No JS test framework in `site/`; verify manually against real exported data (post-ticket-008
  data, once available) and/or constructed fixtures covering all three tiers: an opportunity with
  `image_src` set (shows its own image), one without `image_src` but with a partner `logo_src`
  (shows the logo, today's unchanged behavior), and one with neither (shows the placeholder).
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [x] An opportunity with `image_src` set shows its own image on both the card and the detail
      page.
- [x] An opportunity without `image_src` but with a partner `logo_src` shows the partner logo —
      today's behavior, unchanged.
- [x] An opportunity with neither shows the existing generic placeholder.
- [x] The fallback decision is made by one shared helper function, called from both the card and
      the detail page (not duplicated conditionals).
- [x] The chosen visual layout for an event image (replace the logo tile vs. a new larger slot)
      is implemented consistently and documented in the completion notes.
- [x] `npm run build` succeeds.

## Completion Notes

- **Fallback helper**: `resolveImage(imageSrc, logoSrc)` added to `site/src/lib/helpers.ts`.
  Tier 1 (event image) is resolved directly against
  `${base}/images/opportunities/${imageSrc}`; tiers 2/3 (logo, placeholder) are delegated to the
  existing `getLogoPath()` rather than re-implemented, so there is exactly one place that knows
  the logo/placeholder path convention. Both `OpportunityCard.astro` and `[slug].astro` call this
  one function — no per-page conditionals.
- **Visual layout decision (Open Question 2)**: chose **option (a)** — the event image replaces
  the existing logo tile at the same size/crop (`.opp-card-logo` / `.detail-logo`), rather than
  adding a new larger top-of-card slot. Rationale: lowest layout risk, no restructuring of the
  card/detail markup, and most records won't have a real event photo until the post-sprint
  re-scrape populates `image_src`, so a speculative larger-slot layout would mostly render empty
  today. One visual refinement was added to distinguish the two content types sharing that slot:
  a new `data-event-image="true"` attribute (set only when `image_src` resolved, i.e. tier 1)
  switches `object-fit` from the existing `contain` (keeps a logo's full mark visible on its
  tinted backdrop) to `cover` (fills the tile edge-to-edge, which suits a landscape photo better).
  This lives in `site/src/styles/global.css` under a new `=== Opportunity Image ===` section,
  alongside the sibling `.opp-card-date[data-weekend]` pattern from the same sprint. Alt text also
  switches with the tier: the opportunity's own title for an event photo, the partner name for a
  logo/placeholder.
- **Verification**: `npm run build` (offline) succeeds. All three fallback tiers were exercised
  against the built HTML output: (1) an existing record with a `logo_src` but no `image_src`
  renders the logo — unchanged; (2) an existing record with neither renders
  `default-partner.svg`; (3) `image_src` was temporarily set on one record (pointed at an
  existing `public/images/logos/` asset copied into a temp
  `public/images/opportunities/TEST_EVENT_IMAGE.jpg`), rebuilt, and confirmed the card and detail
  page both rendered `/images/opportunities/TEST_EVENT_IMAGE.jpg` with `data-event-image="true"`
  and the opportunity's title as alt text — then the data file and temp image were reverted
  (`git diff` confirms `site/src/data/opportunities.json` is unchanged) before the final build.
  `opportunities.json` still has no `image_src` key on any record as of this ticket (re-scrape is
  a separate, post-sprint step per ticket 008/sprint.md Migration Concerns), so tier 1 is untested
  on production data but fully exercised via the constructed fixture above.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by manual check across all three fallback
  tiers plus a successful build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
