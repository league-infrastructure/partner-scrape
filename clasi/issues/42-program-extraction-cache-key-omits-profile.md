---
status: pending
---

# Program extraction cache key omits the extraction profile

## Description

`partner_scrape/adapters/program_cache.py`'s `ProgramExtractionCache`
keys entries on `(url, content_hash(body))`. It does not include the
extraction `profile`.

There are now three profiles — `"program"` (sprint 027),
`"competition"` (sprint 029 ticket 006), and `"pd"` (sprint 030 ticket
004) — selected in `program_page.py` from the source's
`config["opportunity_type"]`. Each produces materially different
extractions from the same page.

No collision exists today: a given URL is registered under exactly one
`opportunity_type` for its whole life, so no URL has ever been cached
under two profiles. The bug is realized only when a source's
`opportunity_type` override changes after a cache entry already
exists — at which point the pipeline silently serves the old profile's
extraction and the change appears to have no effect.

Latent, pre-existing since sprint 027, and flagged as an Open Question
in `partner_scrape/adapters/DESIGN.md` rather than fixed, in both
sprints 029 and 030.

## Proposed fix

Include `profile` in the cache key. Note that sprint 029 bumped
`_CACHE_SCHEMA_VERSION` 2→3 for a related reason; decide whether this
needs another bump or whether adding the key component is sufficient
(an unrecognized old-shaped key simply misses).

## Verification

- Unit: the same URL and body cached under two different profiles
  produce two distinct entries, and each lookup returns its own.
