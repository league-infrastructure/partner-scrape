---
id: '005'
title: Register the individual HS internship and research program pages
status: open
use-cases: [SUC-031, SUC-033, SUC-034]
depends-on: ['003']
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

- [ ] At least the majority of the ~13 named individual pages in scope
      here (excluding the 3 UCSD-listing-covered programs and pending
      the Illumina/SD2 disposition) are registered, live-verified, and
      `enabled = true` — matching this sprint's Success Criteria
      ("majority of the ~15").
- [ ] Every registered page's live dry-run yields one `Event` with a
      non-empty title, a real `date_end` or an explicit "rolling"
      determination, and a plausible `eligibility` value.
- [ ] Any page that could not be live-verified successfully is
      registered `enabled = false` with a reason comment, and listed in
      this ticket's Notes.
- [ ] The OPTIMUS/ENLACE/COSMOS reconciliation decision (registered via
      ticket 006's listing only, not here) is recorded in this ticket's
      Notes, cross-referenced from ticket 006.
- [ ] The Illumina/SD2 "closed pipeline" investigation outcome
      (registered, or explicitly not, and why) is recorded in this
      ticket's Notes.
- [ ] Full test suite stays green; registry-loader parsing tests cover
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
