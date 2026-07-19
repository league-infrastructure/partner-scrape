---
status: pending
---

# Normalization, cross-source dedup, and site export contract

The seam between the engine and the site. Turn canonical Events into the
site's `opportunities.json`, without duplicates.

## Why

As an aggregator pulling the same event from multiple places (an org's own
site AND a hub it happens to be on), we will get collisions. Dedup today is
within-org by slug — that won't hold once coverage grows.

## Proposed scope

- **Normalize** canonical Events to the site's opportunity schema (map/derive
  the controlled-vocab fields from issue 04's output).
- **Cross-source dedup** — identity = normalized(title) + date + venue,
  across organizations; prefer the highest-confidence/most-complete instance;
  record all sources it was seen on.
- **Collapse recurring** (org, title) instances into a dated range.
- **Partner join** — link to `partners.json` for id / logo / geo.
- **Export** only current + upcoming into the site repo; bump
  `scrape-meta.json`. Historical data never ships.

## Sequence

Depends on: 01–04. This is the contract the site consumes.

_Proposal / mock-up — rewrite freely._
