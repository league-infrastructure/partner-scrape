---
id: '007'
title: Persist settings in dotconfig and update scheduled-run CI
status: open
use-cases: ["SUC-001", "SUC-002"]
depends-on: ["003", "004", "005", "006"]
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Persist settings in dotconfig and update scheduled-run CI

## Description

Make settings permanent and remove git/actions-cache machinery from CI.

## Acceptance Criteria

- [ ] `config/prod/public.env`: `SCRAPE_CACHE_DIR`, `PARTNER_SCRAPE_DATA_DIR` (s3 values matching defaults), `DO_SPACES_ENDPOINT=https://sfo3.digitaloceanspaces.com` (not bucket-qualified)
- [ ] `config/prod/secrets.env` (SOPS): `DO_SPACES_ACCESS_KEY`, `DO_SPACES_SECRET_KEY`; if SOPS key is unavailable, document and hand to the operator (do not write plaintext)
- [ ] `.github/workflows/scheduled-run.yml`: actions/cache steps removed, `git add data/` publish step removed, DO_SPACES_* secrets passed, `contents: read`
- [ ] `docs/deploy/scheduled-run.md` updated; known external blocker (missing SITE_REPO_TOKEN) noted as an operator task

## Implementation Plan

Note: .env currently holds a bucket-qualified endpoint; correct it.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
