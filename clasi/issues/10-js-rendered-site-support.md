---
status: pending
sprint: '003'
---

# JS-rendered site support (headless fetch)

A fetch path for client-rendered sites whose static HTML is effectively
empty.

## Why

The ~9 known Wix sites (and other client-rendered platforms) hydrate content
from JSON at runtime, so mirrored HTML has near-empty `<body>` tags and the
generic extractor gets nothing. These orgs are part of the long tail we
exist to cover.

## Proposed scope

- A **headless-browser fetch strategy** (e.g. Playwright) selectable per
  source in the registry, feeding the same generic extractor downstream.
- Used sparingly (it's expensive) — only for sources flagged as
  JS-rendered; investigate cheaper server-render triggers first.

## Sequence

Depends on: 01 (fetch layer), 03 (generic extractor). Lower priority — a
capped set of sources; do after the structured + sitemap tiers land.

_Proposal / mock-up — rewrite freely._
