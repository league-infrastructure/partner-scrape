---
id: '001'
title: 'Add storage module: Store protocol, LocalStore, S3Store'
status: open
use-cases: ["SUC-001", "SUC-002"]
depends-on: []
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add storage module: Store protocol, LocalStore, S3Store

## Description

Create the Store abstraction that everything else builds on. No project config access; leaf module.

## Acceptance Criteria

- [ ] `partner_scrape/storage.py` defines a `Store` protocol: `read_bytes(key)` (None when missing), `write_bytes(key, data, content_type=None)`, `read_text`/`write_text`, `read_json`/`write_json` (indent=2), `exists(key)`, `list(prefix)`
- [ ] `LocalStore(root: Path)` creates parent dirs and writes atomically (temp file + `os.replace`); the helper moves from `export/partner_log.py::_atomic_write_text` and callers are updated
- [ ] `S3Store(bucket, prefix, client)` maps NoSuchKey/404 to None, applies prefix to keys, sets ContentType
- [ ] `store_from_location(str | Path)` returns S3Store for `s3://bucket/prefix`, else LocalStore
- [ ] `storage.py` does not import `config`
- [ ] `boto3` added to dependencies, `moto[s3]` to dev group
- [ ] `tests/test_storage.py` covers both backends: missing->None, round trip, prefix keys, content type, list, no stray .tmp left

## Implementation Plan

Files: partner_scrape/storage.py (new), export/partner_log.py, pyproject.toml, tests/test_storage.py. Docs: partner_scrape/DESIGN.md storage section.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
