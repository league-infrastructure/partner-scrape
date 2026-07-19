---
status: pending
sprint: '003'
---

# Flagship source adapters: Fleet Science Center + Birch Aquarium

Fix the two most visible zero-yield gaps. The host organization's own events
are currently absent from its own site.

## Why

The Fleet Science Center hosts sdstemecosystem.org. A Fleet-hosted directory
with no Fleet events is the first thing they'll notice — and it directly
undercuts the pitch to keep the site alive. Birch Aquarium is the second
flagship org and rides one API (UCSD Localist) that also unlocks many other
university sources.

## Proposed scope

- **Fleet Science Center adapter** — identify how fleetscience.org publishes
  events (page structure, feed, or platform) and build the source.
- **Birch Aquarium / UCSD Localist adapter** —
  `calendar.ucsd.edu/api/2/events/...`; one API covers Birch plus many
  campus departments.
- Verify both appear in the exported opportunities.

## Sequence

Depends on: 01–05. High priority for the stakeholder demo; can run in
parallel with the automation work (07).

_Proposal / mock-up — rewrite freely._
