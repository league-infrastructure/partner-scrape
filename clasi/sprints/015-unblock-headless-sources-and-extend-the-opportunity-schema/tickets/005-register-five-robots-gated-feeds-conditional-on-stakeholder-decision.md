---
id: '005'
title: Register five robots-gated feeds (conditional on stakeholder decision)
status: open
use-cases:
- SUC-006
depends-on:
- '003'
github-issue: ''
issue: 38-acquisition-policy-threading-and-feed-robots.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register five robots-gated feeds (conditional on stakeholder decision)

## Description

**This ticket is conditional and gated on a stakeholder decision that
was pending as of sprint planning.** Five live, high-yield,
well-formed feeds are blocked solely by host `robots.txt`: SD County
Parks (Tockify ICS, ~553-677 events measured live in sprint 014),
Mission Trails Regional Park Foundation (~164), Surfrider SD (~2313),
San Diego Astronomy Association, and SWE San Diego (an existing
partner with no other event source today) — all `calendar.google.com`
or `tockify.com` ICS subscription URLs. Registration TOMLs for all
five were drafted during sprint 014 ticket 004's investigation and
deliberately not committed.

Whether `partner-scrape` treats an explicitly-published ICS
subscription URL (designed to be polled by calendar clients) as
feed-client traffic — fetching it politely while ignoring robots.txt
for that specific URL class — or keeps strict robots compliance is a
policy call for the stakeholder, not an engineering one. Do not
register any of the five without a recorded decision.

This ticket depends on ticket 003: without acquisition-policy
threading actually working, setting
`acquisition_policy.respect_robots = false` in these TOMLs would be
dead configuration, exactly the gap ticket 003 fixes.

## Acceptance Criteria

- [ ] **Gate check first**: confirm a stakeholder decision on the
      robots-policy question is recorded (where the team-lead directs —
      e.g. a `clasi/issues/38-...md` update or an explicit sprint note)
      before writing or committing any of the five TOMLs.
- [ ] If the decision is "treat as feed-client traffic, ignore robots
      for this URL class": all five TOMLs are committed with
      `acquisition_policy.respect_robots = false`, each live-verified
      to return non-zero, dated output via `partner-scrape --dry-run
      --source <id>` before commit.
- [ ] If the decision is "keep strict robots compliance," or does not
      land during this sprint: no TOML is committed, and this ticket
      is left `open` (not `done`) with a note explaining the gate
      state, to roll to a future sprint rather than block this
      sprint's close.
- [ ] If shipped, `org_name` matches `partners.json`'s existing `name`
      field where the org is already a partner (SWE San Diego); the
      other four are noted as candidates for the roster-expansion
      issue, not force-matched.
- [ ] Full test suite stays green if any TOML is committed.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`); registry
  loader tests to confirm every new TOML parses, if any are committed.
- **New tests to write**: none expected purely from adding data-only
  TOML files.
- **Verification command**: `uv run pytest`, plus a `--dry-run` per
  source if shipped.

## Implementation Plan

**Approach**: Gate check first, then (only if cleared) per-feed TOML
authoring against the endpoints already verified live in sprint 014
ticket 004, exactly as drafted there.

**Files to modify** (only if the gate clears):
- `partner_scrape/registry/sources/{county-parks,sd-astronomy-
  association,mission-trails,surfrider-sd,swe-san-diego}.toml` (exact
  filenames per the drafted sprint 014 versions).

**Testing plan**: see Testing above.

**Documentation updates**: none unless shipped, in which case
`partner_scrape/registry/DESIGN.md` gets a one-line sprint-015 note
matching its existing per-sprint registry-growth convention.
