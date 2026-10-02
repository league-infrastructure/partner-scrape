---
id: '012'
title: Wheel smoke test, publish workflow, README
status: open
use-cases: ["SUC-004"]
depends-on: ["006", "009"]
github-issue: ''
issue: 51-make-partner-scrape-a-pip-installable-standalone-package.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wheel smoke test, publish workflow, README

## Description

Prove and publish the wheel.

## Acceptance Criteria

- [ ] `requires-python` re-checked; decision recorded on shipping DESIGN.md files
- [ ] CI workflow builds the wheel, installs it in a fresh venv in a temp dir outside the repo, runs `partner-scrape --help` (no bucket credentials needed) and one dry run with `SCRAPE_CACHE_DIR` and `PARTNER_SCRAPE_DATA_DIR` set explicitly to local temp dirs
- [ ] `.github/workflows/publish.yml` using PyPI trusted publishing, triggered on tag/release
- [ ] README documents `pip install partner-scrape` / `pipx install "partner-scrape[headless]"` and `playwright install chromium`
- [ ] Operator steps (claim PyPI name, configure trusted publisher) listed in the README/ticket, not performed

## Implementation Plan

Optionally have scheduled-run install the built wheel.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
