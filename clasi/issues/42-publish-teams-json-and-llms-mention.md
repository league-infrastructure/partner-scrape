---
status: pending
---

# Publish teams.json in the public data contract and mention it in llms.txt

## Description

Stakeholder request (Eric, 2026-08-31): the robot-teams dataset should
be part of the published, statically-served data contract, and the
llms.txt discovery file should mention it.

Today `teams/export.py` writes `{site_dir}/src/data/teams.json` only —
a build-internal input the Astro site consumes. The public contract
(`public/data/` — partners.json + per-partner events, built by
`export/publish.py`) does not include teams at all, and
`site/public/llms.txt` describes only the partner/event files.

## Proposed fix

1. **Publish the file**: make `teams.json` available under the served
   `public/data/` tree (e.g. `public/data/teams.json`). Design choice
   for the planner: teach `teams/export.py` a second write target vs.
   project it at publish time alongside `export/publish.py`'s outputs —
   pick whichever respects the existing one-way dependency directions
   (teams/ never imports export/ internals and vice versa today).
   `teams.json` is already self-describing (its `meta` envelope carries
   `generated`, `total`, `by_league`, `by_location_precision`), so no
   new envelope work is needed — that was a deliberate sprint-011
   design property.
2. **Mention it in llms.txt** (`site/public/llms.txt`): a Data bullet
   describing the file (FIRST/VEX robotics teams directory for San
   Diego County: id, league, grade band, organization, location w/
   precision, status, sponsors) with its absolute URL
   (https://league-infrastructure.github.io/partner-scrape/data/teams.json
   if `public/data/` is the location chosen).
3. **Keep the discovery surfaces consistent**: llms.txt links to
   data-access and for-agents pages as the authoritative docs — add the
   teams.json shape there too (a short section: envelope + team field
   list, mirroring how data-access documents the event schema), so the
   llms.txt claim "no other data source needed" stays true.
4. Remember `site/` (beta, this repo) is the write target; the sibling
   production repo's parity is issue 41's concern, not this one's.

## Verification

Hermetic tests per project convention (fixture teams → published file
exists at the public path with intact envelope; llms.txt/data-access
content assertions if the existing test suite covers those pages — see
tests/test_site_data_access_page.py precedent).

## References

partner_scrape/teams/export.py · partner_scrape/export/publish.py ·
site/public/llms.txt · sprint 010 issues 16/17 (llms.txt + agent
discovery) · sprint 009 issue 15 (self-describing export).
