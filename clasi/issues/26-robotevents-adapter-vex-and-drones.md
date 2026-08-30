---
status: pending
---

# RobotEvents API adapter: VEX Region 4 events and teams, plus drone competitions

## Description

FIRST teams are now covered; VEX is the other big robotics league in
San Diego and is entirely absent. CA Region 4 (San Diego/Imperial) runs
V5RC (MS/HS) and VIQRC (ES/MS): roughly a dozen local tournaments per
season plus two ~96-team regional championships (Feb 27-Mar 1 2026 at
Town & Country). Sweetwater UHSD STEAM anchors the region. The Aerial
Drone Competition (RECF + partner Robolink, grades 5-12, West
championship at Balboa Park Activity Center) lives on the same
platform.

**RobotEvents API v2** (robotevents.com/api/v2): /events, /teams,
/seasons, /programs, filterable by season/region/level; free bearer
token from a RobotEvents account. robotevents.com 403s plain fetches —
use the API, not scraping.

## Proposed fix

- New `robotevents` adapter (structured API, like tec/localist):
  events → opportunity pipeline (spectator-open tournaments, free).
- Teams → the `teams/` pipeline as a new TeamSource (like ftcscout.py):
  VEX teams alongside FTC/FRC/FLL, with the same org merge + geocoding
  ladder. This also feeds the sponsor/recruitment angle from sprint 013.
- Token in secrets.env (SOPS), like TBA_KEY.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
