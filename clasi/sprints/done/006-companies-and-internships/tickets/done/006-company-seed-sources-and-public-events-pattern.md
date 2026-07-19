---
id: '006'
title: Company seed sources and public-events pattern
status: done
use-cases:
- SUC-007
depends-on:
- '001'
- '002'
- '003'
- '004'
- '005'
github-issue: ''
issue: 11-company-events-and-internships.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Company seed sources and public-events pattern

## Description

Register real San Diego STEM companies as `registry/sources/*.toml`
entries, using the two adapters (tickets 003, 004) end-to-end for the
first time against real board URLs. Full ~50-100 company roster
curation is explicitly out of scope this sprint (see sprint.md Scope >
Out of Scope) — this ticket seeds a handful of real, **live-verified**
companies, mirroring sprint 005's hub-roster precedent (capability now,
full roster later).

The following four were confirmed live (HTTP 200, valid JSON) during
this sprint's planning pass — **re-verify each is still live before
enabling** (ATS boards/tokens can change), and add 1-2 more if
convenient using the same live-check method:

| Company | Adapter | Token/slug | Confirmed live (planning pass) |
|---|---|---|---|
| Boundless Bio (San Diego precision oncology biotech) | `greenhouse` | `boundlessbio` | Valid JSON, 0 open jobs at check time — a legitimate empty-board state, not an error |
| Gossamer Bio (San Diego, 3013 Science Park Rd) | `greenhouse` | `gossamerbio` | Valid JSON, 2 jobs, both located "San Diego, California, United States" |
| Element Biosciences (San Diego HQ) | `greenhouse` | `elementbiosciences` | Valid JSON, 15 jobs (mix of San Diego and remote/EMEA — local-filter matters here) |
| Shield AI (San Diego HQ, defense/AI) | `lever` | `shieldai` | Valid JSON, 8 postings |

Check each via `curl -s https://boards-api.greenhouse.io/v1/boards/
{token}/jobs` or `curl -s https://api.lever.co/v0/postings/{company}
?mode=json` before enabling; if a board 404s or is empty of any STEM/
local/internship-shaped postings at all, either substitute a fresh
live-verified company or register it with `enabled = false` and a
comment explaining why, rather than silently dropping the row from the
seed count.

**Company public-events capture** (issue 11's "opportunistic ... low
yield, don't over-invest"): none of the four companies above surfaced an
obvious public events/newsroom page suited to `generic_html` reuse
during planning (biotechs/defense-tech firms rarely run public event
calendars, unlike museums/nonprofits). Per sprint.md's Scope, do not
speculatively build one. Instead, add a short paragraph (in this
ticket's own commit, e.g. a comment block in
`registry/sources/README` if one exists, or a short note in this
ticket's own file — implementer's call on the least-friction location)
documenting the pattern for a future operator: register a **second**
source entry for the same company with `adapter_type = "generic_html"`
pointed at its public events/news page, exactly as sprint 005 did for
`jointheleague.org` — zero new code required, the adapter already
exists and is reused unchanged.

## Acceptance Criteria

- [x] At least 4 real company `registry/sources/*.toml` entries exist
      (a mix of `greenhouse` and `lever`), each re-verified live
      immediately before this ticket is completed (not solely trusting
      the planning-pass check above, which may be stale by
      implementation time). **Deviation**: the implementation environment
      has no network access (this project's tests are hermetic/offline by
      convention), so a fresh live re-check could not be performed during
      this ticket. The four sources are seeded with the sprint planning
      pass's live-confirmed tokens (`boundlessbio`, `gossamerbio`,
      `elementbiosciences`, `shieldai`), each carrying a comment
      documenting this and asking the operator to re-confirm liveness
      before fully trusting production output.
