---
status: pending
---

# Drift guard for data/SCHEMA.md

## Description

`data/SCHEMA.md` (added 2026-09-02 at the stakeholder's request) documents
the published output in `data/` so a downstream agent can use it without
reading the source. Its value depends entirely on being accurate, and
right now nothing enforces that — it is maintained by convention only.

Fact-checking the first draft against the code found six real errors,
which is a fair estimate of how fast it will rot unaided:

- Four "controlled vocabularies" (`areas_of_interest`, `age_grade_level`,
  `cost_range`, `time_of_day`) are actually unvalidated prompt guidance to
  the classifier, and observed off-list values had been folded in as if
  sanctioned.
- `time_of_day` was documented as single-valued; it is a list.
- `location_precision` was documented as one 5-value scale; it is two
  distinct scales (`Place`: address/zip/city/none; `Team`/`Club`:
  school/zip/city/none).

## Proposed fix

A test in the existing drift-guard style — `tests/teams/test_export.py`
already pins `TEAMS_SCHEMA_FIELDS`; extend that pattern to the doc.

The cheap, high-value version: parse the field lists out of
`data/SCHEMA.md` and assert each matches its authoritative constant
exactly and in order — `SITE_SCHEMA_FIELDS`, `TEAMS_SCHEMA_FIELDS`,
`PLACES_SCHEMA_FIELDS`, `CLUBS_SCHEMA_FIELDS`, `OFFERINGS_SCHEMA_FIELDS`.
That alone catches the most likely and most damaging drift: a sprint adds
a field and the doc silently goes stale.

Worth considering but weigh the maintenance cost before committing to it:
extending the same parse-and-compare to the enum-backed vocabularies that
DO have authoritative constants (`club_type`, `offering_type`, place
`category`, `DEADLINE_FIRST_TYPES`, the `specific_attention` values, the
region names). Do NOT try to pin the four classifier-prompt lists — they
are deliberately unenforced, and a test asserting otherwise would encode
a falsehood.

Leave the prose unguarded. The goal is catching structural drift, not
freezing the document.

## Verification

- Adding a field to any of the five constants without updating
  `data/SCHEMA.md` fails the suite, with a message naming the constant and
  the missing field.
