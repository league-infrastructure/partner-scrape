---
id: '001'
title: Write the do-not-scrape / excluded-source reference
status: in-progress
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: 36-hub-registry-discovery-only.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Write the do-not-scrape / excluded-source reference

## Description

Issue 36 asks for a checked-in "do-not-scrape list" so future sessions
don't re-litigate ToS/robots findings this project has already settled.
Sprint 024's planning (see `sprint.md`'s Architecture > Design
Rationale) decided where this lives: `partner_scrape/registry/DO_NOT_SCRAPE.md`,
colocated with `registry/DESIGN.md`, `hubs/`, `sources/`, and
`candidates/` — the same directory a future session would already be
looking at before adding a new hub or source. No schema/loader pair is
needed; nothing in the pipeline consumes this file programmatically
(the registry is opt-in-by-construction — see `sprint.md`'s "Why"
subsection for the full reasoning).

This ticket has three distinct groups of content, each with a different
provenance — do not blur them together:

1. **Issue 36's original pre-vetted do-not-scrape list** (10 entries):
   Eventbrite, Idealist/VolunteerMatch, ActivityHero, Tinybeans, SDCOE
   OMS (k12oms.org), Patch, SanDiego.org/CONNECT/StartupSD, ActiveNet
   apm REST, JustServe/HandsOn San Diego/Points of Light, and Meetup
   per-group iCal. Pull the exact reason stated for each directly from
   `clasi/issues/36-hub-registry-discovery-only.md`'s "Do-NOT-scrape
   list" section — do not paraphrase away the specific clause/directive
   named there (ToS §13, robots `Disallow: /`, bot-wall, etc.).
2. **Four candidates sprint 024's own live re-verification newly found
   ToS-blocked**, excluded from this sprint's hub registration
   specifically because of it: KidsOutAndAbout San Diego,
   sandiegostemsummercamps.com, sandiegomoms.com, and San Diego Reader.
   Pull the exact ToS clause and verification date (2026-08-31) for
   each from `sprint.md`'s Architecture > Design Rationale, first
   decision entry ("exclude KidsOutAndAbout,
   sandiegostemsummercamps.com, sandiegomoms.com, and San Diego Reader
   ...") — quote the clause verbatim, the same way the issue's own
   entries quote a ToS section or robots directive.
3. **Two deferred (not excluded, not registered) entries** with their
   own distinct reasons: KPBS's community calendar (both `kpbs.org/arts`
   and `kpbs.org/events/all` — legal and robots-clean, but
   `discovery/hub_scan.py`'s single-hop mechanism can't reach the
   outbound organization links, which live one hop deeper on individual
   event pages) and Macaroni Kid (already flagged optional/low-yield in
   issue 36; its `/terms-conditions` route did not resolve reliably
   under direct fetch, so ToS could not be verified this sprint). Pull
   these from `sprint.md`'s Design Rationale second decision entry and
   Open Question 3. Keep this group visually distinct from group 2 in
   the doc (e.g. a separate `## Deferred` heading) — these are not
   "banned," they're "not yet resolved," and conflating the two
   defeats the point of writing any of this down precisely.

Also add exactly one cross-reference line in `partner_scrape/registry/DESIGN.md`
(its Orientation section, §2, is the natural spot, next to the
four-catalog table) pointing at the new file, so someone reading the
subsystem doc discovers it. Do not add a fifth row to the §2 catalog
table itself — that table documents *loaded* catalogs
(`sources/`/`hubs/`/`ads/`/`candidates/`), and `DO_NOT_SCRAPE.md` is
documentation, not a loaded catalog (see `sprint.md`'s Architecture >
Impact on Existing Components for why that distinction matters).

## Acceptance Criteria

- [x] `partner_scrape/registry/DO_NOT_SCRAPE.md` exists and is checked in.
- [x] It contains all 10 entries from issue 36's original do-not-scrape
      list, each with the specific reason the issue names (ToS clause,
      robots directive, bot-wall, etc.) — not a generic restatement.
- [x] It contains the 4 newly-excluded entries (KidsOutAndAbout,
      sandiegostemsummercamps.com, sandiegomoms.com, San Diego Reader),
      each with the exact ToS clause quoted from `sprint.md`'s Design
      Rationale and dated 2026-08-31.
- [x] It contains a clearly separate `## Deferred` section for KPBS's
      community calendar and Macaroni Kid, each explaining why it's
      deferred rather than excluded (mechanism mismatch vs.
      unverifiable ToS), so a future session knows these are open, not
      closed, questions.
- [x] Every entry states what it's about (one line), the reason, and a
      date — matching the "Live-verified `<date>`" phrasing convention
      already used in `registry/sources/balboa-park.toml` and
      `registry/sources/usasciencefestival.toml`'s header comments.
- [x] `partner_scrape/registry/DESIGN.md` gains exactly one new
      cross-reference line to `DO_NOT_SCRAPE.md` in its §2 Orientation
      section; its four-catalog table is otherwise untouched.
- [x] No code file is touched by this ticket.

## Implementation Plan

**Approach**: Pure documentation ticket. Read `clasi/issues/36-hub-registry-discovery-only.md`
and this sprint's `sprint.md` (Architecture > Design Rationale, Open
Questions) as the two source-of-truth inputs; do not re-derive or
re-verify ToS/robots findings — they're already established by this
sprint's planning. Write `DO_NOT_SCRAPE.md` with three headed sections
matching the Description's three groups above (e.g. `## Do Not Scrape`,
with the two provenance groups distinguishable by a short note per
entry — "per issue 36" vs. "found during sprint 024 planning,
2026-08-31" — plus `## Deferred`).

**Files to create**:
- `partner_scrape/registry/DO_NOT_SCRAPE.md`

**Files to modify**:
- `partner_scrape/registry/DESIGN.md` (one cross-reference line only)

**Testing plan**: No code changes, so no unit test is added or
modified. Run `uv run pytest` to confirm the full suite still passes
(expected to be a no-op given nothing executable changed — this is a
regression check, not new coverage). Manually verify the new markdown
file renders correctly and that every URL cited either resolves or is
explicitly marked dead (`thefinestsd.com`, per this sprint's own
finding, does not resolve — say so in the KPBS deferred entry rather
than linking it as if live).

**Documentation updates**: This ticket *is* the documentation update;
no further doc changes beyond the one `DESIGN.md` cross-reference
described above.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — regression
  check only; no code path in this ticket is exercised by any test).
- **New tests to write**: None — this ticket adds no code.
- **Verification command**: `uv run pytest`
