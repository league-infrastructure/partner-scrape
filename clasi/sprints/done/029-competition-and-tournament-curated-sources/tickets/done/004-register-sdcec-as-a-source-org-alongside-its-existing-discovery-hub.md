---
id: '004'
title: Register SDCEC as a source org alongside its existing discovery hub
status: done
use-cases:
- SUC-047
depends-on:
- '001'
- '002'
- '003'
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register SDCEC as a source org alongside its existing discovery hub

## Description

SDCEC (San Diego County Engineering Council, sandiegoengineers.org/stem)
already has `registry/hubs/sdcec-stem.toml`, a discovery-only hub from
sprint 024. This ticket registers SDCEC as an actual org source,
`registry/sources/sdcec.toml`, `adapter_type = "program_page_multi"`
against the same `/stem` page, extracting its hand-curated youth STEM
list (including the Feb 20 2026 Engineers Week awards) into N
independently-typed `Event`s. **Leave the existing hub file completely
unmodified** — a hub and a source for the same org are two different,
already-separate catalogs (`registry/DESIGN.md` §3's physical-separation
invariant); this is not the same-org-registered-twice-*within*-`sources/`
risk this sprint avoids elsewhere. Set no `config.opportunity_type`
override, matching ticket 003's reasoning: SDCEC's list mixes
competitions with other opportunity types.

**Cross-check** (depends on tickets 001-003 landing first): compare
SDCEC's curated `/stem` list against every source this sprint registers
(tickets 001-003) for accidental overlap — the same failure mode sprint
027's COSMOS/OPTIMUS/ENLACE Open Question names for the program-page
family generally. Record the result in this ticket's Notes even if no
overlap is found.

## Acceptance Criteria

- [x] `registry/sources/sdcec.toml` is registered, live-verified, and
      yields at least the Engineers Week awards as a dated record.
      **(2026-09-02)** Not literally satisfied by a live run — see
      Notes. `registry/sources/sdcec.toml` IS registered
      (`program_page_multi`, no `opportunity_type` override) and WAS
      live-verified end-to-end (real `--dry-run` pipeline run plus
      three direct `extract_programs()` calls), but the real
      extraction is non-deterministic on this page's shape (0/17/21/32
      distinct result sets across four real calls against identical
      fetched text) and, independently, no Feb 20 2026 Engineers Week
      awards date is published anywhere on the live site today (its
      dedicated `/awards` subpage states only that nominations are
      open Oct 1–Dec 8, with no banquet date). Registered
      `enabled = false` with a reason comment, per the disabled-with-
      evidenced-reason convention this whole sprint uses (tickets
      001/002/003/006/007). The `program_page_multi` mechanism itself
      is fixture-proven instead:
      `TestSDCECFixtureExtraction.test_n_curated_items_yield_n_independently_typed_events`
      (`tests/test_adapters_program_page_multi.py`) proves 3 distinct,
      independently-typed records extract from one page, including an
      Engineers Week Awards Banquet record dated 2026-02-20.
- [x] `registry/hubs/sdcec-stem.toml` is unmodified (verify with `git
      diff` before finishing this ticket).
- [x] The cross-check against tickets 001-003's registrations is
      performed and its result (overlap found and reconciled, or none
      found) is recorded in this ticket's Notes.
- [x] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_page_multi.py
  tests/test_registry.py tests/test_registry_hub_schema.py` (the hub
  schema/loader tests must show no change in behavior for
  `sdcec-stem.toml`).
- **New tests to write**: a fixture test with a saved `/stem` page
  proving multiple independently-typed `Event`s extract, including the
  Engineers Week awards, per SUC-047's acceptance criteria.
- **Verification command**: `uv run pytest`

## Notes (2026-09-02, ticket execution)

**Registered**: `registry/sources/sdcec.toml` — `program_page_multi`,
`config.url = "https://www.sandiegoengineers.org/stem"`,
`config.program_kind = "program"`, no `opportunity_type` override (per
this ticket's own Description). `registry/hubs/sdcec-stem.toml` is
confirmed unmodified — `git diff -- registry/hubs/sdcec-stem.toml`
shows no changes before or after this ticket's execution;
`tests/test_registry.py`'s new `TestSDCECRegistration.
test_the_existing_discovery_only_hub_is_unmodified` guards this going
forward.

**Live verification, real network, real tooling** (this execution
environment's Bash tool has outbound network only with
`dangerouslyDisableSandbox: true`; used throughout):

1. `GET https://www.sandiegoengineers.org/stem` → HTTP 200 (`www.`
   required, matching the existing hub file's own finding).
