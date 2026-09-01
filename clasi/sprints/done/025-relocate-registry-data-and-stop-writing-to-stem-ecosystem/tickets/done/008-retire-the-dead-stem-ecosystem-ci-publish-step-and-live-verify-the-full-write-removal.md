---
id: 008
title: Retire the dead stem-ecosystem CI publish step and live-verify the full write-removal
status: done
use-cases:
- SUC-029
- SUC-030
depends-on:
- '001'
- '002'
- '003'
- '004'
- '005'
- '006'
- '007'
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

- [x] `.github/workflows/scheduled-run.yml`'s "Publish refreshed site
      data to stem-ecosystem" step is removed.
- [x] The "Checkout stem-ecosystem" step is unchanged (still needed for
      the `partners.json` read).
- [x] The "Verify SITE_REPO_TOKEN is configured" step's error message no
      longer says this workflow "publishes scraped data to
      league-infrastructure/stem-ecosystem" — reworded to reflect a
      read-only checkout.
- [x] A code comment near `SITE_REPO_TOKEN`'s declaration notes its
      `contents:write` scope on stem-ecosystem is no longer exercised by
      this workflow (informational only — no token/secret change is made
      by this ticket).
- [x] **Live verification, performed and its result recorded in this
      ticket's own notes before it is marked done**:
  1. [x] Checksum (or mtime-sweep) every file under `../stem-ecosystem`.
  2. [x] Run `uv run partner-scrape --site-dir ../stem-ecosystem` (a real,
     non-dry-run, full run — no `--limit`/`--source`).
  3. [x] Run `uv run partner-scrape teams --site-dir ../stem-ecosystem`.
  4. [x] Run `uv run partner-scrape directory --site-dir ../stem-ecosystem`.
  5. [x] Re-checksum/re-sweep `../stem-ecosystem`; assert **zero** files
     changed (added, removed, or modified).
  6. [x] Confirm `data/` is fully populated: `opportunities.json`,
     `scrape-meta.json`, `ads.json`, `teams.json`, `places.json`,
     `clubs.json`, `yield-history.json`, `partners.json`,
     `partners/<slug>/events.json`, `partners/<slug>/past-events.json`,
     `images/opportunities/*` — flat layout throughout, no `src/`/
     `public/` split.
  7. [x] Spot-check at least one newly-downloaded image under
     `data/images/opportunities/` is resized (smaller than a
     known-oversized original) if any oversized source image was
     encountered this run.
- [x] `uv run pytest -q` is green.

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

## Live Verification Result

Performed 2026-09-01, on branch
`sprint/025-relocate-registry-data-and-stop-writing-to-stem-ecosystem`,
against the real sibling checkout at `../stem-ecosystem`
(`/Volumes/Proj/proj/league-projects/infrastructure/stem-ecosystem`, a
pre-existing developer checkout with its own unrelated pending local
changes — a modified `.gitignore` and an untracked `config/` dir —
present both before and after this verification, unchanged).

### Environment

- `SCRAPE_CACHE_DIR` sourced from `config/prod/public.env`
  (`/Volumes/Cache/stem-ecosystem`, pre-populated from prior local runs).
- `ANTHROPIC_API_KEY` was already ambient in the session environment —
  no sourcing needed.
