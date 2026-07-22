---
status: done
sprint: 008
tickets:
- 008-008
- 008-009
---

# Try to get images for events

Give individual opportunities their own image where possible, so cards and
detail pages show an event-specific visual instead of only the partner
logo. Today an opportunity card shows the partner's `logo_src`
(`site/src/components/OpportunityCard.astro`); there is no per-event image
field on the `Opportunity` record.

## Goal
During scraping, capture a representative image for each event (where one
exists) and surface it on the card and/or detail page. Fall back to the
partner logo / placeholder when no event image is found.

## Where things live
- Export schema: the `Opportunity` dataclass in
  `partner_scrape/normalize/run.py` (24 fields) + `export/` writer — a new
  `image_src` (or similar) field would be added here.
- Extraction: `partner_scrape/extract/ladder.py` and the adapters already
  fetch each event's detail page — the image can be pulled from the same
  HTML (`og:image`, `twitter:image`, JSON-LD `image`, or a hero `<img>`).
- Rendering: `OpportunityCard.astro` (+ `[slug].astro`) would prefer the
  event image, then fall back to `logo_src`, then the placeholder.

## Considerations
- The site is a static build with a strict CSP — images must be
  **self-hosted** (download + downscale at scrape/build time; no runtime
  remote hotlinking).
- Storage/size: many events → keep images small; dedupe identical images;
  budget disk in the cache/export.
- Quality gate: skip tracking pixels, spacers, and tiny/low-res images;
  prefer a real content image over a generic site banner.
- Related to [[18-partner-icons-images]] (same rendering/fallback path).

## Acceptance (rough)
- Opportunities carry an optional event image field, populated where an
  adapter can extract a good `og:image`/hero image.
- Cards/detail pages render the event image when present, else fall back to
  the partner logo, else the placeholder.
- Images are self-hosted and reasonably sized; applies to both beta and
  production.
