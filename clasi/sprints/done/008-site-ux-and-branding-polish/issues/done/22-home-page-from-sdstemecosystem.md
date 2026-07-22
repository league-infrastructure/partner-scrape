---
status: done
sprint: 008
tickets:
- 008-006
---

# Rebuild the home page to match sdstemecosystem.org

Duplicate the look of the production home page (**https://www.sdstemecosystem.org**)
for the beta home page (`site/src/pages/index.astro`), adapting it to the
pages this site actually has.

## Bring over from production
- **Hero background image** — download the production hero image and
  self-host it in `site/public/` (static build, strict CSP → no runtime
  remote fetch), then use it as the home hero background.
- **Shaded/shadowed button style** — replicate production's button styling
  (the shaded, drop-shadowed treatment) as the site's button style.
- **Hero cards** — replicate the style of production's two cards
  ("Find Opportunity" and "Get Involved"): same layout/visual treatment.

## Adapt (don't copy 1:1)
- **Only include features/sections for pages we actually have.** Do NOT
  bring over cards, links, or sections for production features that don't
  exist on this site. This site has: the Opportunities directory
  (List/Calendar/Map) and the Partners directory.
- Card #1 "Find Opportunity" → links to the Opportunities page (keep the
  label, or match production's wording).
- Card #2: reuse the "Get Involved" card **style**, but change its **text
  to "View Partners"**, linking to the Partners page.

## Notes
- Match production's fonts/colors/spacing where they drive the hero + cards
  (the site already carries the brand fonts/CSS variables).
- Keep everything base-path-safe (`import.meta.env.BASE_URL`) and
  self-contained (no external assets at runtime).
- Related visual-polish issues: [[21-site-favicon]], [[18-partner-icons-images]].
- Applies to the beta (`partner-scrape/site`); production already has this.
