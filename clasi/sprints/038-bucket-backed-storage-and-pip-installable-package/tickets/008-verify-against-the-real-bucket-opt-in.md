---
id: 008
title: Verify against the real bucket (opt-in)
status: in-progress
use-cases:
- SUC-001
- SUC-002
depends-on:
- '007'
github-issue: ''
issue: 50-move-cache-and-data-to-digitalocean-spaces.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify against the real bucket (opt-in)

## Description

Verify code against the pre-uploaded bucket before data leaves git.

## Acceptance Criteria

- [ ] Opt-in pytest marker `bucket` (skipped by default) and `dev/verify_bucket.py`
- [ ] Object counts under each `cache/` folder and `data/` match expectations from the local trees (data/ minus mirrors/)
- [ ] Spot-check byte-identity of sample objects
- [ ] A one-source run (e.g. coastalrootsfarm) with the s3 cache shows cache hits and no new LLM calls for unchanged content; partner_log for that source updated
- [ ] Results recorded in the ticket; if credentials are unavailable, escalate to team-lead rather than skipping

## Implementation Plan

Read/limited-write against real bucket only through the opt-in path.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
