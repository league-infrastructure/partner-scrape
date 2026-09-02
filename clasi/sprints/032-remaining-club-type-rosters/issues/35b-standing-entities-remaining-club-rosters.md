---
status: in-progress
split_from: 35-standing-entities-clubs-and-places.md
sprint: '032'
tickets:
- 032-001
- 032-002
- 032-003
- 032-004
- 032-005
- 032-006
- 032-007
---

# Standing entities: remaining club-type rosters (deferred half of issue 35)

## Description

Split off from issue 35 by sprint 018 planning: the sprint-018 half of
issue 35 (see `35-standing-entities-clubs-and-places.md`, `split_into`)
delivers the `directory/` module (shared geocoding ladder, `Place`
model, full places directory, `Club` model, and Hack Club chapters as
the one populated proof-of-concept club type). It deliberately does
**not** populate every club type the original issue named — each
remaining type needs its own curated-list research pass, which is
genuine content work, not just applying the now-established pattern.

Remaining club types to populate against the `directory/` module's
`Club` model and static-roster source pattern, once curated lists
exist:

- CyberPatriot teams (Del Norte, Scripps Ranch are national finalists
  — a starting point, not a complete list)
- Science Olympiad school teams
- 4-H clubs (22+, robotics/drones/AI/animal science)
- Girls Who Code clubs
- Civil Air Patrol squadrons (144, 201, Group 8)
- Sea Cadets units

**Explicitly out of this issue's scope, resolved by sprint 018
planning:** San Diego Math Circle and San Diego Astronomy Association
(SDAA) are single organizations, not multi-chapter clubs — they belong
in the partner roster (issue 32) and/or the existing event-source
registry, not the `Club` standing-entity model. Do not re-register
them here. VEX teams already arrive via the RobotEvents adapter
(sprint 016 ticket 005, `teams/sources/robotevents.py`) and are out of
scope for this issue too.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
Split from issue 35 during sprint 018 planning (2026-08-31) — see
sprint 018's Architecture section for the `directory/` module design
this issue's future tickets should extend rather than re-design.
