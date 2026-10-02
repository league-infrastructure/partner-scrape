---
id: '012'
title: Wheel smoke test, publish workflow, README
status: done
use-cases:
- SUC-004
depends-on:
- '006'
- 009
github-issue: ''
issue: 51-make-partner-scrape-a-pip-installable-standalone-package.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wheel smoke test, publish workflow, README

## Description

Prove and publish the wheel.

## Acceptance Criteria

- [x] `requires-python` re-checked; decision recorded on shipping DESIGN.md files
- [x] CI workflow builds the wheel, installs it in a fresh venv in a temp dir outside the repo, runs `partner-scrape --help` (no bucket credentials needed) and one dry run with `SCRAPE_CACHE_DIR` and `PARTNER_SCRAPE_DATA_DIR` set explicitly to local temp dirs
- [x] `.github/workflows/publish.yml` using PyPI trusted publishing, triggered on tag/release
- [x] README documents `pip install partner-scrape` / `pipx install "partner-scrape[headless]"` and `playwright install chromium`
- [x] Operator steps (claim PyPI name, configure trusted publisher) listed in the README/ticket, not performed

## Implementation Plan

Optionally have scheduled-run install the built wheel.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`

## Implementation Notes

- `requires-python` lowered `>=3.13` -> `>=3.11` with evidence: full suite (2617 passed, 2 skipped) on 3.11, 3.12, 3.13; 3.10 fails on stdlib `tomllib`. Decision recorded in `partner_scrape/DESIGN.md` section 4.
- Smoke test found a real bug: ticket 009's unanchored `data/` in `.gitignore` made hatchling drop `partner_scrape/directory/data/` and `teams/data/` from the wheel. Fixed by anchoring to `/data/` (and `tests/test_schema_doc.py` now asserts the anchored form); the smoke test asserts those files are in the installed package.
- `dev/wheel_smoke_test.py` + `.github/workflows/wheel-smoke.yml` (3.11 and 3.13) + `.github/workflows/publish.yml` (test -> smoke -> build -> trusted publish, `id-token: write`, environment `pypi`).
- Operator steps (NOT done): claim the PyPI name / pending publisher; register trusted publisher (league-infrastructure/partner-scrape, publish.yml, env pypi); create GitHub env `pypi`. Documented in README "Releasing".
- Optional "scheduled-run installs the wheel" left undone (ticket says optional).
