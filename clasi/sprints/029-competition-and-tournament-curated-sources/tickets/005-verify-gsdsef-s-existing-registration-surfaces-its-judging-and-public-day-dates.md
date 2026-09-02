---
id: '005'
title: Verify GSDSEF's existing registration surfaces its judging and public-day dates
status: done
use-cases:
- SUC-048
depends-on: []
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify GSDSEF's existing registration surfaces its judging and public-day dates

## Description

GSDSEF is an existing partner already registered at
`registry/sources/gsdsef.toml` (`generic_html`, `enabled = true`,
headless fetch strategy). Issue 30 explicitly asks that its Mar 18 2026
judging date and Mar 21 2026 public day date "surface" on the site.

**Do not create a second registration for GSDSEF under any
circumstance** — this is exactly the dual-registration risk sprints 027
and 028 both hit for real (COSMOS/OPTIMUS/ENLACE; Air & Space Museum/
Helen Woodward) and this sprint's own Architecture section calls out by
name.

1. Live-verify whether the *existing* registration's extraction
   (`extract/`'s deterministic ladder, plus `enrich/`'s LLM
   field-recovery pass) already surfaces both dates today. Check the
   pipeline's actual output for GSDSEF, not just that the page is
   fetchable.
2. If both dates already surface correctly, make no change — record
   that finding in this ticket's Notes and close it.
3. If not, edit the *existing* `gsdsef.toml`'s `config` in place (e.g.
   point `site_url` at the specific page carrying these dates — recall
   this doc's own sprint 015 addendum found the site's calendar/
   workshops pages via a headless dry-run — or, if that alone proves
   insufficient, change its `adapter_type` to `program_page` or
   `program_page_multi` so the LLM-extraction mechanism recovers the
   two dates the deterministic ladder is missing). This is a data edit
   to the existing file, never a new file.

## Acceptance Criteria

- [x] A live check records whether the two dates surface today, and the
      finding is written into this ticket's Notes.
- [x] If a config edit is needed, it is made to the existing
      `gsdsef.toml` file only — confirm with `git status`/`git diff`
      that no new `registry/sources/` file for GSDSEF was created.
- [x] Exactly one `registry/sources/` entry exists for GSDSEF before and
      after this ticket.
- [x] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_registry.py
  tests/test_adapters_generic_html.py` (and, only if the adapter_type
  changes, `tests/test_adapters_program_page.py`/
  `tests/test_adapters_program_page_multi.py`).
- **New tests to write**: only if `gsdsef.toml`'s config changes — a
  fixture test proving the two dates now extract correctly. No new test
  is needed if live verification finds no change is required.
- **Verification command**: `uv run pytest`

## Notes (2026-09-02, ticket execution)

**Step 1 — live check of the existing registration** (real network, no
mocking, this execution environment's Bash tool has outbound network
only with `dangerouslyDisableSandbox: true`):

`uv run partner-scrape --source gsdsef --dry-run -v` against the
*unmodified* `generic_html` registration yielded **0 events** —
`WARNING ... discovered 0 URL(s)`, `sitemap.xml ... did not parse as
sitemap XML`. Investigated directly rather than accepted at face value
(the sprint 015 addendum on file claimed this exact failure was already
fixed): this project's own on-disk fetch cache held a *stale* entry for
`gsdsef.org/sitemap.xml` from an earlier headless fetch whose body
genuinely was Chromium's rendered XML-viewer markup — the original bug
— and `PoliteFetcher`'s conditional-GET revalidation kept re-serving
that stale body indefinitely (the live server resource is unchanged, so
revalidation always succeeds and a fresh raw fetch never fires).
Deleting that one cache entry and re-fetching confirmed the underlying
bug is real and current, not fixed: a fresh `fetch_strategy = "static"`
fetch of `sitemap.xml` (no Playwright/Chromium involved) returns clean,
valid XML directly, both via `curl` and via this project's own
`PoliteFetcher()` — so the failure is specifically a
`fetch/headless.py` (`PlaywrightFetcher`) XML-content-type rendering
bug, reproduced live today, contradicting the sprint 015 addendum's
"fixed" claim. **Finding recorded**: neither date surfaces today — the
existing registration yields zero events, full stop, not "yields
events but missing these two dates."

**Step 2 skipped** (both dates do not surface — proceeding to step 3,
a config edit).

**Step 3 — config edit, real live verification**: fixing the
fetch-cache/`fetch_strategy` bug alone was not sufficient — even with a
fresh, valid sitemap fetch, `discovery/sitemap.py`'s `EVENT_PATH_RE`
(matching `/events?/`, `/calendar/`, `/programs?/`, `/workshops?/`,
etc.) structurally cannot discover the one page that actually carries
the fair week's schedule, `/information/schedule` (found via the site's
own `/news` page's internal links, followed manually). A fresh
`generic_html` run (fetch-cache bug worked around) discovers only 3
URLs — `slb/workshops`, `students/workshops` (extracted title: literally
"Workshops (OLD, DO NOT USE)"), and `calendar` (page states "Calendar
and Schedule (NOT IN USE)", carrying only two unrelated dates) — none
of which carry the judging/public-day dates. Per this ticket's own
authorized fallback, `gsdsef.toml`'s `adapter_type` was changed to
`program_page_multi`, `config.url` pointed directly at
`https://www.gsdsef.org/information/schedule` (bypassing sitemap-diff
discovery entirely), `config.opportunity_type = "Competitions"` (the
sprint 029 ticket 006 competition profile). `fetch_strategy` left at
`"static"` — live-confirmed this page's full content (5,795 chars of
reduced text, the complete Fair Week schedule) fetches identically via
plain HTTP and via headless; this site's original 2026-08-30 "plain
HTTP cannot render" finding no longer holds for this page (a
site-behavior-changed-over-time finding, matching ticket 003/004's
similar findings this sprint).

