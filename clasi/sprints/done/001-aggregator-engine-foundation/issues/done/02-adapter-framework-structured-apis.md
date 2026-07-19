---
status: done
sprint: '001'
tickets:
- 001-004
- 001-005
- 001-008
---

# Adapter framework + structured-API adapters

The "many scrapers" backbone. Define the pluggable **adapter interface**
(discover → fetch → extract → emit canonical Event) and implement the
reliable, structured tier first, where data is clean and dated.

## Why

Structured feeds give 100%-dated, high-quality records with no HTML parsing.
They should be the load-bearing majority of our data; fragile HTML scraping
is the fallback, not the default.

## Proposed scope

- **Adapter interface** — a small contract each source implements; one
  adapter ≈ one scraper. New adapters register against the Source Registry.
- **The Events Calendar (TEC) REST** — `/wp-json/tribe/events/v1/events/`
  (already proven for ~6 sites; generalize + paginate + future-only).
- **WordPress REST** — `/wp-json/wp/v2/` for WP sites without TEC.
- **iCal / RSS feeds** — many event pages expose `?ical=1`; cheap structured
  wins we currently ignore.

## Sequence

Depends on: 01 (foundation). Do early — highest quality-per-effort.

_Proposal / mock-up — rewrite freely._