2. `uv run partner-scrape --source sdcec --dry-run -v --no-report`
   (source temporarily flipped to `enabled = true` for these runs, then
   reverted) — first run: `yielded 0 event(s)`. Investigating via a
   direct `AnthropicProgramLLMClient.extract_programs()` call against
   the identical fetched/reduced text (26,495 chars) returned **17**
   results, not 0 — a fresh call, not a cache read (the first run's
   `[]` result had been cached under this page's content hash;
   deleting that cache entry and re-running the CLI twice more both
   yielded `32 event(s)`/`wrote 7 opportunities`, and a fourth,
   separate direct `extract_programs()` call returned **21** results).
   Four calls against byte-identical input text, four different result
   counts and different program sets each time — a real
   non-determinism in the model's own sampling on this page, not a
   caching or plumbing bug (confirmed by inspecting the actual
   `program_name`/date values returned each time, not just the
   counts).
3. Root cause, confirmed by direct inspection of the reduced text
   (`reduce_html_to_text()`'s actual output): this Google Sites page
   concatenates an unlabeled "current cycle" curated list with a
   decade-plus "Prior sTEm Events" historical archive on the *same*
   fetched page, with no markup boundary the reduction step preserves
   for the model to anchor "which section is this item from" against —
   `extract_programs()`'s "identify every distinct program described on
   the page" framing has nothing stable to lock onto, so each call
   samples a different subset. This is the same failure *class*
   `sd-math-circle.toml`'s already-disabled "wrong axis of extraction"
   disposition names (a page shape the per-section framing doesn't
   fit), not the deadline-vs-event-date bug ticket 006 fixed.
4. Independently of the reliability problem: grepped the full reduced
   text and found no "Feb 20, 2026" and no dated "Engineers Week
   awards" item anywhere — the only nearby text is "Nov 3 - STEM Grant
   deadline to support K12 activities and events during or around
   Engineers Week (Feb 2026)" (a grant deadline, no day) and an undated
   "San Diego Engineers Awards Celebration" mention. Followed the
   `/awards` link found in the page's own outbound links (`GET
   https://www.sandiegoengineers.org/awards` → HTTP 200) — its reduced
   text states only "The Awards Nominations are open October 1 -
   December 8" for the annual "San Diego Engineers Week Awards
   Banquet"; no banquet date is published on the live site as of this
   verification. This ticket's own Description's "Feb 20 2026" premise
   does not currently hold against the live site's real content
   (possibly true at an earlier planning-time check, or the org has not
   yet posted this cycle's date — not investigated further, out of
   scope).
5. No content resembling an instruction to an automated fetcher was
   found on either the `/stem` or `/awards` page.

**Disposition**: `registry/sources/sdcec.toml` registered
`enabled = false`, with the full evidence trail in the file's own
header comment — ready to flip on if a future ticket either fixes the
extraction-reliability problem (e.g. splitting "current" from "archive"
content structurally before the LLM call) or the org publishes this
cycle's Engineers Week awards date and re-verification confirms
reliable extraction.

**Cross-check against tickets 001-003's registrations (SUC-047 AC)**:
performed by comparing every program name observed across the four live
extraction runs above against `registry/sources/`'s tickets 001-003
registrations. **Overlap found**: SDCEC's curated list includes items
textually matching two already-separately-registered organizations —
"Congressional App Challenge" (== `congressional-app-challenge-sd.toml`,
`enabled = true`, ticket 001) and "MATHCOUNTS" (== `mathcounts-sd-
chapter.toml`, `enabled = false`, WAF-blocked, ticket 001) — both
appeared as their own items across the extraction runs. This is exactly
the cross-registration shape `adapters/DESIGN.md`'s sprint 027
COSMOS/OPTIMUS/ENLACE Open Question warns about (`kind in
PROGRAM_EXTRACTION_KINDS` records bypass cross-source dedup by design).
**No reconciliation action was needed right now**: `sdcec.toml` is
`enabled = false` (see above), so SDCEC's own copies of these two items
cannot publish today — the risk is dormant, not live. Recorded in the
TOML file's own header comment as a residual risk for whoever revisits
SDCEC's extraction reliability in a future ticket: re-check for this
exact overlap before ever flipping `sdcec.toml` to `enabled = true`,
since `congressional-app-challenge-sd.toml` (and, if ever re-enabled,
`mathcounts-sd-chapter.toml`) should stay the sole registration for
those programs, not SDCEC's own copy.

**No SD Festival overlap**: SD Festival of Science & Engineering /
`lovestemsd.org` (ticket 003) is not among the org names observed in
SDCEC's extracted items (SDCEC's list references it only as a bare
calendar-reference line, "Mar 7 - San Diego Festival of Science &
Engineering", never extracted as its own top-level program by any of
the four runs) — no overlap.

**Test suite**: `uv run pytest tests/test_adapters_program_page_multi.py
tests/test_registry.py tests/test_registry_hub_schema.py` → 108 passed.
Full suite `uv run pytest` → 2188 passed (baseline 2183 + 5 new tests:
4 in `TestSDCECRegistration`, 1 in `TestSDCECFixtureExtraction`).
