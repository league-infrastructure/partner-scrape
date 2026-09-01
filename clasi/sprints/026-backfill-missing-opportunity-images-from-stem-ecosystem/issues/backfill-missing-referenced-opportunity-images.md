---
status: in-progress
sprint: '026'
tickets:
- 026-001
---

# Backfill 172 missing referenced opportunity images from stem-ecosystem

Gap surfaced during the stem-ecosystem peer session's cross-verification of
sprint 025's output (2026-08-31/09-01 conversation), not a pre-existing
filed issue.

## Background

Sprint 025 redirected every partner-scrape write target to this repo's own
`data/` directory, including `data/images/opportunities/` (populated by
`EventImageDownloader`, which as of sprint 025 ticket 002 resizes newly-
downloaded images on fetch). The first real production run under the new
architecture populated `data/images/opportunities/` with 375 images — a
snapshot of one run's *current* opportunities, not an accumulated history.

The per-partner event files (`data/partners/<slug>/events.json` and
`data/partners/<slug>/past-events.json`, written by `export/publish.py`'s
`project()`) reference *past* opportunities too, accumulated over many
historical runs via the persistent per-partner log under
`SCRAPE_CACHE_DIR`. Diffing every `image_src` filename referenced across
`data/partners/*/{events,past-events}.json` against what actually exists in
`data/images/opportunities/` turns up 172 referenced-but-missing filenames
(out of 449 distinct filenames referenced total) — confirmed independently
by the stem-ecosystem peer session, by team-lead, and by sprint-planner
during this sprint's own planning pass (all three counts agree: 449
referenced, 375 present, 172 missing).

All 172 missing filenames exist, unresized (pre-resize originals — sprint
025 ticket 002's resize-on-fetch only applies to newly-downloaded images,
not this historical accumulation), at
`../stem-ecosystem/public/images/opportunities/` on this same machine (a
sibling checkout, readable) — also independently confirmed. The
stem-ecosystem side declined to write into partner-scrape's own checkout
themselves, correctly matching the exact cross-repo-write boundary sprint
025 just established (just pointed the other direction), and left it to
partner-scrape to pull from their tree.

Separately, `data/opportunities.json`'s own image references were checked
as a sanity control: 143 referenced filenames, all 143 present — that
contract already has perfect referential integrity and is not part of this
gap.

## Decision (already made, not open for this sprint to re-litigate)

Seed ONLY the 172 currently-referenced-but-missing images into
`data/images/opportunities/`, copied by exact filename from
`../stem-ecosystem/public/images/opportunities/` — NOT all 631 images in
that directory. Rationale: keeps `data/` lean, matches the point of sprint
025's resize work (avoid re-accumulating unresized bloat), and the 172 are
exactly what the current published contract actually needs. This is a
one-time backfill; going forward `data/`'s own accumulated history stays
complete on its own (each real run's image download only ever adds,
content-hash deduped, never overwrites, and the directory persists across
runs, git-committed).

Exact-filename copy only — no resize/re-encode/re-derive in this pass. The
172 images stay pre-resize originals until they naturally age out of the
published contract via a future re-fetch.
