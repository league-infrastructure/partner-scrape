---
status: in-progress
sprint: '015'
tickets:
- 015-001
- 015-002
---

# Fix headless raw-XML fetching and sitemap namespace parsing (unblocks the 9 headless sources)

## Description

Two root-caused bugs from sprint 014 ticket 003's live triage, both
documented-with-evidence in that ticket's "Deviations / Findings for
Follow-up" and in per-source TOML addenda, deliberately not fixed there
(outside the ticket's declared file scope):

1. **`fetch/headless.py` — `PlaywrightFetcher.get()` cannot retrieve
   raw non-HTML resources.** `page.content()` serializes Chromium's
   *rendered document*, so fetching a `.xml` sitemap through the
   headless path either returns unparseable HTML-wrapped content
   (5 sites) or aborts navigation entirely (`net::ERR_ABORTED`,
   4 sites). This currently blocks **all 9** headless-flagged sources
   (the Wix partners + AoPS) at the discovery step, even though ticket
   002's wait-strategy fix made their HTML pages render perfectly.
   Likely fix shape: route non-HTML URLs (or a content-type/extension
   heuristic) through the plain HTTP fetcher even for headless sources,
   or use Playwright's request API (`page.request.get()` /
   `APIRequestContext`) for raw resources instead of `page.goto()` +
   `content()`.
2. **`discovery/sitemap.py` — `_parse_urlset()` hardcodes the
   `sitemaps.org/schemas/sitemap/0.9` namespace** while root-tag
   acceptance is namespace-agnostic, so any sitemap in another
   namespace parses to zero URLs silently (confirmed live:
   sandiego.edu's legacy 0.84 namespace; source `sandiego` disabled
   with this reason). Narrow fix: namespace-insensitive tag matching
   (localname comparison), with fixture tests for 0.9, 0.84, and
   unnamespaced sitemaps.

After both fixes: re-enable/re-probe the affected dispositioned sources
from ticket 014-003 (the 9 headless-flagged ones, plus `sandiego`) and
record their new yields.

Both need hermetic fixture regression tests. High leverage: these are
the last blockers between the sprint-014 ops work and actual Wix
partner yield.

## References

Sprint 014 ticket 003 (done) — full live evidence per source.
Gap analysis: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
