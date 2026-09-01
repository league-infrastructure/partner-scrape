---
id: '008'
title: Retire the dead stem-ecosystem CI publish step and live-verify the full write-removal
status: open
use-cases: [SUC-029, SUC-030]
depends-on: ['001', '002', '003', '004', '005', '006', '007']
github-issue: ''
issue: stop-writing-to-stem-ecosystem-checkout.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Retire the dead stem-ecosystem CI publish step and live-verify the full write-removal

## Description

Once tickets 001–007 land, `.github/workflows/scheduled-run.yml`'s
"Publish refreshed site data to stem-ecosystem" step (`git add -A` /
commit / push inside the `stem-ecosystem` checkout) becomes permanently
dead — nothing writes there anymore, so it will always no-op. Remove
it. The "Checkout stem-ecosystem" step **stays** — `pipeline.run()`
still reads `{site_dir}/src/data/partners.json` as an input.

This ticket also carries the sprint's required live verification: a
real, non-dry-run invocation of `run`, `teams`, and `directory` against
the real `../stem-ecosystem` checkout and the real (post-move)
`registry/`, proving the write-removal holds outside of any test
fixture.

## Acceptance Criteria

- [ ] `.github/workflows/scheduled-run.yml`'s "Publish refreshed site
      data to stem-ecosystem" step is removed.
- [ ] The "Checkout stem-ecosystem" step is unchanged (still needed for
      the `partners.json` read).
- [ ] The "Verify SITE_REPO_TOKEN is configured" step's error message no
      longer says this workflow "publishes scraped data to
      league-infrastructure/stem-ecosystem" — reworded to reflect a
      read-only checkout.
- [ ] A code comment near `SITE_REPO_TOKEN`'s declaration notes its
      `contents:write` scope on stem-ecosystem is no longer exercised by
      this workflow (informational only — no token/secret change is made
      by this ticket).
- [ ] **Live verification, performed and its result recorded in this
      ticket's own notes before it is marked done**:
  1. Checksum (or mtime-sweep) every file under `../stem-ecosystem`.
  2. Run `uv run partner-scrape --site-dir ../stem-ecosystem` (a real,
     non-dry-run, full run — no `--limit`/`--source`).
  3. Run `uv run partner-scrape teams --site-dir ../stem-ecosystem`.
  4. Run `uv run partner-scrape directory --site-dir ../stem-ecosystem`.
  5. Re-checksum/re-sweep `../stem-ecosystem`; assert **zero** files
     changed (added, removed, or modified).
  6. Confirm `data/` is fully populated: `opportunities.json`,
     `scrape-meta.json`, `ads.json`, `teams.json`, `places.json`,
     `clubs.json`, `yield-history.json`, `partners.json`,
     `partners/<slug>/events.json`, `partners/<slug>/past-events.json`,
     `images/opportunities/*` — flat layout throughout, no `src/`/
     `public/` split.
  7. Spot-check at least one newly-downloaded image under
     `data/images/opportunities/` is resized (smaller than a
     known-oversized original) if any oversized source image was
     encountered this run.
- [ ] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: CI-wiring edit first (small, low-risk, mirrors sprint
020 ticket 008's own precedent of touching `scheduled-run.yml`), then
the live verification, which is the only way to prove "stop writing to
stem-ecosystem" holds against the real checkout rather than a `tmp_path`
fixture.

1. Edit `.github/workflows/scheduled-run.yml`: delete the "Publish
   refreshed site data to stem-ecosystem" step in its entirety. Update
   the "Verify SITE_REPO_TOKEN is configured" step's `::error::`
   message lines. Add a short comment near the `permissions:` block or
   the `SITE_REPO_TOKEN` checkout step noting the write-scope note above.
2. Run the live verification exactly as enumerated in Acceptance
   Criteria, against the real sibling `../stem-ecosystem` checkout on
   this machine. Record the before/after checksum comparison result
   (e.g. a diff of `find ../stem-ecosystem -type f -exec sha256sum {}
   \; | sort` before and after) directly in this ticket file under a
   "Live Verification Result" heading before marking it done.
3. If the checksum comparison shows ANY change under
   `../stem-ecosystem`, that is a signal a write path was missed by
   tickets 001–007 — do not mark this ticket done; identify the leak
   (grep for `site_dir`/`get_site_dir` usages that still perform a
   write, not just a read) and either fix it here or throw an exception
   per this project's Exception Protocol if it points to an upstream
   architecture gap.

**Files to modify**: `.github/workflows/scheduled-run.yml`.

**Testing plan**: this ticket's "testing" *is* the live verification
above — not a substitute for it. Also run the full suite one final time
(`uv run pytest -q`) to confirm every prior ticket's test updates are
still green together, not just individually.

**Documentation updates**: none beyond the workflow file's own inline
comments (see step 1).
