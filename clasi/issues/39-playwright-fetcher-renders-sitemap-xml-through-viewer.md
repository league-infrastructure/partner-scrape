---
status: pending
---

# PlaywrightFetcher still renders sitemap.xml through Chromium's XML viewer

## Description

Found during sprint 029 ticket 005 while investigating why GSDSEF was
yielding zero events. The registration looked healthy; a stale
fetch-cache entry was masking a live, reproducible bug.

`partner_scrape/fetch/headless.py`'s `PlaywrightFetcher` returns
sitemap.xml wrapped in Chromium's XML *viewer* markup rather than the
raw XML bytes. `discovery/sitemap.py` then parses viewer chrome instead
of URLs and discovers nothing.

Sprint 015 landed "headless raw-XML fetch and sitemap namespace fixes"
and recorded this as fixed. It is not fixed on this path — verify what
sprint 015 actually covered and why this case escapes it before
assuming either result is wrong.

## Impact

Any `fetch_strategy = "headless"` source that relies on sitemap
discovery silently discovers zero URLs. GSDSEF is the confirmed case
(worked around in sprint 029 ticket 005 by switching it to
`program_page_multi` pointed at a specific page — the workaround is not
the fix). Sweep `registry/sources/` for other headless + sitemap
sources and check their recent yield before assuming GSDSEF was the
only one.

The stale-cache masking is its own hazard: the source looked fine in
cached runs. Consider whether a zero-discovery result should invalidate
rather than reuse a cache entry.

## Verification

- Unit: a headless fetch of a sitemap.xml fixture returns parseable raw
  XML, not viewer markup.
- Live: a headless + sitemap source discovers a non-zero URL count.
