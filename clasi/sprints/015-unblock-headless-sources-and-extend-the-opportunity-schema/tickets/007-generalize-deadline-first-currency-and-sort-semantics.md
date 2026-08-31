---
id: '007'
title: Generalize deadline-first currency and sort semantics
status: in-progress
use-cases:
- SUC-008
depends-on:
- '006'
github-issue: ''
issue: 27-taxonomy-camps-competitions-deadlines-eligibility.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Generalize deadline-first currency and sort semantics

## Description

Internships and competition registrations are "apply by" items, not
"attend on" items: `date_start` may be in the past (an internship's
posting-observed date) while the record should keep shipping through
its `date_end` (the actual deadline). `export/writer.py`'s
`is_current_or_upcoming()` already special-cases this for
`opportunity_type == "Work-based Learning"` (the one hardcoded
internship type). Generalize the mechanism — reusing the existing
`end`-as-deadline convention, not a new field — to also cover
`Competitions` (ticket 006), and fix the export sort key, which today
always sorts by `date_start` even for a deadline-first record.

Depends on ticket 006 because it needs the `"Competitions"` string
this ticket references to already exist in the controlled vocabulary.

## Fix shape

In `normalize/run.py`, add:

```python
DEADLINE_FIRST_TYPES = frozenset({WORK_BASED_LEARNING_TYPE, "Competitions"})
```

Generalize the two places that currently hardcode
`opportunity_type == WORK_BASED_LEARNING_TYPE` (or `is_internship`) to
check `opportunity_type in DEADLINE_FIRST_TYPES` instead:

1. **`export/writer.py`'s `is_current_or_upcoming()`**: the branch
   that treats an unset/future `date_end` as current, and an expired
   `date_end` as not current, applies to any `DEADLINE_FIRST_TYPES`
   member, not only `Work-based Learning`. Import
   `DEADLINE_FIRST_TYPES` alongside the existing
   `WORK_BASED_LEARNING_TYPE` import.
2. **`export/writer.py`'s `export_opportunities()` sort key**: today
   `current.sort(key=lambda o: o.date_start)` unconditionally. Change
   the key to use `date_end` for a `DEADLINE_FIRST_TYPES` record and
   `date_start` otherwise, so a winter-dated posting with a
   spring/summer deadline sorts near other near-term deadlines rather
   than by its stale `date_start` — the concrete "Dec-Mar deadlines
   for Jun-Aug programs in winter" scenario this issue names.
3. **`normalize/run.py`'s availability text derivation**: the existing
   `_internship_availability()` ("Apply by <date>" / "Rolling — apply
   anytime") is reused for any `DEADLINE_FIRST_TYPES` record, not only
   `is_internship` records — generalize the branch in `_to_opportunity()`
   that currently checks `is_internship` to also check
   `opportunity_type in DEADLINE_FIRST_TYPES` for availability-text
   purposes (internship/`kind` bypass logic elsewhere — collapse,
   dedup, forced type — is unaffected; only the availability-text
   derivation generalizes).

No change is needed to the site's display layer: `[slug].astro`
already renders `opportunity.availability` as a generic, unconditional
text field whenever non-empty — "Apply by …" is already automatic
once the value is set correctly.

## Acceptance Criteria

- [ ] `DEADLINE_FIRST_TYPES` is defined once in `normalize/run.py` and
      imported (not re-declared) wherever `export/writer.py` needs it.
- [ ] A fixture `Competitions`-typed, non-internship record with a
      future `date_end` and a past `date_start` is exported by
      `is_current_or_upcoming()`.
- [ ] The same record with a past `date_end` is excluded.
- [ ] A fixture `Competitions`-typed record's `availability` reads
      "Apply by <date>" (or "Rolling — apply anytime" if `date_end`
      unset), matching the existing `Work-based Learning` behavior
      exactly.
- [ ] A sort-order fixture test in `export/writer.py`'s test module
      proves a deadline-first record sorts by `date_end`, and a
      non-deadline-first record still sorts by `date_start` as today.
- [ ] Every existing `Work-based Learning`/internship fixture test
      continues to pass unmodified — this is a pure generalization,
      not a behavior change for the existing case.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite (`uv run pytest`), especially
  `export/writer.py`'s and `normalize/run.py`'s existing
  `is_current_or_upcoming`/availability/sort tests.
- **New tests to write**: per Acceptance Criteria above, extending
  the existing single-case (`Work-based Learning`) tests to a second,
  parallel `Competitions` case rather than replacing them.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Small, mechanical generalization of an existing,
already-tested special case to a set-membership check, in the same two
files that already implement it.

**Files to modify**:
- `partner_scrape/normalize/run.py` — `DEADLINE_FIRST_TYPES`,
  availability-derivation generalization.
- `partner_scrape/export/writer.py` — `is_current_or_upcoming()`,
  sort key.
- Corresponding test files for both.

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/normalize/DESIGN.md` and
`partner_scrape/export/DESIGN.md` each get a short sprint-015 addendum
describing the generalization and explicitly noting the rejected
alternative (a new `application_deadline` field) and why — no adapter
or the LLM prompt currently distinguishes a registration deadline from
an event's own end date/time for any non-internship record, so a new
field would have no real producer yet; reusing `end` is not
speculative, it extends an already-shipped convention to one more
already-shipped type value.