- For the `teams` run, `TBA_KEY` (needed for the `frc-sd` source) was
  sourced from the repo's dotconfig-assembled `.env` via `set -a &&
  source .env && set +a`, per sprint 024 ticket 002's documented
  fallback. `ROBOTEVENTS_KEY` (needed for `vex-sd`) is not present in
  `.env`, `public.env`, or the ambient session environment — this is a
  pre-existing, structural credential gap unrelated to this ticket (the
  `teams` pipeline is explicitly designed to tolerate it: it logs a
  `CredentialError`, skips only that one source, continues the run, and
  reports it in `teams.json`'s own `meta.credential_failures` field —
  confirmed below).

### Steps 1–5: checksum, three real runs, re-checksum, diff

1. **Before**: `find ../stem-ecosystem -type f -exec sha256sum {} \; |
   sort` → 14,083 files, saved to scratchpad `before.txt`.
2. `uv run partner-scrape --site-dir ../stem-ecosystem -v` — real,
   non-dry-run, full run, no `--limit`/`--source`/`--no-enrich`. All 122
   registry sources ran; 9 failed individually (network/site issues —
   `climate-science-alliance`, `escondido-creek-conservancy`, `gsdsef`,
   `leaguesync`, `robotevents-vex-sd`, `sandiego-cv-aopsacademy`,
   `sdrvc`, `techadventurecamp`, `xplorstem`) and were skipped per the
   documented per-source isolation ("run continues with the remaining
   sources"); `ALERTS: none`. LLM enrichment ran for real (Anthropic API
   calls visible in the log). Result: **wrote 334 opportunities.**
3. `uv run partner-scrape teams -v` — real, full run. Note: the `teams`
   subcommand does **not** accept a `--site-dir` flag at all (confirmed
   via `--help`; it was fully decoupled from `site_dir` by ticket 004,
   with no read dependency on it either) — this ticket's own
   Acceptance Criteria item 3's exact command line is stale in that one
   respect; ran the command as the CLI actually accepts it. Result:
   **wrote 278 teams** (`by_league`: FLL 48, FRC 78, FTC 152;
   `credential_failures: ["VEX"]` — the expected `ROBOTEVENTS_KEY` gap
   above; `frc-sd` succeeded with `TBA_KEY` sourced).
4. `uv run partner-scrape directory --site-dir ../stem-ecosystem -v` —
   real, full run. Result: **wrote 19 places and 4 clubs.**
5. **After**: re-ran the same `find ... | sha256sum | sort` sweep → also
   14,083 files, saved to scratchpad `after.txt`. `diff before.txt
   after.txt` → **0 lines of diff. Zero files added, removed, or
   modified under `../stem-ecosystem` across all three runs.** This is
   the proof that "stop writing to stem-ecosystem" holds against the
   real checkout. `git -C ../stem-ecosystem status` before and after
   the verification is also identical (same pre-existing unrelated
   local changes, nothing new).

### Step 6: `data/` contents

All required files present, all flat (no `src/`/`public/` split):

- `data/opportunities.json` (334 opportunities, 548 KB)
- `data/scrape-meta.json` (`{"last_updated": "2026-09-01T08:27:52Z"}`)
- `data/ads.json` (1 ad)
- `data/teams.json` (278 teams, 265 KB)
- `data/places.json` (19 places, 14.8 KB)
- `data/clubs.json` (4 clubs, 2.3 KB)
- `data/yield-history.json` (93 source keys, 133 KB)
- `data/partners.json` (294 KB)
- `data/partners/<slug>/events.json` and `.../past-events.json` — 211
  partner directories, every one has both files (verified
  programmatically, zero missing).
- `data/images/opportunities/*` — 375 newly-downloaded images.
- `data/` total size: 169 MB (163 MB images, 4.7 MB partner logs).
- Top level of `data/` contains only `*.json` files plus the `images/`
  and `partners/` directories — confirmed no `src/` or `public/` subtree
  exists anywhere under it.

### Step 7: image-resize spot-check

Among the 375 newly-downloaded images, none exceed 1600px on either
dimension (max long edge observed: 1600), and 90 of the 375 have a long
edge of exactly 1600px — consistent with `RESIZE_LONG_EDGE` capping.

For a definitive, non-circumstantial check, one specific case was
traced end-to-end: `data/images/opportunities/19034ab6318540a3.png`
(stored: 1600×1067, RGBA, 3,241,863 bytes) is the image for The Living
Coast Discovery Center's "Sea Turtle Presentation" event
(`https://www.thelivingcoast.org/programs-events-upcoming-events/
sea-turtle-presentation-2-2/2026-09-02/`, found via the per-partner
accumulation log under `$SCRAPE_CACHE_DIR/partner_log/`). Re-fetching
the same source image live
(`https://www.thelivingcoast.org/wp-content/uploads/2024/11/
emerald-web.png`) returned the true original: **1800×1200,
RGBA, 3,782,212 bytes** — i.e. our stored copy is smaller in both
dimensions and bytes than the real oversized original, and
1800×1200 scaled to fit within a 1600×1600 box (preserving aspect
ratio, matching `Image.thumbnail`) computes to exactly **1600×1067**,
which is exactly what was stored. This confirms resize-on-fetch fired
correctly for a real, newly-downloaded, genuinely oversized source
image during this run. (Temp files from this check were written to and
removed from the session scratchpad; nothing was added to the repo or
to `../stem-ecosystem`.)

### Additional grep sweep (Acceptance Criteria / Implementation Plan
step 3's instruction, run proactively rather than only on a non-zero
checksum diff)

`grep -rn "site_dir\|get_site_dir" partner_scrape/ --include="*.py"`
across the whole package found no remaining *write* usage — every
production `site_dir`/`get_site_dir()` reference left standing is a
read (the `{site_dir}/src/data/partners.json` join/reference read that
tickets 001–007 always intended to keep). That matches the zero-diff
checksum result above and required no fix under Implementation Plan
step 3.

The sweep did surface three **stale help-text/docstring** strings left
over from tickets 003/005/007 that still described `--site-dir` (or
`pipeline.run()`'s `site_dir` parameter) as a *write* target after the
write itself had already been removed — not a functional leak (nothing
in these strings performs I/O), but directly misleading operator-facing
documentation about the exact behavior this ticket exists to correct.
Fixed as a small, low-risk, in-scope correction alongside the CI edit:

- `partner_scrape/cli.py`: the `run` subcommand's `--site-dir` and
  `--dry-run` help text (previously said "to write opportunities.json /
  scrape-meta.json into" and "without writing anything to --site-dir").
- `partner_scrape/cli.py`: the `directory` subcommand's description,
  `--dry-run` help, and `--site-dir` help text (previously said
  "publish {site_dir}/src/data/places.json and
  {site_dir}/src/data/clubs.json..." and "same default and override as
  the `run`/`teams` commands' --site-dir" — the `teams` half of that
  claim was independently wrong too, since `teams` never accepted
  `--site-dir` at all, see step 3 above).
- `partner_scrape/pipeline.py`: `run()`'s `site_dir` parameter
  docstring (previously said "sibling `stem-ecosystem` checkout to
  write into").

All three are documentation-only edits (help strings / docstrings); no
behavior changed. Verified no test asserts the old strings, and the
full suite (below) is unaffected.

### `uv run pytest -q`

**1941 passed** — run once before the live verification (confirming
tickets 001–007's changes are green together) and once again after all
of the above, including the three doc-string fixes. Both runs: 1941
passed, 0 failed.
