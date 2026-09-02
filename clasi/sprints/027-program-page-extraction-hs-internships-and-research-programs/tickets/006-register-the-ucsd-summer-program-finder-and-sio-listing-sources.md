---
id: '006'
title: Register the UCSD Summer Program Finder and SIO listing sources
status: done
use-cases:
- SUC-032
depends-on:
- '005'
- 008
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register the UCSD Summer Program Finder and SIO listing sources

## Description

**Rescoped by architecture revision (2026-09-02).** This ticket's
original Fix shape assumed both sources register as plain
`program_listing` sources using unmodified `EVENT_PATH_RE` discovery.
This ticket's own required live-verification step found that
assumption false for both sources and threw a ticket exception,
recorded (before this rewrite) in this file's `exception:` frontmatter
history — see git history for the original text, or ticket 008's
Description for a summary. The team-lead reclassified the exception's
surface `user-visible` -> `internal` and dispatched an architecture
revision (`design/adapters-DESIGN.md`'s Revision note); ticket 008
implements the resulting mechanism changes and must land first
(`depends-on` below).

Register two `program_listing`-family sources, now using the mechanism
ticket 008 adds: the UCSD Summer Program Finder
(summer.ucsd.edu/program-finder — ~24 HS-eligible program cards
including COSMOS/ENLACE/OPTIMUS/Research Scholars/Sally Ride/SPARK/
Upward Bound, discovered via a `config.link_selector` CSS selector
against their `data-grade`/`a.learnmore` markup, not `EVENT_PATH_RE`)
and the SIO research-internships page (scripps.ucsd.edu/education/
research-internships — JT-SURF, MPL, CW3E and other undergrad programs
with explicit deadlines, registered as `program_page_multi` since its
~10 programs are inline sections on one page, not linked detail pages).
Both are `kind = "internship"` (see ticket 005's Architecture
rationale).

Depends on ticket 005 (must land first so the OPTIMUS/ENLACE/COSMOS
reconciliation decision ticket 005 records is already settled before
this ticket registers the listing that would otherwise duplicate them)
and ticket 008 (the mechanism this ticket's Fix shape now depends on).

## Fix shape

1. Create `registry/sources/ucsd-summer-program-finder.toml`:
   `adapter_type = "program_listing"`, `config.site_url =
   "https://summer.ucsd.edu"`, `config.listing_urls =
   ["/program-finder"]` (confirm the live path — this sprint's
   exception-cycle live verification found a trailing-slash redirect to
   200), `config.program_kind = "internship"`, and `config.link_selector`
   set to a CSS selector that both discovers the HS-eligible cards' links
   and filters to eligibility in one string — e.g.
   `li[data-grade*="High School"] a.learnmore`, confirmed against the
   live page's real markup during this revision's design work
   (`<li data-grade="High School">…<a class="learnmore" href=…>`); adjust
   if the live page's markup differs at implementation time.
2. Create `registry/sources/sio-research-internships.toml`:
   `adapter_type = "program_page_multi"` (not `program_listing` — SIO's
   page is one page with N inline program records, not a listing of
   links to N detail pages), `config.url =
   "https://scripps.ucsd.edu/education/research-internships"`,
   `config.program_kind = "internship"`.
3. Live-verify both with `uv run partner-scrape --source <id> --dry-run
   -v` before enabling. For UCSD, confirm the `link_selector` yields a
   plausible non-zero count of distinct HS-eligible program cards (~24
   expected, per issue 28's own "21 HS-eligible" estimate plus this
   ticket's own live count). For SIO, confirm `extract_programs()`
   yields one `Event` per named program (~10 expected: JT-SURF, MPL,
   CW3E, CCE LTER, etc.), each with its own deadline pulled from the
   page's own inline prose (not the outbound program-homepage link,
   which this revision's investigation confirmed does not itself carry
   the deadline).
4. Confirm the OPTIMUS/ENLACE/COSMOS reconciliation from ticket 005:
   verify the UCSD listing's own `link_selector`-based discovery and
   extraction actually produces usable records for those three programs
   (correct name, deadline, eligibility) from their cross-domain target
   pages (jacobsschool.ucsd.edu/cosmos/about,
   resilientmaterials.ucsd.edu/ENLACE, and OPTIMUS's own page) before
   relying on the listing as their sole source — if any of the three
   extracts poorly (e.g. its cross-domain target page doesn't carry a
   deadline/eligibility an LLM extraction can recover), register that
   one individually as a `program_page` source instead (reopening this
   decision from ticket 005), and update ticket 005's Notes to record
   the change and cross-reference this ticket.

## Acceptance Criteria

- [x] Both sources are registered, live-verified, and `enabled = true`,
      each yielding a plausible non-zero count of distinct program
      `Event`s (~24ish for UCSD via `link_selector`, ~10 for SIO via
      `program_page_multi`).
- [x] OPTIMUS, ENLACE, and COSMOS each appear among the UCSD listing's
      extracted `Event`s with a real title, deadline, and eligibility —
      or the reconciliation decision is revised and recorded (registered
      individually instead, ticket 005's Notes updated) if not.
- [x] SIO's extracted `Event`s carry the deadline stated in the page's
      own inline prose, not a blank/missing value inherited from the
      outbound program-homepage link.
- [x] No program registered by ticket 005 also appears in either
      source's extracted output under a matching identity (spot-check
      by title, not an automated dedup check — these `kind`s bypass
      dedup by design).
- [x] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite.
- **New tests to write**: a registry-loader fixture test proving a
  `program_page_multi`-typed TOML with `config.program_kind` parses
  correctly, and one proving a `program_listing`-typed TOML with
  `config.link_selector` parses correctly (both should need no new
  loader code, per `registry/DESIGN.md`'s untyped-`config`-dict
  convention) — beyond that, this ticket is live registration and
  verification, not new adapter code (that's ticket 008's scope).
- **Verification command**: `uv run pytest`, plus live `--dry-run -v`
  verification for both sources.

## Implementation Plan

**Approach**: Register and live-verify one source at a time, same
convention as ticket 005. Requires ticket 008's mechanism changes to be
merged first.

**Files to create**: 2 new `registry/sources/*.toml` files.

**Testing plan**: see Testing above.

**Documentation updates**: None expected beyond this ticket's own Notes
recording live-verification outcomes and the OPTIMUS/ENLACE/COSMOS
reconciliation confirmation (or, if the reconciliation flips, updating
ticket 005's Notes directly).

## Notes

**4 sources registered** (2 more than the Fix shape's original "2 new
files" estimate -- the OPTIMUS/ENLACE/COSMOS reconciliation, described
below, required two additional individual `program_page` files):

| source_id | adapter_type | enabled | live yield |
|---|---|---|---|
| `ucsd-summer-program-finder` | `program_listing` (`link_selector`) | true | 22 discovered refs (of 24 real HS-eligible cards, minus COSMOS/OPTIMUS excluded per reconciliation below) -> 21 `Event`s (one card, `www.rmtlacademy.org`, fetched a body too large for the model's context window -- logged and skipped per this ticket's own adapter fix, not a registration failure) |
| `sio-research-internships` | `program_page_multi` | true | 1 discovered ref -> 9 `Event`s, 5 with explicit inline deadlines (JT-SURF Feb 27 2026, MPL Jan 23 2026, CCE LTER Jan 31 2026, CW3E Jan 15 2026, UC NRS Field Science Fellowship Feb 15 2026) |
| `ucsd-cosmos` | `program_page` | true | 1 `Event`: title "COSMOS...", `start`=2026-01-07 (applications open), `end`=2026-02-06 (deadline), rich eligibility (grades 8-12, CA residents, GPA/vaccination detail) |
| `ucsd-optimus` | `program_page` | **false** (disabled with reason) | 1 `Event`: title "OPTIMUS" only -- no deadline, no eligibility recoverable from the live page; see below |

All four live-verified 2026-09-02 via a direct
`discover()`->`fetch()`->`extract()` call against the live network and a
real `AnthropicProgramLLMClient`, bypassing normalize/export, matching
ticket 005's own precedent.

**Live markup confirmation (Fix shape step 1).** The UCSD Summer
Program Finder's real page (`https://summer.ucsd.edu/program-finder/`)
was fetched and inspected directly (`lxml.cssselect`) before writing the
registry file: `li[data-grade*="High School"] a.learnmore` matches
exactly 24 cards, confirming the ticket's own ~24 estimate and the
`data-grade` markup shape recorded in `adapters/DESIGN.md`'s Revision
note. `https://summer.ucsd.edu/program-finder` (no trailing slash) is a
301 to the `http://` (not `https://`) trailing-slash form; the
registered `listing_urls = ["/program-finder/"]` uses the trailing-slash
form directly to avoid that extra hop.

**OPTIMUS/ENLACE/COSMOS reconciliation (Fix shape step 4).** Each of the
three programs' own listing-card target page was fetched and read
directly:

- **ENLACE** (`resilientmaterials.ucsd.edu/ENLACE`): extracts well --
  "The deadline to apply is February 6, 2026," plus explicit grade-11/
  university eligibility text, both directly on the page the listing's
  own card links to. Left listing-only, exactly as ticket 005 originally
  decided -- no change.
- **COSMOS** (`jacobsschool.ucsd.edu/cosmos/about`, the listing's own
  card target): a program-description page with no deadline anywhere on
  it. The real deadline/eligibility lives on a sibling page,
  `/cosmos/how-to-apply` ("Applications for COSMOS 2026 open... and
  close on Friday, February 6th"), which the listing's card link never
  reaches -- a `program_listing` crawl has no mechanism to follow to a
  program's *other* pages. Registered individually
  (`ucsd-cosmos.toml`), pointed directly at `/cosmos/how-to-apply`,
  `enabled = true`; the listing's own `link_selector` gained a
  `:not([href*="jacobsschool.ucsd.edu/cosmos"])` clause excluding
  COSMOS's card so it is never double-published.
- **OPTIMUS** (`moorescancercenter.ucsd.edu/education/training-programs/high-school.html`,
  the listing's own card target): a one-paragraph blurb, no deadline, no
  eligibility beyond generic nav categorization; its own "Learn more and
  Apply" link resolves to
  `.../training-programs/_archive/optimus/index.html`, confirmed HTTP
  404 (a dead, archived page). A web search surfaced a richer
  description (specific partner high schools, grades 10-11, a stipend)
  attributed to `moorescancercenter.ucsd.edu/education/optimus/index.html`,
  but that URL, `.../education/optimus/`, and a `sites.medschool.ucsd.edu`
  mirror were all tried live and are unreachable (404 or connection
  failure) -- so this ticket could not confirm any richer OPTIMUS page
  still resolves, and registered the one OPTIMUS-naming page that does.
  Registered individually (`ucsd-optimus.toml`), `enabled = false` with
  a reason comment (registry/DESIGN.md's disabled-with-reason
  convention): even this best-reachable page's own live dry-run yielded
  a title only, not the "real title, deadline, and eligibility" this
  ticket's own acceptance criterion requires. The listing's own
  `link_selector` gained a matching
  `:not([href*="moorescancercenter.ucsd.edu/education/training-programs/high-school.html"])`
  clause excluding OPTIMUS's card, so it is not double-published either
  (it simply isn't published via the listing at all, and its individual
  registration is disabled) -- kept in the registry rather than deleted,
  per the same disabled-with-reason convention, so re-verification stays
  possible if UCSD ever republishes a real OPTIMUS application page.
  Ticket 005's Notes were updated in place with a cross-referenced
  "UPDATE" entry recording this split.

**Adapter bug found and fixed during live verification (not part of the
original Fix shape, landed here per sprint 016 ticket 001's precedent
for a registration ticket fixing an adapter bug its own live
verification uncovers).** The first live run of the UCSD listing raised
an uncaught `anthropic.BadRequestError` ("prompt is too long: 259984
tokens > 200000 maximum") from inside
`_extract_one_program`'s/`_extract_many_programs`' call to
`llm_client.extract_program()`/`extract_programs()`, for the
`www.rmtlacademy.org` card (a 612KB page). `adapters/base.py`'s `run()`
has no per-ref try/except of its own -- by design, each adapter's own
`extract()` is responsible for per-record isolation (`Adapter.extract()`'s
own docstring) -- so this one oversized card's exception would have
aborted the *entire* source, discarding all 21 other already-fetched
cards' `Event`s along with it, every run, forever. Fixed in
`partner_scrape/adapters/program_page.py`: both
`_extract_one_program`/`_extract_many_programs` now wrap their
respective `llm_client` call in `except Exception`, log a warning naming
the URL and exception, and return `[]` for that one ref -- mirroring
`enrich/enricher.py`'s own documented "any exception the call raises,
not only a specific error type" fail-open stance for its own LLM call.
New tests: `tests/test_adapters_program_page.py::TestExtractRobustness::test_extract_program_raising_is_logged_and_skipped_not_raised`,
`tests/test_adapters_program_page_multi.py::TestExtractRobustness::test_extract_programs_raising_is_logged_and_skipped_not_raised`,
and `tests/test_adapters_program_listing.py::TestPerCardIsolation::test_a_card_whose_llm_extraction_raises_is_skipped_but_the_rest_still_yield_events`
(the last proves the multi-ref case: one broken card is skipped, the
other cards in the same listing run still yield their own `Event`s).

**No duplicate identity with ticket 005's 13 individually-registered
pages (spot-check).** None of the UCSD listing's 21 or SIO's 9 extracted
titles/URLs match any of ticket 005's registered `source_id`s or their
recorded extracted titles. One coincidental name collision was checked
closely: the UCSD listing yields a card titled "SPARK (Summer Program to
Accelerate Regenerative medicine Knowledge)"
(`stemcellprogram.ucsd.edu/cmm250/spark-program.html`, UCSD's Stem Cell
Program), which shares only the acronym "SPARK" with ticket 005's
`sbp-spark.toml` (Sanford Burnham Prebys, extracted title "Internships
and Training Programs" per ticket 005's own Notes table) -- a different
organization, a different URL, and a different extracted title,
confirmed not a duplicate identity: two distinct real-world programs
that happen to share a common training-program acronym.

**Registry location**: root-level `registry/sources/` (sprint 025;
confirmed via ticket 005's precedent), same as every other source in
this sprint.

**New test coverage**: `tests/test_registry.py`'s
`TestProgramListingAndMultiSourceConfig` (fixture-parsing proof for
`program_listing`'s `link_selector` and `program_page_multi`'s
`program_kind`, both against synthetic fixtures in their own sibling
directories per `TestProgramPageSourceConfig`'s precedent, plus a
real-registry test for both new sources);
`test_ucsd_optimus_enlace_cosmos_not_registered_as_individual_program_pages`
was split into `test_ucsd_enlace_not_registered_as_an_individual_program_page`
and `test_ucsd_cosmos_and_optimus_registered_individually_not_via_listing`
to assert the revised reconciliation. Full suite: 2076 passed (baseline
2069 + 7 new tests: 3 registry fixture/real-registry tests net of the
1-test split above, 3 adapter per-record LLM-exception-isolation tests,
1 additional program_listing per-card isolation test).
