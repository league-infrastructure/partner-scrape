---
status: pending
---

# Publish the pipeline's own output in a well-known data/ directory in this repo

## Description

Stakeholder request (Eric, 2026-08-31): partner-scrape's job is scrape →
cache raw pages → transform into JSON. Right now, that JSON has nowhere
to live *in this repo*. Every writer (`export/writer.py`'s
opportunities.json/scrape-meta.json, `teams/export.py`'s teams.json,
`directory/export.py`'s places.json/clubs.json) writes exclusively to
`SITE_DIR`, which defaults to the sibling `../stem-ecosystem` checkout.
Clone partner-scrape today and run it, and nothing the pipeline produces
ends up committed anywhere in partner-scrape's own git history — the
data engine publishes nothing of its own.

Meanwhile the root `data/` directory holds two files nobody reads:
`partners_viable.csv` (its only production reader, `run_mirrors.py`, was
deleted tonight in sprint 019 ticket 003 — a test file is now the only
remaining reference) and `robot-teams.json` (always docstring/comment-only
— it informed a hand-written city list in `teams/sources/tba.py` once,
never read at runtime). Confirmed dead, not merely stale.

## Cause

The pipeline's output was designed around a single consumer (the site
checkout at `SITE_DIR`) rather than as a published artifact in its own
right. Tonight's site consolidation (issue "consolidate-partner-scrape-
s-beta-site-into-stem-ecosystem-production") removed the one thing that
used to give partner-scrape a local copy of its own output — the
`site/` mirror target — without replacing it with anything, since at
the time the only known consumer was the site build. This surfaced the
gap: the data engine's product deserves a home independent of any one
consumer.

## Proposed fix

1. Delete `data/partners_viable.csv` and `data/robot-teams.json`
   (confirmed dead per above); update the one test referencing the CSV
   (`tests/test_roster_housekeeping.py`).
2. Every pipeline run additionally writes its output — `opportunities.json`,
   `scrape-meta.json`, `teams.json`, `places.json`, `clubs.json`,
   `ads.json`, `yield-history.json` — into `data/` in partner-scrape's
   own tree, committed to this repo's git history. Unconditional, not an
   opt-in mirror: this becomes the pipeline's own published home, not an
   extra copy of someone else's.
3. **Do not include `partners.json`.** It is hand-curated input (never a
   pipeline output — `normalize/partners.py` reads it read-only) and is
   now owned exclusively by stem-ecosystem post-consolidation
   ("hand-curated, edited only here" per its README). Including a copy
   here would recreate the exact two-independently-edited-copies problem
   tonight's consolidation eliminated. If a consumer needs the roster,
   stem-ecosystem is the source.
4. **Do not include the raw scrape cache.** `SCRAPE_CACHE_DIR` stays
   off-repo (tens of GB, no safe default, git-ignored) exactly as today
   — this issue is about the transformed JSON product, not the raw
   mirror.
5. `SITE_DIR`'s existing role (writing a build-time copy into
   stem-ecosystem, via `scheduled-run.yml`'s PAT-based push) is
   unchanged — this is an *additional*, simultaneous publish target from
   the same pipeline run, not a replacement. One generation event,
   two destinations: this repo's own `data/` (self-published artifact)
   and stem-ecosystem (the site's build-time input).

## Verification

A real pipeline run produces a diff-visible, committed change under
`data/` in this repo; `uv run pytest -q` green with the CSV-referencing
test updated; the two legacy files are gone with zero remaining
references outside `clasi/`.

## References

Discovered during the site-consolidation sprint's aftermath (2026-08-31);
`partner_scrape/config.py` (`SITE_DIR`), `export/writer.py`,
`teams/export.py`, `directory/export.py`.
