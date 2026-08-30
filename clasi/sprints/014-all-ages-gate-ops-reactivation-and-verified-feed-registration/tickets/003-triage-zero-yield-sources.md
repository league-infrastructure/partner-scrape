---
id: '003'
title: Triage zero-yield sources
status: in-progress
use-cases:
- SUC-006
depends-on:
- '002'
github-issue: ''
issue: 24-triage-zero-yield-sources.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Triage zero-yield sources

## Description

Investigate the ~33 of 99 registered sources that found zero
adapter-level records in the last run and give each one a resolved
disposition: **fixed** (a real bug found and corrected, with a
regression test), **re-typed** (wrong `adapter_type`, corrected),
**marked headless** (needs `fetch_strategy = "headless"`, now
installable per ticket 002), or **disabled with reason** (`enabled =
false  # disabled: <reason>`, matching the existing
`jointheleague.toml`/`olivewood-gardens.toml` convention). Includes two
known mis-registrations: `sd-river-park-foundation` (currently
`generic_html`, should be `tec_rest` against
`https://sandiegoriver.org/wp-json/tribe/events/v1/events/`, verified
live with 73 events) and `sandiego-gov` (whose `org_name`, "Discover U
at San Diego Public Library," names a different organization than its
`site_url`, sandiego.gov).

The committed `dev/output/live-scrape-2026-07-19/yield-history.json` is
stale and predates this sprint's 2026-08-30 research run — it is not
the source of truth for "which 33." Regenerate a current per-source
yield report first.

Depends on ticket 002 (ops reactivation): a source that's zero-yield
because it needs headless fetching can only be correctly diagnosed and
verified once Playwright is actually installed and the headless
dispatch fix has landed.

## Acceptance Criteria

- [ ] A current per-source yield report is regenerated (live dry-run
      against the real, active registry) and used as the authoritative
      "which sources are zero-yield" list for this ticket, not the
      stale committed snapshot.
- [ ] Every source in that current zero-yield set has one of the four
      dispositions (fixed / re-typed / marked headless / disabled with
      reason) recorded, verifiable by reading its TOML or, for a code
      fix, its diff.
- [ ] `sd-river-park-foundation.toml` is `adapter_type = "tec_rest"`
      with a working `api_base` pointed at the verified TEC endpoint.
- [ ] `sandiego-gov.toml`'s `org_name` and `site_url` refer to the same
      organization (corrected in place, or split into two source files
      if the TOML was genuinely conflating two organizations).
- [ ] The named Tier-1 candidates (`sdpl`, `cleansd`, `ilacsd`,
      `eefkids`) are each individually probed and dispositioned, not
      lumped into a generic "still broken" note.
- [ ] The four ATS boards (`boundlessbio`, `gossamerbio`,
      `elementbiosciences`, `shieldai`) are re-verified live; a
      genuinely-empty board (zero open matching postings) stays
      `enabled = true` with a comment confirming the token is still
      live — not disabled just for returning zero this run.
- [ ] Any adapter-level code fix found along the way has a
      fixture-based regression test; no committed test depends on live
      network access — live probing is a diagnosis step, not something
      that ships as a test.
- [ ] A disabled source is never deleted — `enabled = false` with an
      inline reason comment is the only mechanism used, preserving
      history.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`); registry
  loader tests (`load_sources`/`load_active_sources`) to confirm every
  edited/added TOML still parses.
- **New tests to write**: a fixture-based regression test for any real
  adapter-level bug this investigation finds (scoped to that specific
  fix, e.g. a `bibliocommons` adapter edge case if `sdpl`'s zero-yield
  turns out to be code, not config). No new test is needed purely for
  a TOML re-type or `enabled = false` edit — the existing registry
  loader tests already cover generic parsing.
- **Verification command**: `uv run pytest`. Live probing during
  investigation uses `partner-scrape --source <id> --dry-run -v` (or
  direct endpoint checks) — not committed as tests.

## Implementation Plan

**Approach**: Investigation-first, per-source. For each source in the
current zero-yield set: check whether the site/API still exists, probe
live for the actual platform/endpoint shape, compare against the
registered `adapter_type`/`config`, and assign exactly one of the four
dispositions. Batch similar findings (e.g. "site moved to a new domain,
still the same TEC platform") but record each source's outcome
individually so the registry stays auditable per-file.

**Files to modify**:
- `partner_scrape/registry/sources/*.toml` — the ~33 zero-yield
  sources: edits (re-type, config fix, `enabled = false` + reason) as
  each disposition requires.
- `partner_scrape/registry/sources/sd-river-park-foundation.toml` —
  `adapter_type` and `[config]` corrected to `tec_rest`.
- `partner_scrape/registry/sources/sandiego-gov.toml` — `org_name`/
  `site_url` consistency fix (or split into two files).
- Any `partner_scrape/adapters/*.py` file, only if live probing
  reveals a genuine adapter-level bug (e.g. a parsing edge case) rather
  than a registry misconfiguration — scoped narrowly to what's
  actually found.

**Testing plan**: see Testing above.

**Documentation updates**: `sprint.md`'s Architecture Overview table
already lists this ticket's contingent `adapters/*` touch; no separate
design-doc overlay was seeded for `adapters/` or `registry/`'s core
content since none of its schema/loader logic changes — only
`design/registry-DESIGN.md`'s Open Questions section, already updated
during planning to note the `sandiego-gov`-style cross-field-consistency
lesson and the disabled-with-reason convention. If this ticket's
investigation reveals something that genuinely changes `registry/`'s
own architecture (not just its data), flag it rather than silently
expanding scope — the sprint's own Exception Protocol applies if a
finding conflicts with an existing design decision.
