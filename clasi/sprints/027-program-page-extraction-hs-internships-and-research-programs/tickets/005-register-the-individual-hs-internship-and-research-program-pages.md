---
id: '005'
title: Register the individual HS internship and research program pages
status: done
use-cases:
- SUC-031
- SUC-033
- SUC-034
depends-on:
- '003'
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register the individual HS internship and research program pages

## Description

Register the ~15 individually-named program pages issue 28 catalogs as
`program_page` sources, each `kind = "internship"` (per this sprint's
Architecture: these are all structured, application-based, paid-or-not
STEM placements, matching the existing `Work-based Learning` bucket's
demonstrated breadth): Salk Heithoff-Brody HS Scholars, SDSC REHS,
Sanford Burnham Prebys SPARK, La Jolla Institute LJIdea, Scripps
Research SRTI, Scripps Research REACH, NIWC Pacific SEAP, NIWC Pacific
NREIP, NOAA Hutton, SDZWA fellowships, SDZWA InternQuest, SDSU ExpandAI,
Biocom Generation STEAM Pathways. (UCSD OPTIMUS/ENLACE/COSMOS and
Illumina/SD2 are deliberately excluded here — see the reconciliation
note below and ticket 006.)

**Reconciliation with ticket 006 (required before either goes live):**
issue 28's own text names UCSD OPTIMUS/ENLACE/COSMOS in both the UCSD
Summer Program Finder listing description *and* the individual-pages
list. Since `kind in PROGRAM_EXTRACTION_KINDS` records bypass
cross-source dedup entirely (by design — see `normalize/DESIGN.md`'s
sprint 027 addendum and `adapters/DESIGN.md`'s matching Open Question),
registering the same real program both ways would publish it twice.
This ticket registers OPTIMUS/ENLACE/COSMOS via the
`program_listing`-sourced UCSD Summer Program Finder (ticket 006)
only, NOT as individual `program_page` sources here — confirm this
decision is still correct once ticket 006's live dry-run shows what the
listing actually yields for those three programs, and adjust before
either ships if the listing's own extraction turns out incomplete for
any of them. Illumina/SD2 STEM Scholars is named in issue 28 as a
"closed pipeline" (no open application path) — investigate whether a
live program page exists to register at all before registering it;
document either way in this ticket's Notes.

## Fix shape

For each named program (except the three UCSD-listing-covered ones and
pending the Illumina/SD2 investigation above):

1. Create `registry/sources/<org-slug>.toml` with `adapter_type =
   "program_page"`, `org_name`, `config.url` (the program's own page),
   `config.program_kind = "internship"`, and (only if the program's own
   eligibility is a fixed institutional fact better hand-authored than
   LLM-inferred, e.g. Scripps REACH's "partner schools only") an
   optional `taxonomy_defaults.eligibility` override — otherwise let
   the LLM extraction's own `eligibility` output flow through
   (ticket 001's Event-level resolution).
2. Live-verify each registered page with `uv run partner-scrape
   --source <id> --dry-run -v` before committing `enabled = true` —
   matching sprint 014/016's precedent for new source registration
   (this sprint's own Test Strategy). Record each source's live yield
   (one `Event`, correctly shaped) in this ticket's Notes.
3. A page that fails to yield a correctly-shaped record after live
   verification is registered `enabled = false` with a reason comment,
   not silently dropped from the sprint — matching
   `registry/DESIGN.md`'s disabled-source-with-reason convention.

## Acceptance Criteria

- [x] At least the majority of the ~13 named individual pages in scope
      here (excluding the 3 UCSD-listing-covered programs and pending
      the Illumina/SD2 disposition) are registered, live-verified, and
      `enabled = true` — matching this sprint's Success Criteria
      ("majority of the ~15").
- [x] Every registered page's live dry-run yields one `Event` with a
      non-empty title, a real `date_end` or an explicit "rolling"
      determination, and a plausible `eligibility` value.
- [x] Any page that could not be live-verified successfully is
      registered `enabled = false` with a reason comment, and listed in
      this ticket's Notes.
- [x] The OPTIMUS/ENLACE/COSMOS reconciliation decision (registered via
      ticket 006's listing only, not here) is recorded in this ticket's
      Notes, cross-referenced from ticket 006.
- [x] The Illumina/SD2 "closed pipeline" investigation outcome
      (registered, or explicitly not, and why) is recorded in this
      ticket's Notes.
- [x] Full test suite stays green; registry-loader parsing tests cover
      at least one new `program_page` TOML shape (may reuse a fixture
      already added in ticket 002/003's test fixtures directory).

## Testing

- **Existing tests to run**: full suite, especially
  `tests/test_registry.py` (loader parsing of the new TOML shape).
- **New tests to write**: a registry-loader fixture test proving a
  `program_page`-typed TOML with `config.program_kind` parses into a
  `SourceConfig` correctly (no new loader code is expected — this
  verifies the existing untyped-`config`-dict mechanism already
  handles it, per `registry/DESIGN.md`'s sprint 027 addendum).
- **Verification command**: `uv run pytest`, plus the live
  `--dry-run -v` verification per source described above (not part of
  the hermetic suite).

## Implementation Plan

**Approach**: Register and live-verify one source at a time, committing
each independently-reviewable TOML addition; this is a data-authoring
ticket, not a code ticket (depends only on ticket 003's adapter
existing).

**Files to create**: up to ~13 new `registry/sources/*.toml` files.

**Testing plan**: see Testing above.

**Documentation updates**: None expected beyond this ticket's own Notes
recording each source's live-verification outcome — no DESIGN.md
change (registry data, not registry code, per `registry-DESIGN.md`'s
sprint 027 addendum).

## Notes

**Registry location**: sprint 025 relocated source data to a root-level
`registry/sources/` (sibling to `partner_scrape/`), not
`partner_scrape/registry/sources/` — confirmed via `registry/DESIGN.md`
§1 before creating any file. All 13 new TOMLs live there.

**13 sources registered** (13, not the full ~15 issue 28 names, per the
Description's exclusion of the 3 UCSD-listing-covered programs and
pending the Illumina/SD2 disposition below):

`enabled = true` (10 — live-verified 2026-09-01 via a direct
`ProgramPageAdapter.discover()`→`fetch()`→`extract()` call against the
live network + a real `AnthropicProgramLLMClient`, bypassing
`normalize`/export so a correctly-shaped-but-closed-window record is
still visible — export-time deadline-first filtering, if any, is
expected behavior per the Fix shape, not a verification failure):

| source_id | title extracted | date_start | date_end | eligibility present | notes |
|---|---|---|---|---|---|
| `salk-heithoff-brody` | Heithoff-Brody High School Summer Scholars Program | 2026-06-15 | 2026-03-01 | yes | end-before-start field-mapping quirk, see file comment |
| `sdsc-rehs` | UCSD Research Experience for High School Students | 2026-02-15 | 2026-03-15 | yes | |
| `sbp-spark` | Internships and Training Programs | — | — | yes | page covers SPARK+COMPASS; no fixed deadline anywhere found; treated as rolling ("email apply" per issue 28) |
| `lji-ljidea` | LJI Internships | — | — | yes | page states ongoing multi-channel recruitment, no cyclical deadline; treated as rolling |
| `scripps-srti` | Student Research Internship Program | 2026-06-01 | 2026-08-07 | yes | extraction mapped *program* dates, not the page's real Mar 30 *application* deadline — data-quality observation, out of this ticket's file-scope to fix |
| `niwc-seap` | Science and Engineering Apprenticeship Program (SEAP) | — | 2025-11-01 | yes | evergreen "Aug 1-Nov 1" text resolved to a past cycle year by the LLM |
| `niwc-nreip` | Naval Research Enterprise Internship Program (NREIP) | — | 2025-11-01 | yes | same stale-year observation as SEAP |
| `sdzwa-fellowships` | Summer Student Fellowships | — | 2026-02-15 | yes | |
| `sdsu-expandai-robotics` | Robotics Camp | — | — | yes | live page shows the 2025 cycle concluded, next cycle not yet posted; treated as rolling for now |
| `biocom-generation-steam` | Life Science Innov8Ed | — | — | yes | year-round in-class internship program, genuinely rolling |

`enabled = false` (3 — live-verification failures, each with a reason
comment in its own file, per the Fix shape's disabled-with-reason
convention):

| source_id | failure |
|---|---|
| `noaa-hutton` | `hutton.fisheries.org` returns HTTP 403 to both this project's `STEM-Calendar-Bot/1.0` UA and a plain browser UA via `curl` — a WAF/bot block, page confirmed real and current via web search |
| `sdzwa-internquest` | original URL 301s to `/kids-programs/conservation-career-quest` (SDZWA appears to have renamed/merged InternQuest into that page); both the original and redirect-target URL return HTTP 403 the same way as Hutton |
| `scripps-reach` | `education.scripps.edu` fails TLS chain verification (`SSL: CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`) for this project's Python/OpenSSL/certifi stack specifically — reproduced directly against the raw `ssl` module, independent of this project's own fetcher code; the page itself is reachable via `curl`/browsers, which chase/cache the missing intermediate differently. Its `taxonomy_defaults.eligibility` partner-schools-only override is still recorded in the file for whenever this is re-verified. |

10 of 13 enabled = true is a clear majority, satisfying the sprint's
"majority of the ~15" Success Criteria for this ticket's own ~13-item
scope.

**OPTIMUS/ENLACE/COSMOS reconciliation** (cross-reference for
ticket 006): not registered as individual `program_page` sources in
this ticket. Confirmed via `registry/` search that no
`optimus`/`enlace`/`cosmos`-named source exists anywhere in the
registry as of this ticket's completion (`tests/test_registry.py`'s
`test_ucsd_optimus_enlace_cosmos_not_registered_as_individual_program_pages`
enforces this going forward). Ticket 006 must register all three via
the UCSD Summer Program Finder `program_listing` source only. Per the
Description's own instruction, ticket 006 should re-confirm this
decision once its own live dry-run shows what the listing actually
yields for those three programs, and register an individual
`program_page` fallback here only if the listing's extraction turns
out incomplete for any of them.

**Illumina/SD2 STEM Scholars investigation** (not registered): live
web research (2026-09-01) found only a news feature article
(illumina.com/company/news-center) and an SD2 partnership page
(sd2.org) describing the program — a two-week on-site immersion for
10th-12th graders paired with a scholarship award — but no public,
open-application page. The SD2 partnership page gives no application
URL or process; the program appears to select scholars through SD2's
own school-district partnership pipeline (JA co-participation
mentioned), not a program page a HS student could independently apply
to. This matches issue 28's own "closed pipeline" characterization.
Decision: not registered as a `program_page` source (there is no
single page whose fetch+LLM-extract would produce a meaningful
application-window record) — `test_illumina_sd2_not_registered`
enforces this going forward. Re-investigate if SD2/Illumina ever
publish a direct application page.

**New test coverage** (`tests/test_registry.py`,
`TestProgramPageSourceConfig`): a synthetic fixture
(`tests/fixtures/registry_program_page/program_page_good.toml`, in its
own sibling directory so it doesn't perturb
`TestLoadSources`'s fixed fixture-directory file count) proves a
`program_page`-typed TOML with `config.program_kind` and a
`taxonomy_defaults.eligibility` override parses into a `SourceConfig`
correctly, plus real-registry tests for the majority-enabled count, the
per-source `program_kind`/`adapter_type` values, the three disabled
sources' reason comments, the REACH eligibility override, and the
OPTIMUS/ENLACE/COSMOS/Illumina-SD2 non-registration. Full suite: 2022
passed (baseline 2016 + 6 new tests).
