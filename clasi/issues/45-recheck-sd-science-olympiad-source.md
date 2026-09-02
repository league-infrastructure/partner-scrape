---
status: pending
---

# Re-check the disabled SD Regional Science Olympiad source

## Description

Small correction, found incidentally during sprint 032 ticket 006.

Sprint 029 registered `registry/sources/sd-science-olympiad.toml` with
`enabled = false` because `scilympiad.com` refused every connection
(`curl` returned 000 across three attempts and two URL paths, and this
was reconfirmed on a second pass with real network access).

Sprint 032 ticket 006 checked the same host a day later while sourcing
Science Olympiad school teams and got **HTTP 200**. So the outage was
transient, and the disable reason in that TOML is now stale.

## Proposed fix

Re-run `uv run partner-scrape --source sd-science-olympiad --dry-run -v`
against the live site and apply sprint 029's standard: enable it if it
extracts a correctly-dated `Competitions` record; otherwise update the
reason comment to the current failure mode rather than leaving the
"connection refused" text behind.

Worth doing at the same time: sprint 029 disabled several other sources
for site-level reachability rather than extraction quality
(`garibaldi-bowl`, `cipherhacks` was recovered, `mathcounts-sd-chapter`
for a WAF block). A single re-check pass across the sprint-029 disabled
set is cheaper than doing them one at a time, and would catch any other
transient block recorded as permanent.

Note that sprint 032 ticket 006 sourced the school-team roster from
Duosmium Results' archived official results, not from scilympiad — so
the roster does not depend on this source's outcome either way.
