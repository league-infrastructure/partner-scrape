---
id: '003'
title: Populate free/Title I school-program records (issue 33 part 2)
status: open
use-cases: [SUC-051]
depends-on: ['001']
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

- [ ] `directory/data/offerings.toml` has exactly seven new
      `offering_type = "free_program"` rows, one per program listed
      above.
- [ ] Each row's `eligibility` states the actual qualifying criterion
      (Title I status, SD County school, grade band, etc.) in specific
      terms, not a vague summary.
- [ ] Each row's `how_to_book` states the actual process: the Zoo's
      4-week lead time, the Nat's Title I application/contact process,
      Living Coast/CVESD's transport-partnership mechanism, Birch's
      2026-27 financial-aid application window, Fleet's discount/
      booking process, Thinkabit Lab's site-specific
      (SDUSD/Sweetwater) access, Biocom's Innov8Ed enrollment path.
- [ ] Each row's `link_url` points to that program's own live page,
      verified.
- [ ] Each row's `last_verified` is set to the actual date this
      ticket's author checked the program's own current page — never a
      placeholder or copied date.
- [ ] `age_minimum` stays `None` for every row in this ticket (these
      are school-group programs, not individual-volunteer roles — an
      individual age minimum does not apply).
- [ ] `uv run partner-scrape directory --source offerings-sd --dry-run -v`
      shows all thirteen rows (this ticket's seven plus ticket 002's
      six) parsed with no validation warnings.

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/`.
- **New tests to write**: extend the dataset-validity spot-check
  ticket 002 adds (or add a sibling case) to cover the seven
  free-program rows' `eligibility`/`how_to_book` non-empty invariant
  and `age_minimum is None` for this `offering_type`.
- **Verification command**: `uv run pytest`
