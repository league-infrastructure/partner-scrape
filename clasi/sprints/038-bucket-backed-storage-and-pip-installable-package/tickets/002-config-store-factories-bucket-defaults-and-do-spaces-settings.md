---
id: '002'
title: Config Store factories, bucket defaults and DO_SPACES settings
status: in-progress
use-cases:
- SUC-001
- SUC-002
- SUC-004
depends-on:
- '001'
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Config Store factories, bucket defaults and DO_SPACES settings

## Description

Config resolves cache and data locations into Stores, defaulting to the bucket, with loud credential errors.

## Acceptance Criteria

- [ ] `config.py` adds `DO_SPACES_ENDPOINT` (region endpoint; rejects a bucket-qualified URL with an actionable message), `DO_SPACES_ACCESS_KEY`, `DO_SPACES_SECRET_KEY`
- [ ] One lazily built, shared boto3 client
- [ ] `get_scrape_cache_store()`: `SCRAPE_CACHE_DIR` defaults to `s3://jtl-stem-ecosystem-scrape/cache`; local path only when set explicitly (no longer required-with-no-default)
- [ ] `get_data_store()`: `PARTNER_SCRAPE_DATA_DIR` defaults to `s3://jtl-stem-ecosystem-scrape/data`; local only when set explicitly
- [ ] When an s3:// location is in effect and any `DO_SPACES_*` value is missing, a clear error names the missing variables and how to set them; `--help` and local-only runs need no credentials
- [ ] `tests/conftest.py` autouse fixture sets both locations to tmp_path, and a guard fails any test that builds an S3Store for the real bucket without moto
- [ ] Tests (monkeypatch env + moto) cover defaults, explicit local, explicit s3, missing credentials, bad endpoint

## Implementation Plan

Files: partner_scrape/config.py, tests/conftest.py, tests/test_config*.py. get_own_data_dir may remain as thin wrapper until ticket 005/006 remove call sites.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
