---
status: done
sprint: 018
split_into:
- 35b-standing-entities-remaining-club-rosters.md
tickets:
- 018-006
- 018-007
- 018-008
- 018-009
---
## Description

Robot teams proved the pattern: undated standing entities need their
own model or the pipeline drops them. Two more directories of the same
shape:

**Clubs (sprint 018 scope: model + one proof-of-concept type).**
Generalize the `teams/` standing-entity pattern (model, static-roster
source, offline geocoding ladder) into a new `directory/` module
shared with Places below. Populate it with **Hack Club chapters** only
(University City HS, La Jolla HS, Helix Charter, Mater Dei Catholic —
`finder.hackclub.com` is a static list, the one club type this issue
already cites a ready curated source for). Every other club type named
in the original gap analysis (CyberPatriot teams, Science Olympiad
school teams, 4-H clubs, Girls Who Code clubs, Civil Air Patrol
squadrons, Sea Cadets units) is split off to
`35b-standing-entities-remaining-club-rosters.md` — each needs its own
curated-list research pass this sprint does not have room for
alongside issues 32 and 43. San Diego Math Circle and SDAA are single
orgs, not clubs — they stay issue 32's / the source registry's
concern, not this issue's.

**Places (sprint 018 scope: full directory).** A "where to go any day"
directory — makerspaces (SDPL IDEA Labs are the only free public ones;
Atlas Labs opening Jan 2027), planetariums (Fleet, Palomar College),
observatories (Palomar, Mount Laguna), tide pools (Cabrillo, Birch),
nature centers (County Parks, Agua Hedionda Discovery Center, Living
Coast, Tijuana Estuary), library maker labs. Small curated dataset,
high family value, near-zero maintenance — delivered in full this
sprint (no split needed; it was already bounded).

Same offline geocoding ladder as `teams/`, same "recruitment list"
value for Fleet/League. Do NOT design live scrapers for either
directory — a static-roster source (the FLL `static_roster` precedent)
plus site directory pages is the right shape; these are curated,
slow-changing datasets.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
