---
status: in-progress
sprint: 028
tickets:
- 028-003
- 028-004
- 028-005
- 028-006
split_into:
- pike13-camp-platform-adapter.md
---
Camps are most of the STEM seats in the county and invisible on the
site — including our own partners' camps (Fleet ran 27 topics over 10
weeks for 787 campers in 2025). Registration platforms mostly block
bots, but ~10 of the largest providers publish full session dates and
prices in plain HTML on their marketing pages (verified 2026-08-30).

**Marketing-page extraction targets (dates+prices in HTML):**
- San Diego Zoo per-program pages (zoo.sandiegozoo.org/kids-programs/*,
  9 programs × 8 weeks, Jun 8-Aug 7 2026, $525/wk)
- Air & Space Museum (sandiegoairandspace.org/education/summer-camps,
  incl. sold-out flags)
- Living Coast (thelivingcoast.org/camps — full table, 4 seasons)
- Coastal Roots Farm (coastalrootsfarm.org/farm-camp — sessions table)
- Elementary Institute of Science (eisca.org/camps)
- SD Model Railroad Museum (sdmrm.org/summer-camps — table + sold-out)
- Camp Galileo SD location page (all weeks + per-grade prices) —
  **resolved 2026-09-01 (sprint 028 detail planning): this is the
  commercial "Galileo" studio brand named in this same issue's open
  stakeholder decision below, not a separate nonprofit-adjacent
  source. Excluded from sprint 028's marketing-page registration on
  that basis, not registered.**
- Camp Invention per-program pages (invent.org/program-search/...)
- CMOD (visitcmod.org/camps + seasonal pages)
- Helen Woodward (animalcenter.org — week dates in HTML) — **sprint
  028 registers this org via the ActiveNet platform adapter below
  instead of its marketing page, to avoid dual registration.**
- Southwestern College Y.E.S. (XenDirect, server-rendered)
- Birch: newsroom page carries dates/prices (main site 403s → issue 23)
- Fleet: marketing page is in-season only; reg opens Feb — schedule a
  seasonal check.

**Platform adapters worth building (in order):**
1. `campscui.active.com` (ActiveNet camps UI — Air & Space, Helen
   Woodward, likely more; HTML-ish) — **sprint 028**
2. CampBrain (Coastal Roots, Watersports Camp) — **sprint 028**
3. Pike13 API (developer.pike13.com — the League's own camps; the
   cleanest API of any provider; supersedes gaps in leaguesync?) —
   **split out 2026-09-01 to `pike13-camp-platform-adapter.md`**,
   deferred past sprint 028 (credential provisioning and the
   leaguesync-overlap question both unresolved).

**Blocked/JS (needs issue 23 browser path):** Gateway Galaxy webstores,
SeaWorld, YMCA Salesforce, Code Ninjas, Mad Science, Challenge Island
portal, RoboThink, iD Tech.

Depends on the schema issue for the `Camps` opportunity_type, already
delivered by sprint 015. A season-ahead view ("Summer 2027 camps" in
January when registration opens) is the site-side payoff — sprint 028
delivers this via the existing weekly cron plus graceful empty-page
handling, not a new scheduling subsystem (see
`adapters/DESIGN.md`'s sprint 028 Design Rationale).

**Open stakeholder decision:** whether commercial chains (Code Ninjas,
iD Tech, Galileo, Mathnasium, RSM — competitors of the League's own
classes) are listed. Not decided 2026-08-30; institutional/nonprofit
camps are uncontroversial — start there. Sprint 028 does not resolve
this decision; it excludes all named commercial chains, Camp Galileo
included, per the note above.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266