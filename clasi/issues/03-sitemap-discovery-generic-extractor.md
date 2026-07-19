---
status: pending
---

# Sitemap-diff discovery + generic page extractor

Covers the long tail of org sites that have no API — the orgs that most need
us to be their aggregator.

## Why

~100 of 144 known sites expose XML sitemaps. Diffing them is how we stay
incremental (fetch only changed pages) instead of re-mirroring everything.
The generic extractor is the universal fallback for any HTML page.

## Proposed scope

- **Sitemap-diff discovery** — fetch `sitemap_index.xml` / `sitemap.xml`,
  pattern-match event/program URLs by filename and path, diff against the
  prior snapshot by `<lastmod>`, enqueue only new/changed URLs.
- **Generic page extractor** — priority ladder: JSON-LD `Event` schema →
  `<time datetime>` → OpenGraph meta → URL/slug date patterns → body-text
  date regex. Emits canonical Events with confidence set by which rung hit.
- Port the useful platform-specific logic from the `dev/` mock-up
  (BiblioCommons, Drupal, title/URL-date) as generic-extractor strategies,
  not bespoke scripts.

## Sequence

Depends on: 01, 02. The undated/low-confidence output here is exactly what
issue 04 (LLM enrichment) cleans up.

_Proposal / mock-up — rewrite freely._
