---
id: '005'
title: Route data output through the data Store
status: open
use-cases: ["SUC-002"]
depends-on: ["002"]
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Route data output through the data Store

## Description

Make every writer of published output use the data Store with unchanged keys.

## Acceptance Criteria

- [ ] Switched to `get_data_store()`: `export/writer.py`, `export/ads.py`, `export/publish.py`, `export/images.py`, `teams/export.py`, `directory/export.py`, `observability/snapshot.py`, `dev/backfill_missing_images.py`, and call sites in `pipeline.py`/`cli.py`
- [ ] Keys are identical to today's `data/` layout; Content-Type `application/json` or `image/*`
- [ ] `EventImageDownloader` takes a store plus the `images/opportunities/` prefix and skips the write when the key exists
- [ ] `yield-history.json` is read back and saved through the Store
- [ ] Docstrings/comments claiming data is committed to git are corrected
- [ ] All tests use LocalStore/tmp_path and stay offline

## Implementation Plan

Files listed above plus tests.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
