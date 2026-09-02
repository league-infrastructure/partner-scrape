---
id: '003'
title: Fix accessibility offering coverage (Fleet, the Nat, CMOD)
status: open
use-cases: [SUC-063, SUC-065]
depends-on: ['001']
github-issue: ''
issue: 34-audience-gaps-spanish-regional-accessibility.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix accessibility offering coverage (Fleet, the Nat, CMOD)

## Description

Issue 34: as of 2026-08-30, only 1 of the county's 3 known accessibility
offerings (Fleet Accessibility Mornings — 3rd Saturday, the Nat's ASD
Mornings, CMOD Sensory Friendly Mornings) surfaces in the pipeline's output.
Ticket 001 gives us the flag (`derive_specific_attention` →
`"Programs for students with disabilities"`); this ticket is the
investigative + registry-data work to make sure all three offerings are
actually *reachable* by the pipeline in the first place, so the flag has
something to attach to.

**Known findings from planning-time investigation** (verify live, do not
assume these are complete):
- CMOD (`registry/sources/visitcmod.toml`, `adapter_type = "tec_rest"`) is
  registered and its TEC REST API adapter already populates
  `Event.categories` from Tribe Events' own category list — plausibly
  already the "1 of 3" that surfaces, per issue 34's framing that CMOD's
  "Bilingual"/Sensory-Friendly events are "already captured." Verify, don't
  assume.
- The Nat (San Diego Natural History Museum) has **no
  `registry/sources/*.toml` entry at all** as of this sprint's planning
  (confirmed by search) — the most likely reason its ASD Mornings doesn't
  surface: the source isn't registered, not a bug in an existing adapter.
- Fleet Science Center (`registry/sources/fleet-science-center.toml`,
  `adapter_type = "listing_html"`) is registered and scrapes `/events`, but
  whether its 3rd-Saturday Accessibility Mornings page is actually linked
  from that listing (vs. e.g. a page only reachable from a different nav
  path, or filtered by the relevance gate/extraction ladder) needs live
  verification — do not assume registration alone means coverage.

This ticket's job is per-offering: confirm registered + reachable, or
register/fix what's missing. No new adapter code is expected — "onboarding
an organization is a new TOML file" already covers The Nat if its site uses
a supported pattern (check for a WordPress/TEC/Localist/iCal feed first,
same triage The Nat likely got as any other Balboa Park institution;
`listing_html` as a fallback if it's a plain server-rendered site like
Fleet's own).

## Acceptance Criteria

- [ ] Investigation documented in this ticket's Notes: which of the three
      offerings currently surfaces, which doesn't, and why (registration
      gap vs. discovery gap vs. something else) — issue 34's "only 1 of 3"
      claim confirmed or corrected against current live behavior.
- [ ] The Nat is registered in `registry/sources/` (new TOML file) if it
      is not already covered by an existing Balboa Park umbrella source —
      check whether Balboa Park's own park-wide TEC calendar
      (`normalize/DESIGN.md`'s sprint 014 addition) already includes Nat
      events before assuming a dedicated source is needed.
- [ ] Fleet Accessibility Mornings is confirmed reachable from Fleet's
      registered `/events` listing (or `listing_urls` config is
      corrected/extended if it is not).
- [ ] CMOD Sensory Friendly Mornings continues to surface — regression
      check, not just a forward-looking fix.
- [ ] All three, once reachable, export with `"Programs for students with
      disabilities"` in `specific_attention` (depends on ticket 001's
      `derive_specific_attention`).
- [ ] No adapter code changes unless live investigation genuinely shows an
      existing adapter cannot reach the offering's page at all (e.g. it is
      behind a nav path `listing_html`'s discovery cannot find) — prefer a
      registry config fix (`listing_urls`, `default_location`, etc.) over
      new code, matching this subsystem's existing "configuration is data"
      convention.

## Testing

- **Existing tests to run**: `uv run pytest tests/adapters/` (whichever
  adapter type ends up covering the Nat) and any `registry/` loader tests,
  plus the full suite.
- **New tests to write**: a fixture-based test for whichever adapter
  registers the Nat (following the existing per-adapter test-module
  convention), and/or a `listing_html` discovery test confirming Fleet's
  Accessibility Mornings page is enumerated from `/events` if that turns
  out to be the gap.
- **Verification command**: `uv run pytest`

## Notes

(Fill in during implementation: which offering(s) were actually broken and
why, per the first acceptance criterion.)
