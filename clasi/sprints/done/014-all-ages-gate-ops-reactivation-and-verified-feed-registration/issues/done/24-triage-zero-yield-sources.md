---
status: done
sprint: '014'
tickets:
- 014-003
---

# Triage the 33 zero-yield sources

## Description

33 of 99 sources found zero records in the 2026-08-28 run, including
sources that should be among the largest:

- **sdpl** (San Diego Public Library) — bibliocommons adapter, same
  platform as SDCL's 3,957 found. Something is broken, not empty.
- **cleansd / ilacsd / eefkids** — Tier-1 TEC REST APIs that worked in
  the dev/ era. Probe the endpoints; the cleansd/ilacsd domain split is
  documented in dev/SCRAPER_GUIDELINES.md §8.
- **sandiegozoowildlifealliance, sdgirlscouts, ecovivarium,
  agua-hedionda, sdcwa, sdfutures, robolink, lajollalibrary,
  usasciencefestival** and the rest — classify each: site moved, Wix/JS
  (→ issue 23), sitemap gone, org defunct, or genuinely quiet.
- ATS boards (boundlessbio, gossamerbio, elementbiosciences, shieldai)
  — zero open matching jobs is a legitimate state; re-verify the board
  tokens are still live per the source TOML comments.

Full zero list is in yield-history.json. Output: each source either
fixed, re-typed (better adapter), marked headless, or disabled with a
reason in its TOML. Also fix two mis-registrations found 2026-08-30:
`sd-river-park-foundation` runs TEC (verified live, 73 events) but is
registered `generic_html` → flip to `tec_rest`
(https://sandiegoriver.org/wp-json/tribe/events/v1/events/); and
`sandiego-gov`'s org_name says "Discover U at San Diego Public Library"
while its site_url is sandiego.gov — untangle.

## References

Gap analysis 2026-08-30: https://claude.ai/code/artifact/02ba9c3e-61a2-40eb-a987-444463cd3266
