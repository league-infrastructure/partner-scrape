---
id: '002'
title: Register county-parks and sd-astronomy-association feeds
status: open
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
issue: 40-ical-parser-robustness-and-remaining-robots-gated-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register county-parks and sd-astronomy-association feeds

## Description

With ticket 001's `ical.py` fixes merged, the two feeds sprint 015
ticket 005 withheld are ready to re-verify and register. Both TOMLs
were drafted in sprint 014 ticket 004's investigation (the same
endpoints, same `respect_robots = false` policy already decided in
issue 38 and made real by sprint 015 ticket 003) — this ticket
re-verifies against the fixed adapter and commits.

## Acceptance Criteria

- [ ] `county-parks.toml` and `sd-astronomy-association.toml` are
      committed with `acquisition_policy.respect_robots = false`,
      matching the already-registered `mission-trails`/`surfrider-sd`/
      `swe-san-diego` TOMLs' shape from sprint 015 ticket 005.
- [ ] Each is live-verified via `partner-scrape --dry-run --no-enrich
      --source <id>` through the real `ical` adapter to return
      non-zero, dated output before commit.
- [ ] If either still returns zero at dry-run time (ticket 001's fix
      did not fully resolve it), that TOML is **not** committed and
      this ticket records why in its Notes, per sprint 015 ticket
      005's own withholding convention — this ticket does not close
      as fully done in that case; it is left `open` with the finding
      recorded, matching that same precedent.
- [ ] `org_name` is checked against `site/src/data/partners.json`;
      neither is expected to match (both remain issue 32
      roster-expansion candidates per sprint 014 ticket 004's original
      list), so this is a check, not an expected force-match.
- [ ] Full test suite stays green (registry loader tests already cover
      generic `ical` TOML parsing; no new hermetic tests expected
      purely from adding data-only TOML files).

## Testing

- **Existing tests to run**: `uv run pytest`; registry loader tests to
  confirm both new TOMLs parse.
- **New tests to write**: none expected purely from adding data-only
  TOML files, matching sprint 014/015's own precedent for this exact
  kind of ticket.
- **Verification command**: `uv run pytest`, plus the required
  `--dry-run` live verification per source (not pytest).

## Implementation Plan

**Approach**: Re-use the sprint 014 ticket 004 TOML drafts verbatim
(endpoint URLs already confirmed live), add `acquisition_policy.
respect_robots = false`, live-verify against the now-fixed adapter,
commit only on non-zero output.

**Files to modify**:
- `partner_scrape/registry/sources/county-parks.toml`
- `partner_scrape/registry/sources/sd-astronomy-association.toml`

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/registry/DESIGN.md` gets a
one-line sprint-016 note recording the 5-of-5 completion of the
robots-gated batch issue 38/40 track, matching its existing per-sprint
registry-growth convention.
