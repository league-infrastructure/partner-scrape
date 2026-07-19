---
id: '002'
title: ATS internship/STEM/San Diego classification module
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: 11-company-events-and-internships.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# ATS internship/STEM/San Diego classification module

## Description

New shared module `partner_scrape/adapters/ats_filters.py`: pure
functions deciding whether one raw ATS posting (title, department/
commitment text, location text) is an in-scope internship, used by both
the Greenhouse adapter (ticket 003) and the Lever adapter (ticket 004)
so the heuristics live in exactly one place. No fetching, no JSON
parsing, no `Event` construction here — that stays in each adapter (see
sprint.md's Architecture > Step 3 module table, "ATS Filters" row).

Reuses `normalize/taxonomy.py`'s `tag_by_keywords()` helper (pure,
already general-purpose) but supplies a **new, job-title-oriented STEM
keyword list**, not `taxonomy.AREA_KEYWORDS` — that list is tuned for
K-12 event/program titles ("marine|ocean|aquarium...") and does not
reliably match company job titles like "Bioinformatics Intern" or "Data
Science Intern" (confirmed gap during architecture planning: neither
"biology" nor "data science" appears in `AREA_KEYWORDS` at all).

## Acceptance Criteria

- [x] `is_internship_posting(title: str, commitment: str = "") -> bool`:
      matches "Software Engineering Intern", "Biology Research Intern",
      "Data Science Co-op", "Marketing Apprenticeship"; does not match
      "Senior Software Engineer", "VP of Sales", "International Sales
      Manager" (word-boundary safe — must not false-positive on
      "international"/"internal").
- [x] `is_stem_posting(title: str, department: str = "") -> bool`: a
      job-title-oriented STEM keyword set (engineering, software, data,
      biology/biomedical/bioinformatics/genomics, chemistry, physics,
      hardware/firmware, robotics/ML/AI, mechanical/electrical/aerospace,
      manufacturing/lab/R&D, semiconductor/wireless — broader than
      `taxonomy.AREA_KEYWORDS`); matches "Bioinformatics Intern", "Data
      Science Intern", "Hardware Engineering Intern"; does not match
      "Marketing Intern", "HR Coordinator Intern".
- [x] `is_local_posting(location: str, keywords: list[str] | None =
      None) -> bool`: defaults to `["San Diego"]`; "San Diego, CA"
      matches, "Remote" and "Austin, TX" do not; an explicit
      `keywords=["La Jolla", "San Diego"]` override changes the match set
      with no code change (mirrors `SourceConfig.config`'s existing
      per-source-tunable pattern, e.g. `localist.py`'s `days`/`pp`).
- [x] A single `classify_posting(title, commitment, department, location,
      location_keywords=None) -> PostingVerdict | None` (or equivalent)
      combining the three checks (AND across all three) plus default
      classification values for a match: `age_grade_level = ["Grades
      9-12", "Undergraduate"]` (add `"Graduate"` when the title contains
      a PhD/graduate-level keyword), `time_of_day = ["All Day"]`. Returns
      `None` (or equivalent "no match") when any check fails.
- [x] Does **not** produce a `cost_range` value — the caller (adapters,
      tickets 003/004) must not set `Event.cost`/`Event.cost_range` from
      this module's output (see sprint.md's Architecture self-review
      note on the misleading-"Free"-badge risk).
- [x] Every function is a pure function over plain strings — no `Event`,
      no `Fetcher`, no I/O — independently unit-testable without either
      adapter.

## Testing

- **Existing tests to run**: `test_normalize_taxonomy.py` (proves no
  regression to the reused `tag_by_keywords` helper), full
  `uv run pytest`.
- **New tests to write**: `tests/test_adapters_ats_filters.py` — table-
  driven unit tests for each of the acceptance criteria above, including
  the word-boundary-safety case ("international" must not match
  internship) and the `location_keywords` override case.
- **Verification command**: `uv run pytest`
