---
id: '004'
title: Rewire LLM caches to Store and new layout; profile in program key
status: done
use-cases:
- SUC-001
depends-on:
- '002'
github-issue: ''
issue:
- 50-move-cache-and-data-to-digitalocean-spaces.md
- 42-program-extraction-cache-key-omits-profile.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rewire LLM caches to Store and new layout; profile in program key

## Description

Move the four LLM extraction caches onto the Store and add the profile to the program cache key.

## Acceptance Criteria

- [x] `enrich/cache.py` -> `enrichment/`; `adapters/program_cache.py` -> `programs/`; `teams/description_cache.py` -> `descriptions/`; `teams/sponsor_cache.py` -> `sponsors/`; file names unchanged; constructors keep `cache_dir: Path | None`
- [x] Program cache key includes the extraction `profile`; NO legacy-key read fallback (stakeholder decision) -- the ~67 existing `programs/` entries re-extract once
- [x] Unit test: same URL and body cached under two profiles yield two distinct entries and each lookup returns its own
- [x] Tests asserting old folder names updated
- [x] adapters/DESIGN.md Open Question about the missing profile is resolved and the change noted

## Implementation Plan

Files: the four cache modules, their tests, adapters/DESIGN.md. Completes issue 42.
See design/ticket-plan.md and architecture-update.md. Update affected DESIGN.md files.

## Testing

- **Existing tests to run**: `uv run pytest` (all offline)
- **New tests to write**: as listed in acceptance criteria
- **Verification command**: `uv run pytest`
