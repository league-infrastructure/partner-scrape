---
status: done
sprint: '025'
tickets:
- 025-002
- 025-003
- 025-004
- 025-005
- 025-006
- 025-007
- 025-008
---

# Stop writing to the sibling stem-ecosystem checkout; publish exclusively to this repo's own data/

## Description

Stakeholder directive (Eric, 2026-08-31 conversation), verbatim: "I want you
not to write to the stem ecosystem directory. I want the stem ecosystem to
get data from you, so you're not writing the stem ecosystem anymore." Eric
then immediately asked for a full production scrape to be run — which only
makes sense once this write-removal has landed (a full run today would still
write into `../stem-ecosystem`, contradicting the directive).

Every export module already dual-writes: once into `{site_dir}/...` (the
sibling `stem-ecosystem` checkout) and once into `config.get_own_data_dir()`
(`<repo_root>/data`, established sprint 020, issue 60). This issue is about
removing the `{site_dir}/...` half of each already-dual-write function —
`data/` becomes the only place partner-scrape ever writes its own output;
`stem-ecosystem` becomes a pull-based consumer of it instead of a push
target.

## Known write paths to remove (site_dir → data/ only)

- `pipeline.py`'s `run()` → `export/writer.py`'s `export_opportunities()`
  (opportunities.json, scrape-meta.json).
- `export/ads.py`'s `export_ads()` (ads.json).
- `teams/pipeline.py`'s `run_teams()` → `teams/export.py`'s `export_teams()`
  (teams.json, written twice today: `src/data/` and `public/data/`).
- `directory/pipeline.py`'s `run_directory()` → `directory/export.py`'s
  `export_directory()` (places.json, clubs.json, each written twice:
  `src/data/` and `public/data/`).
- `cli.py`'s yield-history save (`observability/snapshot.py`'s
  `save_snapshot()`).
- `export/publish.py`'s `project()` — writes a *third*, richer per-partner
  data contract (`public/data/partners.json` + per-partner
  `events.json`/`past-events.json`) not part of sprint 020's dual-write
  pattern; needs its own investigation and its own redirect to `data/`.
- **Found during sprint 025 investigation, not in Eric's original
  enumeration**: `pipeline.py`'s `run()` constructs a real
  `export.images.EventImageDownloader` (when `image_resolver` is omitted)
  writing downloaded opportunity images into `{site_dir}/public/images/
  opportunities/` — a write path with no `own_data_dir` equivalent at all.
  stem-ecosystem's own measurement: 631 images, ~405MB, mean 655KB/median
  303KB, 147 files >1MB accounting for 67% of total bytes (including a
  5.2MB raw-camera-original JPEG served as a card thumbnail) — the
  downloader fetches and quality-gates but never resizes. Folding a
  resize-on-fetch step (long-edge cap, ~80% JPEG quality) into
  `EventImageDownloader` for newly-downloaded images, and redirecting the
  write target to `data/images/opportunities/`, is in scope here. The
  existing 631 unresized legacy images already committed in stem-ecosystem
  are explicitly NOT in scope (tracked as stem-ecosystem's own issue 58).

**`partners.json` — the READ, not a write — is explicitly out of scope.**
`pipeline.run()` reads `{site_dir}/src/data/partners.json` as a curated
input (roster validation, org_name join checks); this stays unchanged.
Eric's directive was specifically about writes; raised with him explicitly
during the conversation and not corrected.
