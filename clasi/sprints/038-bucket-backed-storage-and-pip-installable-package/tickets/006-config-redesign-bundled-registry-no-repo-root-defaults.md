---
id: '006'
title: 'Config redesign: bundled registry, no REPO_ROOT defaults'
status: in-progress
use-cases:
- SUC-004
depends-on:
- '005'
github-issue: ''
issue:
- 51-make-partner-scrape-a-pip-installable-standalone-package.md
- 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Config redesign: bundled registry, no REPO_ROOT defaults

## Description

One coherent config redesign: every location is a setting; the registry ships inside the package.

## Acceptance Criteria

- [ ] Root `registry/` (sources, hubs, candidates, ads) moves to `partner_scrape/registry_data/` via git mv and is included in the wheel
- [ ] `PARTNER_SCRAPE_REGISTRY_DIR` (location string, local path supported now) overrides the bundled default; designed so it could later be an s3:// location but no bucket registry loading is implemented
- [ ] `registry/loader.py`, `hub_schema.py`, `candidates.py`, `export/ads.py` defaults resolve through config; `SITE_DIR` required or CWD (no `../stem-ecosystem`)
- [ ] `REPO_ROOT`, `DEFAULT_OWN_DATA_DIR`, `DEFAULT_SITE_DIR` removed; a test greps that no module under `partner_scrape/` resolves defaults via `REPO_ROOT`
- [ ] Tests reading the real registry (test_registry.py, test_registry_candidates.py, teams/directory dataset-validity) still pass
- [ ] Verified that no test can silently hit the real bucket (conftest autouse + guard from ticket 002 still effective)
- [ ] Docs/scripts referencing `registry/` paths updated; registry DESIGN.md updated

## Implementation Plan

Files: config.py, registry/*, export/ads.py, pyproject.toml, docs.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
