---
id: '001'
title: Record the robots-allowlist exception in DO_NOT_SCRAPE.md
status: done
use-cases:
- SUC-067
depends-on: []
github-issue: ''
issue: 44-robots-named-allowlist-policy-decision.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Record the robots-allowlist exception in DO_NOT_SCRAPE.md

## Description

Issue 44 asked whether the bright-line "ToS/robots says no automated
access → exclude" rule in `partner_scrape/registry/DO_NOT_SCRAPE.md`
should stand for sources whose robots.txt blocks all bots except a
named allow-list (Googlebot, bingbot, LinkedInBot, etc.), or whether a
narrower reading applies for low-volume, non-republishing, link-out-
only fetching of public job postings. Eric's ruling, verbatim: "for
number one, issue 44, go ahead and scrape them." This ticket records
that ruling durably in `DO_NOT_SCRAPE.md`, scoped precisely, so a
future session doesn't re-litigate it — and so it is not mistaken for
a general license to override robots.txt.

This ticket is documentation only. It does not touch any
`registry/sources/*.toml` file — that is ticket 002, which depends on
this one landing first so the registry edits can cite an already-
recorded decision.

Read `partner_scrape/registry/DO_NOT_SCRAPE.md` in full before editing
— it has an existing "Excluded — per issue 36", "Excluded — found
during sprint 024 planning", and "Deferred" structure. Add a new
section (e.g. "Exceptions") following that same style, rather than
folding this into either "Excluded" grouping (this is the opposite of
an exclusion) or "Deferred" (this is a resolved decision, not an open
question).

## Acceptance Criteria

- [x] `DO_NOT_SCRAPE.md` gains a new entry/section (distinct from
      "Excluded" and "Deferred") stating the exception's precise
      scope: **named-allowlist robots.txt** on an **ATS/job-board
      vendor**, for **low-volume, non-republishing, link-out-only**
      fetching of **public job postings**. The scope statement must
      make clear this is not a general robots-override license.
- [x] The entry cites issue 44 and the decision date (2026-09-02).
- [x] The entry names the five sources this exception covers:
      `servicenow` (api.smartrecruiters.com, allows LinkedInBot only),
      `city-of-san-diego-careers`, `county-of-san-diego-careers`,
      `sandag-careers`, and `port-of-san-diego-careers` (all four on
      www.governmentjobs.com).
- [x] The entry explains the reasoning issue 44 gives: the four
      public-sector agencies (County of SD, City of SD, SANDAG, Port
      of SD) want their postings found by job-seekers — the robots
      block is the ATS vendor's blanket policy, not the agency's own
      choice.
- [x] The entry states explicitly that this does **not** reopen the
      sprint-024 hub exclusions — KidsOutAndAbout,
      sandiegostemsummercamps.com, sandiegomoms.com, and San Diego
      Reader remain excluded, because those were blocked by an actual
      ToS clause forbidding scraping, a different and unrelated
      grounds from a robots.txt named-allowlist. Do not alter the
      existing "Excluded — found during sprint 024 planning" section's
      content.
- [x] The existing bright-line rule statement and all other existing
      content in `DO_NOT_SCRAPE.md` (the issue-36 exclusions, the
      sprint-024 exclusions, the Deferred section) is otherwise
      unchanged.

## Testing

- **Existing tests to run**: none apply — this is a documentation-only
  change with no code path. Confirm no test references
  `DO_NOT_SCRAPE.md`'s content directly (it is documentation only, not
  loaded by the pipeline — see `registry/DESIGN.md` §1: "Nothing in
  the pipeline loads or parses it").
- **New tests to write**: none — no code changes.
- **Verification command**: `uv run pytest` (confirm the full suite,
  2508-test baseline, is unaffected — expected to pass unchanged since
  no source file changes).

## Notes

`uv run pytest` run after the `DO_NOT_SCRAPE.md` edit: 2508 passed,
matching the baseline exactly. No test references `DO_NOT_SCRAPE.md`'s
content.