**Real extraction result** (2026-09-02, real `AnthropicProgramLLMClient`,
reproduced 5x — 3x `extract_programs()`, 2x `extract_program()` — all
consistent): the live page currently shows the org's *next* cycle,
"2027 GSDSEF Fair Week Dates: March 8-14, 2027" — Wednesday March 10,
2027 is Category/Special/Grand Awards Judging; Saturday March 13, 2027
is "BPAC open to public to view projects" (the public day). Every
extraction call returns exactly ONE record spanning the whole Fair Week
(`date_start = "2027-03-08"`, `date_end = "2027-03-14"`,
`registration_deadline = "2027-02-19"`) — the model treats the week as
one program with an internal day-by-day itinerary, not as N separate
top-level programs, so it does not split "Judging" and "Public Day"
into two independently-dated records. Both target *days* fall inside
the one exported `[2027-03-08, 2027-03-14]` range. A real end-to-end
`uv run partner-scrape --source gsdsef --dry-run -v` run (2x,
reproducible) confirms `yielded 1 event(s)` / `wrote 1 opportunity` —
where the pre-fix registration wrote 0.

**Honest disposition**: this is a real, material improvement (0 → 1
correctly-dated, currently-upcoming record, unambiguously about this
specific fair) but it does not surface "Mar 18"/"Mar 21" (2026)
literally — the org has already rotated one full cycle past issue 30's
dates (the same "site rotated to next cycle" pattern ticket 003's SD
Festival finding hit). The current equivalent pair is Mar 10 / Mar 13,
2027, both inside the exported date range, not as two individually
labeled facts. Splitting "Judging"/"Public Day" into two distinct
records would need prompt-level changes to `program_llm.py` — out of
this registry-only ticket's scope (mirrors ticket 004's own "not
attempted, no prompt engineering" boundary) — flagged here as a
follow-up if finer-grained surfacing is ever wanted.

**Dual-registration check**: `git status`/`git diff` confirm no new
`registry/sources/` file was created — `gsdsef.toml` is the same file,
edited in place. `tests/test_registry.py`'s new `TestGSDSEFRegistration.
test_exactly_one_gsdsef_registration_exists` guards this going forward.

**Test suite**: `uv run pytest tests/test_registry.py
tests/test_adapters_generic_html.py tests/test_adapters_program_page_multi.py`
→ 105 passed. Full suite `uv run pytest` → 2192 passed (baseline 2188
after ticket 004 + 4 new tests: 3 in `TestGSDSEFRegistration`, 1 in
`TestGSDSECFixtureExtraction`).
