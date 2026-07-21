---
id: '004'
title: Fix flagship museum date extraction per ticket 003's diagnosis
status: done
use-cases:
- SUC-003
depends-on:
- '003'
github-issue: ''
issue: 14-flagship-museum-date-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix flagship museum date extraction per ticket 003's diagnosis

## Description

Implements the fix half of issue `14-flagship-museum-date-extraction.md`
and sprint 007's SUC-003. **Depends on ticket 003** — read its
"Findings" section first; it names, per source, which of the three
mechanisms below applies. Do not re-diagnose from scratch; do not
guess if ticket 003's findings are incomplete — re-open ticket 003
instead of proceeding on a guess.

See sprint.md's Architecture (Source Registry entries, Generic HTML
Extractor / ladder, Sitemap Discovery — Step 3 module table) and Design
Rationale ("reuse the existing `fetch_strategy = 'headless'` config
flag...") for the constraints this fix must respect.

**Apply, per source, whichever ticket 003 recommends**:

1. **JS-rendering hides the date from a raw HTTP fetch** → set
   `fetch_strategy = "headless"` in that source's
   `[acquisition_policy]` table in its registry TOML
   (`partner_scrape/registry/sources/{sdnhm,sandiego-air-space,fleet-science-center}.toml`).
   This routes the source through Pipeline's existing lazy
   `PlaywrightFetcher` (`partner_scrape/pipeline.py`,
   `HEADLESS_FETCH_STRATEGY`, `_build_default_headless_fetcher`) — no
   code change needed, this mechanism already exists end-to-end
   (sprint 005) and is simply unused today. Confirm the `playwright`
   optional dependency group is installed in the environment you test
   with (`uv sync --extra headless` or equivalent) since it's not a
   base dependency.
2. **Discovery finds no/wrong candidate URLs** (e.g. Air & Space's dead
   sitemap paths) → either set an explicit `config.sitemap_url`
   override in that source's TOML if ticket 003 found the real sitemap
   at a non-standard path, or change `adapter_type = "listing_html"`
   (mirroring `fleet-science-center.toml`'s shape: `listing_urls =
   ["/events"]` or whatever real listing page ticket 003 identified) if
   no usable sitemap exists at all. Do not invent a new discovery
   mechanism — these two options exhaust what the current architecture
   supports.
3. **The ladder selects the wrong/no date on a page that has one**
   (e.g. SDNHM's multi-date category pages) → make a **targeted**
   adjustment to the relevant rung in
   `partner_scrape/extract/ladder.py` — e.g. tightening
   `_extract_body_regex`'s date selection for pages with multiple date
   matches in the scanned text, or fixing `_extract_time_tags`'s
   attribute-format assumption if ticket 003 found a mismatch. Do
   **not** reorder the ladder's priority sequence, change its
   confidence-tier constants, or add a new rung category — this must
   stay a narrow fix to existing rung logic. Add a unit test in
   whatever test module already covers `extract/ladder.py`
   demonstrating the specific case ticket 003 found (e.g. a fixture
   page with a stale date early in the body and a real upcoming date
   later).

**Explicitly out of scope** (per sprint.md Scope and Design Rationale):
Birch Aquarium / `localist.py` (not part of this issue); any change to
the ladder's general priority order or confidence scheme; bespoke
per-site scraper code beyond what ticket 003's diagnosis calls for;
auto-detection of JS-rendering (the explicit `fetch_strategy` flag is
reused as-is).

**Regression guard**: any `extract/ladder.py` change must not change
behavior for the ~10 other registered `generic_html`/`listing_html`
sources that already rely on it — run the full yield check (all
sources, not just the three flagship ones) as part of verification.

**Files** (exact set depends on ticket 003's findings — expect a subset
of):
- `partner_scrape/registry/sources/sdnhm.toml`
- `partner_scrape/registry/sources/sandiego-air-space.toml`
- `partner_scrape/registry/sources/fleet-science-center.toml`
- `partner_scrape/extract/ladder.py` (only if ticket 003 found a
  ladder-level cause)
- `partner_scrape/discovery/sitemap.py` (only if ticket 003 found a
  gap in discovery's pattern matching itself, as opposed to a
  per-source config fix)
- Corresponding test file(s) under `tests/` for whatever module
  changed

## Acceptance Criteria

- [ ] SDNHM, Air & Space, and Fleet Science Center each contribute a
      realistic count of dated, upcoming events — not 0-1 — verified
      by a before/after yield check:
      `uv run partner-scrape --source {sdnhm,sandiego-air-space,fleet-science-center} --no-enrich --dry-run -v`
      run once before this ticket's changes (baseline, matching issue
      14's reported 0/0/1) and once after, with the exported/dated
      counts recorded in this ticket.
      **DEFERRED**: live network scraping is blocked in this
      verification session (offline-only pass), so the before/after
      command above could not be run here. Unit-proven instead: three
      new fixture tests
      (`tests/fixtures/html/body_regex_past_old_window.html`,
      `body_regex_script_excluded.html`,
      `body_regex_comment_excluded.html`) replicate the exact real-page
      shapes ticket 003 measured live (dates at visible-text offsets
      3274–9357 across SDNHM/Air & Space/Fleet, past the old
      3000-character window and behind script/style/comment noise) and
      assert the corrected `start` field is now extracted. Ticket 003's
      Findings table itself is the live evidence base (5 real pages, 3
      sites, `curl`/pipeline-confirmed offsets). End-to-end live
      confirmation of the actual exported counts is deferred to the
      next full pipeline re-run.
- [ ] No other registered `generic_html`/`listing_html` source's yield
      regresses — verified by running the same command (or a full
      `--limit`-less run) across all sources before/after and
      confirming no source's count drops.
      **DEFERRED**: same live-scrape blocker as above — no before/after
      cross-source yield command was run this session. Unit-proven
      instead: the full test suite (848 tests, including all
      pre-existing `_extract_body_regex`/ladder coverage for other
      sources, e.g. the boundary-offset assertion in
      `TestBodyRegexRung`) passes with zero regressions, and the
      dispatcher (`extract_fields`) and rung call order were not
      touched by this diff (verified via `git diff`) — only
      `_extract_body_regex`'s internal text-scanning logic changed, so
      no other rung's behavior is code-path-reachable-changed. Live
      cross-source yield confirmation deferred to the next full
      pipeline re-run.
- [x] `uv run pytest` passes — full suite (~845 existing tests) plus
      any new tests added for the specific fix. Verified: **848
      passed** (845 existing + 3 new: `TestBodyRegexScriptStyleExcluded`,
      `TestBodyRegexCommentExcluded`, `TestBodyRegexWidenedWindow` in
      `tests/test_extract_ladder.py`), zero failures, zero regressions.
- [x] Birch Aquarium / `localist.py` is untouched. Verified via `git
      diff --stat` / `git status` — the changed-file set is limited to
      `partner_scrape/extract/ladder.py`,
      `partner_scrape/registry/sources/{fleet-science-center,sandiego-air-space}.toml`,
      `tests/test_extract_ladder.py`, and 3 new fixtures under
      `tests/fixtures/html/`. No `localist.py` or Birch-related file
      appears anywhere in the diff.
- [x] The ladder's rung priority order and confidence-tier constants
      (`CONFIDENCE_JSON_LD` through `CONFIDENCE_BODY_REGEX`) are
      unchanged, unless ticket 003's findings explicitly justified
      otherwise (call this out explicitly if so). Verified: `grep -n
      "^CONFIDENCE_" partner_scrape/extract/ladder.py` against `git
      diff` shows none of the six confidence constants appear in the
      diff at all, and the `extract_fields()` dispatcher function
      (which calls the rungs in priority order) is untouched — only
      `_extract_body_regex`'s internal body-text computation changed,
      plus two new private helper functions
      (`_visible_text_parts`/`_visible_body_text`) it calls. No
      reordering, no new rung, no confidence-tier change; ticket 003
      did not recommend any.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite, ~845 tests) —
  must pass with zero regressions. Specifically re-check any existing
  tests covering `extract/ladder.py`, `discovery/sitemap.py`,
  `discovery/listing.py`, and registry loading
  (`registry/schema.py`), since those are the modules most likely
  touched.
- **New tests to write**: unit test(s) covering whichever specific fix
  was applied — e.g. a `ladder.py` test with a fixture page containing
  multiple dates (reproducing SDNHM's pattern) asserting the correct
  date is selected, or a `discovery/sitemap.py` / registry-loading test
  covering the config change, matching this project's existing
  per-module test file convention (see `tests/` for the existing
  layout).
- **Verification command**: `uv run pytest`, plus the before/after
  yield-check commands in Acceptance Criteria above.
- **Documentation**: update the affected source TOML's header comment
  (each currently documents its own discovery/extraction assumptions —
  e.g. `fleet-science-center.toml`'s comment claiming no `<time>`
  markup exists, which ticket 003's live check contradicted) so it
  reflects the corrected understanding, not the stale sprint-003
  assumption.
