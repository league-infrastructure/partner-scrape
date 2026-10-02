---
id: '003'
title: Rewire fetch, sitemap and partner_log caches to Store and new layout
status: in-progress
use-cases:
- SUC-001
depends-on:
- '002'
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rewire fetch, sitemap and partner_log caches to Store and new layout

## Description

Move the HTTP cache, sitemap snapshots and partner_log onto the Store with the stakeholder key layout.

## Acceptance Criteria

- [ ] `fetch/cache.py`: `_HOSTS_SUBDIR = "hosts"`; key `hosts/<domain>/<sha256(url)>.json`; `cache_path()` kept; `read_cache_entry`, `write_cache_entry`, `touch_fetch_timestamp`, `PoliteFetcher.__init__` use a Store; `cache_dir: Path | None` still accepted and wrapped in LocalStore
- [ ] `discovery/sitemap.py`: `_SNAPSHOT_SUBDIR = "sitemaps"`, uses `get_scrape_cache_store()` instead of inline config path
- [ ] `export/partner_log.py` and `export/publish.py`: `partner_log/` reads/writes via Store; the duplicate `_LOG_SUBDIR` constant is unified; `_default_log_dir` updated
- [ ] `tests/test_fetch_cache.py` assertions at ~:222, :774, :799 updated; file names/contents unchanged
- [ ] fetch/DESIGN.md, discovery and export DESIGN.md updated per design overlays

## Implementation Plan

Files: fetch/cache.py, discovery/sitemap.py, export/partner_log.py, export/publish.py plus tests.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
