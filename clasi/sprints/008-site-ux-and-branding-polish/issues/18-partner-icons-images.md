---
status: in-progress
sprint: 008
tickets:
- 008-005
---

# Get icons or images for all partners

Every partner should have a logo/icon so cards and partner pages look
complete and recognizable. Today **28 of 153 partners have no `logo_src`**
(125 do), so those fall back to the default/placeholder in
`getLogoPath` (`site/src/lib/helpers.ts`, used by
`site/src/components/OpportunityCard.astro`).

## Goal
Source a reasonable icon or image for each partner that lacks one, so the
directory has a visual for every organization.

## Where things live
- Partner records: `site/src/data/partners.json` — `logo_src` field (and
  `website` for each org, which is the natural source for a logo).
- Rendering: `getLogoPath` / `logo_src` in `helpers.ts` +
  `OpportunityCard.astro`; logo image files under the site's assets.

## Possible approaches (to decide during planning)
- Pull each partner's `website` favicon / `og:image` / apple-touch-icon
  automatically, downscale, and store locally (self-hosted — the site is a
  static build with a strict CSP, so remote hotlinking won't work).
- Use a logo lookup service (e.g. Clearbit-style logo API by domain) as a
  fallback, again downloading and storing locally.
- Manual curation for the stragglers where automated lookup fails.
- Improve the placeholder itself (e.g. a monogram/initials tile derived
  from the org name) so anything still missing degrades gracefully.

## Acceptance (rough)
- Each of the 28 logo-less partners has a stored icon/image wired to
  `logo_src`, or a clearly-better generated placeholder.
- Images are self-hosted (no runtime external fetches), reasonably sized.
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`).
