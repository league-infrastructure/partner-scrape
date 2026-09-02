---
id: '006'
title: Register the UCSD Summer Program Finder and SIO listing sources
status: open
use-cases: [SUC-032]
depends-on: ['004', '005']
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register the UCSD Summer Program Finder and SIO listing sources

## Description

Register two `program_listing` sources: the UCSD Summer Program Finder
(summer.ucsd.edu/program-finder — 21 HS-eligible program cards
including COSMOS/ENLACE/OPTIMUS/Research Scholars/Sally Ride/SPARK/
Upward Bound) and the SIO research-internships table
(scripps.ucsd.edu/education/research-internships — JT-SURF, MPL, CW3E
and other undergrad programs with explicit deadlines). Both are
`kind = "internship"` (see ticket 005's Architecture rationale).

Depends on ticket 004 (the adapter) and ticket 005 (must land first so
the OPTIMUS/ENLACE/COSMOS reconciliation decision ticket 005 records is
already settled before this ticket registers the listing that would
otherwise duplicate them).

## Fix shape

1. Create `registry/sources/ucsd-summer-program-finder.toml`:
   `adapter_type = "program_listing"`, `config.site_url =
   "https://summer.ucsd.edu"`, `config.listing_urls =
   ["/program-finder"]` (or the confirmed live path), `config.
   program_kind = "internship"`.
2. Create `registry/sources/sio-research-internships.toml`: same shape,
   `config.site_url = "https://scripps.ucsd.edu"`, `config.listing_urls
   = ["/education/research-internships"]`.
3. Live-verify both with `uv run partner-scrape --source <id> --dry-run
   -v` before enabling. If `discovery.listing.discover_via_listing`'s
   `EVENT_PATH_RE` matching (§`adapters-DESIGN.md`'s Open Questions)
   yields zero or unexpectedly few cards for either page, investigate
   before assuming the adapter is broken — the listing page's actual
   card-link shape may not match the expected `/program(s)?` pattern,
   in which case document the finding rather than silently forcing a
   pattern change outside this ticket's data-only scope (escalate as a
   ticket exception if a code change in `discovery/listing.py` turns
   out to be required).
4. Confirm the OPTIMUS/ENLACE/COSMOS reconciliation from ticket 005:
   verify the listing's own extraction actually produces usable
   records for those three programs (correct name, deadline,
   eligibility) before relying on the listing as their sole source —
   if any of the three extracts poorly from the listing card/detail
   page, re-open the decision (register that one individually instead,
   updating ticket 005's Notes) rather than shipping an incomplete
   record.

## Acceptance Criteria

- [ ] Both sources are registered, live-verified, and `enabled = true`,
      each yielding a plausible non-zero count of distinct program
      `Event`s (21ish for UCSD, several for SIO).
- [ ] OPTIMUS, ENLACE, and COSMOS each appear among the UCSD listing's
      extracted `Event`s with a real title, deadline, and eligibility —
      or the reconciliation decision is revised and recorded if not.
- [ ] No program registered by ticket 005 also appears in either
      listing's extracted output under a matching identity (spot-check
      by title, not an automated dedup check — these `kind`s bypass
      dedup by design).
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite.
- **New tests to write**: none required beyond ticket 004's own
  `ProgramListingAdapter` fixture tests — this ticket is live
  registration and verification, not new code.
- **Verification command**: `uv run pytest`, plus live `--dry-run -v`
  verification for both sources.

## Implementation Plan

**Approach**: Register and live-verify one source at a time, same
convention as ticket 005.

**Files to create**: 2 new `registry/sources/*.toml` files.

**Testing plan**: see Testing above.

**Documentation updates**: None expected beyond this ticket's own Notes
recording live-verification outcomes and the OPTIMUS/ENLACE/COSMOS
reconciliation confirmation.
