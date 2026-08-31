---
status: pending
---

# 9 duplicate-name slug collisions collapse 153 partners into 144 published directories

## Description

Found live during sprint 018 ticket 010's verification of `publish.project()`
(the first successful run since sprint 015): the curated partner roster has
153 entries but the published `public/data/` tree produces only 144 partner
directories — 9 pairs (or more) of partners whose slugified names collide,
so one silently overwrites another's directory in the per-partner
`events.json`/`past-events.json` output. Not a regression from ticket 010's
fix; pre-existing, confirmed unrelated, left untouched there.

## Proposed fix

Identify the 9 colliding name pairs (likely candidates: sprint 018 added
69 new roster orgs across two batches plus 52 backfilled logos — check for
near-duplicate names like differently-suffixed chapters, "X" vs "X, Inc.",
or genuine accidental dupes the ticket-002 housekeeping pass didn't catch).
Fix shape: either rename to disambiguate (append city/chapter per the
Boys & Girls Clubs precedent from ticket 004) or, if genuinely the same
org, dedupe per ticket 002's established method (verify registry org_name
join before removing either row). Add a regression test asserting the
roster's slugified names are unique (the missing invariant that let this
happen silently).

## References

Sprint 018 ticket 010 Notes (discovery); export/publish.py slug
derivation; sprint 018 ticket 002 (roster dedup precedent).
