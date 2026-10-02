---
id: '010'
title: Schema doc drift guard
status: in-progress
use-cases:
- SUC-005
depends-on:
- 009
github-issue: ''
issue: 46-schema-doc-drift-guard.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Schema doc drift guard

## Description

Issue 46 drift guard targeting the new docs location.

## Acceptance Criteria

- [ ] Test parses field lists from `docs/data-schema.md` and asserts each equals `SITE_SCHEMA_FIELDS`, `TEAMS_SCHEMA_FIELDS`, `PLACES_SCHEMA_FIELDS`, `CLUBS_SCHEMA_FIELDS`, `OFFERINGS_SCHEMA_FIELDS` exactly and in order
- [ ] Failure message names the constant and the missing/extra field
- [ ] Classifier-prompt vocabularies are NOT pinned; prose unguarded; enum-backed vocabularies only if cheap
- [ ] Demonstrated: adding a field to a constant without updating the doc fails the suite

## Implementation Plan

Follow tests/teams/test_export.py pattern.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
