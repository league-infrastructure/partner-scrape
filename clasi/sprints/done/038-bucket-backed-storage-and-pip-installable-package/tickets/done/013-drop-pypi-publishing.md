---
id: '013'
title: Drop PyPI publishing
status: done
use-cases:
- SUC-004
depends-on:
- '012'
github-issue: ''
issue: 51-make-partner-scrape-a-pip-installable-standalone-package.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Drop PyPI publishing

## Description

Stakeholder decision 2026-10-02: partner-scrape will not be published to PyPI. The package code will later move into a different repo (partner-scrape and stem-ecosystem are being consolidated). SITE_REPO_TOKEN will not be provisioned, for the same reason. Remove the PyPI publishing artifacts added by ticket 012.

## Acceptance Criteria

- [x] `.github/workflows/publish.yml` deleted
- [x] README "Releasing" section and all PyPI/trusted-publishing instructions removed; install instructions describe only installing from a checkout or a built wheel (no `pip install partner-scrape` from PyPI)
- [x] `dev/wheel_smoke_test.py` and `.github/workflows/wheel-smoke.yml` kept; its `workflow_call` trigger removed if publish.yml was its only caller
- [x] sprint.md operator-task list: PyPI and SITE_REPO_TOKEN items removed, consolidation reason noted, and a note added that bucket versioning must be enabled with a full-access Spaces key (the bucket-scoped project key got AccessDenied on PutBucketVersioning)
- [x] `docs/deploy/scheduled-run.md` states SITE_REPO_TOKEN will not be provisioned pending repo consolidation and the weekly job's verify step will keep failing until then; the workflow itself is unchanged
- [x] Grep for "pypi", "trusted publish", "publish.yml" (case-insensitive) finds no remaining publishing workflow or instructions outside clasi/ history
- [x] `uv run pytest` passes

## Implementation Plan

Files: .github/workflows/publish.yml (delete), .github/workflows/wheel-smoke.yml, README.md, docs/deploy/scheduled-run.md, clasi/sprints/038-*/sprint.md. Also check pyproject.toml and docs for PyPI references.

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: none
- **Verification command**: `uv run pytest`
