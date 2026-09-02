---
id: '005'
title: Verify GSDSEF's existing registration surfaces its judging and public-day dates
status: open
use-cases: [SUC-048]
depends-on: []
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify GSDSEF's existing registration surfaces its judging and public-day dates

## Description

GSDSEF is an existing partner already registered at
`registry/sources/gsdsef.toml` (`generic_html`, `enabled = true`,
headless fetch strategy). Issue 30 explicitly asks that its Mar 18 2026
judging date and Mar 21 2026 public day date "surface" on the site.

**Do not create a second registration for GSDSEF under any
circumstance** — this is exactly the dual-registration risk sprints 027
and 028 both hit for real (COSMOS/OPTIMUS/ENLACE; Air & Space Museum/
Helen Woodward) and this sprint's own Architecture section calls out by
name.

1. Live-verify whether the *existing* registration's extraction
   (`extract/`'s deterministic ladder, plus `enrich/`'s LLM
   field-recovery pass) already surfaces both dates today. Check the
   pipeline's actual output for GSDSEF, not just that the page is
   fetchable.
2. If both dates already surface correctly, make no change — record
   that finding in this ticket's Notes and close it.
3. If not, edit the *existing* `gsdsef.toml`'s `config` in place (e.g.
   point `site_url` at the specific page carrying these dates — recall
   this doc's own sprint 015 addendum found the site's calendar/
   workshops pages via a headless dry-run — or, if that alone proves
   insufficient, change its `adapter_type` to `program_page` or
   `program_page_multi` so the LLM-extraction mechanism recovers the
   two dates the deterministic ladder is missing). This is a data edit
   to the existing file, never a new file.

## Acceptance Criteria

- [ ] A live check records whether the two dates surface today, and the
      finding is written into this ticket's Notes.
- [ ] If a config edit is needed, it is made to the existing
      `gsdsef.toml` file only — confirm with `git status`/`git diff`
      that no new `registry/sources/` file for GSDSEF was created.
- [ ] Exactly one `registry/sources/` entry exists for GSDSEF before and
      after this ticket.
- [ ] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_registry.py
  tests/test_adapters_generic_html.py` (and, only if the adapter_type
  changes, `tests/test_adapters_program_page.py`/
  `tests/test_adapters_program_page_multi.py`).
- **New tests to write**: only if `gsdsef.toml`'s config changes — a
  fixture test proving the two dates now extract correctly. No new test
  is needed if live verification finds no change is required.
- **Verification command**: `uv run pytest`
