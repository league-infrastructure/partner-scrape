---
id: '002'
title: Enable and live-verify the five named-allowlist ATS sources
status: open
use-cases:
- SUC-066
depends-on:
- '001'
github-issue: ''
issue: 44-robots-named-allowlist-policy-decision.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Enable and live-verify the five named-allowlist ATS sources

## Description

Five sources registered in sprint 031 are fully built and fixture-
tested but `enabled = false`, solely because each vendor's robots.txt
allows only a named crawler allow-list and this project's default
`respect_robots = true` makes `PoliteFetcher` raise `RobotsDisallowed`
for our bot's user agent:

- `registry/sources/servicenow.toml` (api.smartrecruiters.com — allows
  LinkedInBot only)
- `registry/sources/city-of-san-diego-careers.toml`
- `registry/sources/county-of-san-diego-careers.toml`
- `registry/sources/sandag-careers.toml`
- `registry/sources/port-of-san-diego-careers.toml`

(the last four all on www.governmentjobs.com, which allows Googlebot/
bingbot/yahoobot/msnbot/gsa-crawler-www/NHN/Twitterbot/
facebookexternalhit only).

Issue 44 asked whether to keep the bright-line exclusion or override it
for these five. Eric ruled: "go ahead and scrape them." Ticket 001
records that decision in `DO_NOT_SCRAPE.md`; this ticket makes it real
in the registry, using the **existing** per-source
`acquisition_policy.respect_robots` override (sprint 015's
iCal-feed precedent, issue 38) — **do not change the global default**.

No adapter code changes are needed or in scope. `adapters/
smartrecruiters.py` and `adapters/neogov.py` are already complete and
fixture-tested (sprint 031); this is a registry-data change plus live
verification.

**Read `partner_scrape/registry/DESIGN.md` and
`partner_scrape/fetch/DESIGN.md` first** for how `acquisition_policy.
respect_robots` threads from `registry/schema.py` through
`adapters/base.acquisition_kwargs` into
`fetch/cache.PoliteFetcher.get()` — this ticket applies that existing
mechanism, it does not build anything new.

**Live-verification standard — read this before running anything**:
these are ATS/job-board sources. **Zero matching postings is a PASS,
not an error.** What must be verified is that the fetch no longer
raises `RobotsDisallowed` (or any other exception) and that the
adapter parses and filters the real response. Do not re-disable a
source, or treat the ticket as failed, because a live run returns no
matching internships — internship postings are seasonal and rare
relative to total postings. For calibration, sprint 031's own live
results on this exact class of source: Sony/Greenhouse 197 postings →
0 matches (a pass); Workable/Airport Authority 5 postings → 0 (a
pass); Workday's five tenants, 55-3715 postings each → 0 matches each
(all passes). The same standard applies here.

Live verification requires real network access — use
`dangerouslyDisableSandbox: true` on the Bash tool call that runs the
dry run. Nothing else in this ticket needs network access, and no
hermetic test may make a live call.

## Acceptance Criteria

- [ ] Each of the five named TOML files has `enabled = true`.
- [ ] Each of the five named TOML files has
      `acquisition_policy.respect_robots = false` added (as a
      per-source override — the file's other existing
      `acquisition_policy` keys, e.g. `rate_limit_seconds`,
      `discovered_via`, are preserved unchanged).
- [ ] Each of the five files gets a new comment (alongside, not
      replacing, the sprint 031 header comment already documenting the
      live-verified endpoint shape and the genuine robots block) naming
      this stakeholder decision: issue 44, date 2026-09-02.
- [ ] No other `registry/sources/*.toml` file's `respect_robots`
      setting or global default changes. Confirm by checking that no
      project-wide default (e.g. in `registry/schema.py` or
      `config.py`) was touched — only these five files' per-source
      `acquisition_policy` blocks.
- [ ] `adapters/smartrecruiters.py` and `adapters/neogov.py` are not
      modified.
- [ ] A real, live `uv run partner-scrape --source servicenow
      --dry-run -v` completes with no `RobotsDisallowed` error (or any
      other exception) — record the actual result (posting count,
      match count) in this ticket's notes.
- [ ] A real, live `uv run partner-scrape --source
      city-of-san-diego-careers --dry-run -v` completes with no
      `RobotsDisallowed` error — record the result.
- [ ] A real, live `uv run partner-scrape --source
      county-of-san-diego-careers --dry-run -v` completes with no
      `RobotsDisallowed` error — record the result.
- [ ] A real, live `uv run partner-scrape --source sandag-careers
      --dry-run -v` completes with no `RobotsDisallowed` error —
      record the result.
- [ ] A real, live `uv run partner-scrape --source
      port-of-san-diego-careers --dry-run -v` completes with no
      `RobotsDisallowed` error — record the result.
- [ ] Zero matching postings on any (or all) of the five live-verified
      sources is treated as a pass and is explicitly noted as such in
      this ticket's notes — not as a reason to revert `enabled` to
      `false` or to flag the source as broken.
- [ ] The full hermetic test suite (2508-test baseline) passes
      unchanged, with no live network call in any test.

## Testing

- **Existing tests to run**: `uv run pytest` — the full suite,
  confirming the 2508-test baseline still passes. `tests/
  test_adapters_smartrecruiters.py` and `tests/test_adapters_neogov.py`
  specifically, to confirm this registry-only change didn't
  accidentally regress either adapter's fixture-based tests.
- **New tests to write**: none — no code changes. The registry loader
  (`registry/loader.py`) already round-trips arbitrary
  `acquisition_policy` keys with no schema change needed (§3/§5b of
  `registry/DESIGN.md`), so no new hermetic test is needed to prove the
  five edited TOML files parse; `load_sources()`/`load_active_sources()`
  parsing them without error is implicitly covered by any existing test
  that loads the full registry.
- **Verification command**: `uv run pytest` for the hermetic suite;
  the five `uv run partner-scrape --source <id> --dry-run -v` commands
  above (each with `dangerouslyDisableSandbox: true`) for live
  verification — these are deliberately outside the hermetic suite and
  must not be added as automated tests (no live network in tests).
