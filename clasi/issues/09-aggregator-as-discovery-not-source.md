---
status: pending
sprint: '005'
---

# Other aggregators as discovery, not as a data source

Use external calendars to find orgs and events we're missing — then go get
the data from the source ourselves. We are the aggregator; we don't
republish someone else's aggregation.

## Why

Two constraints from the stakeholder: (1) don't over-focus on aggregators and
miss the long tail of orgs that only publish on their own sites — that long
tail is the whole point; (2) we can't just lift data from other aggregators
— it has to be our own, acquired respectfully.

## Proposed scope

- **Discovery crawl** — scan a curated set of regional hubs (e.g. Balboa Park
  calendar, county library systems, regional STEM networks like the Barrio
  Logan / Southeastern SD network on Cureo, university calendars) to surface
  organizations and events we don't yet cover.
- **Source-back acquisition** — for each discovered org/event, register the
  org and acquire from its own site/feed; do **not** ingest the aggregator's
  records as our data.
- **Policy** — respect each hub's robots/ToS; record "discovered via" as
  provenance; a hub is a lead generator, not a feed.
- Feeds a growing backlog of new sources for the Source Registry.

## Sequence

Depends on: 01 (registry), 04 (relevance gate). Ongoing once the engine runs.

_Proposal / mock-up — rewrite freely._
