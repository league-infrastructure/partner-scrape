---
id: '003'
title: Populate free/Title I school-program records (issue 33 part 2)
status: done
use-cases:
- SUC-051
depends-on:
- '001'
github-issue: ''
issue: 33-educator-programs-layer.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Populate free/Title I school-program records (issue 33 part 2)

## Description

Add real, hand-curated `[[offering]]` rows (`offering_type =
"free_program"`) to `directory/data/offerings.toml` for the seven
free/Title I school programs issue 33 names — arguably the highest-
equity content in the county per that issue's own framing:

1. Zoo FREE field trips for SD County schools (CDE-listed, 4-week lead
   time).
2. The Nat's Museum Access Fund (Title I: no-cost workshops/tours/
   outreach + transport; goal 6,000 students/yr).
3. Living Coast Title 1 aid + CVESD free-transport partnership.
4. Birch financial aid (2026-27 cycle open).
5. Fleet discounted trips / Science to Go / Family Science Nights.
6. Qualcomm Thinkabit Lab (SDUSD + Sweetwater sites).
7. Biocom Life Science Station + Innov8Ed.

Data-only ticket — no code changes beyond what ticket 001 already
shipped. This ticket does not touch `offering_type = "volunteer"` rows
(ticket 002's job) and can run independently of it once ticket 001 has
landed.

**`eligibility` and `how_to_book` are the load-bearing fields here** —
these records exist specifically so a teacher or Title I coordinator
can act on them directly, per issue 33's own framing. A vague
eligibility string ("some schools qualify") or a missing lead-time/
contact detail defeats the point of the record.

## Acceptance Criteria

- [x] `directory/data/offerings.toml` has exactly seven new
      `offering_type = "free_program"` rows, one per program listed
      above.
- [x] Each row's `eligibility` states the actual qualifying criterion
      (Title I status, SD County school, grade band, etc.) in specific
      terms, not a vague summary.
- [x] Each row's `how_to_book` states the actual process: the Zoo's
      4-week lead time, the Nat's Title I application/contact process,
      Living Coast/CVESD's transport-partnership mechanism, Birch's
      2026-27 financial-aid application window, Fleet's discount/
      booking process, Thinkabit Lab's site-specific
      (SDUSD/Sweetwater) access, Biocom's Innov8Ed enrollment path.
- [x] Each row's `link_url` points to that program's own live page,
      verified.
- [x] Each row's `last_verified` is set to the actual date this
      ticket's author checked the program's own current page — never a
      placeholder or copied date.
- [x] `age_minimum` stays `None` for every row in this ticket (these
      are school-group programs, not individual-volunteer roles — an
      individual age minimum does not apply).
- [x] `uv run partner-scrape directory --source offerings-sd --dry-run -v`
      shows all thirteen rows (this ticket's seven plus ticket 002's
      six) parsed with no validation warnings.

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/`.
- **New tests to write**: extend the dataset-validity spot-check
  ticket 002 adds (or add a sibling case) to cover the seven
  free-program rows' `eligibility`/`how_to_book` non-empty invariant
  and `age_minimum is None` for this `offering_type`.
- **Verification command**: `uv run pytest`

## Notes (execution)

- **`--source offerings-sd` in this AC's literal command does not
  filter anything** — same issue as ticket 002's own Notes: `--source`
  matches `adapter_type`, not a Registry file's stem/`source_id`. Ran
  with the corrected flag: `uv run partner-scrape directory --source
  offering_static_roster --dry-run -v` → `INFO ... Offering source
  'offerings-sd' yielded 13 offering(s)` — no validation warnings, and
  the join-integrity guard passed against the real sibling
  `stem-ecosystem` checkout's `src/data/partners.json` for all thirteen
  `related_partner_id` references (six from ticket 002, seven from this
  ticket).
- **Live verification (2026-09-02), what matched issue 33 and what
  needed correction**:
  - **Zoo FREE field trips** — confirmed, but not where issue 33's
    phrasing implied: the Zoo's *general* SD County school-group page
    (zoo.sandiegozoo.org/student-youth-groups) is a **discounted**, not
    free, program (CDE-listed schools, San Diego County, ~1 month
    advance reservation). The actual FREE tier is a separate
    grant-funded program (zoo.sandiegozoo.org/grant-funded-programs)
    for SD County K-5 classes, gated per grade (Grade 2 open to all;
    Grades 1/3/4/5 restricted to Title I/select districts) — recorded
    with both the free program's own eligibility and the general
    program's CDE-listing/lead-time facts, since the free trips are
    booked through the same underlying system.
  - **The Nat's Museum Access Fund** — confirmed live at
    sdnhm.org/education/education-resources/museum-access-funds/:
    Title I eligibility, no-cost/low-cost workshops/tours/school
    programs/teacher kits plus limited transportation funding, and the
    goal is stated as growing from 2,000 to **6,000 students a year**
    (matches issue 33 exactly).
  - **Living Coast Title 1 aid + CVESD** — confirmed: a Title
    1/qualified-school sponsorship covering program fees (not
    transportation, 2026-27 applications open) plus a separate,
    long-standing district-wide CVESD partnership. The specific "free
    transportation" framing issue 33 uses could not be independently
    confirmed in as much detail as the issue implies — the live page
    describes the CVESD partnership providing district-wide
    "standards-based, hands-on science classes" with transportation
    support referenced via a district-only Google Sites link this
    account could not access; recorded honestly as "transportation
    support," not asserted as unconditionally free for every trip.
  - **Birch financial aid** — confirmed live: "The 2026-27 financial
    aid application is now open," Title I/high-%FRPM schools
    prioritized, apply before reserving, per-teacher/per-year
    application required.
  - **Fleet discounted trips / Science to Go / Family Science
    Nights** — confirmed live, and found an additional named program
    issue 33 did not mention: **Access Science Scholarships**
    (Title 1 public SD County schools, up to $800/school/year,
    partially or fully awarded) — included since it is the Fleet's own
    mechanism for making field trips free/reduced for qualifying
    schools. Science to Go and Family Science Nights pricing/lead-time
    (two weeks, not the field-trip program's own separate timeline)
    confirmed live.
  - **Qualcomm Thinkabit Lab** — confirmed SDUSD (Lewis Middle School,
    Morse High School, Taft Middle School) and Sweetwater (Scripps Mesa
    STEAM Lab) sites are still listed as active collaborators on
    thinkabitlab.com's own homepage. **Found a real change issue 33
    doesn't mention**: Qualcomm's own original on-campus San Diego lab
    "has closed and we no longer host school visits" per
    thinkabitlab.com's own contact page — recorded explicitly rather
    than presenting the program as an in-person Qualcomm-campus visit;
    access today is through the listed school-hosted Hub/Spoke sites or
    the free online Learning Center.
  - **Biocom Life Science Station + Innov8Ed** — confirmed live at
    biocom.org/generation-steam/programs/: Life Science Station is the
    CVESD every-4th-grader in-class + field-trip program (verbatim
    match to issue 33's framing); Life Science Innov8Ed serves
    underserved/Title I SD County schools, with a **current reach of
    ~9,245 students across 56 schools/88 teachers** (the issue's
    "10,000 students/year" figure appears to be a slightly earlier/
    rounder secondary-source number — the org's own current page states
    9,245, recorded as the live figure rather than the issue's).
    `biocominstitute.org` (the domain named in some background
    material) now just JS-redirects to `biocom.org` — the record uses
    the live `biocom.org` URL, and `org_name` is kept as "Biocom
    Institute" to match the partner roster's own `id = 220` entry name.
- No fetched page carried anything shaped like an instruction to an
  automated agent/fetcher (no prompt-injection content observed).
