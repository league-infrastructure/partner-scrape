---
id: '001'
title: Generalize the curated-program-kind bypass mechanism
status: done
use-cases:
- SUC-033
- SUC-034
depends-on: []
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Generalize the curated-program-kind bypass mechanism

## Description

This is the foundational, no-new-adapter ticket: it generalizes the
existing `kind="internship"` bypass mechanism (relevance-gate/LLM skip
in `enrich/enricher.py`; collapse/dedup skip in `normalize/run.py`) to
also cover a new `kind="program"` value, and extends the deadline-first
availability/currency mechanism (sprint 015 ticket 007) to handle a
not-yet-open application window and one new `opportunity_type` member.
No new adapter is built here — this ticket makes the rest of the
pipeline ready to receive `kind="program"`/`"internship"` Events from
the program-page extraction adapters tickets 003/004 will add, and is
independently testable via hand-built fixture `Event`s.

See `clasi/sprints/027-.../design/DESIGN.md`, `enrich-DESIGN.md`, and
`normalize-DESIGN.md` (this sprint's design overlay) for the full
rationale — this ticket implements exactly what those documents
describe as "Sprint 027" additions.

## Fix shape

1. **`partner_scrape/model.py`**:
   - Add `PROGRAM_EXTRACTION_KINDS = frozenset({"internship", "program"})`
     — the shared constant naming which `Kind` values get curated-record
     bypass treatment. Export it (module-level, no `__all__` gate needed
     if this module doesn't use one; otherwise add it).
   - Add `eligibility: str = ""` to the `Event` dataclass (a defaulted
     field, placed among the other defaulted content fields).
2. **`partner_scrape/enrich/enricher.py`**: change the pass-1 bypass
   check from `if event.kind == "internship":` to `if event.kind in
   PROGRAM_EXTRACTION_KINDS:` (import from `model.py`). No other change
   to this module — the bypass behavior (no cache lookup, no LLM call,
   no field mutation) is otherwise identical.
3. **`partner_scrape/normalize/run.py`**:
   - Change the internship/other split (`(internship_events if
     event.kind == "internship" else other_events).append(event)`) to
     check `event.kind in PROGRAM_EXTRACTION_KINDS` instead, and rename
     the local variables to reflect the broader set (e.g.
     `curated_events`/`other_events`) — purely a rename, the routing
     behavior generalizes identically to both kinds.
   - Add `"Funding Opportunities"` to `DEADLINE_FIRST_TYPES`.
   - In `_to_opportunity()`, resolve `eligibility` with the same
     field_provenance-presence precedence pattern already used for
     `areas_of_interest`/`age_grade_level`/`cost_range`/`time_of_day`/
     `opportunity_type`: prefer `event.eligibility` when `"eligibility"
     in event.field_provenance`, else fall back to
     `taxonomy_defaults.get("eligibility", "")` exactly as today.
   - Thread `today` into `_to_opportunity()` (new parameter, passed from
     `run()`'s existing resolved `today` value) and use it in
     `_internship_availability()` (or a renamed equivalent — keep the
     existing name if a rename isn't warranted) to add a new first-
     checked branch: if `event.start` is set and `event.start.date() >
     today`, return `f"Opens ~{event.start.date().isoformat()}"`; else
     fall through to the existing "Apply by <date>" / "Rolling — apply
     anytime" logic unchanged.
   - Generalize the availability-derivation trigger condition from
     `is_internship or opportunity_type in DEADLINE_FIRST_TYPES` to
     `event.kind in PROGRAM_EXTRACTION_KINDS or opportunity_type in
     DEADLINE_FIRST_TYPES` — the forced-`opportunity_type`-to-
     `WORK_BASED_LEARNING_TYPE` branch stays `kind == "internship"`-only,
     unchanged; only the availability-text trigger widens.

## Acceptance Criteria

- [x] `model.PROGRAM_EXTRACTION_KINDS == frozenset({"internship",
      "program"})`; `Event.eligibility` defaults to `""`.
- [x] A fixture `kind="program"` `Event` passed through
      `LLMEnricher.enrich()` results in zero `LLMClient` calls and zero
      field mutation (mirrors the existing `kind="internship"` bypass
      test).
- [x] Every existing `kind="internship"` fixture test in
      `tests/test_enrich_enricher.py` continues to pass unmodified.
- [x] A fixture pair of same-title, same-date `kind="program"` `Event`s
      from different sources both survive `normalize.run()` as separate
      `Opportunity` records (no cross-source collapse or dedup).
- [x] A fixture `kind="program"` `Event` with `eligibility` set via
      `Event.set("eligibility", ..., source=..., confidence=...)`
      produces an `Opportunity.eligibility` equal to that value, even
      when `source_taxonomy_defaults` also sets a (different) value for
      that source — the Event-level value wins.
- [x] A fixture `Event` with no `eligibility` field_provenance entry
      still resolves `Opportunity.eligibility` from
      `source_taxonomy_defaults` exactly as before this ticket (no
      regression for the sprint-015 mechanism).
- [x] A fixture `Funding Opportunities`-typed `Opportunity` with a
      future `date_end` is kept current by
      `export.writer.is_current_or_upcoming()`; the same record with a
      past `date_end` is excluded — proves the `DEADLINE_FIRST_TYPES`
      extension reaches `export/writer.py` with no code change there.
- [x] A fixture `kind="program"` (or `"internship"`) `Event` with
      `start` in the future and no/future `end` produces
      `Opportunity.availability == "Opens ~<date>"`.
- [x] A fixture `kind="program"`/`"internship"` `Event` with `start` in
      the past and `end` in the future still produces `"Apply by
      <date>"`, unchanged.
- [x] Every existing `Work-based Learning`/`Competitions`
      availability/currency/sort fixture test continues to pass
      unmodified — this ticket is a pure generalization, not a behavior
      change for any existing case.
- [x] Full test suite stays green (`uv run pytest`).

## Testing

- **Existing tests to run**: full suite, especially
  `tests/test_model.py`, `tests/test_enrich_enricher.py`,
  `tests/test_normalize_run.py`, `tests/test_export_writer.py`.
- **New tests to write**: per Acceptance Criteria above — extend the
  existing single-case (`kind="internship"`/`Work-based Learning`)
  tests with parallel `kind="program"`/`Funding Opportunities` cases
  rather than replacing them, matching sprint 015 ticket 007's own
  precedent for this exact kind of generalization.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Data-model and mechanism generalization only, no new
module. Land `model.py`'s two additions first (nothing else compiles
against them yet), then `enrich/enricher.py`'s one-line bypass
generalization, then `normalize/run.py`'s three changes together (they
touch the same functions and should land as one coherent diff).

**Files to modify**:
- `partner_scrape/model.py` — `PROGRAM_EXTRACTION_KINDS`,
  `Event.eligibility`.
- `partner_scrape/enrich/enricher.py` — bypass condition.
- `partner_scrape/normalize/run.py` — split condition,
  `DEADLINE_FIRST_TYPES`, `_to_opportunity()`'s eligibility resolution
  and `today` threading, availability-derivation trigger.
- Corresponding test files: `tests/test_model.py`,
  `tests/test_enrich_enricher.py`, `tests/test_normalize_run.py`,
  `tests/test_export_writer.py`.

**Testing plan**: see Testing above.

**Documentation updates**: None beyond this sprint's `design/` overlay
(already written and reviewed during planning) — no further DESIGN.md
edits are expected from this ticket's implementation, since the design
already describes this exact change. If implementation surfaces a real
deviation from the design overlay's description, update the affected
overlay file in place and flag it in this ticket's Notes.
