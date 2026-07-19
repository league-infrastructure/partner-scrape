---
status: pending
---

# Rearchitect into an aggregator engine (foundation)

**We are the aggregator.** The core asset is a large, growing fleet of our
own source scrapers that pull events directly from organizations — especially
the long tail of orgs that never make it onto anyone else's calendar. This
issue replaces the `dev/` mock-up and `run_mirrors.py` with a real
foundation. Treat all existing code as disposable reference.

## Why

The current pipeline is ~150 one-off extractors with keyword-regex
classification and a full 40GB re-mirror model. It can't run unattended and
silently drops whole sources (Fleet, Birch produce zero). We need a spine
that makes adding a scraper cheap and keeps data trustworthy.

## Proposed scope

- **Source Registry** — a data-driven catalog of organizations and how to
  reach their events: adapter type, endpoints/URL patterns, taxonomy
  defaults, and an explicit acquisition policy per source (robots/ToS,
  rate limits, "discovered via"). Adding a source is a data edit, not code.
- **Canonical Event record** — one intermediate shape every adapter emits,
  carrying `kind` (event / program / internship), per-field **provenance**
  and **confidence**, and a stable identity for dedup.
- **Fetch + cache layer** — polite HTTP (respect robots, rate-limit,
  conditional GET via etag/last-modified), raw responses cached under
  `SCRAPE_CACHE_DIR` (`/Volumes/Cache/stem-ecosystem`), off-repo.

## Sequence

Foundation — everything else depends on this. Do first.

_Proposal / mock-up — rewrite freely._
