---
id: '006'
title: Verify issue 14's existing dated volunteer-event source registrations
status: open
use-cases: [SUC-053]
depends-on: []
github-issue: ''
issue: 14-improve-volunteer-opportunity-discovery.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify issue 14's existing dated volunteer-event source registrations

## Description

Independent of every other ticket in this sprint. Issue 14's own
2026-08-30 research update concluded that Strategy A (scraping
third-party volunteer-aggregator platforms) is dead, and that the
volunteer content which *is* scrapable already flows through the
normal pipeline once registered: UCSD Localist's Volunteer event type,
Coastkeeper TEC, Surfrider SD Google Calendar, and ILACSD. This ticket
**verifies these four sources' current registration state — it does
not register anything new.**

For each of the four: confirm it is registered, confirm its
`adapter_type` (`localist`/`tec_rest`/`ical`/`generic_html`, whichever
applies) and `enabled` state, and confirm it is actually yielding
`Volunteering`-typed records (`normalize/taxonomy.py` already supports
this `opportunity_type` value — this ticket does not touch taxonomy).
Where a source is found disabled, misconfigured, or zero-yield for a
reason fixable with a config edit, fix it. Where the gap needs more
than a config edit (a genuine adapter bug, a site change), document it
with a dated comment and leave it — this ticket's scope is
verification and config fixes, not new adapter development.

## Acceptance Criteria

- [ ] UCSD Localist's Volunteer event type: confirmed registered,
      `enabled` state recorded, live-verified (or documented if not
      feasible) to yield `Volunteering`-typed records.
- [ ] Coastkeeper TEC: same verification.
- [ ] Surfrider SD Google Calendar: same verification.
- [ ] ILACSD: same verification.
- [ ] Any config-level fix applied (e.g. an `enabled = false` flipped
      to `true`, a stale URL corrected) is recorded with a dated
      comment in that source's own TOML, matching this codebase's
      existing self-documenting-registry convention.
- [ ] No new source is registered by this ticket.
- [ ] This ticket's own Notes section records the final state of all
      four sources (enabled/disabled, yield), so the sprint's Success
      Criteria can be checked off without re-deriving it.

## Testing

- **Existing tests to run**: `uv run pytest tests/registry/
  tests/adapters/` (confirm no regression from any config edit).
- **New tests to write**: none expected unless a config fix reveals an
  actual adapter bug worth a regression test — judgment call at
  execution time, not planned here.
- **Verification command**: `uv run pytest`; live yield verification
  (`uv run partner-scrape --source <source-id> --dry-run -v`,
  `dangerouslyDisableSandbox: true`) is a manual step, not a pytest
  test.
