---
id: 009
title: Remove data/ from git; move SCHEMA.md and publish it
status: in-progress
use-cases:
- SUC-002
depends-on:
- 008
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove data/ from git; move SCHEMA.md and publish it

## Description

Take generated data out of git and publish the schema doc with the data.

## Acceptance Criteria

- [ ] `git rm -r --cached data/`; `data/` added to `.gitignore`
- [ ] `data/SCHEMA.md` moved to `docs/data-schema.md` (source copy); bundled in the wheel via hatch force-include (approved); published to `data/SCHEMA.md` in the data Store at the end of a run
- [ ] Text claiming data is committed to git fixed (SCHEMA.md line 6, snapshot.py docstring, docs/deploy/scheduled-run.md)
- [ ] `git ls-files data/` is empty; full suite passes
- [ ] docs/design/design.md updated: Storage section, bucket versioning replaces git history for yield-history.json

## Implementation Plan

Operator enables bucket versioning (not part of this ticket).
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
