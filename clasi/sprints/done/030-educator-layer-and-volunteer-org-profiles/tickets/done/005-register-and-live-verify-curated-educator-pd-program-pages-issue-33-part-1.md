---
id: '005'
title: Register and live-verify curated educator-PD program pages (issue 33 part 1)
status: done
use-cases:
- SUC-049
depends-on:
- '004'
github-issue: ''
issue: 33-educator-programs-layer.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register and live-verify curated educator-PD program pages (issue 33 part 1)

## Description

Register the nine educator-PD sources issue 33 part 1 names, using the
`profile="pd"` mechanism ticket 004 ships: UCSD CREATE, SD Science
Project, UCSD Math Project, Code.org regional partner, CSTA-SD, SDSU
CRMSE, Fleet educator workshops, Salk STEM Educators Summit, Zoo
teacher workshops. Each gets `config.opportunity_type = "Professional
Development / Conferences"` and `config.program_kind = "program"` in
`registry/sources/`.

**Do not repeat sprint 029's original optimism.** Sprint 029 first
registered its whole competition batch assuming the existing mechanism
would "just work," and real live verification later found 10 of 13
sources' extraction was wrong, not merely site-blocked — traced to a
prompt written for the wrong genre. Ticket 004 exists specifically so
this ticket doesn't repeat that mistake, but the *adapter_type choice
per source* (`program_page` for a single-event page, `program_page_multi`
for one page holding several session dates inline, `program_listing`
with or without `config.link_selector` for a listing whose cards link
to N detail pages) still has to be decided from each page's **actual**
observed markup, not assumed from its description. **This ticket
requires a real, live-network `--dry-run -v` run against
`AnthropicProgramLLMClient` for every source before marking it
`enabled = true`** — a WebFetch-only check is not sufficient, per
sprint 029's ticket 001/002's own documented correction. This requires
`dangerouslyDisableSandbox: true` on the verification Bash calls (real
network, real Anthropic API), per this sprint's hard constraints —
tests themselves still use fixtures only, never live calls.

**SDCOE's own PD registration system, k12oms.org, is out of scope** —
confirmed already excluded in `registry/DO_NOT_SCRAPE.md`
(`robots Disallow: /`, issue 36's 2026-08-30 research). Do not register
it; re-confirm the existing exclusion before starting, don't re-derive
it.

If any source is blocked by PlaywrightFetcher's sitemap-through-Chromium
issue (issue 39) or the extraction non-determinism/date-fabrication
issue (issue 40), register it `enabled = false` with a comment citing
the issue number — do not attempt to work around either issue in this
ticket.

## Acceptance Criteria

- [x] Each of the nine named sources is either registered
      `enabled = true` and live-verified (real `--dry-run -v` run) to
      yield at least one correctly-dated `Professional Development /
      Conferences` record, or registered `enabled = false` with a
      dated comment stating the specific reason (site-blocked,
      extraction failure even under `profile="pd"`, issue 39/40
      blocker, etc.) — matching sprint 027/028/029's disabled-source
      comment precedent exactly.
- [x] Each `enabled = true` source's chosen `adapter_type`
      (`program_page`/`program_page_multi`/`program_listing`, with
      `config.link_selector` where needed) matches that page's actual
      observed markup, decided during this ticket's own live
      verification, not assumed from the source's description.
- [x] Every registered source's TOML records the live-verification
      result (found/dated/wrote counts, date verified) in a header
      comment, matching sprint 029 ticket 007's own Notes-in-TOML
      precedent.
- [x] k12oms.org is confirmed excluded, not registered.
- [x] No existing source's `enabled` state, `adapter_type`, or config
      changes as a side effect of this ticket.

## Testing

- **Existing tests to run**: `uv run pytest tests/registry/
  tests/adapters/` (registry-loader parsing must accept the new TOML
  files without error).
- **New tests to write**: registry-loader parsing tests for the new
  curated TOML files (matching the existing per-source registry test
  convention — confirming each new file parses into a valid
  `SourceConfig` with the expected `adapter_type`/`config` keys), if
  this repo's registry test convention requires one file's worth of
  coverage per new source (check `tests/registry/` for the existing
  pattern before adding new test files vs. relying on parametrized
  coverage).
- **Verification command**: `uv run pytest` for the hermetic suite;
  live verification itself (`uv run partner-scrape --source
  <source-id> --dry-run -v`, `dangerouslyDisableSandbox: true`) is a
  manual step recorded in each TOML's own header comment, not a
  pytest test.

## Notes

Real, live end-to-end verification (2026-09-02, real network + real
`AnthropicProgramLLMClient`) of all nine named sources:

**Enabled (4)** — real, correctly-dated `Professional Development /
Conferences` records recovered:
- `sd-science-project` (`program_page_multi`,
  sdscienceproject.org/sdspevents) — found=3 dated=2, both past-cycle
  (RET @ Penn State, BASP Wildfire Workshops).
- `sdsu-crmse-math-project` (`program_page_multi`, crmse.sdsu.edu/mathproject)
  — found=5 dated=2 (pipeline count; 3 correctly-dated records
  confirmed by direct inspection), all past-cycle.
- `salk-stem-educators-summit` (`program_page`,
  salk.edu/.../salk-stem-educators-summit) — found=1 dated=1,
  **wrote 1 opportunity** (2026-09-23, still upcoming) — the one
  source that actually survives the export currency filter in this
  run.
- `sdzwa-teacher-workshops` (`program_page_multi`,
  science.sandiegozoo.org/teacherworkshops) — found=5 dated=5,
  all five past-cycle 2026 sessions.

All four's past-cycle dates are filtered by the existing currency rule
at export time, matching `doe-science-bowl-sd.toml`'s accepted
precedent — the extraction itself is correct in every case; next
year's dates will be picked up automatically by the existing weekly
cron.

**Disabled (5)** — genuine content-availability gaps (the extraction
call succeeded; the page itself has no current dated content), not
site blocks or extraction bugs:
- `ucsd-create-pd` — hub page names 6 constituent programs, zero
  inline dates.
- `ucsd-math-project` — Summer Academies subpage names 4 real (2025-
  cycle) programs, zero recoverable dates for any of them.
- `codeorg-sd-regional-partner` — program description page, no
  specific date published anywhere.
- `csta-sd` — chapter's own Events page states no events are
  currently scheduled.
- `fleet-educator-workshops` — page explicitly states workshops are
  "currently being scheduled."

k12oms.org (SDCOE's own PD registration system) was re-confirmed
excluded via the existing `registry/DO_NOT_SCRAPE.md` entry — not
registered, no new `DO_NOT_SCRAPE.md` entry needed since no additional
site's ToS/robots.txt was found to warrant one during this ticket.

No page (of the 9 registered plus the two intermediate URLs checked
for UCSD Math Project) carried any instruction-shaped text directed at
an automated crawler or AI agent — each TOML's own header comment
records this explicitly.

New test class `TestEducatorPDSourceConfig` in `tests/test_registry.py`
covers all nine sources' `adapter_type`/`config` shape, the
enabled/disabled split, the dated reason comments, the k12oms.org
exclusion, and a spot-check that no pre-existing source (Fleet, Salk,
San Diego Zoo) was touched. Full suite: 2312 passed (baseline 2306 + 6
new tests).
