---
id: '011'
title: stem-ecosystem fetch-data.sh bucket mode (cross-repo)
status: in-progress
use-cases:
- SUC-003
depends-on:
- 009
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# stem-ecosystem fetch-data.sh bucket mode (cross-repo)

## Description

CROSS-REPO: this change is made in /Users/eric/proj/league/infrastructure/stem-ecosystem and committed in that repo, not partner-scrape.

## Acceptance Criteria

- [ ] `scripts/fetch-data.sh` gains a bucket source mode: `aws s3 sync s3://jtl-stem-ecosystem-scrape/data/` (sfo3 endpoint) into a temp dir, then the existing explicit copy list and image check run unchanged
- [ ] Existing source mode behavior unchanged
- [ ] Usage documented in the script header/README; deploy workflow stays manual
- [ ] Verified: image check passes and `npm run build` succeeds against bucket data (needs credentials)

## Implementation Plan

Record the stem-ecosystem commit hash in this ticket.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
