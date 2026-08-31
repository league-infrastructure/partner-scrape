---
id: '001'
title: Fix headless raw-resource fetch and sitemap namespace parsing
status: done
use-cases:
- SUC-001
- SUC-002
depends-on: []
github-issue: ''
issue: 37-headless-xml-fetch-and-sitemap-namespace-bugs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix headless raw-resource fetch and sitemap namespace parsing

## Description

Two root-caused bugs from sprint 014 ticket 003's live triage
(documented, not fixed there — see that ticket's "Deviations /
Findings for Follow-up" and the dated addenda on the 9 affected
sources' TOML files), both currently blocking real yield:

1. **`fetch/headless.py`'s `PlaywrightFetcher.get()` cannot retrieve a
   raw, non-HTML resource.** It always navigates (`page.goto()`) and
   reads the rendered document (`page.content()`) — correct for an
   HTML page, but for a bare `.xml` sitemap this either returns
   Chromium's own XML-viewer-wrapped markup (5 confirmed sites:
   `gsdsef`, `xplorstem`, `sdrvc`, `titanbot`, `lajollalibrary`) or
   aborts navigation outright with `net::ERR_ABORTED` (4 confirmed
   sites: `climate-science-alliance`, `escondido-creek-conservancy`,
   `techadventurecamp`, `sandiego-cv-aopsacademy`). All 9 of ticket
   002's headless-flagged sources remain zero-yield at the discovery
   step because of this, even though their HTML pages already render
   correctly (sprint 014 ticket 002's `wait_until="load"` fix).
2. **`discovery/sitemap.py`'s `_parse_urlset()` is namespace-strict
   while root-tag acceptance is namespace-agnostic.** It queries only
   `root.findall("sm:url", _NS)` against the hardcoded
   `_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}`, so a
   sitemap declaring any other namespace parses successfully (its root
   tag is recognized by `_local_name()`, which already strips
   namespaces) but silently yields zero `<url>` matches even when real
   event pages exist in it. Confirmed live: `sandiego.edu`'s legacy
   `xmlns="http://www.google.com/schemas/sitemap/0.84"` sitemap.
   `sandiego` is currently disabled with this exact reason.

## Fix shape

1. **`fetch/headless.py`**: give `PlaywrightFetcher.get()` a
   content-type/extension heuristic that routes a non-HTML target
   through a raw request (Playwright's `page.request`/
   `APIRequestContext` surface) instead of `page.goto()` +
   `page.content()`. Keep the method's external contract identical
   (`Fetcher.get(url, headers=None) -> FetchResponse`, same class,
   same Protocol) — no adapter, `PoliteFetcher`, or discovery module
   should need to change or learn headless fetching exists. Extend the
   `HeadlessPage`/fixture-double surface only as needed to support the
   raw-request path in tests without a real browser.
2. **`discovery/sitemap.py`**: in `_parse_urlset()`, if the existing
   namespace-qualified `sm:url` query returns zero elements, retry
   with a namespace-agnostic match (iterate children by
   `_local_name(child.tag) == "url"`/`"loc"`/`"lastmod"`, reusing the
   `_local_name()` helper already used elsewhere in this module for
   root/child-tag acceptance). Try the qualified query first — every
   currently-registered sitemap already validates against it — so this
   is purely additive.

## Acceptance Criteria

- [x] `PlaywrightFetcher.get()` returns the real raw body for a `.xml`
      (or otherwise non-HTML) target, verified by a fixture `HeadlessPage`
      double that simulates both failure modes (wrapped-markup and
      aborted navigation) being avoided.
- [x] `PlaywrightFetcher.get()`'s behavior for an HTML target is
      unchanged (existing fixture tests for the `wait_until="load"`
      path still pass unmodified).
- [x] `_parse_urlset()` returns correct `{loc: lastmod}` for
      0.9-namespaced, 0.84-namespaced, and unnamespaced `<urlset>`
      fixtures.
- [x] An existing 0.9-namespaced sitemap fixture test is unaffected
      (fallback only fires when the qualified query returns zero).
- [x] No adapter, `PoliteFetcher`, `robots.py`, `throttle.py`, or
      discovery module outside `discovery/sitemap.py` changes.
- [x] Full test suite stays green; no new test touches a real network
      or a real browser.

## Deviations / Findings for Follow-up (2026-08-30)

- **`_RAW_RESOURCE_EXTENSIONS` deliberately excludes `.txt`, discovered
  during implementation, not planned up front.** The initial extension
  set (`.xml`, `.json`, `.txt`, `.csv`, `.rss`, `.atom`) broke two
  pre-existing, unmodified `TestPoliteFetcherWrapsPlaywrightFetcher`
  tests: `fetch/robots.py` fetches `robots.txt` through this same
  `PlaywrightFetcher.get()` for every source (headless or not), so
  including `.txt` silently routed robots.txt fetches through the new
  raw-request path too. Nothing in issue 37's live triage evidence
  flagged robots.txt as broken — only `.xml` sitemaps were confirmed
  failing (5 wrapped-markup, 4 `net::ERR_ABORTED`). Removed `.txt` from
  the tuple rather than updating the robots.txt tests, per the ticket's
  own "no `robots.py` changes" scope boundary read in spirit (an
  unevidenced behavior change to robots.txt retrieval, even a plausibly
  correct one, isn't this ticket's fix). Documented as a bullet in
  `fetch/DESIGN.md`'s Open Questions and covered by a dedicated
  regression test (`test_txt_target_still_navigates_not_raw_path`) so a
  future extension-list edit doesn't reintroduce this silently. A
  genuinely broken `.txt` (or other extension) fetch, if ever found
  live, is a small follow-up: add the extension back with its own
  evidence.
- **Live smoke test (real Playwright/Chromium, not a fixture) against
  `lajollalibrary.org`** — the exact site issue 37 cites for
  `net::ERR_ABORTED` on `https://www.lajollalibrary.org/sitemap.xml`:
  - `PlaywrightFetcher().get("https://www.lajollalibrary.org/sitemap.xml")`
    now returns `status=200` and a real, parseable
    `<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" ...>`
    body (487 bytes, 3 child `<sitemap>` entries) — previously this
    call raised `net::ERR_ABORTED`.
  - A real child sitemap fetch
    (`https://www.lajollalibrary.org/pages-sitemap.xml`, reached the
    same way `_parse_sitemap_index()` reaches it) also returns
    `status=200` with a real `<urlset>` body — confirms the fix holds
    for sitemap-index recursion, not just the root document.
  - End-to-end `discover_changed_urls()` against the real source
    (via `PoliteFetcher(fetcher=PlaywrightFetcher())`) completed with
    no exception and returned 0 refs: this site's sitemap has no
    dedicated event child sitemap, and none of its actual pages
    (`staff-picks`, `summer-reading-program`, `kids`, etc.) match
    `EVENT_PATH_RE`'s path-segment patterns (`summer-reading-program`
    is one hyphenated segment, not `/program(/|$)`). This is a real,
    separate discovery-classification question for ticket 002's
    re-probing pass, not a fetch failure — the fetch itself now
    succeeds and returns real content, which is this ticket's whole
    scope.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), especially
  `tests/test_fetch_headless.py` and the sitemap discovery test file.
- **New tests to write**: `PlaywrightFetcher.get()` cases for a
  non-HTML target (both simulated failure modes); `_parse_urlset()`
  cases for 0.84-namespaced and unnamespaced `<urlset>` documents.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Fix both bugs entirely inside their owning modules — no
cross-module signature changes. For `fetch/headless.py`, branch inside
`get()` on a URL-suffix/content-type heuristic before deciding whether
to navigate or issue a raw request. For `discovery/sitemap.py`, add
the namespace-agnostic fallback as a second pass inside
`_parse_urlset()`, only when the first pass is empty.

**Files to modify**:
- `partner_scrape/fetch/headless.py` — `PlaywrightFetcher.get()`,
  `HeadlessPage` Protocol (if the raw-request seam needs a new
  method).
- `partner_scrape/discovery/sitemap.py` — `_parse_urlset()`.
- `tests/test_fetch_headless.py`, the sitemap discovery test file —
  new fixture cases per Acceptance Criteria.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/fetch/DESIGN.md` and
`partner_scrape/discovery/DESIGN.md` each get a short sprint-015
addendum describing the fix (matching this repo's existing per-sprint
DESIGN.md addendum convention) — not a rewrite of either document's
existing content.
