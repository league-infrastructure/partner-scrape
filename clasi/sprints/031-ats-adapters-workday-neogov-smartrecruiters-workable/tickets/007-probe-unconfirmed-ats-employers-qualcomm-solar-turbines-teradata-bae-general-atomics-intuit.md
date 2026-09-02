---
id: "007"
title: "Probe unconfirmed-ATS employers (Qualcomm, Solar Turbines, Teradata, BAE, General Atomics, Intuit)"
status: open
use-cases: [SUC-060]
depends-on: []
github-issue: ""
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Probe unconfirmed-ATS employers (Qualcomm, Solar Turbines, Teradata, BAE, General Atomics, Intuit)

## Description

For each of Qualcomm (Eightfold-ish, previously 403), Solar Turbines,
Teradata, BAE (Phenom), General Atomics (BrassRing), and Intuit
(Radancy), attempt a live, read-only probe of its careers site/API to
determine whether a public, unauthenticated, structured endpoint
exists. Record findings — do not build a bespoke adapter for any
genuinely new ATS shape this sprint, per `design/adapters-DESIGN.md`'s
sprint 031 Design Rationale (avoiding four speculative adapters against
an unconfirmed shape). If an employer turns out to already run
Greenhouse, Lever, SmartRecruiters, or Workable under an unlisted
board/company name, registering it is data-only and stays in scope for
this ticket.

This ticket's deliverable is a findings record, not necessarily new
code. A probe that finds every employer blocked is a complete, correct
ticket outcome.

## Acceptance Criteria

- [ ] Each of the six employers has a recorded finding in this
      ticket's Notes: reachable-and-structured (name the shape),
      reachable-but-HTML-only, or blocked-and-how (403, credential
      required, robots-disallowed, etc.).
- [ ] No new adapter module is added for a genuinely new ATS vendor
      shape (Eightfold, Phenom, BrassRing, Radancy) this sprint.
- [ ] If any employer is found reachable through one of this
      codebase's existing adapter types (`greenhouse`, `lever`,
      `smartrecruiters`, `workable`), it is registered and
      live-verified in this same ticket, with a header comment
      recording the finding.
- [ ] Full test suite (`uv run pytest`) stays green (a pure-probe
      outcome with no new registrations still needs to leave the suite
      green — it should be unaffected either way).

## Implementation Plan

**Approach**: This is primarily a research ticket. For each employer,
attempt: (1) a plain unauthenticated GET/POST against the platform's
typical public API pattern for its named ATS vendor (Eightfold's
`career.eightfold.ai` widget API shape, Phenom's typical GraphQL/REST
surface, BrassRing's typical public feed, Radancy's typical public
feed); (2) if that fails, check whether the employer's careers page
itself exposes a Greenhouse/Lever/SmartRecruiters/Workable-shaped
endpoint under a name not in issue 31's original census (some
employers run more than one ATS for different job families). Record
each attempt and its result.

**Files to create/modify**:
- `registry/sources/` — zero or more new TOML files, only for an
  employer found reachable through an *existing* adapter type
- No new adapter module expected; if the probe genuinely finds a
  cleanly reachable new shape worth building, stop and flag it in this
  ticket's Notes as a recommended follow-up issue rather than building
  it inline — that decision belongs to the team-lead/stakeholder, not
  this ticket's own scope (per `design/adapters-DESIGN.md`'s Design
  Rationale)

**Testing plan**:
- **Existing tests to run**: `uv run pytest` (full suite — confirm no
  regression from any new registry entries this ticket adds).
- **New tests to write**: only if an employer is registered through an
  existing adapter type — the same fixture-based test convention
  ticket 002/003 already established, or confirmation that the
  existing adapter's test suite already covers the new registration's
  shape.
- **Verification command**: `uv run pytest`

**Documentation updates**: This ticket's Notes are the primary
deliverable for the five (or six) employers that don't result in a new
registration — write them in enough detail that a future sprint
picking one up doesn't need to re-probe from scratch. Recommend, but
do not file, a follow-up issue number for any employer found genuinely
buildable (see `sprint.md`'s Architecture > Migration Concerns for why
no issue is filed in advance of this ticket's findings).