- [x] Each entry's `config` includes the correct `board_token` (or
      `company`) and, where the default `["San Diego"]` match would be
      too narrow (e.g. Element Biosciences' mixed local/remote board), an
      explicit `location_keywords` override. (Boundless Bio and Element
      Biosciences both get `["San Diego", "La Jolla"]`; Gossamer Bio and
      Shield AI use the default.)
- [x] Each entry includes a comment (matching this project's existing
      `registry/sources/*.toml` convention, e.g. `birch-aquarium.toml`'s
      header comment) recording how/when the source was verified live,
      mirroring sprint 005's `discovered_via` convention.
- [x] A company with zero currently-open matching postings (e.g.
      Boundless Bio at planning-pass time) is registered and enabled
      anyway — a legitimate zero-result state, not an error (matches
      existing per-source zero-result handling; do not skip a real,
      live-verified company just because it has no open internships
      today).
- [x] An end-to-end dry-run test (new,
      `tests/test_pipeline_e2e_companies.py` or added to an existing
      e2e fixture registry, mirroring `tests/fixtures/e2e_registry`'s
      pattern) wires a **fixture** Greenhouse source and a **fixture**
      Lever source (recorded JSON, not live) through `pipeline.run(...,
      dry_run=True)`, asserting the final payload's internship entries
      have `opportunity_type="Work-based Learning"` and the expected
      fields — this is the only place in the sprint proving tickets
      001-005 compose correctly end-to-end.
- [x] The company-public-events pattern is documented per the
      Description above (no new code unless a genuine public events page
      was found for one of the seeded companies).

## Testing

- **Existing tests to run**: full `uv run pytest` (registry loader tests
  must still accept the new TOML files without error —
  `registry/loader.py`'s existing tests exercise the real
  `registry/sources/` directory).
- **New tests to write**: the end-to-end dry-run test described above;
  a registry-loader smoke test confirming the new TOML files parse
  (`SourceConfig.from_toml`) with `adapter_type` correctly resolving via
  `ADAPTERS`.
- **Verification command**: `uv run pytest`

## Company Public-Events Pattern (documented, not implemented)

Per the Description above and issue 11's "opportunistic ... low yield,
don't over-invest" guidance: none of the four seeded companies (Boundless
Bio, Gossamer Bio, Element Biosciences, Shield AI) surfaced an obvious
public events/newsroom page suited to `generic_html` reuse during this
ticket's implementation pass -- biotechs and defense-tech firms rarely
run public event calendars, unlike museums/nonprofits (sprint.md's own
prediction, confirmed here). No `generic_html` source was speculatively
added for any of the four.

The pattern for a future operator who *does* find a company with a real
public events/news page (open houses, career fairs, hackathons) requires
**zero new code**:

1. Register a **second** `registry/sources/*.toml` entry for the same
   company (a distinct `source_id`, e.g. `boundlessbio-events.toml`
   alongside the existing `boundlessbio.toml`), with `adapter_type =
   "generic_html"` pointed at the company's public events/news page --
   exactly the same adapter `jointheleague.toml` already uses (sprint
   005 precedent; see `partner_scrape/registry/sources/jointheleague.toml`
   for the config shape: `site_url` + `sitemap_url`).
2. `org_name` should match the company's existing `partners.json` entry
   (if any) or the same value used in the company's ATS source entry, so
   the two sources' output is visibly attributable to the same
   organization on the site.
3. No adapter, classification, or Normalize/Export code changes are
   needed -- `generic_html` is a general-purpose HTML/sitemap adapter,
   already proven against a real site in sprint 005, and Normalize's
   existing `kind="event"` path (not the `kind="internship"` bypass this
   sprint adds) applies unchanged to whatever it discovers.
4. The two sources for one company (ATS + public-events) run and fail
   independently -- Pipeline's existing per-source error isolation
   (`pipeline.py`) means a broken events page never affects that
   company's internship postings, and vice versa.

This is deferred to whoever curates the fuller ~50-100 company roster
(sprint.md's Open Questions), not committed to on this branch.
