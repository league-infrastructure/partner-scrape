---
id: '005'
title: Research new STEM competition-team types for San Diego rosters
status: open
use-cases:
- SUC-071
depends-on:
- '004'
github-issue: ''
issue: 47-generalize-teams-and-narrow-clubs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Research new STEM competition-team types for San Diego rosters

## Description

Issue 47 asks for a bounded brainstorm-and-hunt for other San Diego
STEM competition-team types, beyond the robotics leagues and the two
ticket 002 just migrated. Starting list (not exhaustive): DOE Science
Bowl, National/Garibaldi Ocean Sciences Bowl, MATHCOUNTS, American
Rocketry Challenge (TARC), SeaPerch, Botball, Envirothon, Future City,
TSA chapters, SkillsUSA chapters, eCyberMission, Zero Robotics, Junior
Solar Sprint, Solar Cup, Math Circle/AMC-AIME school teams, picoCTF,
Mayor's Cyber Cup.

This is genuinely open-ended research, not implementation — this
ticket produces **findings**, no code or data changes. Sprint 029
already registered several of these as *events* in `registry/
sources/*.toml` (`doe-science-bowl-sd.toml`, `garibaldi-bowl.toml`,
`mathcounts-sd-chapter.toml`, `botball-greater-sd.toml`,
`seaperch-sd-regional.toml`, `sd-math-circle.toml`, `cyberpatriot-sd.toml`
already covered by ticket 002) — those pages are event/competition-date
announcements, not team rosters, so they are the *first place to
check* for a roster link, not a substitute for finding one. Apply the
standard held since sprint 027: live-verify, and record "no public
roster exists" as a finding, not a failure — the same discipline
sprint 029's own registry comments already model (several of those
sources are `enabled = false` with a documented, live-verified reason).

## Acceptance Criteria

- [ ] All 16 starting-list types (plus any additional type discovered
      along the way, e.g. by following a link from one of the checked
      sources) have a recorded disposition: **roster found and
      verified** (link + what it shows + San Diego-specific team
      count), **no public roster exists** (what was checked and how),
      or **roster exists but not usable** (e.g. paywalled, no
      San-Diego-specific breakout, stale/superseded, requires an
      account) — matching the granularity sprint 029's own registry
      comments use for a disabled source.
- [ ] For each of the 7 types sprint 029 already registered as an
      *event* (`doe-science-bowl-sd`, `garibaldi-bowl`,
      `mathcounts-sd-chapter`, `botball-greater-sd`,
      `seaperch-sd-regional`, `sd-math-circle`, plus MATHCOUNTS/
      Envirothon/TSA/SkillsUSA if a matching entry exists), the
      existing registry TOML is checked first for any roster-page
      reference before an independent web search begins.
- [ ] Every "roster found" claim is live-verified by an actual fetch
      (WebFetch or a direct `curl`/browser check), not asserted from a
      search-result summary alone — per sprint 029's own corrected
      precedent (ticket 001/002's "first pass never exercised the real
      fetcher" lesson).
- [ ] Findings are written into `teams/DESIGN.md`'s Open Questions or a
      dedicated "Sprint 036 research findings" section — not left only
      in this ticket's own file, so a future sprint planner finds them
      without having to re-open sprint 036's tickets.
- [ ] No roster is populated by this ticket — that is ticket 006's job,
      gated on this ticket's findings.
- [ ] If zero types clear the "real, live, verifiable, San
      Diego-specific roster" bar, that is an acceptable, fully
      documented outcome (matching sprints 027-032's own precedent) —
      this ticket's acceptance criteria are about the *quality and
      completeness of the research*, not about finding a minimum number
      of populatable types.

## Testing

- **Existing tests to run**: none — no code or data changes in this
  ticket.
- **New tests to write**: none.
- **Verification command**: N/A. Any live fetch performed as part of
  this research (checking a candidate roster page) requires
  `dangerouslyDisableSandbox: true` on the Bash tool per this project's
  standing constraint that live verification uses the real network
  even though the test suite never does.
