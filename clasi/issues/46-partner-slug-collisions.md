---
status: pending
---

# 9 duplicate-name slug collisions collapse 153 partners into 144 published directories

## Description

Found live during sprint 018 ticket 010's verification of `publish.project()`
(the first successful run since sprint 015): the curated partner roster had
153 entries but the published `public/data/` tree produced only 144 partner
directories — 9 pairs of partners whose slugified names collided, so one
silently overwrote another's directory in the per-partner
`events.json`/`past-events.json` output. Not a regression from ticket 010's
fix; pre-existing, confirmed unrelated, left untouched there.

## Resolution (2026-08-31, verified by stem-ecosystem-8d)

**Content already fixed, diagnosis corrected.** Running `slugify()`
(`partner_scrape/model.py`) against both rosters: the old 153-row roster
produced 144 distinct slugs (9 collisions); the 211-row curated roster
that landed via sprint 018 + tonight's site consolidation produces 211
distinct slugs, zero collisions.

The 9 were **not** near-duplicate names needing disambiguation (what
this issue originally guessed) — they were exact duplicate rows, the
same org listed twice under two different ids (Fleet Science Center
twice, Viasat twice, Ocean Connectors twice, and so on). This also
explains the 8 id renumberings observed during the roster swap: the
211-row dedup dropped one row of each pair, and surviving orgs kept
different ids than their old duplicate-era selves. The published 144
directories become 211 the next time the pipeline runs against the
current roster.

**Residual work — the regression guard — folded into issue 48**
(pipeline-level roster validation), which now explicitly includes a
slug-uniqueness check. No separate ticket needed; closing this issue
rather than tracking a phantom "identify the 9 pairs" task that's
already resolved.

## References

Sprint 018 ticket 010 Notes (original discovery); `export/publish.py`
slug derivation; sprint 018 ticket 002 (roster dedup precedent); issue
48 (where the regression guard lives).
