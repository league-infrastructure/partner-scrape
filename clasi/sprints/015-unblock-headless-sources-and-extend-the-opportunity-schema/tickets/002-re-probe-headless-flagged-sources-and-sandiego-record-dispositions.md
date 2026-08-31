---
id: '002'
title: Re-probe headless-flagged sources and sandiego; record dispositions
status: open
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
issue: 37-headless-xml-fetch-and-sitemap-namespace-bugs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Re-probe headless-flagged sources and sandiego; record dispositions

## Description

With ticket 001's two fixes merged, re-probe live every source whose
zero-yield disposition was blocked by either bug and record a current,
evidence-backed disposition for each:

- The 9 headless-flagged sources from sprint 014 ticket 002:
  `climate-science-alliance`, `escondido-creek-conservancy`, `gsdsef`,
  `lajollalibrary`, `sandiego-cv-aopsacademy`, `sdrvc`,
  `techadventurecamp`, `titanbot`, `xplorstem`.
- `sandiego` (`sandiego.edu`), currently disabled with the sitemap
  namespace bug as its recorded reason.

This is a live-diagnosis ticket, matching sprint 014 ticket 003's own
methodology: probe first, then update the registry to match reality,
not the other way around.

## Acceptance Criteria

- [ ] Each of the 10 sources is individually re-probed live
      (`partner-scrape --source <id> --dry-run -v`) after ticket 001's
      fixes, not lumped into a generic note.
- [ ] A source that now yields real, dated records is re-enabled
      (`enabled = true`) with its new live yield count recorded in the
      TOML's addendum comment or this ticket's Notes.
- [ ] A source that still yields nothing keeps `enabled = false`; if
      the root cause has changed (no longer the fetch/sitemap bug),
      the disabled-reason comment is updated to the new, accurate
      cause.
- [ ] `sandiego` specifically is re-probed and its disposition
      resolved (re-enabled, or disabled with an updated, non-stale
      reason).
- [ ] No source is deleted — `enabled = false` with an inline reason
      comment remains the only mechanism used, preserving history
      (matching `jointheleague.toml`/`olivewood-gardens.toml`'s
      existing convention).
- [ ] Full test suite stays green; live probing is a diagnosis step,
      not a committed test.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`); registry
  loader tests to confirm every edited TOML still parses.
- **New tests to write**: none expected purely from TOML disposition
  edits — the existing registry loader tests already cover generic
  parsing. If live probing surfaces a genuine adapter-level bug
  distinct from the two ticket 001 already fixed, flag it for a
  follow-up rather than silently expanding this ticket's scope
  (matching sprint 014 ticket 003's own precedent).
- **Verification command**: `uv run pytest`. Live probing uses
  `partner-scrape --source <id> --dry-run -v` — not committed as a
  test.

## Implementation Plan

**Approach**: Per-source, live-probe-then-record, identical in shape
to sprint 014 ticket 003. Run each of the 10 sources through the real
pipeline post-fix, compare the result against its current TOML
disposition, and update only what changed.

**Files to modify**:
- `partner_scrape/registry/sources/climate-science-alliance.toml`,
  `escondido-creek-conservancy.toml`, `gsdsef.toml`,
  `lajollalibrary.toml`, `sandiego-cv-aopsacademy.toml`, `sdrvc.toml`,
  `techadventurecamp.toml`, `titanbot.toml`, `xplorstem.toml`,
  `sandiego.toml` — disposition updates only.

**Testing plan**: see Testing above.

**Documentation updates**: none expected beyond this ticket's own
Notes recording each source's new disposition and yield.
